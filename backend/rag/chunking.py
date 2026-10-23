"""Section-aware chunking with per-chunk page attribution.

Chunks never cross a section boundary. Within a section, text is split at a
configurable target size with configurable overlap (both env-driven, because
Phase 3 sweeps them).

Page attribution is derived from the physical page each line came from, so a
chunk that spans a page break records both ends rather than picking one and
hoping. Where no heading evidence exists, ``section_title`` stays ``None`` and
``section_provenance`` is ``unknown`` — it is never filled with a guess.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

from rag.config import (CHUNK_MIN_CHARS, CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS,
                        CORPUS_VERSION)
from rag.contracts import Chunk, Heading, PageLabelProvenance, PageRecord, SectionProvenance

_WS = re.compile(r"[ \t]+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip()


class _SectionState:
    """Tracks the active heading stack so ``section_path`` reflects nesting."""

    def __init__(self) -> None:
        self.stack: List[Heading] = []

    def push(self, heading: Heading) -> None:
        while self.stack and self.stack[-1].level >= heading.level:
            self.stack.pop()
        self.stack.append(heading)

    @property
    def title(self) -> Optional[str]:
        return self.stack[-1].title if self.stack else None

    @property
    def path(self) -> Optional[str]:
        return " › ".join(h.title for h in self.stack) if self.stack else None

    @property
    def provenance(self) -> SectionProvenance:
        return self.stack[-1].provenance if self.stack else SectionProvenance.UNKNOWN


def _line_stream(pages: List[PageRecord],
                 headings: List[Heading]) -> Iterable[Tuple[str, int, Optional[Heading]]]:
    """Yield ``(line_text, page_number, heading_or_None)`` in document order."""
    by_page: dict = {}
    for h in headings:
        by_page.setdefault(h.page_number, []).append(h)

    for page in pages:
        if not page.text:
            continue
        pending = list(by_page.get(page.page_number, []))
        for raw in page.text.splitlines():
            line = _norm(raw)
            if not line:
                continue
            match = None
            for h in pending:
                if _norm(h.title) == line:
                    match = h
                    break
            if match is not None:
                pending.remove(match)
                yield line, page.page_number, match
            else:
                yield line, page.page_number, None


def chunk_document(pages: List[PageRecord],
                   headings: List[Heading],
                   *,
                   document_id: str,
                   document_title: str,
                   page_label_provenance: PageLabelProvenance = PageLabelProvenance.NONE,
                   target_chars: int = None,
                   overlap_chars: int = None,
                   min_chars: int = None) -> List[Chunk]:
    """Split ``pages`` into section-aware chunks with page attribution."""
    target = target_chars if target_chars is not None else CHUNK_TARGET_CHARS
    overlap = overlap_chars if overlap_chars is not None else CHUNK_OVERLAP_CHARS
    minimum = min_chars if min_chars is not None else CHUNK_MIN_CHARS
    if overlap >= target:
        raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")

    labels = {p.page_number: p.page_label for p in pages}
    state = _SectionState()
    chunks: List[Chunk] = []

    # buffer of (line, page) for the current section
    buffer: List[Tuple[str, int]] = []
    buf_title: Optional[str] = None
    buf_path: Optional[str] = None
    buf_prov: SectionProvenance = SectionProvenance.UNKNOWN

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        for piece in _split_buffer(buffer, target, overlap, minimum):
            text = " ".join(line for line, _ in piece).strip()
            if not text:
                continue
            page_start = min(pg for _, pg in piece)
            page_end = max(pg for _, pg in piece)
            chunks.append(Chunk(
                chunk_index=len(chunks),
                content=text,
                document_id=document_id,
                document_title=document_title,
                section_title=buf_title,
                section_path=buf_path,
                section_provenance=buf_prov,
                page_number=page_start,
                page_end=page_end,
                page_label=labels.get(page_start),
                page_label_provenance=page_label_provenance,
                spans_pages=page_end != page_start,
                char_count=len(text),
                word_count=len(text.split()),
                corpus_version=CORPUS_VERSION,
            ))
        buffer = []

    for line, page_no, heading in _line_stream(pages, headings):
        if heading is not None:
            flush()
            state.push(heading)
            buf_title, buf_path, buf_prov = state.title, state.path, state.provenance
            continue
        if not buffer:
            # First body line of a section (or of the document, if no heading
            # has been seen yet — in which case provenance stays UNKNOWN).
            buf_title, buf_path, buf_prov = state.title, state.path, state.provenance
            if buf_title is None:
                buf_prov = SectionProvenance.UNKNOWN
            elif buf_prov != SectionProvenance.OUTLINE:
                # Body text under a detected heading inherits that heading's
                # attribution; mark it inherited once we are past the heading line.
                buf_prov = state.provenance
        buffer.append((line, page_no))

    flush()
    return chunks


def _split_buffer(buffer: List[Tuple[str, int]], target: int, overlap: int,
                  minimum: int) -> List[List[Tuple[str, int]]]:
    """Greedy line-packing into ~``target``-char pieces with ``overlap`` carry-over."""
    pieces: List[List[Tuple[str, int]]] = []
    current: List[Tuple[str, int]] = []
    size = 0

    for line, page in buffer:
        addition = len(line) + 1
        if current and size + addition > target:
            pieces.append(current)
            carry: List[Tuple[str, int]] = []
            carried = 0
            for prev_line, prev_page in reversed(current):
                if carried >= overlap:
                    break
                carry.insert(0, (prev_line, prev_page))
                carried += len(prev_line) + 1
            current = carry
            size = carried
        current.append((line, page))
        size += addition

    if current:
        # Fold a runt tail back into the previous piece rather than emitting a
        # fragment too small to be independently retrievable.
        tail_chars = sum(len(l) + 1 for l, _ in current)
        if pieces and tail_chars < minimum:
            pieces[-1] = pieces[-1] + [item for item in current if item not in pieces[-1]]
        else:
            pieces.append(current)
    return pieces
