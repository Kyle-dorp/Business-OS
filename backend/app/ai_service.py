from __future__ import annotations

import json
import os
import re
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


ActionType = Literal[
    "create_employee",
    "update_employee",
    "create_position",
    "set_employee_positions",
    "add_recurring_availability",
    "add_temporary_unavailability",
    "create_labor_projection",
    "create_crew_target",
    "update_manager_settings",
    "regenerate_schedule",
    "adjust_shift",
    "replace_shift_employee",
    "update_ui_config",
    "toggle_module",
]


class AssistantAction(BaseModel):
    type: ActionType
    reason: str = ""

    # Schedule actions
    scope: Literal["full_week", "selected_day", "problems"] = "problems"
    selected_date: Optional[str] = None
    labor_tolerance_percent: float = 0.0
    staffing_level: Literal["lean", "balanced", "full"] = "balanced"
    employee_name: Optional[str] = None
    replacement_employee_name: Optional[str] = None
    position_name: Optional[str] = None
    new_start_time: Optional[str] = None
    new_end_time: Optional[str] = None

    # Employee / position setup
    name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[Literal["employee", "shift_lead", "gm"]] = None
    min_hours_per_week: Optional[int] = None
    max_hours_per_week: Optional[int] = None
    position_names: list[str] = Field(default_factory=list)
    trainee_position_names: list[str] = Field(default_factory=list)
    preferred_position_name: Optional[str] = None

    # Availability
    rule_type: Optional[Literal["unavailable", "preferred"]] = None
    day_of_week: Optional[int] = None
    days_of_week: list[int] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Labor / store settings
    date: Optional[str] = None
    whole_day: bool = False
    projected_sales: Optional[float] = None
    min_labor_percent: Optional[float] = None
    max_labor_percent: Optional[float] = None
    max_labor_hours: Optional[float] = None
    max_labor_dollars: Optional[float] = None
    employee_hourly_rate: Optional[float] = None
    schedule_extra_with_trainee: Optional[bool] = None
    store_open_time: Optional[str] = None
    store_close_time: Optional[str] = None

    # UI customization — pass as a JSON object, not a string
    ui_config_patch: dict = {}

    # Module toggle
    module_key: Optional[str] = None
    module_enabled: bool = True

    # Projected crew target
    target_date: Optional[str] = None
    target_day_of_week: Optional[int] = None
    departments: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    minimum_count: Optional[int] = None
    preferred_count: Optional[int] = None
    hard_minimum: bool = True


class AssistantDecision(BaseModel):
    reply: str
    actions: list[AssistantAction] = Field(default_factory=list)


SYSTEM_PROMPT = """
You are the conversational control layer for a configurable all-in-one business platform.
The tenant-scoped database, double-entry ledger, and deterministic scheduling solver are
the sources of truth. You can answer questions about accounting, invoices, bills, expenses,
contacts, tasks, inventory, employees, availability, and schedules using CURRENT DATABASE
CONTEXT. Never mix businesses. Structured schedule/setup changes require manager approval.

You CAN propose:
- adding or updating employees;
- assigning positions, preferred position, and trainee flags;
- recurring or temporary unavailability/preferences;
- labor projections with a minimum/maximum labor-percent range;
- date-specific or recurring Projected Crew targets;
- store hours, base wage, and the trainee-extra preference;
- schedule regeneration or edits to an existing draft;
- UI theme, branding, and navigation label changes via update_ui_config.

For update_ui_config, set ui_config_patch to a JSON object (not a string) with any combination of:
  "theme": { "primary": "#hex", "sidebar_bg": "#hex", "accent": "#hex", "page_bg": "#hex", "font": "font-family" }
  "branding": { "logo_letter": "B", "tagline": "Sub Shoppe" }
  "nav_labels": { "tasks": "Daily Ops", "accounting": "Books", "reports": "Financials" }

Valid nav_labels keys: home, contacts, sales, purchasing, accounting, finance, reports, tasks, inventory, availability, manager, assistant, notifications, settings.
All color values must be valid CSS hex colors (e.g. "#1a2b3c"). Choose colors that match the business's brand and look professional together. The sidebar_bg should be dark enough for white text to be readable on it.

For toggle_module, set module_key to one of: team, scheduling, accounting, sales, purchasing, tasks, inventory, reports, assistant, notifications. Set module_enabled to true to show it or false to hide it. Home and settings cannot be hidden. One action per module. "contacts" and "customers" map to the "team" module. "scheduling" covers both the schedule view and availability tabs. "finance" is part of the "accounting" module.

Important rules:
- Never invent names, availability, dates, sales, skills, or staffing requirements.
  Use only facts from the manager message, conversation history, or CONTEXT.
- Conversation history and ALWAYS REMEMBER notes are authoritative. Resolve short answers against the manager's configured departments.
  against the clarification immediately before them. Never ask for information that the
  manager already supplied earlier in the conversation.
- Prefer useful actions over follow-up questions. For bulk lists, return every unambiguous
  action in one response. If one line is unclear, handle the rest and briefly identify only
  that line instead of blocking the entire request.
- When the manager says to add employees, add them. Do not ask about open availability;
  no saved unavailability already means open availability.
- Treat common station words as aliases: sandwiches=Sandwich, salads=Salad,
  dishwasher=Dish, cashier=Register. Use the exact saved CONTEXT position in actions.
- A person may share a first name with an existing employee. Department and last name can
  distinguish them. When the manager explicitly says rename the existing employee and add
  another, propose both actions without asking again.
- "training sandwiches/salads" means the employee can work that position with trainee=true.
- Ask one concise clarifying question only when the missing fact makes the requested action
  impossible or unsafe to represent.
- Dates must be YYYY-MM-DD. Times must be 24-hour HH:MM.
- day_of_week uses Monday=0 through Sunday=6; -1 means every day.
- For multiple people, return multiple actions.
- create_employee should be followed by set_employee_positions when positions were stated.
- Normalize common plurals and aliases to saved positions. If a position genuinely does not exist, propose create_position before assigning it instead of refusing the request.
- Position names must match CONTEXT unless create_position is also proposed.
- A Projected Crew target describes demand: minimum_count is must-have when hard_minimum
  is true; preferred_count is the amount the solver tries to reach within labor.
- With no departments/roles/positions on a crew target, it means any crew member.
- For "one opener at 8 and another at 9", create two crew targets so two different
  overlapping people are needed.
- "Whole day" labor means blank start_time/end_time and whole_day=true.
- For labor ranges, use min_labor_percent and max_labor_percent.
- Never publish a schedule. Schedule edits remain reviewable drafts.
- If the manager is only asking a question, return no actions.
- For accounting questions, use exact saved cents and clearly distinguish revenue, cash,
  receivables, payables, expenses, and net income. Never invent a transaction.
- Accounting writes (invoices, bills, expenses, journal entries) are not among your typed
  actions. Explain the steps or direct the user to the correct screen instead.
- Keep replies direct and explain what approval will change.
""".strip()


def ai_is_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _fallback_decision(message: str, context: dict) -> AssistantDecision:
    lower = message.lower()
    actions: list[AssistantAction] = []
    accounting = context.get("accounting") or {}
    summary = accounting.get("summary") or {}

    def dollars(key: str) -> str:
        return f"${float(summary.get(key, 0) or 0) / 100:,.2f}"

    if any(word in lower for word in {"owe us", "owed to us", "receivable", "unpaid invoice"}):
        return AssistantDecision(reply=f"Customers currently owe the business {dollars('accounts_receivable_cents')} in open receivables.")
    if any(word in lower for word in {"we owe", "payable", "unpaid bill", "bills due"}):
        return AssistantDecision(reply=f"The business currently owes {dollars('accounts_payable_cents')} in open payables.")
    if any(word in lower for word in {"profit", "profitable", "net income"}):
        return AssistantDecision(reply=f"Saved ledger activity shows {dollars('income_cents')} of income, {dollars('expenses_cents')} of expenses, and {dollars('net_income_cents')} of net income.")
    if "revenue" in lower or "income" in lower:
        return AssistantDecision(reply=f"Saved ledger income is {dollars('income_cents')}.")
    if "expense" in lower or "spending" in lower:
        return AssistantDecision(reply=f"Saved ledger expenses total {dollars('expenses_cents')}.")
    if "low stock" in lower or "reorder" in lower:
        items = [item for item in context.get("inventory", []) if item.get("quantity_milli", 0) <= item.get("reorder_level_milli", 0)]
        names = ", ".join(item.get("name", "Unnamed item") for item in items)
        return AssistantDecision(reply=f"{len(items)} item(s) are at or below their reorder level" + (f": {names}." if names else "."))

    # Basic employee creation fallback using a saved department.
    add_match = re.search(
        r"(?:add|create)\s+(?:employee\s+)?([a-z][a-z .'-]{1,40}?)\s+(?:to|in)\s+([a-z][a-z &/'-]{1,40})$",
        message,
        re.IGNORECASE,
    )
    if add_match:
        name = add_match.group(1).strip().title()
        requested = add_match.group(2).strip()
        saved_departments = {str(item.get("department", "")) for item in context.get("positions", [])}
        saved_departments |= {str(item.get("department", "")) for item in context.get("employees", [])}
        department = next((item for item in saved_departments if item.lower() == requested.lower()), requested.title())
        actions.append(
            AssistantAction(
                type="create_employee",
                name=name,
                department=department,
                role="employee",
                reason="Add the employee to the saved roster.",
            )
        )
        return AssistantDecision(
            reply=f"I can add {name} to {department}. Approve the change to save it.",
            actions=actions,
        )

    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", lower)
    if "labor" in lower and ("slip" in lower or "over" in lower):
        tolerance = float(percent_match.group(1)) if percent_match else 5.0
        actions.append(
            AssistantAction(
                type="regenerate_schedule",
                scope="problems",
                labor_tolerance_percent=tolerance,
                reason="Allow additional labor while repairing warned shifts.",
            )
        )
        return AssistantDecision(
            reply=f"I can rebuild the warned shifts with up to {tolerance:.1f}% extra labor.",
            actions=actions,
        )

    if "regenerate" in lower or "fix" in lower or "different closer" in lower:
        actions.append(
            AssistantAction(
                type="regenerate_schedule",
                scope="problems",
                reason="Rebuild warned shifts while preserving locked assignments.",
            )
        )
        return AssistantDecision(
            reply="I can regenerate the problem shifts and preserve anything you locked.",
            actions=actions,
        )

    schedule = context.get("schedule") or {}
    employees = context.get("employees") or []
    if "schedule" in lower:
        if schedule:
            return AssistantDecision(
                reply=(
                    f"The selected schedule is version {schedule.get('version')} with "
                    f"{len(schedule.get('shifts', []))} shifts and "
                    f"{len(schedule.get('warnings', []))} notices."
                )
            )
        return AssistantDecision(reply="No schedule is selected, but I can still help build the setup.")

    if "employee" in lower:
        names = ", ".join(item.get("name", "") for item in employees) or "none yet"
        return AssistantDecision(reply=f"Active employees: {names}.")

    return AssistantDecision(
        reply=(
            "I can build the setup or propose schedule changes. Claude is not connected, so "
            "the fallback only understands simple employee additions and regeneration requests."
        )
    )


def decide_with_ai(message: str, context: dict) -> tuple[AssistantDecision, bool]:
    """Return a structured proposal and whether the Claude API was used."""
    if not ai_is_configured():
        return _fallback_decision(message, context), False

    try:
        from anthropic import Anthropic

        client = Anthropic()
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        history = context.get("conversation_history") or []
        always_remember = str(context.get("always_remember") or "").strip()
        database_context = {
            key: value
            for key, value in context.items()
            if key not in {"conversation_history", "always_remember"}
        }
        system = SYSTEM_PROMPT + "\n\n" + (
            f"ALWAYS REMEMBER:\n{always_remember or '(none saved)'}\n\n"
            f"CURRENT DATABASE CONTEXT:\n{json.dumps(database_context, default=str)}\n\n"
            "Return only JSON matching this schema:\n"
            f"{json.dumps(AssistantDecision.model_json_schema())}"
        )
        selected_history = []
        character_budget = 60000
        used_characters = 0
        for item in reversed(history):
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            item_size = len(content)
            if selected_history and used_characters + item_size > character_budget:
                break
            selected_history.append({"role": role, "content": content})
            used_characters += item_size
        input_messages = list(reversed(selected_history))
        input_messages.append({"role": "user", "content": message})
        response = client.messages.create(model=model, max_tokens=4096, system=system, messages=input_messages)
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
        try:
            parsed = AssistantDecision.model_validate_json(text)
            return parsed, True
        except Exception:
            # Lenient path: salvage the reply text even if actions fail validation
            try:
                raw = json.loads(text)
                return AssistantDecision(reply=str(raw.get("reply", text[:300]))), True
            except Exception:
                raise
    except Exception as error:
        fallback = _fallback_decision(message, context)
        fallback.reply += f" (AI fallback active: {type(error).__name__}.)"
        return fallback, False
