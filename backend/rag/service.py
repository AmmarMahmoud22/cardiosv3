"""Flask blueprint for the RAG module.

Phase 1 exposes read-only introspection only: corpus health and corpus
contents. Retrieval (`/rag/retrieve`), generation (`/rag/query`), and the
refusal path are added in Phases 2–5 and are deliberately absent here.

Component-state vocabulary (fixed now so later phases inherit it):

    ``ok``              the component is configured and usable
    ``not_configured``  a required decision has not been made yet
    ``unavailable``     configured but the dependency failed at runtime

``not_configured`` and ``unavailable`` are INFRASTRUCTURE states. They are
distinct from an evidence-insufficiency refusal, which is a clinical judgement
about the corpus and is introduced in Phase 5. The two must never be collapsed
into one response shape: a provider outage must surface as a technical
unavailability, never as "the guidelines do not cover this".
"""
from __future__ import annotations

import logging
import os

from flask import Blueprint, jsonify, request

from rag import __version__
from rag.config import chunk_config
from rag.store import CorpusStore

logger = logging.getLogger(__name__)

rag_bp = Blueprint("rag", __name__)

corpus_store = CorpusStore()


#: Providers that run in-process and need no API key.
_KEYLESS_EMBEDDERS = {"local", "tfidf", "tfidf-svd", "hashing"}


def _embedding_state() -> str:
    """Embedding provider readiness.

    The in-process providers (sentence-transformers, TF-IDF, hashing) need no
    credentials, so requiring a key for them reported a working index as
    unconfigured.
    """
    provider = (os.getenv("EMBEDDING_PROVIDER") or "local").strip().lower()
    if provider in _KEYLESS_EMBEDDERS:
        return "ok"
    return "ok" if os.getenv("EMBEDDING_API_KEY") else "not_configured"


def _generation_state() -> str:
    """Generation readiness. ``extractive_fallback`` means grounded answers work
    offline via the extractive baseline — degraded, but not unavailable."""
    try:
        from rag.generation import provider_state
        return provider_state()
    except Exception:  # noqa: BLE001
        return "not_configured"


def _llm_state() -> str:
    """Generation provider readiness. Phase 0.7 decision; blocks Phase 4 only."""
    provider = os.getenv("LLM_PROVIDER", "").strip()
    if not provider:
        return "not_configured"
    if provider == "local":
        return "ok" if os.getenv("LLM_MODEL") else "not_configured"
    return "ok" if os.getenv("LLM_API_KEY") else "not_configured"


@rag_bp.route("/health", methods=["GET"])
def rag_health():
    """Readiness of the RAG module's components.

    Returns 200 whenever the module itself is serving. ``phase1Ready`` reports
    whether ingestion is usable; later phases add their own readiness keys.
    """
    store_ok = corpus_store.healthcheck()
    stats = corpus_store.stats() if store_ok else {}
    indexed = stats.get("embeddedChunks", 0) if store_ok else 0
    components = {
        "corpusStore": "ok" if store_ok else "unavailable",
        "embeddingProvider": _embedding_state(),
        "generationProvider": _llm_state(),
        "vectorIndex": "ok" if indexed else "not_configured",
        "retrieval": "ok" if indexed else "not_configured",
        "generation": _generation_state(),
    }
    return jsonify({
        "module": "rag",
        "version": __version__,
        "phase": "5-grounded-answer",
        "components": components,
        "phase1Ready": store_ok,
        "corpus": stats,
        "chunkConfig": chunk_config(),
    })


@rag_bp.route("/documents", methods=["GET"])
def rag_documents():
    """Ingested corpus: documents, provenance, chunk counts, page coverage."""
    if not corpus_store.healthcheck():
        return jsonify({"error": "Corpus store unavailable", "state": "unavailable"}), 503
    docs = corpus_store.documents()
    for doc in docs:
        report = corpus_store.ingest_report(doc["document_id"])
        if report:
            doc["ingestWarnings"] = report.get("warnings", [])
            doc["sectionProvenanceCounts"] = report.get("section_provenance_counts", {})
            doc["pageCoverageGaps"] = report.get("page_coverage_gaps", [])
    return jsonify({"documents": docs, "stats": corpus_store.stats()})


@rag_bp.route("/documents/<document_id>/chunks", methods=["GET"])
def rag_document_chunks(document_id: str):
    """Chunks for one document — used by the metadata verification workflow."""
    if not corpus_store.healthcheck():
        return jsonify({"error": "Corpus store unavailable", "state": "unavailable"}), 503
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    chunks = corpus_store.chunks(document_id, limit=limit)
    if not chunks:
        return jsonify({"error": "Unknown document or no chunks ingested",
                        "documentId": document_id}), 404
    return jsonify({"documentId": document_id, "count": len(chunks), "chunks": chunks})


# ---------------------------------------------------------------------------
# Retrieval (Phase 2/3). Generation is NOT implemented — this endpoint returns
# evidence only, which is exactly what the "display retrieved chunks before
# generation" requirement needs.
# ---------------------------------------------------------------------------
_retriever = None
_retriever_error: str = ""


def get_retriever(force_reload: bool = False):
    """Lazily build the retriever so importing the blueprint never needs a model."""
    global _retriever, _retriever_error
    if _retriever is not None and not force_reload:
        return _retriever
    try:
        from rag.retrieve import Retriever
        _retriever = Retriever()
        _retriever_error = ""
    except Exception as exc:  # noqa: BLE001
        _retriever = None
        _retriever_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Retriever unavailable (%s)", _retriever_error)
    return _retriever


@rag_bp.route("/retrieve", methods=["POST"])
def rag_retrieve():
    """Top-k semantic retrieval. Returns evidence, scores, and provenance.

    Failure modes here are INFRASTRUCTURE failures (no model, no index) and are
    reported as such with a 503. They are not, and must never be presented as,
    a judgement that the guidelines lack relevant evidence — that distinction
    belongs to the Phase-5 refusal layer.
    """
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required", "state": "invalid_request"}), 400
    try:
        k = int(payload.get("k", 5))
    except (TypeError, ValueError):
        return jsonify({"error": "k must be an integer", "state": "invalid_request"}), 400
    if not 1 <= k <= 50:
        return jsonify({"error": "k must be between 1 and 50", "state": "invalid_request"}), 400

    retriever = get_retriever()
    if retriever is None or not retriever.is_ready():
        return jsonify({
            "state": "unavailable",
            "error": "Retrieval is not available: the corpus has no vector index for the "
                     "active embedding model.",
            "detail": _retriever_error or "no embeddings indexed",
            "remedy": "Run `python -m rag.ingest <pdf>` then `python -m rag.index`.",
            "isEvidenceRefusal": False,
        }), 503

    try:
        result = retriever.retrieve(question, k=k)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Retrieval failed")
        return jsonify({"state": "unavailable", "error": "Retrieval failed",
                        "detail": f"{type(exc).__name__}", "isEvidenceRefusal": False}), 503

    result["state"] = "ok"
    result["generation"] = "available"
    return jsonify(result)


@rag_bp.route("/answer", methods=["POST"])
def rag_answer():
    """Grounded answer over guideline evidence.

    Accepts either ``{question, k}`` (one fresh retrieval) or ``{retrievalId}``
    (reuse the exact evidence already shown to the user). It never retrieves
    twice, so the evidence displayed is provably the evidence generated from.

    Three outcome shapes, deliberately distinct:
      200 mode=answer          grounded, cited recommendations
      200 mode=refusal         a clinical judgement about evidence sufficiency
      503 mode=system_failure  infrastructure; isEvidenceRefusal is always false
    """
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    retrieval_id = (payload.get("retrievalId") or "").strip() or None

    if not question and not retrieval_id:
        return jsonify({"error": "question or retrievalId is required",
                        "state": "invalid_request"}), 400
    try:
        k = int(payload.get("k", 5))
    except (TypeError, ValueError):
        return jsonify({"error": "k must be an integer", "state": "invalid_request"}), 400
    if not 1 <= k <= 50:
        return jsonify({"error": "k must be between 1 and 50",
                        "state": "invalid_request"}), 400

    patient_context = None
    raw_context = payload.get("patientContext")
    if isinstance(raw_context, dict) and (raw_context.get("summary") or "").strip():
        from rag.answer_contracts import PatientContext
        patient_context = PatientContext(
            summary=raw_context["summary"],
            source=raw_context.get("source", "client-supplied"),
            is_synthetic=bool(raw_context.get("isSynthetic", True)))

    from rag.answering import answer_question
    retriever = None if retrieval_id else get_retriever()
    outcome, evidence = answer_question(
        question, k=k, retriever=retriever, retrieval_id=retrieval_id,
        patient_context=patient_context)

    body = outcome.model_dump(mode="json")
    if evidence is not None:
        # The evidence is returned with the answer so the UI can render exactly
        # what the generator saw, without a second call.
        body["evidence"] = evidence.model_dump(mode="json")
    status = 503 if body.get("mode") == "system_failure" else 200
    return jsonify(body), status
