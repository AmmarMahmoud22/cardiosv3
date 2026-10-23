"""Environment-driven configuration for the RAG module.

Kept separate from ``backend/security.py`` so the RAG module stays additive and
self-contained. Values are read lazily so tests can monkeypatch the environment.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Where ingested corpora are persisted (Phase 1 uses a local SQLite staging
# store; the pgvector migration in supabase/migrations/ takes over once the
# embedding provider is chosen — see Phase 1.6/1.7 of the adaptation plan).
CORPUS_DIR = Path(os.getenv("RAG_CORPUS_DIR", str(BASE_DIR / "corpus")))
CORPUS_DB = CORPUS_DIR / "corpus.db"

# Chunking parameters. Deliberately env-driven: Phase 3 sweeps these, and the
# sweep must not require code edits.
CHUNK_TARGET_CHARS = int(os.getenv("RAG_CHUNK_SIZE", "1200"))
CHUNK_OVERLAP_CHARS = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
CHUNK_MIN_CHARS = int(os.getenv("RAG_CHUNK_MIN_CHARS", "120"))

# Heading detection thresholds (fallback path only; the PDF outline is used
# when the document provides one).
HEADING_SIZE_RATIO = float(os.getenv("RAG_HEADING_SIZE_RATIO", "1.12"))
HEADING_MAX_CHARS = int(os.getenv("RAG_HEADING_MAX_CHARS", "140"))
# If a document yields at least this many numbered headings, treat its numbering
# as the section structure and ignore font-only heading candidates.
HEADING_NUMBERED_MIN = int(os.getenv("RAG_HEADING_NUMBERED_MIN", "20"))
# Exclude a trailing reference list from the corpus (see pdf_extract).
EXCLUDE_BIBLIOGRAPHY = os.getenv("RAG_EXCLUDE_BIBLIOGRAPHY", "true").lower() in {"1", "true", "yes"}
# Exclude a front-matter table of contents from the corpus (see pdf_extract).
EXCLUDE_FRONT_MATTER = os.getenv("RAG_EXCLUDE_FRONT_MATTER", "true").lower() in {"1", "true", "yes"}

# PDF text extraction. Journal-style PDFs need a tighter word-gap tolerance
# than pdfplumber's default of 3.0, or words run together ("patientswithHFrEF").
PDF_X_TOLERANCE = float(os.getenv("RAG_PDF_X_TOLERANCE", "1.5"))
# "auto" detects a two-column layout per page and reads columns in order;
# "single" forces whole-page extraction.
PDF_LAYOUT = os.getenv("RAG_PDF_LAYOUT", "auto").strip().lower()

# Corpus version tag; recorded on every chunk so a calibration record can be
# bound to the corpus it was calibrated against (see plan §6.7).
CORPUS_VERSION = os.getenv("RAG_CORPUS_VERSION", "v1")


def chunk_config() -> dict:
    """Return the active chunk configuration (logged with every ingest run)."""
    return {
        "targetChars": CHUNK_TARGET_CHARS,
        "overlapChars": CHUNK_OVERLAP_CHARS,
        "minChars": CHUNK_MIN_CHARS,
        "headingSizeRatio": HEADING_SIZE_RATIO,
        "pdfXTolerance": PDF_X_TOLERANCE,
        "pdfLayout": PDF_LAYOUT,
        "excludeBibliography": EXCLUDE_BIBLIOGRAPHY,
        "excludeFrontMatter": EXCLUDE_FRONT_MATTER,
        "corpusVersion": CORPUS_VERSION,
    }
