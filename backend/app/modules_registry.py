"""
Business-EOS Module Registry System

Comprehensive module definitions, presets, and utilities for managing
a completely modular business operations platform.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum


class PricingTier(str, Enum):
    """Module pricing tiers"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class ModuleRoute:
    """API route definition"""
    method: str
    path: str
    description: str


@dataclass
class ModulePage:
    """Frontend page definition"""
    path: str
    component: str
    icon: str
    label: str


@dataclass
class Module:
    """Complete module definition"""
    key: str
    name: str
    description: str
    icon: str
    enabled_by_default: bool = False
    pricing_tier: PricingTier = PricingTier.FREE
    dependencies: List[str] = field(default_factory=list)
    api_routes: List[ModuleRoute] = field(default_factory=list)
    pages: List[ModulePage] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    created_at: str = "2025-01-01"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "enabled_by_default": self.enabled_by_default,
            "pricing_tier": self.pricing_tier.value,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "version": self.version,
            "pages": [{"path": p.path, "component": p.component, "icon": p.icon, "label": p.label} for p in self.pages],
            "api_routes": [{"method": r.method, "path": r.path, "description": r.description} for r in self.api_routes],
        }


# Core Modules (foundation)
SCHEDULING = Module(
    key="scheduling",
    name="Staff Scheduling",
    description="Smart shift generation with AI, availability management, labor planning",
    icon="⏰",
    enabled_by_default=False,
    pricing_tier=PricingTier.STARTER,
    dependencies=[],
    tags=["operations", "scheduling"],
    pages=[
        ModulePage(path="/scheduling", component="SchedulingPage", icon="⏰", label="Scheduling"),
        ModulePage(path="/availability", component="AvailabilityPage", icon="📅", label="My Availability"),
    ],
)

INVENTORY = Module(
    key="inventory",
    name="Inventory Management",
    description="Track stock, manage suppliers, record movements, set reorder points",
    icon="📦",
    enabled_by_default=False,
    pricing_tier=PricingTier.STARTER,
    dependencies=[],
    tags=["operations", "inventory"],
    pages=[
        ModulePage(path="/inventory", component="InventoryPage", icon="📦", label="Inventory"),
    ],
)

FINANCE = Module(
    key="finance",
    name="Finance & Accounting",
    description="Double-entry ledger, chart of accounts, P&L, balance sheet, reporting",
    icon="💰",
    enabled_by_default=False,
    pricing_tier=PricingTier.STARTER,
    dependencies=[],
    tags=["accounting", "finance"],
    pages=[
        ModulePage(path="/finance", component="FinancePage", icon="💰", label="Finance"),
    ],
)

CRM = Module(
    key="crm",
    name="Customer CRM",
    description="Manage customer profiles, track history, preferences, loyalty programs",
    icon="👥",
    enabled_by_default=False,
    pricing_tier=PricingTier.STARTER,
    dependencies=[],
    tags=["sales", "customers"],
    pages=[
        ModulePage(path="/customers", component="CustomersPage", icon="👥", label="Customers"),
    ],
)

INVOICING = Module(
    key="invoicing",
    name="Invoicing & Billing",
    description="Create invoices, track payments, manage recurring billing, payment reminders",
    icon="📄",
    enabled_by_default=False,
    pricing_tier=PricingTier.STARTER,
    dependencies=[],
    tags=["sales", "billing"],
    pages=[
        ModulePage(path="/invoicing", component="InvoicingPage", icon="📄", label="Invoicing"),
    ],
)

# Premium Modules
PAYROLL = Module(
    key="payroll",
    name="Payroll System",
    description="Process payroll, tax compliance, deductions, employee payments",
    icon="💸",
    enabled_by_default=False,
    pricing_tier=PricingTier.PROFESSIONAL,
    dependencies=[],
    tags=["hr", "accounting"],
    pages=[
        ModulePage(path="/payroll", component="PayrollPage", icon="💸", label="Payroll"),
    ],
)

ANALYTICS = Module(
    key="analytics",
    name="Analytics & Reporting",
    description="Custom reports, forecasting, data export, predictive analytics",
    icon="📊",
    enabled_by_default=False,
    pricing_tier=PricingTier.PROFESSIONAL,
    dependencies=[],
    tags=["reporting", "analytics"],
    pages=[
        ModulePage(path="/analytics", component="AnalyticsPage", icon="📊", label="Analytics"),
    ],
)

AI_ASSISTANT = Module(
    key="ai_assistant",
    name="AI Assistant",
    description="Claude-powered AI for scheduling optimization, data insights, business guidance",
    icon="✦",
    enabled_by_default=False,
    pricing_tier=PricingTier.PROFESSIONAL,
    dependencies=[],
    tags=["ai", "automation"],
    pages=[
        ModulePage(path="/assistant", component="AssistantPage", icon="✦", label="AI Assistant"),
    ],
)

TEAM_COMMUNICATION = Module(
    key="team_communication",
    name="Team Communication",
    description="Internal messaging, announcements, team collaboration, shift management",
    icon="💬",
    enabled_by_default=False,
    pricing_tier=PricingTier.PROFESSIONAL,
    dependencies=[],
    tags=["collaboration", "communication"],
    pages=[
        ModulePage(path="/team", component="TeamPage", icon="💬", label="Team"),
    ],
)

# Enterprise Modules
ADVANCED_ANALYTICS = Module(
    key="advanced_analytics",
    name="Advanced Analytics",
    description="Machine learning predictions, custom dashboards, data science tools",
    icon="🤖",
    enabled_by_default=False,
    pricing_tier=PricingTier.ENTERPRISE,
    dependencies=["analytics"],
    tags=["ai", "analytics"],
)

PROJECT_MANAGEMENT = Module(
    key="projects",
    name="Project Management",
    description="Tasks, timelines, resource allocation, milestone tracking, collaboration",
    icon="📋",
    enabled_by_default=False,
    pricing_tier=PricingTier.ENTERPRISE,
    dependencies=[],
    tags=["operations", "projects"],
)

# All modules
ALL_MODULES: Dict[str, Module] = {
    "scheduling": SCHEDULING,
    "inventory": INVENTORY,
    "finance": FINANCE,
    "crm": CRM,
    "invoicing": INVOICING,
    "payroll": PAYROLL,
    "analytics": ANALYTICS,
    "ai_assistant": AI_ASSISTANT,
    "team_communication": TEAM_COMMUNICATION,
    "advanced_analytics": ADVANCED_ANALYTICS,
    "projects": PROJECT_MANAGEMENT,
}

# Industry Presets
PRESETS: Dict[str, List[str]] = {
    "hospitality": [
        "scheduling",
        "inventory",
        "crm",
        "invoicing",
        "payroll",
        "analytics",
        "team_communication",
    ],
    "retail": [
        "inventory",
        "crm",
        "invoicing",
        "payroll",
        "analytics",
        "team_communication",
    ],
    "professional_services": [
        "projects",
        "invoicing",
        "crm",
        "payroll",
        "analytics",
        "ai_assistant",
    ],
    "manufacturing": [
        "inventory",
        "payroll",
        "analytics",
        "team_communication",
    ],
    "healthcare": [
        "scheduling",
        "invoicing",
        "payroll",
        "analytics",
    ],
    "custom": [],  # Empty - user builds their own
}


class ModuleRegistry:
    """Registry utility for module management"""

    @staticmethod
    def get_module(key: str) -> Optional[Module]:
        """Get module by key"""
        return ALL_MODULES.get(key)

    @staticmethod
    def get_all_modules() -> Dict[str, Module]:
        """Get all modules"""
        return ALL_MODULES.copy()

    @staticmethod
    def get_modules_by_tier(tier: PricingTier) -> List[Module]:
        """Get modules by pricing tier"""
        return [m for m in ALL_MODULES.values() if m.pricing_tier == tier]

    @staticmethod
    def get_modules_by_tag(tag: str) -> List[Module]:
        """Get modules by tag"""
        return [m for m in ALL_MODULES.values() if tag in m.tags]

    @staticmethod
    def get_preset_modules(preset_name: str) -> List[Module]:
        """Get modules for a preset"""
        if preset_name not in PRESETS:
            return []
        module_keys = PRESETS[preset_name]
        return [ALL_MODULES[key] for key in module_keys if key in ALL_MODULES]

    @staticmethod
    def get_module_dependencies(module_key: str) -> Set[str]:
        """Get all module dependencies (recursive)"""
        module = ModuleRegistry.get_module(module_key)
        if not module:
            return set()

        deps = set(module.dependencies)
        for dep in module.dependencies:
            deps.update(ModuleRegistry.get_module_dependencies(dep))
        return deps

    @staticmethod
    def validate_module_list(module_keys: List[str]) -> tuple[bool, List[str]]:
        """Validate and auto-resolve dependencies"""
        resolved = set(module_keys)
        for key in module_keys:
            resolved.update(ModuleRegistry.get_module_dependencies(key))
        return True, list(resolved)

    @staticmethod
    def get_default_enabled_modules() -> List[Module]:
        """Get modules enabled by default"""
        return [m for m in ALL_MODULES.values() if m.enabled_by_default]

    @staticmethod
    def export_registry() -> Dict:
        """Export full registry as JSON-serializable dict"""
        return {
            "modules": {key: module.to_dict() for key, module in ALL_MODULES.items()},
            "presets": PRESETS,
            "pricing_tiers": [tier.value for tier in PricingTier],
        }


# Constants for easy access
CORE_MODULES = ["scheduling", "inventory", "finance", "crm", "invoicing"]
PREMIUM_MODULES = ["payroll", "analytics", "ai_assistant", "team_communication"]
OPTIONAL_MODULES = ["advanced_analytics", "projects"]
ALL_MODULE_KEYS = list(ALL_MODULES.keys())
