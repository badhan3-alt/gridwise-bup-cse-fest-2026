from __future__ import annotations

import math

from .models import (
    DirectiveInterpretation,
    MaxGridWindowAdjustment,
    MinimumBatteryReserveAdjustment,
    OptimizeRequest,
    SolarReductionAdjustment,
    WindowAdjustment,
)


class InterpretationError(ValueError):
    pass


def _validate_hours(hours: list[int]) -> None:
    if not hours:
        raise InterpretationError("directive hours must not be empty")
    if hours != sorted(set(hours)):
        raise InterpretationError("directive hours must be unique and in ascending order")
    if any((not isinstance(h, int)) or h < 0 or h > 23 for h in hours):
        raise InterpretationError("directive hours must be integers from 0 through 23")


def validate_interpretations(
    request: OptimizeRequest,
    items: list[DirectiveInterpretation],
) -> list[DirectiveInterpretation]:
    if len(items) != len(request.operator_notes):
        raise InterpretationError("LLM must return exactly one interpretation per operator note")

    indices = [item.note_index for item in items]
    expected = list(range(len(request.operator_notes)))
    if indices != expected:
        raise InterpretationError("directive_interpretation must be in note_index order with no gaps or duplicates")

    for item in items:
        dtype = item.directive_type
        adjustment = item.structured_adjustment

        if dtype == "no_op":
            if item.applies is not False or adjustment is not None:
                raise InterpretationError("no_op requires applies=false and structured_adjustment=null")
            continue

        if item.applies is not True or adjustment is None:
            raise InterpretationError("non-no_op directives require applies=true and a structured adjustment")

        if dtype == "solar_reduction":
            if type(adjustment) is not SolarReductionAdjustment:
                raise InterpretationError("solar_reduction has an invalid structured_adjustment shape")
            _validate_hours(adjustment.hours)
            if not math.isfinite(adjustment.factor) or not (0 <= adjustment.factor <= 1):
                raise InterpretationError("solar_reduction factor must be between 0 and 1")

        elif dtype == "minimum_battery_reserve":
            if type(adjustment) is not MinimumBatteryReserveAdjustment:
                raise InterpretationError("minimum_battery_reserve has an invalid structured_adjustment shape")
            _validate_hours(adjustment.hours)
            value = adjustment.minimum_energy_kwh
            if not math.isfinite(value) or value < 0 or value > request.battery.capacity_kwh:
                raise InterpretationError("minimum battery reserve must be finite, non-negative, and no greater than capacity")

        elif dtype in {"no_charge_window", "no_discharge_window"}:
            if type(adjustment) is not WindowAdjustment:
                raise InterpretationError(f"{dtype} has an invalid structured_adjustment shape")
            _validate_hours(adjustment.hours)

        elif dtype == "max_grid_window":
            if type(adjustment) is not MaxGridWindowAdjustment:
                raise InterpretationError("max_grid_window has an invalid structured_adjustment shape")
            _validate_hours(adjustment.hours)
            if not math.isfinite(adjustment.max_grid_kwh) or adjustment.max_grid_kwh < 0:
                raise InterpretationError("max_grid_kwh must be finite and non-negative")

        else:  # Literal typing should make this unreachable.
            raise InterpretationError(f"unsupported directive type: {dtype}")

    return items
