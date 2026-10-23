"""Tool: predict_heart_failure_risk — wraps backend/risk_model.predict_risk.

The input contract is the SAME pydantic model the Flask /predict route uses
(backend/contracts.RiskRequest) — one source of truth for the 17 health features
and their allowed values. Needs xgboost/sklearn + the pickled artifacts;
otherwise -> dependency error.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..errors import WatError
from ..paths import ensure_backend_on_path
from ..registry import Tool, register

# Reuse the canonical request contract from the backend (lower layer -> no cycle).
ensure_backend_on_path()
from contracts import RiskRequest  # noqa: E402  (path set just above)


class RiskOutput(BaseModel):
    HeartFailureRisk: str
    disclaimer: Optional[str] = None          # clinical-safety gate (set by backend)
    notMedicalAdvice: bool = True


@register
class PredictHeartFailureRisk(Tool):
    name = "predict_heart_failure_risk"
    Input = RiskRequest
    Output = RiskOutput
    kind = "service"          # warm XGBoost model + encoders
    retryable = ("transient",)

    def run(self, inp: RiskRequest) -> RiskOutput:
        ensure_backend_on_path()
        try:
            from risk_model import predict_risk
        except ImportError as exc:
            raise WatError("risk_model unavailable (xgboost/sklearn or artifacts?)",
                           category="dependency", cause=exc)
        result, _status = predict_risk(inp.model_dump())
        if "HeartFailureRisk" not in result:
            raise WatError(result.get("error", "risk prediction failed"),
                           category="parsing")
        return RiskOutput(HeartFailureRisk=result["HeartFailureRisk"],
                          disclaimer=result.get("disclaimer"))
