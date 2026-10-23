"""Evidence-sufficiency: is there enough retrieved evidence to answer safely?

Three concerns kept apart on purpose:

  ordering       done by the retriever (cosine similarity today)
  measuring      a dedicated signal computed from the retrieval result
  deciding       a threshold on that signal, which must be CALIBRATED on
                 labelled data before it means anything

A raw similarity score is not a calibrated confidence, and it is not comparable
across embedding models. Until a calibration record exists for the active
corpus + model, every verdict is stamped ``calibrated=False`` and the threshold
is an explicitly provisional default. That is surfaced in the API response and
in ``/rag/health`` rather than quietly presented as a safety guarantee.

Signals:
  ``top1``    similarity of the best-matching chunk
  ``margin``  top1 minus the mean of the remaining top-k; separates "one clearly
              relevant passage" from "k uniformly mediocre ones", which a bare
              top1 cannot distinguish
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from rag.answer_contracts import EvidenceSet, SufficiencyVerdict

logger = logging.getLogger(__name__)

DEFAULT_SIGNAL = "top1"
# Provisional only. Phase 5/6 replaces this with a value swept against GOLD-v1.
PROVISIONAL_THRESHOLD = 0.30

UNCALIBRATED_NOTE = (
    "PROVISIONAL threshold — no calibration record exists for this corpus and "
    "embedding model yet. This value has not been swept against a labelled gold "
    "set, so it is an engineering default, not a validated safety boundary."
)


def calibration_path() -> Path:
    return Path(os.getenv(
        "RAG_CALIBRATION_FILE",
        str(Path(__file__).resolve().parent / "corpus" / "calibration.json")))


def load_calibration(model_id: str = "", corpus_version: str = "") -> Optional[dict]:
    """Load a calibration record, if one matches the active model + corpus.

    A record calibrated against a different embedding model or corpus version is
    not applicable, and is ignored rather than silently reused.
    """
    path = calibration_path()
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        logger.warning("Calibration file at %s is unreadable; ignoring it", path)
        return None
    if model_id and record.get("modelId") not in (None, "", model_id):
        logger.warning("Calibration was fitted for model %r, active model is %r; ignoring",
                       record.get("modelId"), model_id)
        return None
    if corpus_version and record.get("corpusVersion") not in (None, "", corpus_version):
        logger.warning("Calibration was fitted for corpus %r, active corpus is %r; ignoring",
                       record.get("corpusVersion"), corpus_version)
        return None
    return record


def compute_signal(evidence: EvidenceSet, signal: str = DEFAULT_SIGNAL) -> float:
    scores = sorted((i.score for i in evidence.items), reverse=True)
    if not scores:
        return 0.0
    if signal == "margin":
        rest = scores[1:]
        return round(scores[0] - (sum(rest) / len(rest) if rest else 0.0), 6)
    return round(scores[0], 6)


def assess(evidence: EvidenceSet, corpus_version: str = "") -> SufficiencyVerdict:
    """Judge whether the retrieved evidence is sufficient to attempt an answer."""
    record = load_calibration(evidence.model_id, corpus_version)
    if record:
        signal = record.get("signal", DEFAULT_SIGNAL)
        threshold = float(record["threshold"])
        calibrated, calibration_id, note = True, record.get("calibrationId"), record.get("note", "")
    else:
        signal = os.getenv("RAG_SUFFICIENCY_SIGNAL", DEFAULT_SIGNAL)
        threshold = float(os.getenv("RAG_SUFFICIENCY_THRESHOLD", PROVISIONAL_THRESHOLD))
        calibrated, calibration_id, note = False, None, UNCALIBRATED_NOTE

    value = compute_signal(evidence, signal)
    return SufficiencyVerdict(
        signal=signal, value=value, threshold=threshold,
        sufficient=bool(evidence.items) and value >= threshold,
        calibrated=calibrated, calibration_id=calibration_id, note=note,
    )
