"""Request contracts (pydantic) — the single source of truth for API input
validation, shared by the Flask routes and the WAT tools.

These live in the backend (the lower layer) so both `app.py`/`ecg_service.py`
and `wat/` can import them without a circular dependency. Enforcing the allowed
enums/ranges at the boundary turns vague deep failures (e.g. a sklearn transform
blowing up on a bad category) into clear 400 responses.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

YesNo = Literal["Yes", "No"]


class RiskRequest(BaseModel):
    """Payload for POST /predict (heart-failure risk). Mirrors the categories the
    XGBoost preprocessing pipeline was trained on (see risk_model.valid_options)."""
    BMI: float = Field(ge=0, le=100)
    Smoking: YesNo
    AlcoholDrinking: YesNo
    Stroke: YesNo
    PhysicalHealth: float = Field(ge=0, le=30)
    MentalHealth: float = Field(ge=0, le=30)
    DiffWalking: YesNo
    Sex: Literal["Male", "Female"]
    AgeCategory: Literal[
        "18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
        "55-59", "60-64", "65-69", "70-74", "75-79", "80 or older",
    ]
    Race: Literal[
        "White", "Black", "Asian", "American Indian/Alaskan Native", "Other", "Hispanic",
    ]
    Diabetic: Literal[
        "Yes", "No", "No, borderline diabetes", "Yes (during pregnancy)",
    ]
    PhysicalActivity: YesNo
    GenHealth: Literal["Very good", "Fair", "Good", "Poor", "Excellent"]
    SleepTime: float = Field(ge=0, le=24)
    Asthma: YesNo
    KidneyDisease: YesNo
    SkinCancer: YesNo


class DeviceEcgRequest(BaseModel):
    """Payload for POST /device-ecg (raw ECG batch from the ESP32/USB bridge)."""
    samples: list[float] = Field(min_length=1)
    sampleRateHz: int = Field(default=250, gt=0)
    deviceId: str = "esp32-ad8232"
    leadOff: bool = False
    heartRateBpm: Optional[float] = None
    # Optional patient/owner the device is assigned to, for scoped retrieval.
    userId: Optional[str] = None


def format_validation_errors(exc) -> list[dict]:
    """Turn a pydantic ValidationError into a small, JSON-safe list for API
    responses (avoids leaking non-serializable error context)."""
    return [
        {
            "field": ".".join(str(p) for p in err.get("loc", ())),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
