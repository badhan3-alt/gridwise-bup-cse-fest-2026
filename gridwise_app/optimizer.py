from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from .models import DirectiveInterpretation, HourlyPlanEntry, OptimizeRequest


class OptimizationError(RuntimeError):
    pass


@dataclass
class AppliedDirectives:
    effective_solar: list[float]
    min_reserve: list[float]
    no_charge: list[bool]
    no_discharge: list[bool]
    max_grid: list[float | None]


def build_directive_effects(request: OptimizeRequest, directives: list[DirectiveInterpretation]) -> AppliedDirectives:
    hours = sorted(request.hours, key=lambda x: x.hour)
    effective_solar = [h.solar_kwh for h in hours]
    min_reserve = [request.battery.minimum_energy_kwh for _ in range(24)]
    no_charge = [False] * 24
    no_discharge = [False] * 24
    max_grid: list[float | None] = [None] * 24

    for directive in directives:
        if not directive.applies:
            continue
        adj = directive.structured_adjustment
        assert adj is not None

        if directive.directive_type == "solar_reduction":
            for h in adj.hours:
                effective_solar[h] = min(effective_solar[h], hours[h].solar_kwh * adj.factor)
        elif directive.directive_type == "minimum_battery_reserve":
            for h in adj.hours:
                min_reserve[h] = max(min_reserve[h], adj.minimum_energy_kwh)
        elif directive.directive_type == "no_charge_window":
            for h in adj.hours:
                no_charge[h] = True
        elif directive.directive_type == "no_discharge_window":
            for h in adj.hours:
                no_discharge[h] = True
        elif directive.directive_type == "max_grid_window":
            for h in adj.hours:
                cap = adj.max_grid_kwh
                max_grid[h] = cap if max_grid[h] is None else min(max_grid[h], cap)

    return AppliedDirectives(effective_solar, min_reserve, no_charge, no_discharge, max_grid)


def _clean(value: float, digits: int = 6) -> float:
    value = float(value)
    if abs(value) < 5e-8:
        value = 0.0
    return round(value, digits)


def optimize_schedule(request: OptimizeRequest, directives: list[DirectiveInterpretation]):
    hours = sorted(request.hours, key=lambda x: x.hour)
    battery = request.battery
    effects = build_directive_effects(request, directives)

    # Variable layout: [grid(24), solar(24), delta(24), energy_after(24)]
    n = 96
    G, S, D, E = 0, 24, 48, 72

    c = np.zeros(n, dtype=float)
    for h in range(24):
        c[G + h] = hours[h].tariff_bdt_per_kwh

    bounds: list[tuple[float | None, float | None]] = []
    for h in range(24):
        bounds.append((0.0, effects.max_grid[h]))
    for h in range(24):
        bounds.append((0.0, effects.effective_solar[h]))
    for h in range(24):
        lo = -battery.max_discharge_kwh_per_hour
        hi = battery.max_charge_kwh_per_hour
        if effects.no_charge[h]:
            hi = min(hi, 0.0)
        if effects.no_discharge[h]:
            lo = max(lo, 0.0)
        bounds.append((lo, hi))
    for h in range(24):
        bounds.append((effects.min_reserve[h], battery.capacity_kwh))

    a_eq = []
    b_eq = []

    for h in range(24):
        # grid + solar = demand + delta
        row = np.zeros(n, dtype=float)
        row[G + h] = 1.0
        row[S + h] = 1.0
        row[D + h] = -1.0
        a_eq.append(row)
        b_eq.append(hours[h].demand_kwh)

        # energy_after = energy_before + delta
        row = np.zeros(n, dtype=float)
        row[E + h] = 1.0
        row[D + h] = -1.0
        if h == 0:
            a_eq.append(row)
            b_eq.append(battery.initial_energy_kwh)
        else:
            row[E + h - 1] = -1.0
            a_eq.append(row)
            b_eq.append(0.0)

    # End-of-day battery neutrality.
    row = np.zeros(n, dtype=float)
    row[E + 23] = 1.0
    a_eq.append(row)
    b_eq.append(battery.initial_energy_kwh)

    result = linprog(
        c,
        A_eq=np.asarray(a_eq),
        b_eq=np.asarray(b_eq),
        bounds=bounds,
        method="highs",
        options={"time_limit": 10.0},
    )
    if not result.success:
        raise OptimizationError(f"optimizer failed: {result.message}")

    x = result.x
    plan: list[HourlyPlanEntry] = []
    for h in range(24):
        g = _clean(x[G + h])
        s = _clean(x[S + h])
        d = _clean(x[D + h])
        e = _clean(x[E + h])
        if d > 1e-7:
            action = "charge"
            battery_kwh = d
        elif d < -1e-7:
            action = "discharge"
            battery_kwh = -d
        else:
            action = "idle"
            battery_kwh = 0.0

        plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=g,
                solar_used_kwh=s,
                battery_action=action,
                battery_kwh=_clean(battery_kwh),
                battery_energy_after_kwh=e,
            )
        )

    total_grid = _clean(sum(p.grid_kwh for p in plan))
    total_cost = _clean(sum(plan[h].grid_kwh * hours[h].tariff_bdt_per_kwh for h in range(24)))
    peak_grid = _clean(max(p.grid_kwh for p in plan))
    return plan, total_grid, total_cost, peak_grid, effects
