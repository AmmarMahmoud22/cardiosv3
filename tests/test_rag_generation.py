"""Phase 4/5 tests: grounded generation, citation validation, refusal, safety.

Uses the offline extractive provider plus stub providers, so nothing here needs
an API key or a network call.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from rag import guardrails  # noqa: E402
from rag.answer_contracts import (EvidenceItem, EvidenceSet, FailureKind,  # noqa: E402
                                  GroundedAnswer, PatientContext, Refusal,
                                  RefusalReason, SystemFailure)
from rag.answering import answer_from_evidence, load_evidence_set  # noqa: E402
from rag.chunking import chunk_document  # noqa: E402
from rag.contracts import Heading, PageRecord, SectionProvenance, SourceDocument  # noqa: E402
from rag.embeddings import HashingProvider  # noqa: E402
from rag.generation import (ExtractiveProvider, GenerationProvider,  # noqa: E402
                            GenerationUnavailable, get_generation_provider)
from rag.prompting import SYSTEM_PROMPT, build_user_prompt, parse_model_json  # noqa: E402
from rag.retrieve import Retriever  # noqa: E402
from rag.store import CorpusStore  # noqa: E402

DIURETIC = ("Intravenous loop diuretics are recommended for all patients with acute "
            "heart failure and congestion.")
DEVICE = "An implantable cardioverter defibrillator is recommended for selected patients."


def _evidence(items=None) -> EvidenceSet:
    items = items if items is not None else [
        EvidenceItem(evidence_id="E1", content=DIURETIC, document_id="hf",
                     document_title="Test HF Guideline", chunk_index=0,
                     section_title="4. Acute heart failure", page_number=12,
                     page_end=12, score=0.82),
        EvidenceItem(evidence_id="E2", content=DEVICE, document_id="hf",
                     document_title="Test HF Guideline", chunk_index=1,
                     section_title="5. Devices", page_number=14, page_end=14, score=0.41),
    ]
    return EvidenceSet(retrieval_id="r1", chunk_set_hash="h1",
                       question="What diuretic therapy for acute heart failure?",
                       model_id="test", items=items)


class StubProvider(GenerationProvider):
    name = "stub"

    def __init__(self, payload=None, raises=None):
        self.payload, self.raises = payload, raises
        self.saw_patient_context = None

    def generate(self, question, evidence, patient_context=None):
        self.saw_patient_context = patient_context
        if self.raises:
            raise self.raises
        return self.payload


# --------------------------------------------------------------------------
# prompt construction & the context/evidence separation
# --------------------------------------------------------------------------
def test_prompt_forbids_outside_knowledge_and_requires_citations():
    assert "ONLY from the guideline passages" in SYSTEM_PROMPT
    assert "MUST cite at least one evidence id" in SYSTEM_PROMPT
    assert "MUST refuse" in SYSTEM_PROMPT


def test_prompt_keeps_patient_context_in_a_separate_uncitable_block():
    context = PatientContext(summary="ECG shows frequent PVCs.", source="synthetic-demo")
    prompt = build_user_prompt("What next?", _evidence(), context)
    assert "### PATIENT_CONTEXT" in prompt and "### GUIDELINE_EVIDENCE" in prompt
    assert prompt.index("### PATIENT_CONTEXT") < prompt.index("### GUIDELINE_EVIDENCE")
    assert "NEVER cite this block" in prompt
    # The context block carries no evidence identifier for a model to emit.
    context_block = prompt.split("### GUIDELINE_EVIDENCE")[0]
    assert "[E" not in context_block


def test_prompt_enumerates_the_only_valid_evidence_ids():
    prompt = build_user_prompt("q", _evidence())
    assert "Valid evidence ids for this question: E1, E2" in prompt


def test_patient_context_has_no_evidence_id_field():
    """Structural guarantee, not a wording choice."""
    assert "evidence_id" not in PatientContext.model_fields


def test_parse_model_json_rejects_unusable_replies():
    for bad in ["", "not json", '{"mode": "chatty"}']:
        with pytest.raises(ValueError):
            parse_model_json(bad)


# --------------------------------------------------------------------------
# citation validation
# --------------------------------------------------------------------------
def test_claim_citing_an_unknown_evidence_id_is_dropped():
    kept, dropped = guardrails.build_recommendations(
        [{"text": "Start sacubitril now.", "excerpt": "invented", "evidence_ids": ["E99"]}],
        _evidence())
    assert kept == [] and dropped == ["Start sacubitril now."]


def test_uncited_claim_is_dropped_not_displayed_with_a_warning():
    kept, dropped = guardrails.build_recommendations(
        [{"text": "Everyone should exercise.", "excerpt": "", "evidence_ids": []}], _evidence())
    assert kept == [] and len(dropped) == 1


def test_valid_claim_is_kept_with_a_resolvable_citation():
    kept, _ = guardrails.build_recommendations(
        [{"text": "Give IV loop diuretics.", "excerpt": DIURETIC, "evidence_ids": ["E1"]}],
        _evidence())
    assert len(kept) == 1
    citation = kept[0].citations[0]
    assert citation.evidence_id == "E1"
    assert citation.document == "Test HF Guideline"
    assert citation.page == "12"
    assert kept[0].excerpt_verified is True


def test_reworded_excerpt_is_not_marked_verified():
    kept, _ = guardrails.build_recommendations(
        [{"text": "Give diuretics.", "excerpt": "Diuretics help a lot with fluid.",
          "evidence_ids": ["E1"]}], _evidence())
    assert len(kept) == 1 and kept[0].excerpt_verified is False


def test_excerpt_matching_tolerates_pdf_whitespace_and_punctuation():
    assert guardrails.excerpt_is_verbatim(
        "loop diuretics are recommended",
        "Intravenous  loop-diuretics, are   recommended for congestion.")


def test_partial_validity_keeps_only_the_supportable_claims():
    kept, dropped = guardrails.build_recommendations([
        {"text": "Good claim.", "excerpt": DIURETIC, "evidence_ids": ["E1"]},
        {"text": "Bad claim.", "excerpt": "x", "evidence_ids": ["E7"]},
    ], _evidence())
    assert [r.text for r in kept] == ["Good claim."]
    assert dropped == ["Bad claim."]


def test_coverage_and_excerpt_accuracy_are_computed():
    kept, _ = guardrails.build_recommendations([
        {"text": "A", "excerpt": DIURETIC, "evidence_ids": ["E1"]},
        {"text": "B", "excerpt": "not present anywhere", "evidence_ids": ["E2"]},
    ], _evidence())
    assert guardrails.citation_coverage(kept) == 1.0
    assert guardrails.excerpt_accuracy(kept) == 0.5


# --------------------------------------------------------------------------
# extractive provider
# --------------------------------------------------------------------------
def test_extractive_provider_only_ever_copies_evidence_text():
    out = ExtractiveProvider().generate("diuretic therapy for congestion", _evidence())
    assert out["mode"] == "answer"
    corpus = " ".join(i.content for i in _evidence().items)
    for rec in out["recommendations"]:
        assert rec["text"] == rec["excerpt"]
        assert rec["excerpt"] in corpus


def test_extractive_provider_refuses_when_nothing_matches():
    out = ExtractiveProvider().generate("kubernetes ingress controller", _evidence())
    assert out["mode"] == "refusal"


def test_extractive_provider_is_labelled_as_not_a_language_model():
    provider = ExtractiveProvider()
    assert provider.is_language_model is False
    assert "extractive" in provider.name


def test_provider_selection_defaults_to_extractive_without_a_key(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert isinstance(get_generation_provider(), ExtractiveProvider)


def test_hosted_provider_without_a_key_is_an_infrastructure_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(GenerationUnavailable):
        get_generation_provider()


# --------------------------------------------------------------------------
# orchestration: answer / refusal / system failure
# --------------------------------------------------------------------------
def test_grounded_answer_carries_citations_and_a_disclaimer(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.1")
    out = answer_from_evidence(_evidence(), provider=ExtractiveProvider())
    assert isinstance(out, GroundedAnswer)
    assert out.recommendations and out.recommendations[0].citations
    assert out.citation_coverage == 1.0
    assert out.disclaimer and out.not_medical_advice is True


def test_weak_evidence_refuses_before_calling_the_provider(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.95")
    provider = StubProvider(payload={"mode": "answer", "recommendations": []})
    out = answer_from_evidence(_evidence(), provider=provider)
    assert isinstance(out, Refusal)
    assert out.reason == RefusalReason.INSUFFICIENT_EVIDENCE
    assert out.is_evidence_refusal is True
    assert provider.saw_patient_context is None, "provider must not be called at all"


def test_empty_evidence_always_refuses(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.0")
    out = answer_from_evidence(_evidence(items=[]), provider=ExtractiveProvider())
    assert isinstance(out, Refusal)


def test_answer_with_only_uncitable_claims_becomes_a_refusal(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.1")
    out = answer_from_evidence(_evidence(), provider=StubProvider(payload={
        "mode": "answer",
        "recommendations": [{"text": "Fabricated.", "excerpt": "x", "evidence_ids": ["E42"]}]}))
    assert isinstance(out, Refusal)
    assert out.reason == RefusalReason.NO_VALID_CITATIONS


def test_provider_failure_is_a_system_failure_not_a_refusal(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.1")
    out = answer_from_evidence(_evidence(),
                               provider=StubProvider(raises=GenerationUnavailable("502")))
    assert isinstance(out, SystemFailure)
    assert out.kind == FailureKind.PROVIDER_ERROR
    assert out.is_evidence_refusal is False


def test_malformed_model_output_is_a_system_failure(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.1")
    out = answer_from_evidence(_evidence(), provider=StubProvider(raises=ValueError("bad json")))
    assert isinstance(out, SystemFailure)
    assert out.kind == FailureKind.MALFORMED_MODEL_OUTPUT
    assert out.is_evidence_refusal is False


def test_system_failure_carries_no_medical_disclaimer(monkeypatch):
    """An outage makes no clinical statement, so it gets no clinical framing."""
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.1")
    out = answer_from_evidence(_evidence(), provider=StubProvider(raises=GenerationUnavailable("x")))
    assert "disclaimer" not in out.model_dump()


def test_model_refusal_is_passed_through_as_a_clinical_refusal(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.1")
    out = answer_from_evidence(_evidence(), provider=StubProvider(payload={
        "mode": "refusal", "reason": "out_of_scope", "message": "Not covered."}))
    assert isinstance(out, Refusal)
    assert out.reason == RefusalReason.OUT_OF_SCOPE
    assert out.disclaimer


def test_patient_context_reaches_the_provider_but_never_becomes_a_citation(monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.1")
    context = PatientContext(summary="High cardiac risk profile.", source="cardios-risk-model",
                             is_synthetic=False)
    provider = StubProvider(payload={
        "mode": "answer",
        "recommendations": [
            {"text": "Cited.", "excerpt": DIURETIC, "evidence_ids": ["E1"]},
            {"text": "Based on the patient context.", "excerpt": "High cardiac risk profile.",
             "evidence_ids": ["PATIENT_CONTEXT"]},
        ]})
    out = answer_from_evidence(_evidence(), patient_context=context, provider=provider)
    assert provider.saw_patient_context is context
    assert isinstance(out, GroundedAnswer)
    assert [r.text for r in out.recommendations] == ["Cited."]
    assert out.dropped_claims == ["Based on the patient context."]


# --------------------------------------------------------------------------
# single-retrieval guarantee
# --------------------------------------------------------------------------
@pytest.fixture
def indexed(tmp_path):
    pages = [PageRecord(page_number=1, text=f"1. Acute\n{DIURETIC}\n2. Devices\n{DEVICE}",
                        char_count=99)]
    headings = [
        Heading(title="1. Acute", level=1, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="t"),
        Heading(title="2. Devices", level=1, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="t"),
    ]
    chunks = chunk_document(pages, headings, document_id="hf", document_title="Test HF Guideline")
    store = CorpusStore(tmp_path / "c.db")
    store.replace_document(SourceDocument(document_id="hf", title="Test HF Guideline",
                                          file_sha256="d" * 64, page_count=1), chunks)
    provider = HashingProvider(64)
    store.store_embeddings("hf", provider.model_id, provider.dimension,
                           [c.chunk_index for c in chunks],
                           provider.encode([c.content for c in chunks]))
    return store, Retriever(store=store, provider=provider), chunks


def test_evidence_set_reloads_identically_from_a_retrieval_id(indexed):
    store, retriever, _ = indexed
    result = retriever.retrieve("diuretics", k=2)
    reloaded = load_evidence_set(store, result["retrievalId"])
    assert reloaded.chunk_set_hash == result["chunkSetHash"]
    assert reloaded.ids == [c["evidenceId"] for c in result["chunks"]]
    assert [i.content for i in reloaded.items] == [c["content"] for c in result["chunks"]]


def test_reloading_an_unknown_retrieval_id_raises(indexed):
    store, _r, _c = indexed
    with pytest.raises(LookupError):
        load_evidence_set(store, "does-not-exist")


def test_corpus_change_invalidates_a_pending_evidence_set(indexed):
    """Fail closed: never answer from evidence the user did not see."""
    store, retriever, chunks = indexed
    result = retriever.retrieve("diuretics", k=2)
    edited = [c.model_copy(update={"content": c.content + " EDITED"}) for c in chunks]
    store.replace_document(SourceDocument(document_id="hf", title="Test HF Guideline",
                                          file_sha256="e" * 64, page_count=1), edited)
    with pytest.raises(ValueError, match="corpus changed"):
        load_evidence_set(store, result["retrievalId"])


def test_generation_uses_the_exact_displayed_evidence(indexed, monkeypatch):
    monkeypatch.setenv("RAG_SUFFICIENCY_THRESHOLD", "0.0")
    store, retriever, _ = indexed
    shown = retriever.retrieve("diuretics for congestion", k=2)
    reloaded = load_evidence_set(store, shown["retrievalId"])
    out = answer_from_evidence(reloaded, provider=ExtractiveProvider())
    assert out.chunk_set_hash == shown["chunkSetHash"]
