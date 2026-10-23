# Workflow: `risk_assessment`

Human companion doc for [`risk_assessment.yaml`](risk_assessment.yaml).

## Goal
Turn a health questionnaire into a persisted heart-failure risk result —
**parametrized**, so it runs on real input rather than hardcoded values.

## Steps
| id | tool | purpose |
|----|------|---------|
| `assess` | `predict_heart_failure_risk` | XGBoost risk (warm service). Inputs come from `${params.*}` (17 fields). `on_error: continue` records a clean `dependency` error if XGBoost/artifacts are absent. |
| `persist` | `persist_result` | Append the result (with its disclaimer) to `wat/memory/results.jsonl`. |

## Run (needs the project .venv for XGBoost)
```bash
python -m wat run wat/workflows/risk_assessment.yaml --input-json '{
  "BMI":28.5,"Smoking":"Yes","AlcoholDrinking":"No","Stroke":"No",
  "PhysicalHealth":5,"MentalHealth":3,"DiffWalking":"No","Sex":"Male",
  "AgeCategory":"60-64","Race":"White","Diabetic":"Yes","PhysicalActivity":"Yes",
  "GenHealth":"Fair","SleepTime":6,"Asthma":"No","KidneyDisease":"No","SkinCancer":"No"
}'
```

## Integration note
Because input is `${params.*}`, a Flask route can drive this same workflow with
`run_workflow("wat/workflows/risk_assessment.yaml", params=request.get_json())` —
the WAT engine then validates against `RiskRequest`, runs the model, attaches the
safety disclaimer, traces, and persists.
