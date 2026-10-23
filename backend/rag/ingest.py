"""Ingestion orchestration + CLI.

    python -m rag.ingest <pdf> --title "..." [--publisher ...] [--url ...]
                               [--version ...] [--licence ...] [--id ...]
                               [--verify-sample 20] [--out DIR] [--dry-run]

Phase 1 only: parse → detect sections → chunk → verify metadata → persist.
No embeddings are generated and no vector index is written; that step is gated
on the embedding-provider decision (adaptation plan, Phase 0.5 / 1.7).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from rag.chunking import chunk_document
from rag.config import CORPUS_DIR, CORPUS_VERSION, chunk_config
from rag.contracts import Chunk, IngestReport, SectionProvenance, SourceDocument
from rag.pdf_extract import extract_pages, file_sha256
from rag.store import CorpusStore

logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "document"


def ingest_pdf(path: Path, *, title: str, document_id: Optional[str] = None,
               publisher: Optional[str] = None, source_url: Optional[str] = None,
               version: Optional[str] = None, licence_note: Optional[str] = None,
               target_chars: Optional[int] = None, overlap_chars: Optional[int] = None):
    """Parse and chunk ``path``. Returns ``(document, chunks, report, pages)``."""
    if not path.exists():
        raise FileNotFoundError(f"Guideline PDF not found: {path}")

    pages, headings, label_provenance, warnings = extract_pages(path)
    doc_id = document_id or slugify(title)

    document = SourceDocument(
        document_id=doc_id,
        title=title,
        publisher=publisher,
        source_url=source_url,
        version=version,
        licence_note=licence_note,
        file_sha256=file_sha256(path),
        page_count=len(pages),
        corpus_version=CORPUS_VERSION,
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )

    chunks = chunk_document(
        pages, headings,
        document_id=doc_id,
        document_title=title,
        page_label_provenance=label_provenance,
        target_chars=target_chars,
        overlap_chars=overlap_chars,
    )

    covered = set()
    for c in chunks:
        covered.update(range(c.page_number, c.page_end + 1))
    pages_with_text = [p.page_number for p in pages if not p.is_empty]
    gaps = sorted(set(pages_with_text) - covered)

    prov_counts: dict = {}
    for c in chunks:
        prov_counts[c.section_provenance.value] = prov_counts.get(c.section_provenance.value, 0) + 1

    if gaps:
        warnings.append(
            f"{len(gaps)} page(s) with extractable text produced no chunks: {gaps}. "
            "Their content is NOT retrievable."
        )
    unknown = prov_counts.get(SectionProvenance.UNKNOWN.value, 0)
    if unknown:
        pct = round(100 * unknown / max(1, len(chunks)), 1)
        warnings.append(
            f"{unknown} chunk(s) ({pct}%) have no section attribution. Their citations will "
            "read '(section not determined)' rather than a fabricated section name."
        )
    if label_provenance.value == "none":
        warnings.append(
            "This PDF declares no printed page labels. Citations use the physical PDF page "
            "index. If the document shows different printed page numbers, verify that the "
            "physical index is acceptable for citation before relying on it."
        )

    report = IngestReport(
        document=document,
        chunk_count=len(chunks),
        chunk_config=chunk_config(),
        pages_with_text=len(pages_with_text),
        pages_empty=[p.page_number for p in pages if p.is_empty],
        page_coverage_gaps=gaps,
        headings_found=len(headings),
        section_provenance_counts=prov_counts,
        page_label_provenance=label_provenance,
        warnings=warnings,
    )
    return document, chunks, report, pages


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="rag.ingest", description="Ingest a guideline PDF")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--id", dest="document_id", default=None)
    parser.add_argument("--publisher", default=None)
    parser.add_argument("--url", dest="source_url", default=None)
    parser.add_argument("--version", default=None)
    parser.add_argument("--licence", dest="licence_note", default=None)
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--chunk-overlap", type=int, default=None)
    parser.add_argument("--verify-sample", type=int, default=20,
                        help="Number of chunks in the human verification sample (0 to skip)")
    parser.add_argument("--out", type=Path, default=None, help="Output dir for reports")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and report without writing to the corpus store")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    document, chunks, report, pages = ingest_pdf(
        args.pdf, title=args.title, document_id=args.document_id, publisher=args.publisher,
        source_url=args.source_url, version=args.version, licence_note=args.licence_note,
        target_chars=args.chunk_size, overlap_chars=args.chunk_overlap)

    out_dir = args.out or (CORPUS_DIR / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_json = report.model_dump_json(indent=2)
    (out_dir / f"{document.document_id}_ingest_report.json").write_text(report_json, encoding="utf-8")

    if args.verify_sample:
        from rag.verify import write_verification_sample
        md_path, json_path = write_verification_sample(
            document, chunks, pages, out_dir, sample_size=args.verify_sample)
        print(f"Verification sample : {md_path}")
        print(f"                      {json_path}")

    if not args.dry_run:
        CorpusStore().replace_document(document, chunks, report_json)

    print(f"\nDocument   : {document.title}  [{document.document_id}]")
    print(f"SHA-256    : {document.file_sha256[:16]}…")
    print(f"Pages      : {document.page_count} ({report.pages_with_text} with text)")
    print(f"Chunks     : {report.chunk_count}")
    print(f"Headings   : {report.headings_found}")
    print(f"Provenance : {report.section_provenance_counts}")
    print(f"Page labels: {report.page_label_provenance.value}")
    print(f"Config     : {report.chunk_config}")
    if report.warnings:
        print("\nWARNINGS (uncertainty is reported, not hidden):")
        for w in report.warnings:
            print(f"  ! {w}")
    else:
        print("\nNo parsing warnings.")
    if args.dry_run:
        print("\n(dry run — corpus store not written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
