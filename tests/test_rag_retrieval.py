"""Phase 2/3 tests: embeddings, vector storage, retrieval, and the gold-set harness.

No LLM is involved anywhere here — that is the point of the phase ordering.
Tests use the deterministic hashing provider so they need no model download.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from eval.goldset import (GoldCase, GoldEvidence, evaluate_case, load_goldset,  # noqa: E402
                          normalise, page_hit, span_hit, span_hit_adjacent,
                          validate_goldset)
from rag.chunking import chunk_document  # noqa: E402
from rag.contracts import Heading, PageRecord, SectionProvenance, SourceDocument  # noqa: E402
from rag.embeddings import HashingProvider, TfidfSvdProvider  # noqa: E402
from rag.retrieve import Retriever, chunk_set_hash  # noqa: E402
from rag.store import CorpusStore  # noqa: E402

DOC_ID = "hf"


def _page(n, text):
    return PageRecord(page_number=n, text=text, char_count=len(text), is_empty=not text.strip())


@pytest.fixture
def corpus(tmp_path):
    """A tiny indexed corpus with distinct, separable topics."""
    pages = [
        _page(1, "1. Diuretics\nIntravenous loop diuretics are recommended for congestion.\n"
                 "2. Beta blockers\nA beta blocker is recommended for stable reduced ejection fraction."),
        _page(2, "3. Devices\nAn implantable cardioverter defibrillator is recommended for selected patients."),
    ]
    headings = [
        Heading(title="1. Diuretics", level=1, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="t"),
        Heading(title="2. Beta blockers", level=1, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="t"),
        Heading(title="3. Devices", level=1, page_number=2,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="t"),
    ]
    chunks = chunk_document(pages, headings, document_id=DOC_ID,
                            document_title="Test HF Guideline")
    doc = SourceDocument(document_id=DOC_ID, title="Test HF Guideline",
                         file_sha256="b" * 64, page_count=2)
    store = CorpusStore(tmp_path / "c.db")
    store.replace_document(doc, chunks)
    provider = HashingProvider(64)
    vectors = provider.encode([c.content for c in chunks])
    store.store_embeddings(DOC_ID, provider.model_id, provider.dimension,
                           [c.chunk_index for c in chunks], vectors)
    return store, provider, chunks


# --------------------------------------------------------------------------
# embeddings
# --------------------------------------------------------------------------
def test_hashing_provider_is_deterministic_and_normalised():
    p = HashingProvider(64)
    a, b = p.encode(["heart failure"]), p.encode(["heart failure"])
    assert np.allclose(a, b)
    assert pytest.approx(1.0, abs=1e-5) == float(np.linalg.norm(a[0]))


def test_hashing_provider_declares_itself_non_semantic():
    """Guards against a test-only embedder being mistaken for a real one."""
    p = HashingProvider(32)
    assert p.is_semantic is False
    assert "testing_only" in p.model_id


def test_tfidf_provider_requires_fitting_first():
    p = TfidfSvdProvider(16)
    with pytest.raises(RuntimeError, match="fitted"):
        p.encode(["anything"])


def test_tfidf_provider_places_related_text_closer_than_unrelated():
    p = TfidfSvdProvider(8).fit([
        "loop diuretics for congestion in acute heart failure",
        "beta blocker therapy for reduced ejection fraction",
        "implantable cardioverter defibrillator device therapy",
        "anticoagulation for atrial fibrillation and stroke risk",
    ])
    v = p.encode(["diuretics congestion acute heart failure",
                  "implantable defibrillator device"])
    corpus = p.encode(["loop diuretics for congestion in acute heart failure",
                       "implantable cardioverter defibrillator device therapy"])
    assert float(v[0] @ corpus[0]) > float(v[0] @ corpus[1])


# --------------------------------------------------------------------------
# vector storage
# --------------------------------------------------------------------------
def test_embeddings_roundtrip_preserves_values(corpus):
    store, provider, chunks = corpus
    refs, vectors = store.load_embeddings(provider.model_id)
    assert len(refs) == len(chunks)
    original = provider.encode([c.content for c in chunks])
    assert np.allclose(np.asarray(vectors, dtype=np.float32), original, atol=1e-6)


def test_multiple_models_coexist_without_reingest(corpus):
    """Phase 3 compares models; that must not require re-chunking the corpus."""
    store, _p, chunks = corpus
    other = HashingProvider(32)
    store.store_embeddings(DOC_ID, other.model_id, other.dimension,
                           [c.chunk_index for c in chunks],
                           other.encode([c.content for c in chunks]))
    assert len({m["model_id"] for m in store.embedding_models()}) == 2
    assert store.stats()["chunks"] == len(chunks)


def test_replacing_a_document_clears_its_embeddings(corpus, tmp_path):
    store, provider, chunks = corpus
    doc = SourceDocument(document_id=DOC_ID, title="Test HF Guideline",
                         file_sha256="c" * 64, page_count=2)
    store.replace_document(doc, chunks)
    assert store.load_embeddings(provider.model_id)[0] == []


# --------------------------------------------------------------------------
# retrieval
# --------------------------------------------------------------------------
def test_retrieve_returns_k_ranked_items_with_provenance(corpus):
    store, provider, _ = corpus
    r = Retriever(store=store, provider=provider)
    out = r.retrieve("loop diuretics for congestion", k=2)
    assert len(out["chunks"]) == 2
    assert [c["evidenceId"] for c in out["chunks"]] == ["E1", "E2"]
    assert [c["rank"] for c in out["chunks"]] == [1, 2]
    first = out["chunks"][0]
    for field in ("score", "documentTitle", "sectionTitle", "pageNumber",
                  "pageEnd", "sectionProvenance", "citation"):
        assert field in first


def test_scores_are_monotonically_non_increasing(corpus):
    store, provider, _ = corpus
    out = Retriever(store=store, provider=provider).retrieve("beta blocker", k=3)
    scores = [c["score"] for c in out["chunks"]]
    assert scores == sorted(scores, reverse=True)


def test_retrieval_is_reproducible_for_the_same_question(corpus):
    store, provider, _ = corpus
    r = Retriever(store=store, provider=provider)
    a = r.retrieve("defibrillator", k=3, log=False)
    b = r.retrieve("defibrillator", k=3, log=False)
    assert a["chunkSetHash"] == b["chunkSetHash"]
    assert a["retrievalId"] != b["retrievalId"]


def test_chunk_set_hash_changes_when_evidence_changes():
    base = [{"documentId": "d", "chunkIndex": 0, "content": "alpha"}]
    changed = [{"documentId": "d", "chunkIndex": 0, "content": "alpha beta"}]
    reordered = [{"documentId": "d", "chunkIndex": 1, "content": "alpha"}]
    assert chunk_set_hash(base) != chunk_set_hash(changed)
    assert chunk_set_hash(base) != chunk_set_hash(reordered)


def test_k_is_clamped_to_corpus_and_bounds(corpus):
    store, provider, chunks = corpus
    r = Retriever(store=store, provider=provider)
    assert len(r.retrieve("anything", k=99)["chunks"]) == len(chunks)
    assert len(r.retrieve("anything", k=1)["chunks"]) == 1


def test_empty_question_is_rejected(corpus):
    store, provider, _ = corpus
    with pytest.raises(ValueError):
        Retriever(store=store, provider=provider).retrieve("   ", k=3)


def test_missing_index_raises_infrastructure_error_not_a_refusal(tmp_path):
    """An unindexed corpus is a system failure, never an evidence judgement."""
    store = CorpusStore(tmp_path / "empty.db")
    r = Retriever(store=store, provider=HashingProvider(16))
    assert not r.is_ready()
    with pytest.raises(RuntimeError, match="No embeddings indexed"):
        r.retrieve("anything", k=3)


def test_retrievals_are_logged_with_hash_and_scores(corpus):
    store, provider, _ = corpus
    r = Retriever(store=store, provider=provider)
    out = r.retrieve("diuretics", k=2)
    logged = store.get_retrieval(out["retrievalId"])
    assert logged is not None
    assert logged["chunk_set_hash"] == out["chunkSetHash"]
    assert logged["scores"] == out["scores"]
    assert logged["chunk_refs"] == [(c["documentId"], c["chunkIndex"]) for c in out["chunks"]]


def test_logging_disabled_does_not_write(corpus):
    store, provider, _ = corpus
    before = store.retrieval_count()
    Retriever(store=store, provider=provider).retrieve("x", k=1, log=False)
    assert store.retrieval_count() == before


def test_citation_includes_document_section_and_page(corpus):
    store, provider, _ = corpus
    top = Retriever(store=store, provider=provider).retrieve("defibrillator", k=3)["chunks"]
    for chunk in top:
        assert "Test HF Guideline" in chunk["citation"]
        assert "p." in chunk["citation"]


# --------------------------------------------------------------------------
# gold set: schema + matchers
# --------------------------------------------------------------------------
def _gold(**kw):
    base = dict(id="G1", question="q?", category="in_scope", expected_behaviour="answer",
                gold_evidence=[GoldEvidence(document="Test HF Guideline", pages=[1],
                                            evidence_span="loop diuretics are recommended")])
    base.update(kw)
    return GoldCase(**base)


def test_span_matcher_is_invariant_to_punctuation_and_hyphenation():
    gold = GoldEvidence(document="D", evidence_span="loop diuretics are recommended")
    chunk = {"documentTitle": "D", "documentId": "d",
             "content": "Intravenous loop-diuretics  are, recommended for congestion.",
             "pageNumber": 1, "pageEnd": 1, "chunkIndex": 0}
    assert span_hit(chunk, gold)


def test_span_matcher_requires_the_right_document():
    gold = GoldEvidence(document="ESC", evidence_span="loop diuretics")
    chunk = {"documentTitle": "NICE", "documentId": "nice", "content": "loop diuretics",
             "pageNumber": 1, "pageEnd": 1, "chunkIndex": 0}
    assert not span_hit(chunk, gold)


def test_page_matcher_allows_one_page_of_parser_drift():
    gold = GoldEvidence(document="D", pages=[10])
    near = {"documentTitle": "D", "documentId": "d", "content": "x",
            "pageNumber": 11, "pageEnd": 11, "chunkIndex": 0}
    far = {"documentTitle": "D", "documentId": "d", "content": "x",
           "pageNumber": 14, "pageEnd": 14, "chunkIndex": 0}
    assert page_hit(near, gold)
    assert not page_hit(far, gold)


def test_span_split_across_adjacent_chunks_still_counts():
    """The property that makes span labels survive re-chunking."""
    gold = GoldEvidence(document="D", evidence_span="loop diuretics are recommended for congestion")
    chunks = [
        {"documentTitle": "D", "documentId": "d", "chunkIndex": 4,
         "content": "Intravenous loop diuretics are", "pageNumber": 1, "pageEnd": 1},
        {"documentTitle": "D", "documentId": "d", "chunkIndex": 5,
         "content": "recommended for congestion in acute failure", "pageNumber": 1, "pageEnd": 1},
    ]
    assert not any(span_hit(c, gold) for c in chunks)
    assert span_hit_adjacent(chunks, gold)


def test_evaluate_case_computes_precision_recall_and_mrr():
    case = _gold()
    chunks = [
        {"documentTitle": "Test HF Guideline", "documentId": "hf", "chunkIndex": 0,
         "content": "Intravenous loop diuretics are recommended.", "pageNumber": 1, "pageEnd": 1},
        {"documentTitle": "Test HF Guideline", "documentId": "hf", "chunkIndex": 9,
         "content": "Unrelated device therapy text.", "pageNumber": 7, "pageEnd": 7},
    ]
    m = evaluate_case(case, chunks, k=2)
    assert m["precisionAtK"] == 0.5
    assert m["recallAtK"] == 1.0
    assert m["firstHitRank"] == 1
    assert m["reciprocalRank"] == 1.0
    assert m["hit"] is True


def test_evaluate_case_reports_span_and_page_precision_separately():
    """Divergence between the two is the chunker diagnostic."""
    case = _gold()
    right_page_wrong_text = [{
        "documentTitle": "Test HF Guideline", "documentId": "hf", "chunkIndex": 3,
        "content": "Something else entirely on the same page.",
        "pageNumber": 1, "pageEnd": 1}]
    m = evaluate_case(case, right_page_wrong_text, k=1)
    assert m["precisionAtK_page"] == 1.0
    assert m["precisionAtK_span"] == 0.0


def test_evaluate_case_scores_zero_when_nothing_relevant_retrieved():
    m = evaluate_case(_gold(), [{"documentTitle": "Other", "documentId": "o", "chunkIndex": 0,
                                 "content": "irrelevant", "pageNumber": 99, "pageEnd": 99}], k=1)
    assert m["precisionAtK"] == 0.0 and m["recallAtK"] == 0.0 and m["hit"] is False


# --------------------------------------------------------------------------
# gold set: validation
# --------------------------------------------------------------------------
def test_validation_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate"):
        validate_goldset([_gold(), _gold()])


def test_validation_rejects_unknown_category():
    with pytest.raises(ValueError, match="category"):
        validate_goldset([_gold(category="nonsense")])


def test_in_scope_case_must_have_gold_evidence():
    with pytest.raises(ValueError, match="gold_evidence"):
        validate_goldset([_gold(gold_evidence=[])])


def test_out_of_domain_case_must_not_have_gold_evidence():
    """Negatives are the calibration negatives; labelling them positive breaks that."""
    with pytest.raises(ValueError, match="must NOT carry"):
        validate_goldset([_gold(id="N1", category="out_of_domain", expected_behaviour="refuse")])


def test_gold_evidence_needs_a_span_or_pages():
    with pytest.raises(ValueError, match="evidence_span or pages"):
        validate_goldset([_gold(gold_evidence=[GoldEvidence(document="D")])])


def test_goldset_yaml_loads_and_validates(tmp_path):
    path = tmp_path / "g.yaml"
    path.write_text(
        "- id: A1\n"
        "  question: what diuretic?\n"
        "  category: in_scope\n"
        "  expected_behaviour: answer\n"
        "  gold_evidence:\n"
        "    - document: Test HF Guideline\n"
        "      pages: [1]\n"
        "      evidence_span: loop diuretics are recommended\n"
        "- id: A2\n"
        "  question: kubernetes ingress?\n"
        "  category: out_of_domain\n"
        "  expected_behaviour: refuse\n", encoding="utf-8")
    cases = load_goldset(path)
    assert len(cases) == 2
    assert cases[0].is_retrievable and not cases[1].is_retrievable


# --------------------------------------------------------------------------
# end-to-end harness
# --------------------------------------------------------------------------
def test_run_evaluation_produces_metrics_for_every_k(corpus):
    from eval.run_eval import run_evaluation
    store, provider, _ = corpus
    cases = [
        _gold(id="E1", question="loop diuretics for congestion"),
        GoldCase(id="N1", question="kubernetes ingress controller",
                 category="out_of_domain", expected_behaviour="refuse"),
    ]
    report = run_evaluation(Retriever(store=store, provider=provider), cases, ks=(1, 3))
    assert report["summary"]["cases"] == 1
    assert set(report["summary"]["byK"]) == {"k=1", "k=3"}
    assert report["summary"]["latencyMs"]["p50"] is not None
    # Negatives are scored for later calibration but excluded from retrieval metrics.
    assert len(report["negatives"]) == 1
    assert "NOT a calibrated" in report["summary"]["scoreSeparation"]["note"]
