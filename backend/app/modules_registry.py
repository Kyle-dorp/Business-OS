"""
The module catalogue — one source of truth.

This file previously described a set of modules that did not exist. The app
gates tabs on the keys in platform.MODULES; billing validated against a
different, invented set. Nothing broke visibly because nothing had charged a
card yet, but a subscription would have been priced on modules the product
does not have while the ones it does have went unbilled.

So: platform.MODULES is the authority, and this file describes those keys.
Anything added here must exist there, and the test suite asserts it.

Pricing is $29 for the first billable module and $10 for each one after.
Three modules are always on and never billed — a workspace with no overview,
no settings and no notifications is not a workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


# Always available, never charged for.
ALWAYS_ON = ("home", "settings", "notifications")

FIRST_MODULE_CENTS = 2900
EACH_MODULE_CENTS = 1000


@dataclass(frozen=True)
class Module:
    key: str
    name: str
    tagline: str
    description: str
    icon: str
    # What the same capability costs bought separately, in dollars per month.
    # Used to show an honest comparison, so these are real published list
    # prices rounded, not invented numbers. Sources are in
    # MARKET_ANALYSIS_AND_SCALING.md.
    market_price: int
    replaces: str
    billable: bool = True

    @property
    def monthly_cents(self) -> int:
        return 0 if not self.billable else EACH_MODULE_CENTS


CATALOGUE: List[Module] = [
    Module(
        key="home",
        name="Overview",
        tagline="The daily picture",
        description="Today's numbers across everything you have switched on.",
        icon="⌂",
        market_price=0,
        replaces="",
        billable=False,
    ),
    Module(
        key="settings",
        name="Settings",
        tagline="Workspace configuration",
        description="People, permissions, modules and preferences.",
        icon="⚙",
        market_price=0,
        replaces="",
        billable=False,
    ),
    Module(
        key="notifications",
        name="Notifications",
        tagline="What needs you",
        description="Requests, approvals and alerts in one place.",
        icon="●",
        market_price=0,
        replaces="",
        billable=False,
    ),
    Module(
        key="scheduling",
        name="Scheduling",
        tagline="Shifts that are legal and affordable",
        description=(
            "Constraint-solved rotas, availability, shift requests, and a "
            "pre-publish check across labor law, booked demand, cost and stock."
        ),
        icon="▦",
        market_price=40,
        replaces="Deputy, 7shifts, When I Work",
    ),
    Module(
        key="inventory",
        name="Inventory",
        tagline="Find where the money goes",
        description=(
            "Stock, suppliers and movements — plus recipe costing and true "
            "variance, so shrinkage becomes a number instead of a feeling."
        ),
        icon="□",
        market_price=79,
        replaces="Zoho Inventory, Sortly, inFlow",
    ),
    Module(
        key="accounting",
        name="Bookkeeping",
        tagline="Books that keep themselves",
        description=(
            "Double-entry ledger, chart of accounts, trial balance, P&L and "
            "balance sheet — fed by the operation rather than typed into."
        ),
        icon="≡",
        market_price=70,
        replaces="QuickBooks, Xero",
    ),
    Module(
        key="sales",
        name="Sales & invoices",
        tagline="Bill it, track it, get paid",
        description="Invoices, payments and receivables, posting to the ledger as they issue.",
        icon="$",
        market_price=30,
        replaces="Invoice2go, Wave",
    ),
    Module(
        key="purchasing",
        name="Bills & purchasing",
        tagline="What you owe, and to whom",
        description="Vendor bills, payments and purchase records tied to stock.",
        icon="↓",
        market_price=25,
        replaces="Bill.com",
    ),
    Module(
        key="team",
        name="Customers & vendors",
        tagline="One record per person",
        description="Contacts, history, preferences — shared by bookings, invoices and the ledger.",
        icon="◎",
        market_price=35,
        replaces="HubSpot Starter, Zoho CRM",
    ),
    Module(
        key="booking",
        name="Bookings",
        tagline="A page that takes appointments",
        description=(
            "A public booking page on your own domain, with real slot generation "
            "from your opening hours, deposits, and no-show history attached to "
            "every customer."
        ),
        icon="◑",
        market_price=49,
        replaces="Acuity, Square Appointments, Calendly",
    ),
    Module(
        key="tasks",
        name="Tasks",
        tagline="The things that fall through",
        description="Assignments, due dates and status, attached to whatever they concern.",
        icon="✓",
        market_price=15,
        replaces="Asana, Trello",
    ),
    Module(
        key="reports",
        name="Reports",
        tagline="Answers without a spreadsheet",
        description="Financial and operational reporting across every module you run.",
        icon="↗",
        market_price=49,
        replaces="Custom BI, spreadsheet exports",
    ),
    Module(
        key="assistant",
        name="Assistant",
        tagline="Ask, and change, in plain language",
        description=(
            "Questions answered from your real records, and changes proposed "
            "for you to approve. Included allowance, metered past it."
        ),
        icon="✦",
        market_price=0,
        replaces="Nothing at this price",
    ),
]

ALL_MODULES: Dict[str, Module] = {m.key: m for m in CATALOGUE}
BILLABLE_KEYS = [m.key for m in CATALOGUE if m.billable]


def billable(module_keys) -> List[str]:
    """Filter to keys that are both real and chargeable."""
    return [k for k in module_keys if k in ALL_MODULES and ALL_MODULES[k].billable]


def quote_cents(billable_count: int) -> int:
    """$29 for the first, $10 for each after. Zero modules costs nothing."""
    if billable_count <= 0:
        return 0
    return FIRST_MODULE_CENTS + (billable_count - 1) * EACH_MODULE_CENTS


def stitched_cents(module_keys) -> int:
    """What the same set costs bought from separate vendors."""
    return sum(ALL_MODULES[k].market_price for k in billable(module_keys)) * 100


def catalogue_payload() -> List[dict]:
    """Everything the billing and settings screens need to render."""
    return [
        {
            "key": m.key,
            "name": m.name,
            "tagline": m.tagline,
            "description": m.description,
            "icon": m.icon,
            "billable": m.billable,
            "market_price": m.market_price,
            "replaces": m.replaces,
        }
        for m in CATALOGUE
    ]
