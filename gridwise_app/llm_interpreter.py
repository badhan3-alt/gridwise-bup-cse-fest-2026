from __future__ import annotations

import json
import os
from typing import Any

from .guardrails import InterpretationError, validate_interpretations
from .models import LLMInterpretationBatch, OptimizeRequest


SYSTEM_PROMPT = """You are the language-understanding component of GridWise, a smart-campus energy scheduler.
Interpret EACH operator note into exactly one supported directive. Return one entry per note, in note_index order.

Supported directive types and exact structured_adjustment shapes:
1. solar_reduction -> {"hours":[...], "factor": number}
   factor is the usable solar fraction REMAINING. Example: an 80% reduction means factor=0.2.
2. minimum_battery_reserve -> {"hours":[...], "minimum_energy_kwh": number}
3. no_charge_window -> {"hours":[...]}
4. no_discharge_window -> {"hours":[...]}
5. max_grid_window -> {"hours":[...], "max_grid_kwh": number}
6. no_op -> structured_adjustment must be null and applies must be false.

Rules:
- Every non-no_op directive has applies=true.
- Time windows are whole-hour, start-inclusive and end-exclusive. 1 PM to 3 PM => [13,14].
- Hours must be unique integers 0..23 in ascending order.
- Resolve noon=12 and midnight=0 when context makes it unambiguous.
- If a reserve is expressed as a percentage of battery capacity, calculate the absolute kWh using the supplied battery capacity.
- Do not invent demand, solar, tariff, battery limits, time windows, percentages, or unsupported directive types.
- Notes unrelated to the current 24-hour energy schedule are no_op.
- Hidden notes may paraphrase the same rule. Interpret meaning, not keywords.
- Keep explanations short and factual.
"""


def _scenario_for_llm(request: OptimizeRequest) -> dict[str, Any]:
    return {
        "scenario_id": request.scenario_id,
        "operator_notes": request.operator_notes,
        "hours": [h.model_dump() for h in sorted(request.hours, key=lambda x: x.hour)],
        "battery": request.battery.model_dump(),
    }


def interpret_operator_notes(request: OptimizeRequest) -> list:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    if not api_key:
        raise InterpretationError("OPENAI_API_KEY is not configured")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=8.0, max_retries=0)
    user_prompt = (
        "Interpret the operator_notes in this scenario. The hourly/battery data is context only; "
        "do not modify it.\n\n" + json.dumps(_scenario_for_llm(request), separators=(",", ":"))
    )

    last_error: Exception | None = None
    for _ in range(2):
        try:
            response = client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=LLMInterpretationBatch,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise InterpretationError("LLM returned no parsed structured output")
            return validate_interpretations(request, parsed.directive_interpretation)
        except Exception as exc:  # controlled retry for transient/model-format errors
            last_error = exc

    raise InterpretationError(f"operator-note interpretation failed: {type(last_error).__name__}")
