from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import date, datetime, timedelta
from typing import Optional

from ortools.sat.python import cp_model
from sqlmodel import Session, select

from backend.app.models import (
    CoverageRule,
    Employee,
    EmployeePosition,
    LaborProjection,
    ManagerSettings,
    Position,
    RecurringAvailability,
    Schedule,
    ScheduleShift,
    ScheduleWarning,
    TemporaryUnavailability,
)


@dataclass(frozen=True)
class CandidateSlot:
    key: str
    date: str
    rule_id: int
    label: str
    position_ids: tuple[int, ...]
    departments: tuple[str, ...]
    roles: tuple[str, ...]
    start_time: str
    end_time: str
    start_minute: int
    end_minute: int
    required: bool


def parse_time(value: str, default: int = 0) -> int:
    if not value:
        return default
    hour, minute = value.split(":")[:2]
    return int(hour) * 60 + int(minute)


def overlap_minutes(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    return max(0, min(end_a, end_b) - max(start_a, start_b))


def date_range(week_start: str) -> list[str]:
    first = datetime.strptime(week_start, "%Y-%m-%d").date()
    return [(first + timedelta(days=i)).isoformat() for i in range(7)]


def role_matches(employee_role: str, required_role: str) -> bool:
    if required_role == "employee":
        return True
    if required_role == "shift_lead":
        return employee_role in {"shift_lead", "gm"}
    return employee_role == required_role


def effective_rate(employee: Employee, settings: ManagerSettings) -> float:
    # The store uses one base rate; shift leads and GMs receive a $1 premium.
    return settings.employee_hourly_rate + (1.0 if employee.role in {"shift_lead", "gm"} else 0.0)


def _json_list(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def rule_targets(rule: CoverageRule) -> tuple[tuple[int, ...], tuple[str, ...], tuple[str, ...]]:
    position_ids = tuple(int(value) for value in _json_list(rule.position_ids_json) if str(value).isdigit())
    departments = tuple(str(value) for value in _json_list(rule.departments_json) if str(value).strip())
    roles = tuple(str(value) for value in _json_list(rule.roles_json) if value in {"employee", "shift_lead", "gm"})

    # Read old single-target rows too, so upgrades do not destroy existing rules.
    if not position_ids and rule.position_id:
        position_ids = (rule.position_id,)
    if not departments and rule.department:
        departments = (rule.department,)
    if not roles and rule.role:
        roles = (rule.role,)
    return position_ids, departments, roles


def recurring_rule_blocks(
    rule: RecurringAvailability,
    target_date: str,
    start_minute: int,
    end_minute: int,
) -> bool:
    weekday = datetime.strptime(target_date, "%Y-%m-%d").date().weekday()
    if rule.day_of_week not in {-1, weekday}:
        return False
    rule_start = parse_time(rule.start_time, 0)
    rule_end = parse_time(rule.end_time, 24 * 60)
    return overlap_minutes(start_minute, end_minute, rule_start, rule_end) > 0


def temporary_rule_blocks(
    rule: TemporaryUnavailability,
    target_date: str,
    start_minute: int,
    end_minute: int,
) -> bool:
    if not (rule.start_date <= target_date <= rule.end_date):
        return False
    rule_start = parse_time(rule.start_time, 0)
    rule_end = parse_time(rule.end_time, 24 * 60)
    return overlap_minutes(start_minute, end_minute, rule_start, rule_end) > 0


def fixed_shift_covers_rule(
    shift: ScheduleShift,
    rule: CoverageRule,
    employee_by_id: dict[int, Employee],
    position_by_id: dict[int, Position],
) -> bool:
    rule_start = parse_time(rule.start_time)
    rule_end = parse_time(rule.end_time)
    shift_start = parse_time(shift.start_time)
    shift_end = parse_time(shift.end_time)
    if shift_start > rule_start or shift_end < rule_end:
        return False

    employee = employee_by_id.get(shift.employee_id)
    if not employee:
        return False

    position_ids, departments, roles = rule_targets(rule)
    position = position_by_id.get(shift.position_id) if shift.position_id else None
    if not (position_ids or departments or roles):
        return True
    return (
        bool(shift.position_id and shift.position_id in position_ids)
        or employee.department in departments
        or bool(position and position.department in departments)
        or any(role_matches(employee.role, required_role) for required_role in roles)
    )


def schedule_detail(session: Session, schedule_id: int) -> dict:
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise ValueError("Schedule not found")

    shifts = session.exec(
        select(ScheduleShift).where(ScheduleShift.schedule_id == schedule_id)
    ).all()
    warnings = session.exec(
        select(ScheduleWarning).where(ScheduleWarning.schedule_id == schedule_id)
    ).all()

    employees = {item.id: item for item in session.exec(select(Employee)).all()}
    positions = {item.id: item for item in session.exec(select(Position)).all()}

    shift_rows = []
    for shift in sorted(shifts, key=lambda item: (item.date, item.start_time, item.end_time)):
        employee = employees.get(shift.employee_id)
        position = positions.get(shift.position_id) if shift.position_id else None
        shift_rows.append(
            {
                **shift.model_dump(),
                "employee_name": employee.name if employee else f"Employee #{shift.employee_id}",
                "position_name": position.name if position else "",
                "department": position.department if position else (employee.department if employee else ""),
            }
        )

    return {
        **schedule.model_dump(),
        "shifts": shift_rows,
        "warnings": [warning.model_dump() for warning in warnings],
    }


def generate_schedule(
    session: Session,
    *,
    week_start: str,
    source_schedule_id: Optional[int] = None,
    scope: str = "full_week",
    selected_date: Optional[str] = None,
    labor_tolerance_percent: float = 0.0,
    staffing_level: str = "balanced",
) -> dict:
    week_dates = date_range(week_start)
    employees = session.exec(select(Employee).where(Employee.active == True)).all()  # noqa: E712
    positions = session.exec(select(Position).where(Position.active == True)).all()  # noqa: E712
    employee_positions = session.exec(select(EmployeePosition)).all()
    recurring = session.exec(select(RecurringAvailability)).all()
    temporary = session.exec(select(TemporaryUnavailability)).all()
    coverage_rules = session.exec(
        select(CoverageRule).where(CoverageRule.active == True)  # noqa: E712
    ).all()
    labor_projections = [
        row
        for row in session.exec(select(LaborProjection)).all()
        if row.date in week_dates
    ]
    settings = session.exec(select(ManagerSettings)).first() or ManagerSettings()

    employee_by_id = {employee.id: employee for employee in employees if employee.id is not None}
    position_by_id = {position.id: position for position in positions if position.id is not None}

    ep_by_employee: dict[int, list[EmployeePosition]] = {}
    for row in employee_positions:
        ep_by_employee.setdefault(row.employee_id, []).append(row)

    recurring_by_employee: dict[int, list[RecurringAvailability]] = {}
    for row in recurring:
        recurring_by_employee.setdefault(row.employee_id, []).append(row)

    temporary_by_employee: dict[int, list[TemporaryUnavailability]] = {}
    for row in temporary:
        temporary_by_employee.setdefault(row.employee_id, []).append(row)

    source_schedule = session.get(Schedule, source_schedule_id) if source_schedule_id else None
    source_shifts: list[ScheduleShift] = []
    source_warnings: list[ScheduleWarning] = []
    if source_schedule:
        source_shifts = session.exec(
            select(ScheduleShift).where(ScheduleShift.schedule_id == source_schedule.id)
        ).all()
        source_warnings = session.exec(
            select(ScheduleWarning).where(ScheduleWarning.schedule_id == source_schedule.id)
        ).all()

    if scope == "selected_day":
        if not selected_date or selected_date not in week_dates:
            raise ValueError("A date inside the selected week is required")
        target_dates = {selected_date}
    elif scope == "problems" and source_schedule:
        target_dates = {warning.date for warning in source_warnings if warning.date in week_dates}
        if not target_dates:
            target_dates = set(week_dates)
    else:
        target_dates = set(week_dates)

    copied_shifts = [
        shift
        for shift in source_shifts
        if shift.date not in target_dates or shift.locked
    ]
    copied_warnings = [
        warning
        for warning in source_warnings
        if warning.date not in target_dates
    ]

    existing = session.exec(
        select(Schedule).where(Schedule.week_start == week_start)
    ).all()
    version = max([item.version for item in existing], default=0) + 1

    new_schedule = Schedule(
        week_start=week_start,
        version=version,
        status="draft",
        source_schedule_id=source_schedule_id,
        generation_scope=scope,
        labor_tolerance_percent=labor_tolerance_percent,
        staffing_level=staffing_level if staffing_level in {"lean", "balanced", "full"} else "balanced",
    )
    session.add(new_schedule)
    session.commit()
    session.refresh(new_schedule)

    new_shift_objects: list[ScheduleShift] = []
    for shift in copied_shifts:
        clone = ScheduleShift(
            schedule_id=new_schedule.id,
            date=shift.date,
            employee_id=shift.employee_id,
            position_id=shift.position_id,
            role=shift.role,
            start_time=shift.start_time,
            end_time=shift.end_time,
            locked=shift.locked,
            source_rule_id=shift.source_rule_id,
        )
        session.add(clone)
        new_shift_objects.append(clone)

    for warning in copied_warnings:
        session.add(
            ScheduleWarning(
                schedule_id=new_schedule.id,
                date=warning.date,
                severity=warning.severity,
                code=warning.code,
                message=warning.message,
            )
        )
    session.commit()

    if not coverage_rules:
        session.add(
            ScheduleWarning(
                schedule_id=new_schedule.id,
                severity="error",
                code="NO_CREW_TARGETS",
                message="No Projected Crew targets exist. Add at least one crew target in Manager before generating.",
            )
        )
        new_schedule.status = "needs_review"
        session.add(new_schedule)
        session.commit()
        return schedule_detail(session, new_schedule.id)

    slots: list[CandidateSlot] = []
    for target_date in sorted(target_dates):
        weekday = datetime.strptime(target_date, "%Y-%m-%d").date().weekday()
        for rule in coverage_rules:
            if rule.id is None:
                continue
            if rule.date:
                if rule.date != target_date:
                    continue
            elif rule.day_of_week not in {-1, weekday}:
                continue

            fixed_cover = sum(
                1
                for shift in copied_shifts
                if shift.date == target_date
                and fixed_shift_covers_rule(shift, rule, employee_by_id, position_by_id)
            )
            minimum = max(0, rule.minimum_count - fixed_cover)
            preferred = max(minimum, rule.preferred_count - fixed_cover)
            for index in range(preferred):
                position_ids, departments, roles = rule_targets(rule)
                slots.append(
                    CandidateSlot(
                        key=f"{target_date}-{rule.id}-{index}",
                        date=target_date,
                        rule_id=rule.id,
                        label=rule.name,
                        position_ids=position_ids,
                        departments=departments,
                        roles=roles,
                        start_time=rule.start_time,
                        end_time=rule.end_time,
                        start_minute=parse_time(rule.start_time),
                        end_minute=parse_time(rule.end_time),
                        required=index < minimum and rule.hard_minimum,
                    )
                )

    model = cp_model.CpModel()
    variables: dict[tuple[int, str], cp_model.IntVar] = {}
    variable_position: dict[tuple[int, str], Optional[int]] = {}
    variable_trainee: dict[tuple[int, str], bool] = {}
    objective_terms = []
    missing_variables: list[tuple[CandidateSlot, cp_model.IntVar]] = []
    optional_variables: list[tuple[CandidateSlot, cp_model.IntVar]] = []
    trainee_alone_variables: list[tuple[int, CandidateSlot, cp_model.IntVar]] = []

    fixed_minutes_by_employee: dict[int, int] = {}
    for shift in copied_shifts:
        fixed_minutes_by_employee[shift.employee_id] = (
            fixed_minutes_by_employee.get(shift.employee_id, 0)
            + max(0, parse_time(shift.end_time) - parse_time(shift.start_time))
        )

    def choose_position(employee_id: int, slot: CandidateSlot) -> Optional[int]:
        rows = ep_by_employee.get(employee_id, [])
        active_rows = [row for row in rows if row.position_id in position_by_id]
        matching_rows = [
            row
            for row in active_rows
            if (row.position_id in slot.position_ids)
            or (position_by_id[row.position_id].department in slot.departments)
        ]
        preferred_rows = [row for row in matching_rows if row.preferred]
        if preferred_rows or matching_rows:
            return (preferred_rows or matching_rows)[0].position_id

        # Role-only coverage can still be represented even when the employee has no
        # position selected. If they do have one, use their preferred position for display.
        preferred_rows = [row for row in active_rows if row.preferred]
        return (preferred_rows or active_rows)[0].position_id if (preferred_rows or active_rows) else None

    def employee_eligible(employee: Employee, slot: CandidateSlot) -> bool:
        if employee.id is None:
            return False
        if any(
            recurring_rule_blocks(rule, slot.date, slot.start_minute, slot.end_minute)
            for rule in recurring_by_employee.get(employee.id, [])
            if rule.rule_type == "unavailable"
        ):
            return False
        if any(
            temporary_rule_blocks(rule, slot.date, slot.start_minute, slot.end_minute)
            for rule in temporary_by_employee.get(employee.id, [])
        ):
            return False
        if any(
            fixed.date == slot.date
            and fixed.employee_id == employee.id
            and overlap_minutes(
                slot.start_minute,
                slot.end_minute,
                parse_time(fixed.start_time),
                parse_time(fixed.end_time),
            )
            > 0
            for fixed in copied_shifts
        ):
            return False

        if not (slot.position_ids or slot.departments or slot.roles):
            return True
        position_match = any(
            row.position_id in slot.position_ids
            for row in ep_by_employee.get(employee.id, [])
        )
        department_match = employee.department in slot.departments and choose_position(employee.id, slot) is not None
        role_match = any(role_matches(employee.role, required_role) for required_role in slot.roles)
        return position_match or department_match or role_match

    for slot in slots:
        slot_variables = []
        for employee in employees:
            if not employee_eligible(employee, slot):
                continue
            employee_id = employee.id
            key = (employee_id, slot.key)
            variable = model.NewBoolVar(f"assign-{employee_id}-{slot.key}")
            variables[key] = variable
            chosen_position = choose_position(employee_id, slot)
            variable_position[key] = chosen_position
            employee_position = next(
                (
                    row
                    for row in ep_by_employee.get(employee_id, [])
                    if row.position_id == chosen_position
                ),
                None,
            )
            variable_trainee[key] = bool(employee_position and employee_position.trainee)
            slot_variables.append(variable)

            if employee_position and employee_position.preferred:
                objective_terms.append(variable * 800)
            if any(
                recurring_rule_blocks(rule, slot.date, slot.start_minute, slot.end_minute)
                for rule in recurring_by_employee.get(employee_id, [])
                if rule.rule_type == "preferred"
            ):
                objective_terms.append(variable * 400)

            cost_cents = int(
                round(
                    effective_rate(employee, settings)
                    * 100
                    * (slot.end_minute - slot.start_minute)
                    / 60
                )
            )
            objective_terms.append(variable * -max(1, cost_cents // 100))

        if slot.required:
            missing = model.NewBoolVar(f"missing-{slot.key}")
            model.Add(sum(slot_variables) + missing == 1)
            objective_terms.append(missing * -100000)
            missing_variables.append((slot, missing))
        else:
            assigned = model.NewBoolVar(f"optional-{slot.key}")
            model.Add(sum(slot_variables) == assigned)
            objective_terms.append(assigned * 5000)
            optional_variables.append((slot, assigned))

    variables_by_employee: dict[int, list[tuple[CandidateSlot, cp_model.IntVar]]] = {}
    for (employee_id, slot_key), variable in variables.items():
        slot = next(item for item in slots if item.key == slot_key)
        variables_by_employee.setdefault(employee_id, []).append((slot, variable))

    for employee in employees:
        if employee.id is None:
            continue
        rows = variables_by_employee.get(employee.id, [])
        fixed_minutes = fixed_minutes_by_employee.get(employee.id, 0)
        remaining_max = max(0, employee.max_hours_per_week * 60 - fixed_minutes)
        model.Add(
            sum((slot.end_minute - slot.start_minute) * variable for slot, variable in rows)
            <= remaining_max
        )

        minimum_minutes = max(0, employee.min_hours_per_week * 60)
        shortfall = model.NewIntVar(0, minimum_minutes, f"shortfall-{employee.id}")
        total_variable_minutes = sum(
            (slot.end_minute - slot.start_minute) * variable
            for slot, variable in rows
        )
        model.Add(shortfall >= minimum_minutes - fixed_minutes - total_variable_minutes)
        objective_terms.append(shortfall * -5)

        if rows:
            used = model.NewBoolVar(f"used-{employee.id}")
            for _, variable in rows:
                model.Add(variable <= used)
            model.Add(sum(variable for _, variable in rows) >= used)
            objective_terms.append(used * 150)

        for index, (slot_a, variable_a) in enumerate(rows):
            for slot_b, variable_b in rows[index + 1 :]:
                if slot_a.date != slot_b.date:
                    continue
                if overlap_minutes(
                    slot_a.start_minute,
                    slot_a.end_minute,
                    slot_b.start_minute,
                    slot_b.end_minute,
                ) > 0:
                    model.Add(variable_a + variable_b <= 1)

    if settings.schedule_extra_with_trainee:
        variable_rows = []
        for (employee_id, slot_key), variable in variables.items():
            slot = next(item for item in slots if item.key == slot_key)
            variable_rows.append(
                (
                    employee_id,
                    slot,
                    variable,
                    variable_position[(employee_id, slot_key)],
                    variable_trainee[(employee_id, slot_key)],
                )
            )

        for employee_id, slot, variable, position_id, trainee in variable_rows:
            if not trainee or position_id is None:
                continue
            other_variables = [
                other_variable
                for other_employee_id, other_slot, other_variable, other_position_id, _ in variable_rows
                if other_employee_id != employee_id
                and other_slot.date == slot.date
                and other_position_id == position_id
                and overlap_minutes(
                    slot.start_minute,
                    slot.end_minute,
                    other_slot.start_minute,
                    other_slot.end_minute,
                )
                > 0
            ]
            alone = model.NewBoolVar(f"trainee-alone-{employee_id}-{slot.key}")
            model.Add(sum(other_variables) + alone >= variable)
            objective_terms.append(alone * -12000)
            trainee_alone_variables.append((employee_id, slot, alone))

    def fixed_projection_usage(projection: LaborProjection) -> tuple[int, int]:
        block_start = parse_time(projection.start_time, 0)
        block_end = parse_time(projection.end_time, 24 * 60)
        minutes = 0
        cents = 0
        for shift in copied_shifts:
            if shift.date != projection.date:
                continue
            overlap = overlap_minutes(
                parse_time(shift.start_time),
                parse_time(shift.end_time),
                block_start,
                block_end,
            )
            if overlap <= 0:
                continue
            employee = employee_by_id.get(shift.employee_id)
            if not employee:
                continue
            minutes += overlap
            cents += int(round(effective_rate(employee, settings) * 100 * overlap / 60))
        return minutes, cents

    def selected_labor_percent(projection: LaborProjection) -> Optional[float]:
        minimum = projection.min_labor_percent
        maximum = projection.max_labor_percent
        if minimum is None and maximum is None:
            return projection.labor_percent
        if minimum is None:
            minimum = maximum
        if maximum is None:
            maximum = minimum
        minimum = float(minimum or 0)
        maximum = float(maximum or minimum)
        if maximum < minimum:
            minimum, maximum = maximum, minimum
        if staffing_level == "lean":
            return minimum
        if staffing_level == "full":
            return maximum
        return (minimum + maximum) / 2

    for projection in labor_projections:
        block_start = parse_time(projection.start_time, 0)
        block_end = parse_time(projection.end_time, 24 * 60)
        minute_terms = []
        cost_terms = []

        for (employee_id, slot_key), variable in variables.items():
            slot = next(item for item in slots if item.key == slot_key)
            if slot.date != projection.date:
                continue
            overlap = overlap_minutes(
                slot.start_minute,
                slot.end_minute,
                block_start,
                block_end,
            )
            if overlap <= 0:
                continue
            employee = employee_by_id[employee_id]
            minute_terms.append(variable * overlap)
            cost_cents = int(round(effective_rate(employee, settings) * 100 * overlap / 60))
            cost_terms.append(variable * cost_cents)

        fixed_minutes, fixed_cents = fixed_projection_usage(projection)
        tolerance = 1 + labor_tolerance_percent / 100

        if projection.max_labor_hours is not None:
            allowed_minutes = int(round(projection.max_labor_hours * 60 * tolerance))
            remaining = allowed_minutes - fixed_minutes
            if remaining >= 0:
                model.Add(sum(minute_terms) <= remaining)

        budgets = []
        if projection.max_labor_dollars is not None:
            budgets.append(int(round(projection.max_labor_dollars * 100 * tolerance)))
        chosen_percent = selected_labor_percent(projection)
        if projection.projected_sales is not None and chosen_percent is not None:
            budgets.append(
                int(
                    round(
                        projection.projected_sales
                        * chosen_percent
                        / 100
                        * 100
                        * tolerance
                    )
                )
            )
        for budget_cents in budgets:
            remaining = budget_cents - fixed_cents
            if remaining >= 0:
                model.Add(sum(cost_terms) <= remaining)

    model.Maximize(sum(objective_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_search_workers = 8
    result = solver.Solve(model)

    generated_shifts: list[ScheduleShift] = []
    if result in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        for (employee_id, slot_key), variable in variables.items():
            if solver.Value(variable) != 1:
                continue
            slot = next(item for item in slots if item.key == slot_key)
            employee = employee_by_id[employee_id]
            shift = ScheduleShift(
                schedule_id=new_schedule.id,
                date=slot.date,
                employee_id=employee_id,
                position_id=variable_position[(employee_id, slot_key)],
                role=employee.role,
                start_time=slot.start_time,
                end_time=slot.end_time,
                locked=False,
                source_rule_id=slot.rule_id,
            )
            session.add(shift)
            generated_shifts.append(shift)

        session.commit()
        for shift in generated_shifts:
            session.refresh(shift)

        for slot, missing in missing_variables:
            if solver.Value(missing) == 1:
                session.add(
                    ScheduleWarning(
                        schedule_id=new_schedule.id,
                        date=slot.date,
                        severity="error",
                        code="UNCOVERED_REQUIRED_SLOT",
                        message=f"Could not cover {slot.label}, {slot.start_time}-{slot.end_time}.",
                    )
                )

        all_new_shifts = copied_shifts + generated_shifts
        if settings.schedule_extra_with_trainee:
            ep_lookup = {
                (row.employee_id, row.position_id): row
                for row in employee_positions
            }
            for shift in generated_shifts:
                if shift.position_id is None:
                    continue
                employee_position = ep_lookup.get((shift.employee_id, shift.position_id))
                if not employee_position or not employee_position.trainee:
                    continue
                start = parse_time(shift.start_time)
                end = parse_time(shift.end_time)
                has_overlap = any(
                    other.employee_id != shift.employee_id
                    and other.date == shift.date
                    and other.position_id == shift.position_id
                    and overlap_minutes(
                        start,
                        end,
                        parse_time(other.start_time),
                        parse_time(other.end_time),
                    )
                    > 0
                    for other in all_new_shifts
                )
                if not has_overlap:
                    employee = employee_by_id.get(shift.employee_id)
                    position = position_by_id.get(shift.position_id)
                    session.add(
                        ScheduleWarning(
                            schedule_id=new_schedule.id,
                            date=shift.date,
                            severity="warning",
                            code="TRAINEE_WITHOUT_EXTRA_COVERAGE",
                            message=(
                                f"{employee.name if employee else 'Trainee'} is scheduled alone on "
                                f"{position.name if position else 'their position'} "
                                f"from {shift.start_time}-{shift.end_time}."
                            ),
                            shift_id=shift.id,
                        )
                    )
    else:
        session.add(
            ScheduleWarning(
                schedule_id=new_schedule.id,
                severity="error",
                code="SOLVER_FAILED",
                message="The schedule solver could not produce a draft.",
            )
        )

    all_schedule_shifts = session.exec(
        select(ScheduleShift).where(ScheduleShift.schedule_id == new_schedule.id)
    ).all()

    for employee in employees:
        if employee.id is None:
            continue
        total_minutes = sum(
            max(0, parse_time(shift.end_time) - parse_time(shift.start_time))
            for shift in all_schedule_shifts
            if shift.employee_id == employee.id
        )
        if total_minutes > employee.max_hours_per_week * 60:
            session.add(
                ScheduleWarning(
                    schedule_id=new_schedule.id,
                    severity="error",
                    code="MAX_HOURS_EXCEEDED",
                    message=f"{employee.name} exceeds their weekly maximum hours.",
                )
            )

    for projection in labor_projections:
        block_start = parse_time(projection.start_time, 0)
        block_end = parse_time(projection.end_time, 24 * 60)
        total_minutes = 0
        total_cents = 0
        for shift in all_schedule_shifts:
            if shift.date != projection.date:
                continue
            overlap = overlap_minutes(
                parse_time(shift.start_time),
                parse_time(shift.end_time),
                block_start,
                block_end,
            )
            if overlap <= 0:
                continue
            employee = employee_by_id.get(shift.employee_id)
            if not employee:
                continue
            total_minutes += overlap
            total_cents += int(round(effective_rate(employee, settings) * 100 * overlap / 60))

        base_limits: list[tuple[str, float, float]] = []
        if projection.max_labor_hours is not None:
            base_limits.append(("hours", total_minutes / 60, projection.max_labor_hours))
        if projection.max_labor_dollars is not None:
            base_limits.append(("dollars", total_cents / 100, projection.max_labor_dollars))
        chosen_percent = selected_labor_percent(projection)
        if projection.projected_sales is not None and chosen_percent is not None:
            budget = projection.projected_sales * chosen_percent / 100
            base_limits.append(("dollars", total_cents / 100, budget))

        for limit_type, actual, limit in base_limits:
            if actual > limit + 0.01:
                window = (
                    f"{projection.start_time}-{projection.end_time}"
                    if projection.start_time or projection.end_time
                    else "the whole day"
                )
                unit = "$" if limit_type == "dollars" else ""
                suffix = "" if limit_type == "dollars" else " hours"
                session.add(
                    ScheduleWarning(
                        schedule_id=new_schedule.id,
                        date=projection.date,
                        severity="warning",
                        code="LABOR_TARGET_EXCEEDED",
                        message=(
                            f"Labor for {window} is {unit}{actual:.2f}{suffix}, "
                            f"above the {staffing_level} target of {unit}{limit:.2f}{suffix}."
                        ),
                    )
                )

        if projection.projected_sales and projection.min_labor_percent is not None and projection.max_labor_percent is not None:
            actual_percent = (total_cents / 100) / projection.projected_sales * 100 if projection.projected_sales else 0
            low = min(projection.min_labor_percent, projection.max_labor_percent)
            high = max(projection.min_labor_percent, projection.max_labor_percent)
            window = (
                f"{projection.start_time}-{projection.end_time}"
                if projection.start_time or projection.end_time
                else "the whole day"
            )
            session.add(
                ScheduleWarning(
                    schedule_id=new_schedule.id,
                    date=projection.date,
                    severity="info",
                    code="LABOR_RANGE_SUMMARY",
                    message=(
                        f"Labor for {window} is {actual_percent:.1f}% of projected sales "
                        f"(goal range {low:.1f}%–{high:.1f}%, {staffing_level} draft)."
                    ),
                )
            )

    session.commit()
    warning_rows = session.exec(
        select(ScheduleWarning).where(ScheduleWarning.schedule_id == new_schedule.id)
    ).all()
    warning_count = sum(1 for row in warning_rows if row.severity in {"warning", "error"})
    new_schedule.status = "needs_review" if warning_count else "draft"
    session.add(new_schedule)
    session.commit()
    return schedule_detail(session, new_schedule.id)
