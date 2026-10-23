"""The workflow engine — the missing piece the critique called out.

It gives the architecture diagram (Workflow Engine -> Task Graph -> Executor
Tools -> Verification) real run semantics:

1. Load a YAML workflow (the operational SOP, machine-readable).
2. For each step, resolve ``${step.field}`` references from prior outputs.
3. Validate the resolved input against the tool's Input contract (schema gate).
4. Run the tool; its Output is contract-validated by construction (verification).
5. On failure, classify the error and retry only if the step opted in for that
   category; otherwise abort or continue per ``on_error``.
6. Checkpoint state and emit a telemetry span after every attempt.

Workflows are executed top-to-bottom (a linear task graph); references express
the dependencies. That covers every cardios pipeline today; a topological DAG
is a later extension if branching is ever needed.
"""
from __future__ import annotations

import contextlib
import re
import sys
import time
import uuid
from pathlib import Path

import yaml

from . import registry
from .errors import WatError, classify_exception
from .paths import REPO_ROOT
from .state.store import save_checkpoint
from .telemetry.tracer import Tracer

_REF = re.compile(r"^\$\{([A-Za-z0-9_]+)(?:\.([A-Za-z0-9_]+))?\}$")


def _resolve(value, context: dict):
    """Replace full-match ``${step}`` / ``${step.field}`` references with the
    real (typed) value from a prior step's output."""
    if isinstance(value, str):
        match = _REF.match(value)
        if not match:
            return value
        step, field = match.group(1), match.group(2)
        if step not in context:
            raise WatError(f"reference to unknown step {step!r}", category="schema")
        data = context[step]
        if field is None:
            return data
        if not isinstance(data, dict) or field not in data:
            raise WatError(f"step {step!r} has no field {field!r}", category="schema")
        return data[field]
    if isinstance(value, dict):
        return {k: _resolve(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, context) for v in value]
    return value


class WorkflowResult:
    def __init__(self, run_id, status, context, errors):
        self.run_id = run_id
        self.status = status          # completed | completed_with_errors | failed
        self.context = context        # {step_id: output_dict}
        self.errors = errors

    def as_dict(self) -> dict:
        return {
            "runId": self.run_id,
            "status": self.status,
            "errors": self.errors,
            "context": self.context,
        }


def load_workflow(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / path
    if not p.exists():
        raise WatError(f"workflow not found: {p}", category="dependency")
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _harden_stdio() -> None:
    """Best-effort UTF-8 stdio so a wrapped tool that prints non-ASCII (e.g. the
    Arabic log lines in csv_converter) can't crash the run on a cp1252 console."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:  # noqa: BLE001 - older/odd streams without reconfigure
            pass


def run_workflow(path: str | Path, *, run_id: str | None = None,
                 params: dict | None = None) -> WorkflowResult:
    _harden_stdio()
    wf = load_workflow(path)
    name = wf.get("name", "workflow")
    run_id = run_id or f"{name}-{uuid.uuid4().hex[:8]}"
    tracer = Tracer(run_id)
    # Runtime inputs are exposed to steps as ${params.<field>}, so one workflow
    # can be driven by real request data (e.g. a Flask route passing form input).
    context: dict[str, dict] = {"params": dict(params)} if params else {}
    errors: list[dict] = []
    steps = wf.get("steps", []) or []
    overall = "completed"

    tracer.emit({"event": "workflow_start", "workflow": name, "stepCount": len(steps)})

    for step in steps:
        sid = step["id"]
        tool_name = step["tool"]
        on_error = step.get("on_error", "abort")
        retry_cfg = step.get("retry", {}) or {}
        max_attempts = max(1, int(retry_cfg.get("max_attempts", 1)))
        retry_on = set(retry_cfg.get("on", []))

        attempt = 0
        while True:
            attempt += 1
            started = time.time()
            try:
                tool = registry.get(tool_name)
                raw_input = _resolve(step.get("input", {}) or {}, context)
                inp = tool.Input(**raw_input)            # schema gate
                # Keep stdout pristine for the CLI's result JSON: any chatter a
                # wrapped legacy tool prints (Keras progress bar, csv_converter
                # logs) is redirected to stderr.
                with contextlib.redirect_stdout(sys.stderr):
                    out = tool.run(inp)                   # execute
                if isinstance(out, dict):
                    out = tool.Output(**out)
                result = out.model_dump()                # verified output
                context[sid] = result
                latency = round((time.time() - started) * 1000, 2)
                tracer.emit({"event": "step_ok", "step": sid, "tool": tool_name,
                             "attempt": attempt, "latencyMs": latency})
                save_checkpoint(run_id, {"workflow": name, "status": "running",
                                         "context": context, "errors": errors})
                break
            except Exception as exc:  # noqa: BLE001 - classify, don't swallow blindly
                category = classify_exception(exc)
                latency = round((time.time() - started) * 1000, 2)
                tracer.emit({"event": "step_error", "step": sid, "tool": tool_name,
                             "attempt": attempt, "category": category,
                             "error": str(exc), "latencyMs": latency})
                if category in retry_on and attempt < max_attempts:
                    continue  # safe retry for an opted-in category
                errors.append({"step": sid, "category": category, "error": str(exc)})
                if on_error == "continue":
                    context[sid] = {"_error": str(exc), "_category": category}
                    overall = "completed_with_errors"
                    save_checkpoint(run_id, {"workflow": name, "status": overall,
                                             "context": context, "errors": errors})
                    break
                overall = "failed"
                save_checkpoint(run_id, {"workflow": name, "status": overall,
                                         "context": context, "errors": errors})
                tracer.emit({"event": "workflow_end", "status": overall})
                return WorkflowResult(run_id, overall, context, errors)

    tracer.emit({"event": "workflow_end", "status": overall})
    save_checkpoint(run_id, {"workflow": name, "status": overall,
                             "context": context, "errors": errors})
    return WorkflowResult(run_id, overall, context, errors)
