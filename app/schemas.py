"""Pydantic request/response models. Validation ranges come from app.features."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from .config import MAX_WINDOW_ROWS
from .features import FEATURES

# One sensor reading; fields/limits generated from the feature table so the API,
# the UI and the model can never drift apart.
Reading = create_model(
    "Reading",
    __config__=ConfigDict(extra="forbid"),
    **{
        f.key: (
            float,
            Field(..., ge=f.min, le=f.max, allow_inf_nan=False,
                  description=f"{f.label} ({f.unit}); allowed {f.min} to {f.max}",
                  examples=[f.default]),
        )
        for f in FEATURES
    },
)


class PredictRequest(BaseModel):
    """Provide exactly one of `reading` or `window`."""
    model_config = ConfigDict(extra="forbid")

    reading: Optional[Reading] = Field(  # type: ignore[valid-type]
        None, description="A single sensor reading. It is repeated across the model's "
                          "time window (steady-state approximation).")
    window: Optional[list[Reading]] = Field(  # type: ignore[valid-type]
        None, max_length=MAX_WINDOW_ROWS,
        description="Chronological hourly readings, oldest first. The most recent "
                    "`window` rows (see /api/model/info) are used.")
    label: Optional[str] = Field(None, max_length=120, description="Optional name, e.g. 'Field A - north plot'")

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.reading is None) == (self.window is None):
            raise ValueError("Provide exactly one of 'reading' or 'window'.")
        return self


class FeatureEffect(BaseModel):
    feature: str
    label: str
    effect: float = Field(..., description="Prediction minus prediction with this feature set to its "
                                           "training average (same unit as the prediction).")


class PredictResponse(BaseModel):
    id: int
    prediction: float
    unit: str
    input_mode: Literal["single_reading", "time_series"]
    rows_used: int
    window: int
    attention: list[float] = Field(..., description="Temporal attention weight per hour of the window "
                                                    "(oldest first, sums to 1).")
    feature_effects: list[FeatureEffect]
    warnings: list[str]
    model_version: str
    latency_ms: float
    created_at: datetime


class HistoryItem(BaseModel):
    id: int
    created_at: datetime
    label: Optional[str]
    input_mode: str
    rows_used: int
    prediction: float
    unit: str
    inputs: dict
    warnings: list[str]
    model_version: str


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


class HistoryStats(BaseModel):
    count: int
    mean: Optional[float]
    min: Optional[float]
    max: Optional[float]
    unit: Optional[str]
    series: list[dict]   # [{id, created_at, prediction}] oldest -> newest, last 50
