"""
Admin Panel API Routes
Only accessible to users with is_admin=True
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlmodel import Session, select
from datetime import datetime, timezone

from backend.app.database import get_session, engine
from backend.app.auth import user_from_request
from backend.app.models import (
    UserAccount, Business, Membership, BusinessModule, ApiUsage
)

admin_router = APIRouter(prefix="/admin", tags=["admin"])


def admin_only(request: Request):
    """Dependency: require admin access"""
    user = user_from_request(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@admin_router.get("/customers")
def list_customers(admin: UserAccount = Depends(admin_only), session: Session = Depends(get_session)):
    """Get all customers with their plan/usage info"""
    businesses = session.exec(select(Business).where(Business.active == True)).all()

    result = []
    for biz in businesses:
        # Get owner user
        memberships = session.exec(
            select(Membership).where(
                Membership.business_id == biz.id,
                Membership.role == "owner",
                Membership.active == True
            )
        ).all()

        owner_id = memberships[0].user_id if memberships else None
        owner = session.get(UserAccount, owner_id) if owner_id else None

        # Get enabled modules
        modules = session.exec(
            select(BusinessModule).where(
                BusinessModule.business_id == biz.id,
                BusinessModule.enabled == True
            )
        ).all()

        # Calculate profit (monthly price - api costs)
        profit_cents = biz.monthly_price_cents - biz.claude_api_cost_cents

        result.append({
            "id": biz.id,
            "name": biz.name,
            "legal_name": biz.legal_name,
            "industry": biz.industry,
            "owner": owner.username if owner else "N/A",
            "plan": biz.plan,
            "monthly_price_cents": biz.monthly_price_cents,
            "claude_api_tokens": biz.claude_api_tokens_used,
            "claude_api_cost_cents": biz.claude_api_cost_cents,
            "profit_cents": profit_cents,
            "modules": [m.module_key for m in modules],
            "created_at": biz.created_at,
        })

    return result


@admin_router.get("/customers/{business_id}")
def get_customer_detail(
    business_id: int,
    admin: UserAccount = Depends(admin_only),
    session: Session = Depends(get_session)
):
    """Get detailed info about a specific customer"""
    biz = session.get(Business, business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get owner
    memberships = session.exec(
        select(Membership).where(
            Membership.business_id == biz.id,
            Membership.role == "owner"
        )
    ).all()
    owner_id = memberships[0].user_id if memberships else None
    owner = session.get(UserAccount, owner_id) if owner_id else None

    # Get modules
    modules = session.exec(
        select(BusinessModule).where(BusinessModule.business_id == biz.id)
    ).all()

    # Get API usage history (last 30 days)
    usage = session.exec(
        select(ApiUsage).where(ApiUsage.business_id == biz.id).order_by(ApiUsage.date.desc()).limit(30)
    ).all()

    return {
        "id": biz.id,
        "name": biz.name,
        "legal_name": biz.legal_name,
        "industry": biz.industry,
        "owner": owner.username if owner else "N/A",
        "plan": biz.plan,
        "monthly_price_cents": biz.monthly_price_cents,
        "claude_api_tokens": biz.claude_api_tokens_used,
        "claude_api_cost_cents": biz.claude_api_cost_cents,
        "profit_cents": biz.monthly_price_cents - biz.claude_api_cost_cents,
        "modules": [
            {"key": m.module_key, "enabled": m.enabled}
            for m in modules
        ],
        "usage_history": [
            {
                "date": u.date,
                "tokens": u.tokens_used,
                "cost_cents": u.cost_cents,
                "feature": u.feature,
            }
            for u in usage
        ],
        "created_at": biz.created_at,
    }


@admin_router.patch("/customers/{business_id}")
def update_customer(
    business_id: int,
    payload: dict,
    admin: UserAccount = Depends(admin_only),
    session: Session = Depends(get_session)
):
    """Update customer plan, pricing, etc."""
    biz = session.get(Business, business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Update allowed fields
    if "plan" in payload:
        biz.plan = payload["plan"]
    if "monthly_price_cents" in payload:
        biz.monthly_price_cents = payload["monthly_price_cents"]

    session.add(biz)
    session.commit()
    session.refresh(biz)

    return {"success": True, "customer_id": biz.id}


@admin_router.get("/analytics")
def get_analytics(admin: UserAccount = Depends(admin_only), session: Session = Depends(get_session)):
    """Get platform-wide analytics"""
    businesses = session.exec(select(Business).where(Business.active == True)).all()

    total_revenue_cents = sum(b.monthly_price_cents for b in businesses)
    total_api_cost_cents = sum(b.claude_api_cost_cents for b in businesses)
    total_profit_cents = total_revenue_cents - total_api_cost_cents

    return {
        "total_customers": len(businesses),
        "total_revenue_cents": total_revenue_cents,
        "total_api_cost_cents": total_api_cost_cents,
        "total_profit_cents": total_profit_cents,
        "avg_revenue_per_customer_cents": total_revenue_cents // len(businesses) if businesses else 0,
        "total_api_tokens_used": sum(b.claude_api_tokens_used for b in businesses),
    }
