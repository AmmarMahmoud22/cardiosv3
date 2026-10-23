# Workflow: `health_qa`

Human companion doc for [`health_qa.yaml`](health_qa.yaml).

## Goal
Answer a heart-health question and persist it — a fully green, dependency-free
path (no ML runtime, no hardware) that demonstrates runtime params end to end.

## Steps
| id | tool | purpose |
|----|------|---------|
| `answer` | `get_health_advice` | Wraps `chatbot_logic.generate_chat_response`. Question from `${params.message}`. |
| `persist` | `persist_result` | Append the answer to `wat/memory/results.jsonl`. |

## Run
```bash
python -m wat run wat/workflows/health_qa.yaml --input-json '{"message":"How much exercise is good for my heart?"}'
```

## Expected outcome
Status `completed`; `answer.response` is the chatbot reply; a checkpoint in
`wat/state/runs/` and a trace in `wat/telemetry/spans/`.
