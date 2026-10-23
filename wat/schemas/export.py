"""Export each tool contract as JSON Schema under ``wat/schemas/json/``.

This makes the contracts the system prompt demands inspectable and diffable by
non-Python consumers (frontends, other services, docs).
"""
from __future__ import annotations

import json

from .. import registry
from ..paths import WAT_DIR


def export_all() -> list:
    out_dir = WAT_DIR / "schemas" / "json"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, tool in registry.all_tools().items():
        for kind, model in (("input", tool.Input), ("output", tool.Output)):
            path = out_dir / f"{name}.{kind}.json"
            path.write_text(json.dumps(model.model_json_schema(), indent=2,
                                       ensure_ascii=False), encoding="utf-8")
            written.append(path)
    return written
