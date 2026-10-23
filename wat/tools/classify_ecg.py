"""Tool: classify_ecg — wraps backend/ecg_service.build_prediction_response.

This is a "service" tool: the underlying module loads a Keras CNN-LSTM model
once at import and keeps it warm (the service-adapter pattern from the critique,
instead of spawning a fresh interpreter per call). If TensorFlow or the .keras
artifact is unavailable, the tool reports a clean ``dependency`` error rather
than crashing the run.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..errors import WatError
from ..paths import ensure_backend_on_path
from ..registry import Tool, register


class ClassifyInput(BaseModel):
    samples: list[float] = Field(min_length=1)
    sampleRateHz: int = Field(250, gt=0)
    deviceId: str = "wat-pipeline"
    leadOff: bool = False
    heartRateBpm: Optional[float] = None


class ClassifyOutput(BaseModel):
    prediction: str
    # null when the signal-quality gate refuses to classify a poor trace
    confidence: Optional[float] = None
    heartRateBpm: Optional[float] = None
    sampleRateHz: int
    leadOff: bool
    deviceId: str
    qualityOk: Optional[bool] = None           # signal-quality gate verdict
    signalQuality: Optional[dict] = None       # lead-off / flatline / clipping / noise indicators
    disclaimer: Optional[str] = None          # clinical-safety gate (set by backend)
    notMedicalAdvice: bool = True


@register
class ClassifyEcg(Tool):
    name = "classify_ecg"
    Input = ClassifyInput
    Output = ClassifyOutput
    kind = "service"          # warm CNN-LSTM model
    idempotent = True
    retryable = ("transient",)

    def run(self, inp: ClassifyInput) -> ClassifyOutput:
        ensure_backend_on_path()
        try:
            import ecg_service  # imports tensorflow + loads the model
        except ImportError as exc:
            raise WatError("tensorflow/ecg_service unavailable",
                           category="dependency", cause=exc)
        if getattr(ecg_service, "model", None) is None:
            raise WatError("ECG model not loaded (missing .keras artifact or TF runtime)",
                           category="dependency")
        try:
            resp = ecg_service.build_prediction_response(
                raw_data=inp.samples,
                sample_rate_hz=inp.sampleRateHz,
                device_id=inp.deviceId,
                lead_off=inp.leadOff,
                heart_rate_bpm=inp.heartRateBpm,
            )
        except Exception as exc:  # noqa: BLE001
            raise WatError(f"classification failed: {exc}", category="dependency", cause=exc)
        return ClassifyOutput(
            prediction=resp["prediction"],
            confidence=resp["confidence"],
            heartRateBpm=resp.get("heartRateBpm"),
            sampleRateHz=resp["sampleRateHz"],
            leadOff=resp["leadOff"],
            deviceId=resp["deviceId"],
            qualityOk=resp.get("qualityOk"),
            signalQuality=resp.get("signalQuality"),
            disclaimer=resp.get("disclaimer"),
        )
