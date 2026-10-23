"""Tool: normalize_ecg_csv — wraps backend/csv_converter.convert_csv_to_format.

Imports the existing robust multi-strategy CSV parser; does not reimplement it.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from ..errors import WatError
from ..paths import ensure_backend_on_path, resolve_repo_path
from ..registry import Tool, register


class NormalizeInput(BaseModel):
    file_path: str
    output_path: Optional[str] = None


class NormalizeOutput(BaseModel):
    normalized_path: str
    status: Literal["success"]


@register
class NormalizeEcgCsv(Tool):
    name = "normalize_ecg_csv"
    Input = NormalizeInput
    Output = NormalizeOutput
    kind = "cli"
    retryable = ("transient",)

    def run(self, inp: NormalizeInput) -> NormalizeOutput:
        ensure_backend_on_path()
        try:
            from csv_converter import convert_csv_to_format
        except ImportError as exc:
            raise WatError("csv_converter unavailable (pandas/numpy?)",
                           category="dependency", cause=exc)
        src = resolve_repo_path(inp.file_path)
        if not src.exists():
            raise WatError(f"input file not found: {src}", category="dependency")
        out = convert_csv_to_format(str(src), inp.output_path)
        if not out:
            raise WatError("csv conversion failed", category="parsing")
        return NormalizeOutput(normalized_path=str(out), status="success")
