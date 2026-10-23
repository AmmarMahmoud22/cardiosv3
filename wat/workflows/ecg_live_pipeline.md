# Workflow: `ecg_live_pipeline`

Human companion doc for [`ecg_live_pipeline.yaml`](ecg_live_pipeline.yaml). The
YAML is the source of truth; this file explains intent.

## Goal
Take one ECG batch from end to end: **acquire → classify → persist**.

## Steps
| id | tool | purpose |
|----|------|---------|
| `read` | `read_ecg_device` | Get a sample batch. `source: replay` reads a recorded CSV (no hardware); switch to `source: serial` with a `port` for the ESP32. |
| `classify` | `classify_ecg` | Run the CNN-LSTM model (warm service). `on_error: continue` so a missing TensorFlow/model artifact is recorded as a `dependency` error instead of aborting the run. |
| `persist` | `persist_result` | Append the result to `wat/memory/results.jsonl`. |

## Data flow
`read.samples` / `read.sampleRateHz` / `read.leadOff` feed `classify`; the whole
`classify` output feeds `persist` via `${classify}`.

## Run
```
python -m wat run wat/workflows/ecg_live_pipeline.yaml
```

## Expected outcomes
- **With TensorFlow + the `.keras` model present:** all three steps succeed;
  status `completed`.
- **Without them (e.g. this worktree):** `read` and `persist` succeed, `classify`
  records a `dependency` error; status `completed_with_errors`. A checkpoint is
  written to `wat/state/runs/` and a trace to `wat/telemetry/spans/`.
