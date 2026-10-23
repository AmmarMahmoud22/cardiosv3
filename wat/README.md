# WAT — Workflows · Agents · Tools (cardios)

A small, transparent orchestration layer that turns the existing cardios backend
into contract-validated **tools** driven by machine-readable **workflows**, run by
a minimal **engine**. It was built deliberately *right-sized* — see the
architecture critique in the project plan for what was intentionally left out
(4-type memory, external workflow engine, vector retrieval) and why.

## Layout
```
wat/
├── engine.py            # DAG runner: resolve refs, validate I/O, retry, checkpoint, trace
├── registry.py          # Tool contract + self-registering tool registry
├── errors.py            # error taxonomy (transient/auth/schema/rate_limit/dependency/parsing)
├── paths.py             # repo locations + backend sys.path injection
├── tools/               # one module per tool — each WRAPS existing backend logic
├── workflows/           # YAML DAGs (source of truth) + paired .md docs
├── schemas/             # JSON Schema export of every tool contract (wat/schemas/json/)
├── state/runs/          # one checkpoint JSON per run
├── telemetry/spans/     # one JSONL trace per run (a span per step attempt)
└── memory/results.jsonl # long-term results index (stub; semantic/episodic deferred)
```

## Tools (all wrap, never reimplement)
| tool | wraps |
|------|-------|
| `read_ecg_device` | ESP32 serial reader (consolidated) + hardware-free replay |
| `normalize_ecg_csv` | `backend/csv_converter.convert_csv_to_format` |
| `classify_ecg` | `backend/ecg_service.build_prediction_response` (warm CNN-LSTM) |
| `predict_heart_failure_risk` | `backend/risk_model.predict_risk` (warm XGBoost) |
| `get_health_advice` | `backend/chatbot_logic.generate_chat_response` |
| `persist_result` | appends to `wat/memory/results.jsonl` |

`classify_ecg` and `predict_heart_failure_risk` are **service** tools (heavy
models, kept warm). If TensorFlow/XGBoost or the model artifacts are absent they
report a clean `dependency` error rather than crashing the run.

## Run
> **Interpreter:** the ML tools (`classify_ecg`, `predict_heart_failure_risk`) need
> TensorFlow/XGBoost, which only run on the project's **Python 3.11 `.venv`** (not
> system Python 3.14). Install the framework deps once:
> `.venv\Scripts\python -m pip install -r wat/requirements.txt`, then use that
> interpreter. The pure tools and tests also run on any Python with pydantic+pyyaml.

```bash
python -m wat tools                                   # list tools + contracts
python -m wat run wat/workflows/ecg_csv_pipeline.yaml  # green, no ML/hardware needed
python -m wat run wat/workflows/ecg_live_pipeline.yaml # PoC: read -> classify -> persist
python -m wat schemas                                 # export JSON Schemas
python tests/test_wat.py                              # tests (also pytest-compatible)
```

Verified end-to-end on the `.venv`: `ecg_live_pipeline` → `status: completed`,
CNN-LSTM prediction with confidence; `predict_heart_failure_risk` → XGBoost
result; 7/7 tests pass.

## Workflow format
```yaml
name: my_pipeline
steps:
  - id: step_a
    tool: some_tool
    input: { key: value }
    retry: { max_attempts: 2, on: [transient] }   # retry only these categories
  - id: step_b
    tool: other_tool
    input: { from_a: "${step_a.some_field}" }       # reference a prior output
    on_error: continue                               # record error, keep going
```
Each step's input is validated against the tool's pydantic `Input`; its `Output`
is validated by construction. `${step}` / `${step.field}` inject prior typed
outputs. Failures are classified; the engine retries only categories the step
opted into, then aborts (default) or continues.

## Deliberately out of scope (see plan critique)
- semantic/episodic memory + vector store,
- external engine (LangGraph/Prefect),
- branching DAG (linear + references covers every current pipeline),
- clinical-safety gate — **note:** model outputs are not a diagnosis; a
  human-in-the-loop disclaimer belongs here before any real-world use.
