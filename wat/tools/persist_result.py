"""Tool: persist_result — append a result record to long-term memory.

The terminal step of a pipeline: writes the record to wat/memory/results.jsonl
and returns its id. Mirrors how the live app stores readings, but framework-side.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel

from ..memory.results_index import record_result
from ..registry import Tool, register


class PersistInput(BaseModel):
    record: dict
    label: str = "ecg_result"


class PersistOutput(BaseModel):
    stored: bool
    resultId: str


@register
class PersistResult(Tool):
    name = "persist_result"
    Input = PersistInput
    Output = PersistOutput
    kind = "cli"

    def run(self, inp: PersistInput) -> PersistOutput:
        result_id = uuid.uuid4().hex
        record_result({"id": result_id, "label": inp.label, "record": inp.record})
        return PersistOutput(stored=True, resultId=result_id)
