# Workflow: `ecg_csv_pipeline`

Human companion doc for [`ecg_csv_pipeline.yaml`](ecg_csv_pipeline.yaml).

## Goal
Demonstrate a fully green, reused-logic pipeline that needs no ML runtime and no
hardware: **normalize a CSV → read it back as samples**.

## Steps
| id | tool | purpose |
|----|------|---------|
| `normalize` | `normalize_ecg_csv` | Wraps `backend/csv_converter.convert_csv_to_format` to coerce any CSV into the single-row model format. |
| `read` | `read_ecg_device` | Replay-reads the normalized file into a `samples` batch. `${normalize.normalized_path}` wires the steps together. |

## Run
```
python -m wat run wat/workflows/ecg_csv_pipeline.yaml
```

## Expected outcome
Status `completed`; `read.sampleCount > 0`; a checkpoint in `wat/state/runs/` and
a trace in `wat/telemetry/spans/`.
