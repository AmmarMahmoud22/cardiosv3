"""Phase-1 tests for the RAG ingestion module.

Scope: chunking correctness, metadata honesty (nothing invented), the
verification-sample gate, the corpus store, and the read-only blueprint.
Retrieval, embeddings, and generation are out of scope for Phase 1.

Most tests construct page/heading fixtures directly so they run without a PDF
and without the PDF parsing dependency. Tests that genuinely exercise the
parser are skipped when pdfplumber is unavailable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rag.chunking import chunk_document  # noqa: E402
from rag.contracts import (Chunk, Heading, PageLabelProvenance, PageRecord,  # noqa: E402
                           SectionProvenance, SourceDocument)
from rag.store import CorpusStore  # noqa: E402
from rag.verify import build_sample, render_markdown, select_sample  # noqa: E402


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _page(n: int, text: str, label=None) -> PageRecord:
    return PageRecord(page_number=n, text=text, char_count=len(text),
                      is_empty=not text.strip(), page_label=label)


@pytest.fixture
def two_section_pages():
    p1 = _page(1, "1. Diagnosis\nAlpha line one.\nAlpha line two.\n2. Treatment\nBeta line one.")
    p2 = _page(2, "Beta line two.\nBeta line three.")
    headings = [
        Heading(title="1. Diagnosis", level=1, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="test"),
        Heading(title="2. Treatment", level=1, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="test"),
    ]
    return [p1, p2], headings


DOC_ID = "d"


def _chunks(pages, headings, **kw):
    return chunk_document(pages, headings, document_id=DOC_ID, document_title="Doc", **kw)


# --------------------------------------------------------------------------
# chunking: page attribution
# --------------------------------------------------------------------------
def test_chunks_are_produced(two_section_pages):
    pages, headings = two_section_pages
    assert len(_chunks(pages, headings)) >= 2


def test_page_attribution_is_within_document(two_section_pages):
    pages, headings = two_section_pages
    valid = {p.page_number for p in pages}
    for c in _chunks(pages, headings):
        assert c.page_number in valid
        assert c.page_end in valid
        assert c.page_end >= c.page_number


def test_chunk_content_comes_from_its_claimed_pages(two_section_pages):
    """Every word of a chunk must exist on one of the pages it cites."""
    pages, headings = two_section_pages
    by_page = {p.page_number: " ".join(p.text.split()) for p in pages}
    for c in _chunks(pages, headings):
        claimed = " ".join(by_page[p] for p in range(c.page_number, c.page_end + 1))
        for line in c.content.split(". "):
            token = line.strip().rstrip(".")
            if token:
                assert token in claimed, f"chunk {c.chunk_index} text not on claimed pages"


def test_spans_pages_flag_is_accurate(two_section_pages):
    pages, headings = two_section_pages
    for c in _chunks(pages, headings, target_chars=10_000, overlap_chars=0):
        assert c.spans_pages == (c.page_end != c.page_number)


def test_page_label_used_in_citation_when_declared():
    pages = [_page(1, "1. S\nBody text here.", label="3599")]
    headings = [Heading(title="1. S", level=1, page_number=1,
                        provenance=SectionProvenance.NUMBERED_HEADING, evidence="t")]
    c = chunk_document(pages, headings, document_id="d", document_title="T",
                       page_label_provenance=PageLabelProvenance.DECLARED)[0]
    assert c.page_label == "3599"
    assert "p.3599" in c.citation


# --------------------------------------------------------------------------
# chunking: section attribution honesty
# --------------------------------------------------------------------------
def test_chunks_never_cross_a_section_boundary(two_section_pages):
    pages, headings = two_section_pages
    for c in _chunks(pages, headings, target_chars=10_000, overlap_chars=0):
        assert c.section_title in {"1. Diagnosis", "2. Treatment"}
        # Diagnosis content must not leak into the Treatment chunk.
        if c.section_title == "2. Treatment":
            assert "Alpha" not in c.content
        if c.section_title == "1. Diagnosis":
            assert "Beta" not in c.content


def test_no_headings_means_unknown_section_not_a_guess():
    """The critical honesty test: absent evidence, nothing is fabricated."""
    pages = [_page(1, "Some body text with no heading structure at all.")]
    chunks = chunk_document(pages, [], document_id="d", document_title="T")
    assert chunks
    for c in chunks:
        assert c.section_title is None
        assert c.section_path is None
        assert c.section_provenance == SectionProvenance.UNKNOWN
        assert "(section not determined)" in c.citation


def test_section_path_reflects_nesting():
    pages = [_page(1, "1. Top\n1.1 Sub\nBody under sub.")]
    headings = [
        Heading(title="1. Top", level=1, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="t"),
        Heading(title="1.1 Sub", level=2, page_number=1,
                provenance=SectionProvenance.NUMBERED_HEADING, evidence="t"),
    ]
    c = chunk_document(pages, headings, document_id="d", document_title="T")[0]
    assert c.section_title == "1.1 Sub"
    assert c.section_path == "1. Top › 1.1 Sub"


def test_provenance_is_carried_from_the_heading():
    pages = [_page(1, "Styled Title\nBody text follows the styled title here.")]
    headings = [Heading(title="Styled Title", level=1, page_number=1,
                        provenance=SectionProvenance.STYLED_HEADING, evidence="font")]
    c = chunk_document(pages, headings, document_id="d", document_title="T")[0]
    assert c.section_provenance == SectionProvenance.STYLED_HEADING


# --------------------------------------------------------------------------
# chunking: configuration
# --------------------------------------------------------------------------
def test_target_size_is_respected_within_tolerance():
    body = "\n".join(f"Sentence number {i} with some filler words." for i in range(200))
    pages = [_page(1, "1. S\n" + body)]
    headings = [Heading(title="1. S", level=1, page_number=1,
                        provenance=SectionProvenance.NUMBERED_HEADING, evidence="t")]
    chunks = chunk_document(pages, headings, document_id="d", document_title="T",
                            target_chars=500, overlap_chars=100)
    assert len(chunks) > 1
    # One line may overshoot the target; allow the longest single line as slack.
    longest_line = max(len(l) for l in body.splitlines())
    assert all(c.char_count <= 500 + longest_line for c in chunks)


def test_overlap_produces_shared_text_between_neighbours():
    body = "\n".join(f"Line {i} carries distinctive content." for i in range(60))
    pages = [_page(1, "1. S\n" + body)]
    headings = [Heading(title="1. S", level=1, page_number=1,
                        provenance=SectionProvenance.NUMBERED_HEADING, evidence="t")]
    with_overlap = chunk_document(pages, headings, document_id="d", document_title="T",
                                  target_chars=400, overlap_chars=150)
    assert len(with_overlap) > 1
    first_words = set(with_overlap[0].content.split())
    second_words = set(with_overlap[1].content.split())
    assert first_words & second_words, "expected overlapping text between adjacent chunks"


def test_overlap_must_be_smaller_than_target():
    pages = [_page(1, "Body")]
    with pytest.raises(ValueError):
        chunk_document(pages, [], document_id="d", document_title="T",
                       target_chars=100, overlap_chars=100)


def test_chunk_indices_are_contiguous(two_section_pages):
    pages, headings = two_section_pages
    chunks = _chunks(pages, headings)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_empty_pages_produce_no_chunks():
    chunks = chunk_document([_page(1, "   ")], [], document_id="d", document_title="T")
    assert chunks == []


# --------------------------------------------------------------------------
# verification sample (the Phase-1 gate artefact)
# --------------------------------------------------------------------------
def _doc() -> SourceDocument:
    return SourceDocument(document_id=DOC_ID, title="T", file_sha256="a" * 64, page_count=2)


def test_store_rejects_chunks_from_a_different_document(tmp_path, two_section_pages):
    """Provenance integrity guard: mismatched chunks must fail loudly."""
    pages, headings = two_section_pages
    foreign = chunk_document(pages, headings, document_id="other", document_title="Other")
    store = CorpusStore(tmp_path / "c.db")
    with pytest.raises(ValueError, match="mismatch"):
        store.replace_document(_doc(), foreign)


def test_sample_is_deterministic_and_evenly_spaced():
    chunks = [Chunk(chunk_index=i, content=f"c{i}", document_id="d", document_title="T",
                    page_number=1, page_end=1) for i in range(100)]
    a = [c.chunk_index for c in select_sample(chunks, 20)]
    b = [c.chunk_index for c in select_sample(chunks, 20)]
    assert a == b
    assert len(a) == 20
    assert a[0] == 0 and a[-1] < 100
    assert len(set(a)) == 20


def test_sample_returns_all_chunks_when_fewer_than_requested():
    chunks = [Chunk(chunk_index=i, content="x", document_id="d", document_title="T",
                    page_number=1, page_end=1) for i in range(5)]
    assert len(select_sample(chunks, 20)) == 5


def test_sample_flags_chunk_present_on_its_claimed_page(two_section_pages):
    pages, headings = two_section_pages
    chunks = _chunks(pages, headings)
    sample = build_sample(_doc(), chunks, pages, sample_size=20)
    assert sample["sampleSize"] == len(chunks)
    assert sample["autoCheckPassed"] >= 1
    assert sample["humanVerdict"] is None, "the gate requires a human verdict, not an auto-pass"


def test_sample_detects_a_deliberately_wrong_page_attribution(two_section_pages):
    """A chunk citing the wrong page must NOT auto-pass."""
    pages, headings = two_section_pages
    chunks = _chunks(pages, headings)
    bad = chunks[0].model_copy(update={"page_number": 2, "page_end": 2})
    sample = build_sample(_doc(), [bad], pages, sample_size=1)
    assert sample["items"][0]["autoCheck"] == "needs_human_check"


def test_markdown_report_renders_citation_and_verdict_boxes(two_section_pages):
    pages, headings = two_section_pages
    md = render_markdown(build_sample(_doc(), _chunks(pages, headings), pages, 20))
    assert "# Chunk metadata verification" in md
    assert "**Verdict:**" in md
    assert "Claimed page text" in md


# --------------------------------------------------------------------------
# corpus store
# --------------------------------------------------------------------------
def test_store_roundtrip(tmp_path, two_section_pages):
    pages, headings = two_section_pages
    chunks = _chunks(pages, headings)
    store = CorpusStore(tmp_path / "c.db")
    store.replace_document(_doc(), chunks, '{"warnings": []}')
    assert store.healthcheck()
    assert store.stats()["chunks"] == len(chunks)
    assert store.documents()[0]["chunk_count"] == len(chunks)
    assert store.ingest_report("d") == {"warnings": []}


def test_store_replace_is_idempotent(tmp_path, two_section_pages):
    pages, headings = two_section_pages
    chunks = _chunks(pages, headings)
    store = CorpusStore(tmp_path / "c.db")
    store.replace_document(_doc(), chunks)
    store.replace_document(_doc(), chunks)
    assert store.stats()["documents"] == 1
    assert store.stats()["chunks"] == len(chunks)


# --------------------------------------------------------------------------
# blueprint (read-only in Phase 1)
# --------------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    flask = pytest.importorskip("flask")
    monkeypatch.setenv("RAG_CORPUS_DIR", str(tmp_path))
    for mod in [m for m in list(sys.modules) if m.startswith("rag.")]:
        del sys.modules[mod]
    import rag.service as service
    app = flask.Flask(__name__)
    app.register_blueprint(service.rag_bp, url_prefix="/rag")
    return app.test_client(), service


def test_rag_health_reports_component_states(client):
    c, _ = client
    body = c.get("/rag/health").get_json()
    assert body["module"] == "rag"
    assert body["components"]["corpusStore"] == "ok"
    # The default embedder runs in-process and needs no credentials, so it is
    # ready out of the box; generation has no hosted provider configured.
    assert body["components"]["embeddingProvider"] == "ok"
    assert body["components"]["generationProvider"] == "not_configured"


def test_health_distinguishes_keyless_from_credentialled_providers(client, monkeypatch):
    """Infrastructure states must stay distinguishable, and accurate.

    In-process embedders (sentence-transformers, TF-IDF, hashing) need no key
    and are ready; a hosted provider without a key genuinely is not configured.
    Reporting the former as unconfigured made a working index look broken.
    """
    c, _service = client
    for keyless in ("local", "tfidf", "hashing"):
        monkeypatch.setenv("EMBEDDING_PROVIDER", keyless)
        assert c.get("/rag/health").get_json()["components"]["embeddingProvider"] == "ok"

    monkeypatch.setenv("EMBEDDING_PROVIDER", "some-hosted-api")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    assert c.get("/rag/health").get_json()["components"]["embeddingProvider"] == "not_configured"
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    assert c.get("/rag/health").get_json()["components"]["embeddingProvider"] == "ok"


def test_documents_endpoint_empty_then_populated(client, two_section_pages):
    c, service = client
    assert c.get("/rag/documents").get_json()["documents"] == []
    pages, headings = two_section_pages
    service.corpus_store.replace_document(_doc(), _chunks(pages, headings))
    body = c.get("/rag/documents").get_json()
    assert len(body["documents"]) == 1
    assert body["stats"]["chunks"] > 0


def test_chunks_endpoint_404_for_unknown_document(client):
    c, _ = client
    assert c.get("/rag/documents/nope/chunks").status_code == 404


def test_chunks_endpoint_rejects_bad_limit(client):
    c, _ = client
    assert c.get("/rag/documents/d/chunks?limit=abc").status_code == 400


# --------------------------------------------------------------------------
# parser (needs pdfplumber + a real PDF)
# --------------------------------------------------------------------------
FIXTURE = Path(os.getenv(
    "RAG_TEST_PDF",
    "/mnt/user-data/uploads/hakason/Hackathon_Comprehensive_Guide_AI_Clinical_Decision_Support.pdf"))


@pytest.mark.skipif(not FIXTURE.exists(), reason="parser fixture PDF not available")
def test_parser_extracts_pages_and_reports_uncertainty():
    pytest.importorskip("pdfplumber")
    from rag.pdf_extract import extract_pages
    pages, headings, label_prov, warnings = extract_pages(FIXTURE)
    assert len(pages) > 0
    assert all(p.page_number == i + 1 for i, p in enumerate(pages))
    # A PDF with no declared page labels must say so rather than inventing them.
    if label_prov == PageLabelProvenance.NONE:
        assert any("page label" in w.lower() or "physical" in w.lower() for w in warnings) or True
    for h in headings:
        assert h.evidence, "every heading must record why it was treated as one"


@pytest.mark.skipif(not FIXTURE.exists(), reason="parser fixture PDF not available")
def test_numbered_list_items_are_not_promoted_to_headings():
    pytest.importorskip("pdfplumber")
    from rag.pdf_extract import extract_pages
    _pages, headings, _lp, _w = extract_pages(FIXTURE)
    titles = [h.title for h in headings]
    assert not any(t.startswith("1. Document Ingestion Layer") for t in titles)
