import json
from pathlib import Path

import pytest

from gridwise_app.guardrails import validate_interpretations
from gridwise_app.models import DirectiveInterpretation, OptimizeRequest
from gridwise_app.optimizer import optimize_schedule
from gridwise_app.validator import validate_plan

ROOT = Path(__file__).resolve().parents[1]
PACK = json.loads((ROOT / "public_sample_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", PACK["cases"], ids=lambda c: c["id"])
def test_optimizer_matches_public_optimum(case):
    request = OptimizeRequest.model_validate(case["input"])
    directives = [DirectiveInterpretation.model_validate(x) for x in case["expected_output"]["directive_interpretation"]]
    validate_interpretations(request, directives)

    plan, total_grid, total_cost, peak_grid, effects = optimize_schedule(request, directives)
    validate_plan(request, directives, plan, total_grid, total_cost, peak_grid, effects)

    expected = case["expected_output"]
    assert abs(total_cost - expected["total_cost_bdt"]) <= 0.01
    assert abs(total_grid - expected["total_grid_kwh"]) <= 0.01
