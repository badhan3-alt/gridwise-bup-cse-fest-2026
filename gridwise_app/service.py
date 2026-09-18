from __future__ import annotations

from .guardrails import validate_interpretations
from .llm_interpreter import interpret_operator_notes
from .models import OptimizeRequest, OptimizeResponse
from .optimizer import optimize_schedule
from .validator import validate_plan


def _make_summary(directives, total_cost: float) -> str:
    active = [d.directive_type for d in directives if d.applies]
    if active:
        kinds = ", ".join(active)
        return f"Applied {kinds}; minimized 24-hour grid cost while restoring the battery to its initial energy. Total cost: {total_cost:.2f} BDT."
    return f"No operator note changed the energy constraints; minimized 24-hour grid cost and restored the battery to its initial energy. Total cost: {total_cost:.2f} BDT."


def optimize_energy(request: OptimizeRequest) -> OptimizeResponse:
    directives = interpret_operator_notes(request)
    validate_interpretations(request, directives)
    plan, total_grid, total_cost, peak_grid, effects = optimize_schedule(request, directives)
    validate_plan(request, directives, plan, total_grid, total_cost, peak_grid, effects)
    return OptimizeResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=directives,
        hourly_plan=plan,
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
        plan_summary=_make_summary(directives, total_cost),
    )
