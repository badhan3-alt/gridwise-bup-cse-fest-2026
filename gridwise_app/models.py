from __future__ import annotations

import math
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]
BatteryAction = Literal["charge", "discharge", "idle"]


class HourData(BaseModel):
    hour: int
    demand_kwh: float
    solar_kwh: float
    tariff_bdt_per_kwh: float

    @field_validator("demand_kwh", "solar_kwh", "tariff_bdt_per_kwh")
    @classmethod
    def finite_nonnegative(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("must be a finite non-negative number")
        return value

    @field_validator("hour")
    @classmethod
    def valid_hour(cls, value: int) -> int:
        if value < 0 or value > 23:
            raise ValueError("hour must be between 0 and 23")
        return value


class BatteryData(BaseModel):
    capacity_kwh: float
    initial_energy_kwh: float
    minimum_energy_kwh: float
    max_charge_kwh_per_hour: float
    max_discharge_kwh_per_hour: float

    @field_validator("capacity_kwh", "initial_energy_kwh", "minimum_energy_kwh", "max_charge_kwh_per_hour", "max_discharge_kwh_per_hour")
    @classmethod
    def finite_nonnegative(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("must be a finite non-negative number")
        return value

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.capacity_kwh <= 0:
            raise ValueError("capacity_kwh must be greater than 0")
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError("minimum_energy_kwh cannot exceed capacity_kwh")
        if not (self.minimum_energy_kwh <= self.initial_energy_kwh <= self.capacity_kwh):
            raise ValueError("initial_energy_kwh must be between minimum_energy_kwh and capacity_kwh")
        return self


class OptimizeRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    operator_notes: list[str] = Field(min_length=1, max_length=3)
    hours: list[HourData] = Field(min_length=24, max_length=24)
    battery: BatteryData

    @field_validator("scenario_id")
    @classmethod
    def scenario_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scenario_id must not be blank")
        return value

    @field_validator("operator_notes")
    @classmethod
    def notes_not_blank(cls, value: list[str]) -> list[str]:
        if any(not note.strip() for note in value):
            raise ValueError("operator_notes must contain 1-3 non-empty strings")
        return value

    @model_validator(mode="after")
    def validate_hours(self):
        actual = sorted(item.hour for item in self.hours)
        if actual != list(range(24)):
            raise ValueError("hours must contain each unique hour 0 through 23 exactly once")
        return self


class SolarReductionAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: list[int]
    factor: float


class MinimumBatteryReserveAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: list[int]
    minimum_energy_kwh: float


class WindowAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: list[int]


class MaxGridWindowAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: list[int]
    max_grid_kwh: float


Adjustment = Union[
    SolarReductionAdjustment,
    MinimumBatteryReserveAdjustment,
    WindowAdjustment,
    MaxGridWindowAdjustment,
]


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: Adjustment | None
    explanation: str = Field(min_length=1)


class LLMInterpretationBatch(BaseModel):
    directive_interpretation: list[DirectiveInterpretation]


class HourlyPlanEntry(BaseModel):
    hour: int
    grid_kwh: float
    solar_used_kwh: float
    battery_action: BatteryAction
    battery_kwh: float
    battery_energy_after_kwh: float


class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: list[DirectiveInterpretation]
    hourly_plan: list[HourlyPlanEntry]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
