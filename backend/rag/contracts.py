"""Pydantic contracts for the RAG module.

Mirrors the boundary-validation pattern already used in ``backend/contracts.py``.

Phase 1 defines only ingestion-side types. ``PatientContext`` and ``EvidenceSet``
(plan §6.8) are deliberately NOT defined here yet — they belong to the
generation phase, and defining them early would invite accidental coupling
between patient context and guideline evidence.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SectionProvenance(str, Enum):
    """How a chunk's section attribution was determined.

    This is recorded per chunk and surfaced in the verification sample. It is
    the mechanism that keeps parsing uncertainty visible instead of hiding it
    behind a plausible-looking section title.
    """

    OUTLINE = "outline"                    # from the PDF's own bookmark tree (authoritative)
    NUMBERED_HEADING = "numbered_heading"  # matched a numbering pattern AND a heading font
    STYLED_HEADING = "styled_heading"      # font/size evidence only, no numbering
    INHERITED = "inherited"                # continues a heading detected earlier
    UNKNOWN = "unknown"                    # no heading evidence — NOT guessed


class PageLabelProvenance(str, Enum):
    """How a chunk's printed page label was determined."""

    DECLARED = "declared"        # the PDF declares an explicit page label / numbering tree
    DERIVED_FOLIO = "derived_folio"  # printed folio read off the page and verified across the doc
    NONE = "none"                # nothing usable — physical index is all we have


class PageRecord(BaseModel):
    """One physical page of a source PDF."""

    page_number: int = Field(..., ge=1, description="1-based physical page index in the PDF")
    page_label: Optional[str] = Field(None, description="Printed page label, if the PDF declares one")
    page_label_provenance: PageLabelProvenance = PageLabelProvenance.NONE
    text: str = ""
    char_count: int = 0
    is_empty: bool = False
    extraction_warning: Optional[str] = None


class Heading(BaseModel):
    """A detected or declared section heading."""

    title: str
    level: int = Field(1, ge=1)
    page_number: int = Field(..., ge=1)
    provenance: SectionProvenance
    evidence: str = Field("", description="Why this line was treated as a heading (audit trail)")


class Chunk(BaseModel):
    """A retrievable unit of guideline text with its source attribution."""

    chunk_index: int = Field(..., ge=0)
    content: str

    # --- Source attribution (the fields citations are built from) ---
    document_id: str
    document_title: str
    section_title: Optional[str] = None
    section_path: Optional[str] = None
    section_provenance: SectionProvenance = SectionProvenance.UNKNOWN

    page_number: int = Field(..., ge=1, description="Physical page where this chunk starts")
    page_end: int = Field(..., ge=1, description="Physical page where this chunk ends")
    page_label: Optional[str] = None
    page_label_provenance: PageLabelProvenance = PageLabelProvenance.NONE
    spans_pages: bool = False

    # --- Measurable size (no token claims without a tokenizer) ---
    char_count: int = 0
    word_count: int = 0

    corpus_version: str = "v1"

    @property
    def citation(self) -> str:
        """Human-readable citation string: Document › Section › p.N."""
        page = self.page_label or str(self.page_number)
        if self.page_end != self.page_number:
            end = str(self.page_end)
            page = f"{page}-{end}"
        section = self.section_title or "(section not determined)"
        return f"{self.document_title} › {section} › p.{page}"


class SourceDocument(BaseModel):
    """Provenance record for an ingested guideline PDF."""

    document_id: str
    title: str
    publisher: Optional[str] = None
    source_url: Optional[str] = None
    version: Optional[str] = None
    licence_note: Optional[str] = None
    file_sha256: str
    page_count: int = Field(..., ge=1)
    corpus_version: str = "v1"
    ingested_at: Optional[str] = None


class IngestReport(BaseModel):
    """Summary of one ingestion run — the Phase 1 Definition-of-Done artefact."""

    document: SourceDocument
    chunk_count: int = 0
    chunk_config: dict = Field(default_factory=dict)
    pages_with_text: int = 0
    pages_empty: List[int] = Field(default_factory=list)
    page_coverage_gaps: List[int] = Field(default_factory=list)
    headings_found: int = 0
    section_provenance_counts: dict = Field(default_factory=dict)
    page_label_provenance: PageLabelProvenance = PageLabelProvenance.NONE
    warnings: List[str] = Field(default_factory=list)
