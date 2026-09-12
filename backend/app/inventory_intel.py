"""
Inventory intelligence — recipe costing, theoretical usage, and true variance.

This is the capability no standalone inventory tool can offer at any price,
because it needs sales and stock in the same database.

The chain:

    sales  ->  recipes  ->  theoretical usage
                                  |
                          minus logged waste
                                  |
                         vs. physical count
                                  |
                        = unexplained variance

A standalone tool can only compare stock to stock — it sees the level drop but
has no idea what *should* have been consumed, so every discrepancy looks like
noise. With sales in the same place, the gap becomes a number you can chase.

That gap is the documented ~1.6% of sales that disconnected operators lose to
spoilage, theft and miscounts. Naming it in dollars is the single most valuable
thing this platform does.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlmodel import Session, select

from backend.app.models import InventoryItem, InventoryMovement
from backend.app.ops_models import (
    InventoryCount,
    Recipe,
    RecipeComponent,
    WasteLog,
)

log = logging.getLogger(__name__)

# Movement reasons that represent product leaving because it was sold.
SALE_REASONS = {"sale", "sold", "pos_sale"}


def _q(milli: int) -> float:
    """Thousandths to whole units."""
    return round(milli / 1000, 3)


def _money(cents: int) -> float:
    return round(cents / 100, 2)


# --------------------------------------------------------------- recipe cost

def recipe_cost_cents(session: Session, business_id: int, recipe_id: int) -> dict:
    """
    What one yield of a recipe costs to make, at current unit costs.

    Includes the waste factor on each component, because a recipe that calls for
    200g of a trimmed vegetable consumes rather more than 200g of the untrimmed
    one. Costing without it understates food cost on exactly the items where it
    matters most.
    """
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.business_id != business_id:
        return {"error": "No such recipe."}

    components = session.exec(
        select(RecipeComponent).where(
            RecipeComponent.recipe_id == recipe_id,
            RecipeComponent.business_id == business_id,
        )
    ).all()

    lines: List[dict] = []
    total_cents = 0

    for c in components:
        item = session.get(InventoryItem, c.inventory_item_id)
        if not item or item.business_id != business_id:
            continue

        effective_milli = c.quantity_milli * (1 + c.waste_factor_percent / 100)
        line_cents = round((effective_milli / 1000) * item.unit_cost_cents)
        total_cents += line_cents

        lines.append({
            "item": item.name,
            "sku": item.sku,
            "quantity": _q(c.quantity_milli),
            "effective_quantity": _q(int(effective_milli)),
            "waste_factor_percent": c.waste_factor_percent,
            "unit_cost": _money(item.unit_cost_cents),
            "line_cost": _money(line_cents),
        })

    sells_for_cents = 0
    if recipe.sells_as_item_id:
        sold = session.get(InventoryItem, recipe.sells_as_item_id)
        if sold and sold.business_id == business_id:
            sells_for_cents = sold.sales_price_cents

    margin_cents = sells_for_cents - total_cents
    food_cost_pct = round((total_cents / sells_for_cents) * 100, 1) if sells_for_cents else None

    return {
        "recipe": recipe.name,
        "recipe_id": recipe.id,
        "components": lines,
        "cost": _money(total_cents),
        "sells_for": _money(sells_for_cents),
        "margin": _money(margin_cents),
        "food_cost_percent": food_cost_pct,
        # Food service targets roughly 28-35%. Above that, the item is bleeding.
        "flag": (
            "high_cost" if food_cost_pct and food_cost_pct > 35
            else "healthy" if food_cost_pct else "no_price"
        ),
    }


def menu_engineering(session: Session, business_id: int, days: int = 30) -> dict:
    """
    Every recipe ranked by margin and popularity.

    The classic four-box: high margin + high volume is a star, low margin +
    high volume is a problem worth repricing, and so on. Doing this needs
    recipe cost and sales volume together — which is the whole point.
    """
    since = (date.today() - timedelta(days=days)).isoformat()

    recipes = session.exec(
        select(Recipe).where(Recipe.business_id == business_id, Recipe.active == True)  # noqa: E712
    ).all()
    if not recipes:
        return {"recipes": [], "note": "No recipes defined yet."}

    rows: List[dict] = []
    for r in recipes:
        cost = recipe_cost_cents(session, business_id, r.id)
        if "error" in cost:
            continue

        sold_milli = 0
        if r.sells_as_item_id:
            movements = session.exec(
                select(InventoryMovement).where(
                    InventoryMovement.business_id == business_id,
                    InventoryMovement.item_id == r.sells_as_item_id,
                    InventoryMovement.movement_date >= since,
                )
            ).all()
            sold_milli = sum(
                abs(m.quantity_milli) for m in movements
                if m.reason.lower() in SALE_REASONS
            )

        units = _q(sold_milli)
        rows.append({
            **cost,
            "units_sold": units,
            "total_margin": round((cost["margin"] or 0) * units, 2),
        })

    if not rows:
        return {"recipes": [], "note": "No sales data in this window."}

    median_units = sorted(r["units_sold"] for r in rows)[len(rows) // 2]
    median_margin = sorted(r["margin"] for r in rows)[len(rows) // 2]

    for r in rows:
        popular = r["units_sold"] >= median_units
        profitable = r["margin"] >= median_margin
        r["quadrant"] = (
            "star" if popular and profitable
            else "workhorse" if popular
            else "puzzle" if profitable
            else "drop_or_rework"
        )

    rows.sort(key=lambda r: r["total_margin"], reverse=True)
    return {
        "period_days": days,
        "recipes": rows,
        "stars": [r["recipe"] for r in rows if r["quadrant"] == "star"],
        "needs_attention": [r["recipe"] for r in rows if r["quadrant"] == "drop_or_rework"],
    }


# --------------------------------------------------------------- variance

def theoretical_usage(
    session: Session, business_id: int, since: str, until: Optional[str] = None
) -> Dict[int, int]:
    """
    How much of each ingredient *should* have been consumed, from sales.

    Returns {inventory_item_id: milli consumed}.
    """
    until = until or date.today().isoformat()

    recipes = session.exec(
        select(Recipe).where(Recipe.business_id == business_id, Recipe.active == True)  # noqa: E712
    ).all()
    if not recipes:
        return {}

    components_by_recipe: Dict[int, List[RecipeComponent]] = {}
    for c in session.exec(
        select(RecipeComponent).where(RecipeComponent.business_id == business_id)
    ).all():
        components_by_recipe.setdefault(c.recipe_id, []).append(c)

    movements = session.exec(
        select(InventoryMovement).where(
            InventoryMovement.business_id == business_id,
            InventoryMovement.movement_date >= since,
            InventoryMovement.movement_date <= until,
        )
    ).all()

    sold_by_item: Dict[int, int] = {}
    for m in movements:
        if m.reason.lower() in SALE_REASONS:
            sold_by_item[m.item_id] = sold_by_item.get(m.item_id, 0) + abs(m.quantity_milli)

    usage: Dict[int, int] = {}
    for r in recipes:
        if not r.sells_as_item_id:
            continue
        sold_milli = sold_by_item.get(r.sells_as_item_id, 0)
        if not sold_milli:
            continue

        yields = sold_milli / max(r.yield_quantity_milli, 1)
        for c in components_by_recipe.get(r.id, []):
            consumed = c.quantity_milli * yields * (1 + c.waste_factor_percent / 100)
            usage[c.inventory_item_id] = usage.get(c.inventory_item_id, 0) + int(consumed)

    return usage


def variance_report(session: Session, business_id: int, days: int = 30) -> dict:
    """
    Unexplained variance, in dollars, per item.

    For each item with a physical count in the window:

        expected  = count at start - theoretical usage - logged waste + received
        variance  = counted - expected

    Negative variance is product that left without being sold, wasted or
    recorded. That is the number worth chasing — and it is invisible to any
    tool that cannot see sales and stock together.
    """
    since = (date.today() - timedelta(days=days)).isoformat()

    counts = session.exec(
        select(InventoryCount).where(
            InventoryCount.business_id == business_id,
            InventoryCount.counted_at >= since,
        )
    ).all()
    if not counts:
        return {
            "items": [],
            "note": "No physical counts in this window. Variance needs at least one count.",
            "period_days": days,
        }

    latest: Dict[int, InventoryCount] = {}
    for c in counts:
        prev = latest.get(c.inventory_item_id)
        if not prev or c.counted_at > prev.counted_at:
            latest[c.inventory_item_id] = c

    usage = theoretical_usage(session, business_id, since)

    waste_by_item: Dict[int, int] = {}
    for w in session.exec(
        select(WasteLog).where(
            WasteLog.business_id == business_id,
            WasteLog.occurred_at >= since,
        )
    ).all():
        waste_by_item[w.inventory_item_id] = (
            waste_by_item.get(w.inventory_item_id, 0) + abs(w.quantity_milli)
        )

    rows: List[dict] = []
    total_variance_cents = 0

    for item_id, count in latest.items():
        item = session.get(InventoryItem, item_id)
        if not item or item.business_id != business_id:
            continue

        expected_usage = usage.get(item_id, 0)
        logged_waste = waste_by_item.get(item_id, 0)

        # Variance recorded at count time already compares system belief to reality.
        variance_milli = count.variance_milli or (count.counted_milli - count.expected_milli)
        unexplained_milli = variance_milli + logged_waste
        variance_cents = round((unexplained_milli / 1000) * item.unit_cost_cents)
        total_variance_cents += variance_cents

        rows.append({
            "item": item.name,
            "sku": item.sku,
            "counted": _q(count.counted_milli),
            "expected": _q(count.expected_milli),
            "theoretical_usage": _q(expected_usage),
            "logged_waste": _q(logged_waste),
            "unexplained": _q(unexplained_milli),
            "unexplained_value": _money(variance_cents),
            "counted_at": count.counted_at,
            "severity": (
                "high" if abs(variance_cents) >= 5000
                else "medium" if abs(variance_cents) >= 1000
                else "low"
            ),
        })

    rows.sort(key=lambda r: r["unexplained_value"])

    worst = [r for r in rows if r["severity"] in ("high", "medium") and r["unexplained_value"] < 0]

    return {
        "period_days": days,
        "items": rows,
        "total_unexplained_value": _money(total_variance_cents),
        "worst_offenders": worst[:10],
        "annualized_projection": _money(round(total_variance_cents * (365 / max(days, 1)))),
        "note": (
            "Negative unexplained variance is product that left without being sold, "
            "wasted or recorded. Counts, recipes and waste logs all need to be current "
            "for these numbers to mean anything."
        ),
    }


def record_count(
    session: Session,
    business_id: int,
    item_id: int,
    counted_milli: int,
    user_id: Optional[int] = None,
    notes: str = "",
) -> dict:
    """
    Record a physical count, capturing the system's belief at that instant.

    Snapshotting `expected` here rather than recomputing later matters: by the
    time anyone reads the report, stock has moved on, and a variance measured
    against a later number is meaningless.
    """
    item = session.get(InventoryItem, item_id)
    if not item or item.business_id != business_id:
        return {"error": "No such item in this workspace."}

    expected = item.quantity_milli
    variance = counted_milli - expected
    variance_cents = round((variance / 1000) * item.unit_cost_cents)

    count = InventoryCount(
        business_id=business_id,
        inventory_item_id=item_id,
        counted_milli=counted_milli,
        expected_milli=expected,
        variance_milli=variance,
        variance_cents=variance_cents,
        counted_by_user_id=user_id,
        notes=notes,
    )
    session.add(count)

    # The count is now the truth. Correct stock and leave an auditable movement.
    if variance:
        session.add(InventoryMovement(
            business_id=business_id,
            item_id=item_id,
            movement_date=date.today().isoformat(),
            quantity_milli=variance,
            reason="count_adjustment",
            reference=f"Physical count; variance {_q(variance)}",
            created_by_user_id=user_id or 0,
        ))
        item.quantity_milli = counted_milli
        session.add(item)

    session.commit()
    session.refresh(count)

    return {
        "counted": _q(counted_milli),
        "expected": _q(expected),
        "variance": _q(variance),
        "variance_value": _money(variance_cents),
        "adjusted": bool(variance),
    }
