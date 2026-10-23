"""Clinical-safety gate — single source of truth for the medical disclaimer.

Cardios is a cardiac-adjacent decision-support / educational tool, NOT a
diagnostic device. Every prediction the system emits (heart-failure risk and ECG
classification) is passed through here so neither the web API nor the WAT
pipeline can surface a result without the disclaimer attached.
"""
from __future__ import annotations

DISCLAIMER_VERSION = "1.0"

MEDICAL_DISCLAIMER = (
    "This result is an automated, educational estimate produced by a "
    "machine-learning model — it is NOT a medical diagnosis and can be wrong. "
    "Do not use it to start, stop, or change any treatment. If you have chest "
    "pain, shortness of breath, fainting, or other emergency symptoms, seek "
    "immediate medical care. Always consult a qualified healthcare professional "
    "about your heart health."
)


def attach_disclaimer(payload: dict) -> dict:
    """Return a copy of ``payload`` with the medical disclaimer attached."""
    enriched = dict(payload)
    enriched["disclaimer"] = MEDICAL_DISCLAIMER
    enriched["disclaimerVersion"] = DISCLAIMER_VERSION
    enriched["notMedicalAdvice"] = True
    return enriched

# --- Guideline-evidence variant (RAG module) -------------------------------
# The RAG layer makes a different kind of statement from the ML models: it
# reports what an official guideline says, with a traceable citation. The risk
# it carries is different too — retrieval can miss relevant text, and a
# guideline is written for populations, not for one patient. This variant says
# that plainly instead of reusing the model-prediction wording.
RAG_EVIDENCE_DISCLAIMER = (
    "This response summarises retrieved text from an official clinical guideline "
    "and is provided for decision support and education only. It is NOT a "
    "diagnosis and NOT individualised medical advice. Retrieval may miss relevant "
    "guidance, and guidelines describe populations, not individual patients. "
    "Verify every recommendation against the cited source and the full guideline, "
    "and consult a qualified clinician before acting. If you have chest pain, "
    "shortness of breath, fainting, or other emergency symptoms, seek immediate "
    "medical care."
)


def attach_evidence_disclaimer(payload: dict) -> dict:
    """Return a copy of ``payload`` with the guideline-evidence disclaimer attached."""
    enriched = dict(payload)
    enriched["disclaimer"] = RAG_EVIDENCE_DISCLAIMER
    enriched["disclaimerVersion"] = DISCLAIMER_VERSION
    enriched["notMedicalAdvice"] = True
    return enriched
