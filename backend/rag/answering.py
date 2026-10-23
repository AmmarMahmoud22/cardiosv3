"""Orchestration: retrieval -> sufficiency -> generation -> citation validation.

Enforces the single-retrieval guarantee. Retrieval happens exactly once per
question. Generation either runs on that same in-memory evidence set, or loads a
previously persisted one by ``retrieval_id`` — it never searches again. The
``chunk_set_hash`` is recomputed when a set is reloaded and compared against the
stored value, so a corpus that changed underneath a pending retrieval produces a
detectable failure instead of an answer grounded in evidence nobody saw.

Outcome types are kept strictly distinct (see ``rag.answer_contracts``):
an answer, a clinical refusal, or a system failure.
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Union

from rag import guardrails
from rag.answer_contracts import (EvidenceItem, EvidenceSet, FailureKind, GroundedAnswer,
                                  PatientContext, Refusal, RefusalReason, SystemFailure)
from rag.config import CORPUS_VERSION
from rag.generation import GenerationUnavailable, get_generation_provider
from rag.prompting import parse_model_json
from rag.retrieve import chunk_set_hash
from rag.store import CorpusStore
from rag.sufficiency import assess

logger = logging.getLogger(__name__)

Outcome = Union[GroundedAnswer, Refusal, SystemFailure]


def _attach_disclaimer(outcome: Outcome) -> Outcome:
    """Route clinical outcomes through the existing safety gate.

    A ``SystemFailure`` deliberately carries no medical disclaimer: it makes no
    clinical statement, and dressing an outage in clinical language is exactly
    the conflation this module is built to avoid.
    """
    if not hasattr(outcome, "disclaimer"):
        return outcome
    try:
        from safety import DISCLAIMER_VERSION, RAG_EVIDENCE_DISCLAIMER
        outcome.disclaimer = RAG_EVIDENCE_DISCLAIMER
        outcome.disclaimer_version = DISCLAIMER_VERSION
    except Exception:  # noqa: BLE001 - safety module must never break the response
        logger.exception("Could not attach the medical disclaimer")
    return outcome


def load_evidence_set(store: CorpusStore, retrieval_id: str) -> EvidenceSet:
    """Rebuild the exact evidence set for a persisted retrieval.

    Raises ``LookupError`` if unknown, ``ValueError`` if the corpus changed
    since the retrieval was logged.
    """
    record = store.get_retrieval(retrieval_id)
    if record is None:
        raise LookupError(f"unknown retrieval id: {retrieval_id}")

    rows = store.chunks_by_ref(record["chunk_refs"])
    titles = {d["document_id"]: d["title"] for d in store.documents()}
    scores = record.get("scores") or []

    items, hashable = [], []
    for rank, ref in enumerate(record["chunk_refs"], start=1):
        row = rows.get((ref[0], int(ref[1])))
        if row is None:
            raise ValueError("a chunk from this retrieval no longer exists in the corpus")
        items.append(EvidenceItem(
            evidence_id=f"E{rank}", content=row["content"],
            document_id=row["document_id"],
            document_title=titles.get(row["document_id"], row["document_id"]),
            chunk_index=row["chunk_index"], section_title=row["section_title"],
            section_path=row["section_path"],
            section_provenance=row["section_provenance"],
            page_number=row["page_number"], page_end=row["page_end"],
            page_label=row["page_label"],
            score=float(scores[rank - 1]) if rank - 1 < len(scores) else 0.0))
        hashable.append({"documentId": row["document_id"],
                         "chunkIndex": row["chunk_index"], "content": row["content"]})

    recomputed = chunk_set_hash(hashable)
    if recomputed != record["chunk_set_hash"]:
        raise ValueError("the corpus changed since this retrieval; evidence set is stale")

    return EvidenceSet(
        retrieval_id=retrieval_id, chunk_set_hash=record["chunk_set_hash"],
        question=record["question"], model_id=(record.get("params") or {}).get("modelId", ""),
        items=items)


def answer_from_evidence(evidence: EvidenceSet, *,
                         patient_context: Optional[PatientContext] = None,
                         provider=None, corpus_version: str = CORPUS_VERSION) -> Outcome:
    """Generate a grounded answer from an evidence set that already exists."""
    started = time.perf_counter()

    # --- Safety gate BEFORE generation: no provider call when evidence is weak.
    verdict = assess(evidence, corpus_version)
    if not verdict.sufficient:
        refusal = guardrails.refusal_for_insufficient_evidence(evidence, verdict)
        refusal.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return _attach_disclaimer(refusal)

    try:
        provider = provider or get_generation_provider()
    except GenerationUnavailable as exc:
        return _attach_disclaimer(SystemFailure(
            kind=FailureKind.PROVIDER_UNAVAILABLE,
            message="The answer generator is not available.",
            detail=str(exc), question=evidence.question,
            retrieval_id=evidence.retrieval_id,
            remedy="Set LLM_PROVIDER and LLM_API_KEY, or use LLM_PROVIDER=extractive."))

    try:
        raw = provider.generate(evidence.question, evidence, patient_context)
    except GenerationUnavailable as exc:
        return _attach_disclaimer(SystemFailure(
            kind=FailureKind.PROVIDER_ERROR,
            message="The answer generator failed to respond.",
            detail=str(exc), question=evidence.question,
            retrieval_id=evidence.retrieval_id,
            remedy="Retry, or check the generation provider's status."))
    except (ValueError, KeyError, TypeError) as exc:
        return _attach_disclaimer(SystemFailure(
            kind=FailureKind.MALFORMED_MODEL_OUTPUT,
            message="The answer generator returned an unusable response.",
            detail=f"{type(exc).__name__}: {exc}", question=evidence.question,
            retrieval_id=evidence.retrieval_id,
            remedy="Retry. Nothing was fabricated to fill the gap."))

    latency = round((time.perf_counter() - started) * 1000, 2)
    generator = getattr(provider, "name", "unknown")

    if raw.get("mode") == "refusal":
        reason = raw.get("reason", RefusalReason.INSUFFICIENT_EVIDENCE.value)
        try:
            reason_enum = RefusalReason(reason)
        except ValueError:
            reason_enum = RefusalReason.INSUFFICIENT_EVIDENCE
        return _attach_disclaimer(Refusal(
            retrieval_id=evidence.retrieval_id, chunk_set_hash=evidence.chunk_set_hash,
            question=evidence.question, reason=reason_enum,
            message=raw.get("message") or "The retrieved guideline evidence does not "
                                          "support an answer to this question.",
            sufficiency=verdict, evidence_considered=len(evidence.items),
            generator=generator, latency_ms=latency))

    kept, dropped = guardrails.build_recommendations(raw.get("recommendations"), evidence)
    if not kept:
        refusal = guardrails.refusal_for_no_valid_citations(evidence, dropped, generator)
        refusal.sufficiency = verdict
        refusal.latency_ms = latency
        return _attach_disclaimer(refusal)

    return _attach_disclaimer(GroundedAnswer(
        retrieval_id=evidence.retrieval_id, chunk_set_hash=evidence.chunk_set_hash,
        question=evidence.question, recommendations=kept,
        citation_coverage=guardrails.citation_coverage(kept),
        excerpt_accuracy=guardrails.excerpt_accuracy(kept),
        dropped_claims=dropped, generator=generator, sufficiency=verdict,
        latency_ms=latency))


def answer_question(question: str, *, k: int = 5, retriever=None, store: Optional[CorpusStore] = None,
                    retrieval_id: Optional[str] = None,
                    patient_context: Optional[PatientContext] = None,
                    provider=None) -> tuple:
    """Full path. Returns ``(outcome, evidence_set_or_None)``.

    Exactly one retrieval happens: either a fresh search, or the reload of a
    persisted one. Never both, never twice.
    """
    store = store or CorpusStore()

    if retrieval_id:
        try:
            evidence = load_evidence_set(store, retrieval_id)
        except LookupError as exc:
            return _attach_disclaimer(SystemFailure(
                kind=FailureKind.CORPUS_UNAVAILABLE,
                message="That retrieval is no longer available.",
                detail=str(exc), question=question,
                remedy="Ask the question again to run a fresh retrieval.")), None
        except ValueError as exc:
            return _attach_disclaimer(SystemFailure(
                kind=FailureKind.EVIDENCE_SET_CHANGED,
                message="The guideline corpus changed since this evidence was retrieved.",
                detail=str(exc), question=question, retrieval_id=retrieval_id,
                remedy="Ask the question again so the answer is grounded in current "
                       "evidence.")), None
    else:
        if retriever is None:
            try:
                from rag.retrieve import Retriever
                retriever = Retriever(store=store)
            except Exception as exc:  # noqa: BLE001
                return _attach_disclaimer(SystemFailure(
                    kind=FailureKind.NO_INDEX,
                    message="Guideline retrieval is unavailable.",
                    detail=f"{type(exc).__name__}: {exc}", question=question,
                    remedy="Run `python -m rag.ingest <pdf>` then `python -m rag.index`.")), None
        if not retriever.is_ready():
            return _attach_disclaimer(SystemFailure(
                kind=FailureKind.NO_INDEX,
                message="No guideline corpus is indexed.",
                detail="the vector index is empty for the active embedding model",
                question=question,
                remedy="Run `python -m rag.ingest <pdf>` then `python -m rag.index`.")), None
        try:
            evidence = EvidenceSet.from_retrieval(retriever.retrieve(question, k=k))
        except ValueError as exc:
            return _attach_disclaimer(SystemFailure(
                kind=FailureKind.CORPUS_UNAVAILABLE, message="Invalid question.",
                detail=str(exc), question=question)), None

    outcome = answer_from_evidence(evidence, patient_context=patient_context,
                                   provider=provider)
    return outcome, evidence
