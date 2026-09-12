"""
Tables for labor compliance and inventory intelligence.

These back the two capabilities that separate Business-EOS from every
single-purpose competitor: knowing whether a schedule is legal before it goes
out, and knowing what your stock *should* be versus what it actually is.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from backend.app.models import utc_now_iso
from backend.app.tenancy import current_business_id


# ----------------------------------------------------------- labor compliance

class ComplianceProfile(SQLModel, table=True):
    """
    Which labor rules apply to a workspace.

    One row per business. Jurisdiction keys resolve against the rule table in
    compliance.py; anything unrecognised falls back to federal-only.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)

    jurisdiction: str = "federal"        # federal | ca | ny | nyc | seattle | ...
    industry: str = "general"            # retail and food service trigger extra rules
    employee_count: int = 0              # several ordinances only bite above a threshold

    # Operator-set thresholds, defaulting to federal minimums.
    weekly_overtime_hours: int = 40
    max_consecutive_days: int = 6
    track_minors: bool = True

    # Predictive-scheduling posture. Ignored where the jurisdiction has no such law.
    advance_notice_days: int = 0
    enforce_rest_between_shifts: bool = True

    active: bool = True
    updated_at: str = Field(default_factory=utc_now_iso)


class EmployeeCompliance(SQLModel, table=True):
    """
    Per-employee facts that change which rules apply.

    Separate from Employee so date of birth and exempt status sit in one place
    that can be permissioned more tightly than the roster.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    employee_id: int = Field(index=True)

    date_of_birth: str = ""              # YYYY-MM-DD; blank means "assume adult"
    exempt: bool = False                 # salaried-exempt: overtime rules don't apply
    is_student: bool = False             # school-day limits apply to minors
    hourly_rate_cents: int = 0           # for costing premiums and overtime exposure

    updated_at: str = Field(default_factory=utc_now_iso)


class ComplianceFinding(SQLModel, table=True):
    """
    One detected issue on one schedule.

    Kept rather than recomputed so an operator can prove what they were warned
    about and when — which matters if a violation is ever disputed.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    schedule_id: int = Field(index=True)

    rule_code: str = Field(index=True)   # OT_WEEKLY | REST_SHORT | MINOR_HOURS | ...
    severity: str = "warning"            # info | warning | violation
    employee_id: Optional[int] = None
    date: str = ""
    message: str = ""
    exposure_cents: int = 0              # estimated fine or premium owed
    jurisdiction: str = ""

    acknowledged: bool = False
    created_at: str = Field(default_factory=utc_now_iso)


# ------------------------------------------------------- inventory intelligence

class Recipe(SQLModel, table=True):
    """
    What a sellable thing is made of.

    This is the join that makes true variance possible: without it you can only
    compare stock to stock. With it, every sale implies a draw-down, and the gap
    between implied and counted is shrinkage you can put a number on.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)

    name: str
    sells_as_item_id: Optional[int] = Field(default=None, index=True)  # InventoryItem sold
    yield_quantity_milli: int = 1000     # one portion by default
    active: bool = True
    notes: str = ""
    created_at: str = Field(default_factory=utc_now_iso)


class RecipeComponent(SQLModel, table=True):
    """One ingredient line. Quantities are thousandths, matching InventoryItem."""

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    recipe_id: int = Field(index=True)
    inventory_item_id: int = Field(index=True)
    quantity_milli: int = 0
    # Trim, spillage and cooking loss, as a percentage added to theoretical usage.
    waste_factor_percent: float = 0.0


class InventoryCount(SQLModel, table=True):
    """A physical count. Variance is measured against these, never against guesses."""

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    inventory_item_id: int = Field(index=True)

    counted_at: str = Field(default_factory=utc_now_iso, index=True)
    counted_milli: int = 0
    expected_milli: int = 0              # system belief at the moment of counting
    variance_milli: int = 0              # counted - expected
    variance_cents: int = 0              # variance valued at unit cost
    counted_by_user_id: Optional[int] = None
    notes: str = ""


class WasteLog(SQLModel, table=True):
    """
    Deliberately recorded loss — spoilage, breakage, comps, staff meals.

    Recording waste is what lets variance mean something. Unexplained variance
    with no waste log is just noise; unexplained variance *after* waste is
    accounted for is the number worth chasing.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(default_factory=current_business_id, index=True)
    inventory_item_id: int = Field(index=True)

    occurred_at: str = Field(default_factory=utc_now_iso, index=True)
    quantity_milli: int = 0
    value_cents: int = 0
    reason: str = "spoilage"             # spoilage | breakage | comp | staff_meal | prep_error
    notes: str = ""
    logged_by_user_id: Optional[int] = None
