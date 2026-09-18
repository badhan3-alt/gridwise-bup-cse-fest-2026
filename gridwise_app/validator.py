from __future__ import annotations

import math

from .models import DirectiveInterpretation, HourlyPlanEntry, OptimizeRequest
from .optimizer import AppliedDirectives, build_directive_effects

TOL = 0.01


class PlanValidationError(RuntimeError):
    pass


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= tol


def validate_plan(
    request: OptimizeRequest,
    directives: list[DirectiveInterpretation],
    plan: list[HourlyPlanEntry],
    total_grid_kwh: float,
    total_cost_bdt: float,
    peak_grid_kwh: float,
    effects: AppliedDirectives | None = None,
) -> None:
    if len(plan) != 24 or [p.hour for p in plan] != list(range(24)):
        raise PlanValidationError("hourly_plan must contain exactly the unique hours 0 through 23 in order")

    hours = sorted(request.hours, key=lambda x: x.hour)
    effects = effects or build_directive_effects(request, directives)
    before = request.battery.initial_energy_kwh

    for h, entry in enumerate(plan):
        nums = [entry.grid_kwh, entry.solar_used_kwh, entry.battery_kwh, entry.battery_energy_after_kwh]
        if any((not math.isfinite(x)) or x < -TOL for x in nums):
            raise PlanValidationError(f"hour {h}: numeric values must be finite and non-negative")
        if entry.solar_used_kwh > effects.effective_solar[h] + TOL:
            raise PlanValidationError(f"hour {h}: solar usage exceeds effective solar")

        if entry.battery_action == "charge":
            delta = entry.battery_kwh
            if entry.battery_kwh > request.battery.max_charge_kwh_per_hour + TOL:
                raise PlanValidationError(f"hour {h}: charge rate exceeded")
            if effects.no_charge[h] and entry.battery_kwh > TOL:
                raise PlanValidationError(f"hour {h}: charging prohibited")
        elif entry.battery_action == "discharge":
            delta = -entry.battery_kwh
            if entry.battery_kwh > request.battery.max_discharge_kwh_per_hour + TOL:
                raise PlanValidationError(f"hour {h}: discharge rate exceeded")
            if effects.no_discharge[h] and entry.battery_kwh > TOL:
                raise PlanValidationError(f"hour {h}: discharging prohibited")
        else:
            delta = 0.0
            if entry.battery_kwh > TOL:
                raise PlanValidationError(f"hour {h}: idle requires battery_kwh=0")

        expected_energy = before + delta
        if not _close(entry.battery_energy_after_kwh, expected_energy):
            raise PlanValidationError(f"hour {h}: invalid battery state transition")
        if entry.battery_energy_after_kwh < effects.min_reserve[h] - TOL:
            raise PlanValidationError(f"hour {h}: battery below active minimum reserve")
        if entry.battery_energy_after_kwh > request.battery.capacity_kwh + TOL:
            raise PlanValidationError(f"hour {h}: battery exceeds capacity")

        charge = entry.battery_kwh if entry.battery_action == "charge" else 0.0
        discharge = entry.battery_kwh if entry.battery_action == "discharge" else 0.0
        lhs = entry.grid_kwh + entry.solar_used_kwh + discharge
        rhs = hours[h].demand_kwh + charge
        if not _close(lhs, rhs):
            raise PlanValidationError(f"hour {h}: energy balance failed")

        if effects.max_grid[h] is not None and entry.grid_kwh > effects.max_grid[h] + TOL:
            raise PlanValidationError(f"hour {h}: grid cap exceeded")
        before = entry.battery_energy_after_kwh

    if not _close(plan[-1].battery_energy_after_kwh, request.battery.initial_energy_kwh):
        raise PlanValidationError("final battery energy must equal initial battery energy")

    recomputed_grid = sum(p.grid_kwh for p in plan)
    recomputed_cost = sum(plan[h].grid_kwh * hours[h].tariff_bdt_per_kwh for h in range(24))
    recomputed_peak = max(p.grid_kwh for p in plan)
    if not _close(total_grid_kwh, recomputed_grid):
        raise PlanValidationError("total_grid_kwh does not match hourly_plan")
    if not _close(total_cost_bdt, recomputed_cost):
        raise PlanValidationError("total_cost_bdt does not match hourly_plan")
    if not _close(peak_grid_kwh, recomputed_peak):
        raise PlanValidationError("peak_grid_kwh does not match hourly_plan")
