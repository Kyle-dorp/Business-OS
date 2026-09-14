"""
Recipe costing and physical counts, against a real database.

The variance formula itself is pinned arithmetically in
test_inventory_variance.py. This covers the parts that touch data: whether a
recipe costs what its ingredients cost, and whether recording a count captures
the right "expected" figure.

That second one matters more than it looks. record_count snapshots what the
system believed at the moment of counting. Recompute it later and stock has
moved on, so the variance is measured against the wrong number and the report
is quietly meaningless.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, select

from backend.app.database import engine
from backend.app.inventory_intel import recipe_cost_cents, record_count
from backend.app.models import Business, InventoryItem, InventoryMovement
from backend.app.ops_models import Recipe, RecipeComponent
from backend.app.tenancy import set_current_business_id


@pytest.fixture
def stock():
    """A business with two ingredients and one sellable item."""
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        business = Business(name=f"Kitchen {suffix}", industry="food_service", active=True)
        s.add(business)
        s.flush()
        bid = business.id

        gin = InventoryItem(
            business_id=bid, sku=f"GIN{suffix}", name="Gin", unit="ml",
            quantity_milli=20_000_000, unit_cost_cents=3, active=True,
        )
        tonic = InventoryItem(
            business_id=bid, sku=f"TON{suffix}", name="Tonic", unit="ml",
            quantity_milli=50_000_000, unit_cost_cents=1, active=True,
        )
        drink = InventoryItem(
            business_id=bid, sku=f"GT{suffix}", name="G&T", unit="each",
            item_type="service", quantity_milli=0,
            unit_cost_cents=0, sales_price_cents=1_200, active=True,
        )
        s.add_all([gin, tonic, drink])
        s.commit()
        s.refresh(gin); s.refresh(tonic); s.refresh(drink)
        ids = {"gin": gin.id, "tonic": tonic.id, "drink": drink.id}

    yield {"business_id": bid, **ids}
    set_current_business_id(1)


def _recipe(stock, components, yield_quantity=1.0):
    """components: list of (item_id, quantity_units, waste_percent)"""
    with Session(engine) as s:
        r = Recipe(
            business_id=stock["business_id"], name="G&T",
            sells_as_item_id=stock["drink"],
            yield_quantity_milli=int(yield_quantity * 1000), active=True,
        )
        s.add(r)
        s.flush()
        for item_id, qty, waste in components:
            s.add(RecipeComponent(
                business_id=stock["business_id"], recipe_id=r.id,
                inventory_item_id=item_id,
                quantity_milli=int(qty * 1000),
                waste_factor_percent=waste,
            ))
        s.commit()
        s.refresh(r)
        return r.id


# ---------------------------------------------------------------- costing

def test_a_recipe_costs_what_its_ingredients_cost(stock):
    """50 units of gin at 3c plus 150 of tonic at 1c is 300c."""
    rid = _recipe(stock, [(stock["gin"], 50, 0), (stock["tonic"], 150, 0)])

    with Session(engine) as s:
        cost = recipe_cost_cents(s, stock["business_id"], rid)

    assert cost["cost"] == 3.00
    assert len(cost["components"]) == 2


def test_a_waste_factor_raises_the_cost(stock):
    """
    A recipe calling for 50ml of something trimmed consumes more than 50ml.
    Costing without the waste factor understates food cost on exactly the
    items where it matters most.
    """
    plain = _recipe(stock, [(stock["gin"], 100, 0)])
    with_waste = _recipe(stock, [(stock["gin"], 100, 20)])

    with Session(engine) as s:
        a = recipe_cost_cents(s, stock["business_id"], plain)
        b = recipe_cost_cents(s, stock["business_id"], with_waste)

    assert a["cost"] == 3.00
    assert b["cost"] == 3.60          # 100 units + 20% at 3c
    assert b["cost"] > a["cost"]


def test_margin_and_food_cost_are_derived(stock):
    """Sells for $12, costs $3, so 25% food cost and $9 margin."""
    rid = _recipe(stock, [(stock["gin"], 50, 0), (stock["tonic"], 150, 0)])

    with Session(engine) as s:
        cost = recipe_cost_cents(s, stock["business_id"], rid)

    assert cost["sells_for"] == 12.00
    assert cost["margin"] == 9.00
    assert cost["food_cost_percent"] == 25.0
    assert cost["flag"] == "healthy"


def test_an_expensive_recipe_is_flagged(stock):
    """
    Food service targets roughly 28-35%. Past that an item is bleeding, and
    saying so is the whole point of costing it.
    """
    rid = _recipe(stock, [(stock["gin"], 200, 0)])   # $6 cost against a $12 price

    with Session(engine) as s:
        cost = recipe_cost_cents(s, stock["business_id"], rid)

    assert cost["food_cost_percent"] == 50.0
    assert cost["flag"] == "high_cost"


def test_a_recipe_with_no_sale_price_says_so(stock):
    """Better than reporting a margin of minus its own cost."""
    with Session(engine) as s:
        unpriced = InventoryItem(
            business_id=stock["business_id"], sku=f"UP{uuid.uuid4().hex[:4]}",
            name="Unpriced", unit="each", sales_price_cents=0, active=True,
        )
        s.add(unpriced)
        s.commit()
        s.refresh(unpriced)
        unpriced_id = unpriced.id

        r = Recipe(
            business_id=stock["business_id"], name="Mystery",
            sells_as_item_id=unpriced_id, yield_quantity_milli=1000, active=True,
        )
        s.add(r); s.flush()
        s.add(RecipeComponent(
            business_id=stock["business_id"], recipe_id=r.id,
            inventory_item_id=stock["gin"], quantity_milli=50_000,
        ))
        s.commit()
        rid = r.id

    with Session(engine) as s:
        cost = recipe_cost_cents(s, stock["business_id"], rid)
    assert cost["flag"] == "no_price"
    assert cost["food_cost_percent"] is None


def test_a_recipe_from_another_business_is_not_costable(stock):
    with Session(engine) as s:
        other = Business(name="Other Kitchen", industry="general", active=True)
        s.add(other)
        s.commit()
        s.refresh(other)
        other_id = other.id

    rid = _recipe(stock, [(stock["gin"], 50, 0)])
    with Session(engine) as s:
        result = recipe_cost_cents(s, other_id, rid)
    assert "error" in result


# ----------------------------------------------------------------- counts

def test_a_count_records_what_the_system_believed(stock):
    """
    The snapshot that makes variance meaningful. By the time anyone reads the
    report, stock has moved on — measuring against a later figure would give a
    number that means nothing.
    """
    with Session(engine) as session:
        result = record_count(
            session, stock["business_id"], stock["gin"],
            counted_milli=18_000_000, user_id=1,
        )
    assert result["expected"] == 20000.0
    assert result["counted"] == 18000.0
    assert result["variance"] == -2000.0


def test_a_count_corrects_stock_and_leaves_a_movement(stock):
    """
    The count becomes the truth, and the correction is auditable rather than a
    silent adjustment nobody can trace.
    """
    with Session(engine) as s:
        record_count(s, stock["business_id"], stock["tonic"],
                     counted_milli=45_000_000, user_id=1)

    with Session(engine) as s:
        item = s.get(InventoryItem, stock["tonic"])
        movements = s.exec(
            select(InventoryMovement)
            .where(InventoryMovement.item_id == stock["tonic"])
            .execution_options(include_all_businesses=True)
        ).all()

    assert item.quantity_milli == 45_000_000, "stock was not corrected to the count"
    adjustments = [m for m in movements if m.reason == "count_adjustment"]
    assert adjustments, "no auditable movement was written"
    assert adjustments[-1].quantity_milli == -5_000_000


def test_a_matching_count_writes_no_movement(stock):
    """Counting and finding exactly what was expected is not an adjustment."""
    with Session(engine) as s:
        item = s.get(InventoryItem, stock["gin"])
        current = item.quantity_milli

    with Session(engine) as s:
        result = record_count(s, stock["business_id"], stock["gin"],
                              counted_milli=current, user_id=1)

    assert result["variance"] == 0
    assert result["adjusted"] is False


def test_a_count_values_the_variance(stock):
    """A shortfall of cheap stock and of expensive stock are not the same event."""
    with Session(engine) as s:
        result = record_count(s, stock["business_id"], stock["gin"],
                              counted_milli=19_000_000, user_id=1)
    # 1,000,000 milli short at 3c per unit
    assert result["variance"] == -1000.0
    assert result["variance_value"] == -30.0


def test_counting_an_item_from_another_business_is_refused(stock):
    with Session(engine) as s:
        other = Business(name="Elsewhere", industry="general", active=True)
        s.add(other)
        s.commit()
        s.refresh(other)
        other_id = other.id

    with Session(engine) as s:
        result = record_count(s, other_id, stock["gin"], counted_milli=1, user_id=1)
    assert "error" in result
