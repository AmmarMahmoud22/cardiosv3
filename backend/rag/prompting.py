"""The strict grounding prompt.

Two disjoint, explicitly labelled blocks. PATIENT_CONTEXT never carries an
evidence identifier, so there is no token the model could emit that would
resolve to it — the separation is structural, not merely instructional.
"""
from __future__ import annotations

import json
from typing import Optional

from rag.answer_contracts import EvidenceSet, PatientContext

SYSTEM_PROMPT = """\
You are a clinical evidence assistant. You answer ONLY from the guideline \
passages supplied to you in the GUIDELINE_EVIDENCE block.

Absolute rules:
1. Use ONLY the text inside GUIDELINE_EVIDENCE. You have no other medical \
knowledge available for this task. Do not add facts, drug names, doses, \
thresholds, or caveats that do not appear there.
2. Every recommendation MUST cite at least one evidence id (E1, E2, ...) that \
appears in GUIDELINE_EVIDENCE.
3. Every recommendation MUST include an excerpt copied VERBATIM from the \
evidence item it cites. Do not paraphrase inside the excerpt.
4. The PATIENT_CONTEXT block, if present, is context for interpreting the \
question ONLY. It is not evidence. Never cite it. Never base a recommendation \
on it.
5. If GUIDELINE_EVIDENCE does not contain enough information to answer, you \
MUST refuse. Refusing is the correct behaviour, not a failure.
6. You are a decision-support tool, not a diagnosing clinician. Do not give \
individualised treatment instructions for a specific patient.

Reply with a single JSON object and nothing else:

{"mode": "answer",
 "recommendations": [
   {"text": "<recommendation in your own words, drawn only from the evidence>",
    "excerpt": "<verbatim span copied from the cited evidence item>",
    "evidence_ids": ["E1"]}
 ]}

or, when the evidence is insufficient or the question is out of scope:

{"mode": "refusal",
 "reason": "insufficient_evidence" | "out_of_scope",
 "message": "<one sentence explaining what the retrieved guideline text does not cover>"}
"""


def build_user_prompt(question: str, evidence: EvidenceSet,
                      patient_context: Optional[PatientContext] = None) -> str:
    """Assemble the user turn with the two blocks kept strictly apart."""
    parts = []

    if patient_context is not None:
        parts.append(
            "### PATIENT_CONTEXT  (context only - NOT evidence - NEVER cite this block)\n"
            f"{patient_context.render()}\n"
            "Use this only to interpret the question. It must not support any recommendation."
        )

    parts.append(
        "### GUIDELINE_EVIDENCE  (the ONLY permitted source for recommendations and citations)\n"
        + (evidence.render() if evidence.items
           else "(no guideline passages were retrieved)")
    )

    parts.append(
        f"### QUESTION\n{question.strip()}\n\n"
        f"Valid evidence ids for this question: {', '.join(evidence.ids) or '(none)'}. "
        "Citing any other id is invalid and your answer will be rejected."
    )

    return "\n\n".join(parts)


def build_messages(question: str, evidence: EvidenceSet,
                   patient_context: Optional[PatientContext] = None) -> dict:
    return {
        "system": SYSTEM_PROMPT,
        "user": build_user_prompt(question, evidence, patient_context),
    }


def parse_model_json(text: str) -> dict:
    """Extract the JSON object from a model reply.

    Tolerates a code fence or surrounding prose, because a malformed reply must
    become a clean, detectable failure rather than a silent partial answer.
    """
    if not text or not text.strip():
        raise ValueError("empty model response")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model response")
    payload = json.loads(cleaned[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model response was not a JSON object")
    if payload.get("mode") not in {"answer", "refusal"}:
        raise ValueError(f"unexpected mode: {payload.get('mode')!r}")
    return payload
