"""PDF extraction: pages, page labels, and heading candidates.

Design rule for this module (adaptation plan, Phase 1 gate):
    Never invent metadata. Where the PDF does not tell us something, the field
    is left empty and the uncertainty is recorded, not smoothed over.

Two heading sources, in priority order:
  1. The PDF's own outline / bookmark tree — authoritative when present.
  2. Font-and-numbering evidence from the page layout — a fallback, always
     labelled as such via ``SectionProvenance`` so downstream consumers (and
     the human doing the 20-chunk verification) can see it was inferred.
"""
from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

import pdfplumber
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser

from rag.config import (EXCLUDE_BIBLIOGRAPHY, EXCLUDE_FRONT_MATTER, HEADING_MAX_CHARS,
                        HEADING_NUMBERED_MIN, HEADING_SIZE_RATIO, PDF_LAYOUT,
                        PDF_X_TOLERANCE)
from rag.contracts import Heading, PageLabelProvenance, PageRecord, SectionProvenance

logger = logging.getLogger(__name__)

# "1.", "1.2", "3.4.5 Title" — a strong structural signal in guideline documents.
# A section heading: "7", "7.2", "12.3.4" followed by a Title-cased phrase.
# The capital is what separates "7.2 Clinical characteristics" (a heading) from
# "2 years. Therefore, SAVR is recommended" (body text that happens to start
# with a numeral).
NUMBERED_HEADING_RE = re.compile(
    r"^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-Z][A-Za-z].*)$")
# A running head such as "3664 ESC Guidelines".
RUNNING_HEAD_RE = re.compile(r"^\s*\d{3,5}\s+[A-Z]")
# The opening line of a numbered bibliography entry: "41. Roger VL, Weston SA, ..."
BIBLIO_ENTRY_RE = re.compile(r"^\s*\d{1,4}\.\s+[A-Z][A-Za-z\u2019'-]+\s+[A-Z]{1,3}[,.]")
# Lines that are almost certainly body text despite being short.
SENTENCE_TAIL_RE = re.compile(r"[.;:,]\s*$")
# Glyphs pdfplumber could not map to a character.
CID_RE = re.compile(r"\(cid:\d+\)")
# A line made only of leader dots / rules carries no content in any document.
LEADER_ONLY_RE = re.compile(r"^[\s.\u00b7\u2022_\-–—]*$")
# Runs of spaced leader dots hanging off either end of a line.
TRAILING_LEADER_RE = re.compile(r"(?:\s+[.\u00b7]){1,}\s*$")
LEADING_LEADER_RE = re.compile(r"^(?:[.\u00b7]\s+){1,}")
# A table-of-contents entry: text, a run of leader dots, then a page number.
TOC_ENTRY_RE = re.compile(r"\.\s*\.\s*\.[\s.]*\d*\s*$")
# Characters that are decoration, never evidence of a heading font.
DECORATIVE = set(".\u00b7\u2022_-–—")
# A standalone page folio in a running head or foot.
FOLIO_RE = re.compile(r"^\s*(\d{1,5})\s*$")


def clean_text(text: str) -> str:
    """Strip unmappable glyphs and leader-dot-only lines.

    Both are extraction artefacts, not content. Removing them keeps them out of
    chunk text (where they would pollute embeddings) and out of citations.
    """
    out = []
    for line in (text or "").splitlines():
        line = CID_RE.sub("", line)
        # Leader dots bleed in from the journal's overlay rules. They sit at the
        # start or end of a line and are never content.
        # Table-of-contents entries repeat headings verbatim with a page number.
        # Left in, they become near-duplicate chunks that compete with the real
        # section text in retrieval.
        if TOC_ENTRY_RE.search(line):
            continue
        line = TRAILING_LEADER_RE.sub("", LEADING_LEADER_RE.sub("", line)).rstrip()
        if LEADER_ONLY_RE.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def detect_gutter(page) -> Optional[float]:
    """Find the vertical whitespace channel of a two-column page.

    Returns the gutter x-position, or ``None`` when the page has no clean
    channel (single-column text, or a full-width table). Bins character centres
    across the middle of the page and looks for a genuine empty valley flanked
    by text on both sides — an ambiguous page is reported as single-column
    rather than split on a guess.
    """
    try:
        chars = page.chars
    except Exception:  # noqa: BLE001
        return None
    if len(chars) < 200:
        return None

    width = float(page.width)
    bins: Counter = Counter()
    for ch in chars:
        centre = (float(ch["x0"]) + float(ch["x1"])) / 2
        bins[int(centre // 5) * 5] += 1

    lo, hi = int(width * 0.38 // 5) * 5, int(width * 0.62 // 5) * 5
    band = [(b, bins.get(b, 0)) for b in range(lo, hi + 5, 5)]
    empty = [b for b, n in band if n == 0]
    if not empty:
        return None

    gutter = empty[len(empty) // 2]
    left = sum(n for b, n in bins.items() if b < gutter)
    right = sum(n for b, n in bins.items() if b > gutter)
    # Both sides must carry real text, or this is a margin, not a gutter.
    if left < len(chars) * 0.2 or right < len(chars) * 0.2:
        return None
    return float(gutter)


def extract_page_text(page, report_raw: Optional[list] = None) -> str:
    """Extract page text, reading columns in order when the page has two.

    ``report_raw`` collects each page's table-of-contents density measured on the
    RAW extraction. It has to be measured before cleaning, because cleaning
    removes the very leader-dot lines the measurement counts.
    """
    if PDF_LAYOUT != "single":
        gutter = detect_gutter(page)
        if gutter is not None:
            try:
                left = page.crop((0, 0, gutter, page.height)).extract_text(
                    x_tolerance=PDF_X_TOLERANCE) or ""
                right = page.crop((gutter, 0, page.width, page.height)).extract_text(
                    x_tolerance=PDF_X_TOLERANCE) or ""
                raw = left + "\n" + right
                if report_raw is not None:
                    report_raw.append(toc_density(raw))
                return clean_text(raw)
            except Exception:  # noqa: BLE001 - fall back to whole-page extraction
                logger.info("Column crop failed on a page; using whole-page extraction")
    raw = page.extract_text(x_tolerance=PDF_X_TOLERANCE) or ""
    if report_raw is not None:
        report_raw.append(toc_density(raw))
    return clean_text(raw)


def toc_density(text: str) -> float:
    """Fraction of a page's lines that look like table-of-contents entries."""
    lines = [l for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return 0.0
    return sum(1 for l in lines if TOC_ENTRY_RE.search(l)) / len(lines)


def detect_toc_pages(densities: List[float], threshold: float = 0.25,
                     search_limit: int = 12) -> List[int]:
    """Return 1-based page numbers of a front-matter table of contents.

    A contents page reproduces every heading in the document verbatim. Indexed,
    those fragments compete with the sections they point to and win, because
    they are short and keyword-dense — exactly the wrong thing to retrieve. Only
    the front matter is searched, so a mid-document list is not mistaken for one.
    """
    return [i + 1 for i, density in enumerate(densities[:search_limit])
            if density >= threshold]


def bibliography_density(text: str) -> float:
    """Fraction of a page's lines that open a numbered bibliography entry."""
    lines = [l for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return 0.0
    return sum(1 for l in lines if BIBLIO_ENTRY_RE.match(l)) / len(lines)


def detect_bibliography_tail(pages: List[PageRecord], threshold: float = 0.12,
                             min_pages: int = 3) -> List[int]:
    """Return the page numbers of a trailing reference list, if there is one.

    A bibliography carries no clinical recommendations — only pointers to other
    papers. Indexing it competes directly with the guideline text it cites and
    drags down retrieval precision, so it is identified and excluded rather than
    silently embedded.

    Only a run anchored at the END of the document counts; a dense citation
    block in the middle of a chapter is not a bibliography and is left alone.
    """
    if len(pages) < min_pages + 1:
        return []
    tail: List[int] = []
    for record in reversed(pages):
        if bibliography_density(record.text) >= threshold:
            tail.append(record.page_number)
        else:
            break
    return sorted(tail) if len(tail) >= min_pages else []


def page_margin_numbers(page) -> List[int]:
    """Standalone integers sitting in the top or bottom margin of a page."""
    try:
        chars = page.chars
    except Exception:  # noqa: BLE001
        return []
    if not chars:
        return []
    height = float(page.height)
    top_band, bottom_band = height * 0.07, height * 0.93

    lines: dict = {}
    for ch in chars:
        top = float(ch.get("top", 0))
        if top <= top_band or top >= bottom_band:
            lines.setdefault(round(top, 0), []).append(ch)

    found = []
    for top in sorted(lines):
        ordered = sorted(lines[top], key=lambda c: float(c.get("x0", 0)))
        text = "".join(c.get("text", "") for c in ordered).strip()
        for token in re.split(r"\s+", text):
            match = FOLIO_RE.match(token)
            if match:
                found.append(int(match.group(1)))
    return found


def detect_printed_folios(pages_text: List[str], page_count: int):
    """Recover the printed page numbers and verify them as a single offset.

    Journal PDFs are often paginated 3599-3726 while the PDF's own page-label
    tree says 1-128. Citing the physical index would send a reader to the wrong
    page. This reads standalone numbers out of the running heads and feet, then
    checks whether ALL of them fit one linear mapping ``folio = index + offset``.

    A verified offset is applied to every page. If the observed folios disagree,
    nothing is applied — a partially-correct page number is worse than none.
    Returns ``(labels, provenance, note)``.
    """
    observed = {}
    for idx, candidates in enumerate(pages_text):
        # ``pages_text`` here carries the margin-number candidates per page.
        for value in candidates or []:
            if 1 <= value <= 100000:
                observed[idx] = value
                break

    if len(observed) < 3:
        return [None] * page_count, PageLabelProvenance.NONE, ""

    offsets = Counter(folio - idx for idx, folio in observed.items())
    offset, agree = offsets.most_common(1)[0]
    agreement = agree / len(observed)
    if agreement < 0.9:
        return ([None] * page_count, PageLabelProvenance.NONE,
                f"Printed page numbers were found on {len(observed)} pages but do not follow a "
                f"single sequence (best offset matches only {agreement:.0%}). Physical page "
                "indices are used instead; printed folios were NOT guessed.")

    labels = [str(i + offset) for i in range(page_count)]
    return (labels, PageLabelProvenance.DERIVED_FOLIO,
            f"Printed page numbers recovered from the page headers/footers: physical page 1 "
            f"is printed page {offset + 0}. Verified against {len(observed)} observed folios "
            f"({agreement:.0%} agreement).")


def file_sha256(path: Path) -> str:
    """Content hash of the source PDF — pins the corpus to an exact file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_outline(path: Path) -> List[Tuple[int, str]]:
    """Return the PDF's declared outline as ``[(level, title), ...]``.

    Returns an empty list when the document declares no outline. We do not
    fabricate one.
    """
    try:
        with open(path, "rb") as fh:
            document = PDFDocument(PDFParser(fh))
            return [(int(level), str(title).strip())
                    for level, title, _dest, _a, _se in document.get_outlines()
                    if str(title).strip()]
    except Exception as exc:  # PDFNoOutlines and friends
        logger.info("No usable PDF outline (%s)", type(exc).__name__)
        return []


def read_page_labels(pdf: "pdfplumber.PDF") -> Tuple[List[Optional[str]], PageLabelProvenance]:
    """Return printed page labels when the PDF declares a page-label tree.

    Guideline PDFs extracted from journals often carry printed page numbers
    (e.g. 3599-3726) that differ from the physical index. Citing the physical
    index when a printed label exists would produce a citation a clinician
    cannot follow, so we prefer the declared label and record which we used.
    """
    try:
        catalog = pdf.doc.catalog
        if "PageLabels" not in catalog:
            return [None] * len(pdf.pages), PageLabelProvenance.NONE
    except Exception:
        return [None] * len(pdf.pages), PageLabelProvenance.NONE

    try:
        from pdfminer.pdftypes import resolve1

        labels_obj = resolve1(catalog["PageLabels"])
        nums = resolve1(labels_obj.get("Nums")) if labels_obj else None
        if not nums:
            return [None] * len(pdf.pages), PageLabelProvenance.NONE

        ranges = []
        for i in range(0, len(nums) - 1, 2):
            start = int(resolve1(nums[i]))
            spec = resolve1(nums[i + 1]) or {}
            prefix = spec.get("P")
            prefix = prefix.decode("latin-1") if isinstance(prefix, bytes) else (prefix or "")
            start_at = int(resolve1(spec.get("St")) or 1)
            style = spec.get("S")
            style = style.name if hasattr(style, "name") else str(style or "D")
            ranges.append((start, prefix, start_at, style))
        if not ranges:
            return [None] * len(pdf.pages), PageLabelProvenance.NONE

        labels: List[Optional[str]] = []
        for idx in range(len(pdf.pages)):
            active = ranges[0]
            for r in ranges:
                if r[0] <= idx:
                    active = r
                else:
                    break
            start, prefix, start_at, style = active
            value = start_at + (idx - start)
            if style == "D":
                labels.append(f"{prefix}{value}")
            elif style in ("r", "R"):
                labels.append(f"{prefix}{_roman(value, upper=(style == 'R'))}")
            elif style in ("a", "A"):
                labels.append(f"{prefix}{_alpha(value, upper=(style == 'A'))}")
            else:
                labels.append(f"{prefix}{value}" if prefix else None)
        return labels, PageLabelProvenance.DECLARED
    except Exception as exc:  # noqa: BLE001 — malformed label trees are common
        logger.info("Page-label tree present but unreadable (%s); using physical index",
                    type(exc).__name__)
        return [None] * len(pdf.pages), PageLabelProvenance.NONE


def _roman(n: int, upper: bool = True) -> str:
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
            (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out.upper() if upper else out


def _alpha(n: int, upper: bool = True) -> str:
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(ord("a") + rem) + out
    return out.upper() if upper else out


def extract_pages(path: Path) -> Tuple[List[PageRecord], List[Heading], PageLabelProvenance, List[str]]:
    """Extract pages, detect headings, and report extraction warnings.

    Returns ``(pages, headings, page_label_provenance, warnings)``.
    """
    warnings: List[str] = []
    outline = read_outline(path)
    outline_titles = {t.strip().lower(): lvl for lvl, t in outline}

    pages: List[PageRecord] = []
    headings: List[Heading] = []
    ambiguous_lines = 0
    margin_numbers: List[List[int]] = []
    raw_toc_density: List[float] = []

    with pdfplumber.open(str(path)) as pdf:
        labels, label_provenance = read_page_labels(pdf)

        # Body font size = the most common character size across the document.
        size_counter: Counter = Counter()
        for page in pdf.pages:
            for ch in page.chars:
                size_counter[round(float(ch.get("size", 0)), 1)] += 1
        body_size = size_counter.most_common(1)[0][0] if size_counter else 0.0
        if not body_size:
            warnings.append(
                "No character metrics available — the PDF may be scanned images. "
                "Heading detection and section attribution are unavailable; OCR would be required."
            )

        for idx, page in enumerate(pdf.pages):
            page_no = idx + 1
            try:
                text = extract_page_text(page, report_raw=raw_toc_density)
            except Exception as exc:  # noqa: BLE001
                text = ""
                warnings.append(f"Page {page_no}: text extraction failed ({type(exc).__name__})")

            record = PageRecord(
                page_number=page_no,
                page_label=labels[idx] if idx < len(labels) else None,
                page_label_provenance=label_provenance,
                text=text,
                char_count=len(text),
                is_empty=not text.strip(),
            )
            if record.is_empty and page.chars:
                record.extraction_warning = (
                    "Page has glyphs but no extractable text layer (possible scanned image)."
                )
                warnings.append(f"Page {page_no}: {record.extraction_warning}")
            pages.append(record)
            margin_numbers.append(page_margin_numbers(page))

            if body_size:
                page_headings, ambiguous = _detect_headings_on_page(
                    page, page_no, body_size, outline_titles)
                headings.extend(page_headings)
                ambiguous_lines += ambiguous

    # A declared label tree that merely repeats the physical index tells a reader
    # nothing the index does not. Prefer a verified printed folio when one exists.
    declared_is_trivial = all(
        (p.page_label or "") == str(p.page_number) for p in pages) if pages else True
    if label_provenance == PageLabelProvenance.NONE or declared_is_trivial:
        folios, folio_prov, folio_note = detect_printed_folios(margin_numbers, len(pages))
        if folio_prov == PageLabelProvenance.DERIVED_FOLIO:
            for page_record, label in zip(pages, folios):
                page_record.page_label = label
                page_record.page_label_provenance = folio_prov
            label_provenance = folio_prov
            warnings.append(folio_note)
            if declared_is_trivial and "PageLabels" not in (folio_note or ""):
                warnings.append(
                    "The PDF's declared page labels merely repeated the physical page index, "
                    "so the printed folio recovered from the page itself is used for citations.")
        elif folio_note:
            warnings.append(folio_note)

    # When a document is systematically numbered, its numbering IS its structure.
    # Font-based guesses then add noise (glossaries, captions, emphasised runs)
    # without adding sections, so they are dropped rather than mixed in.
    numbered = [h for h in headings if h.provenance == SectionProvenance.NUMBERED_HEADING]
    if len(numbered) >= HEADING_NUMBERED_MIN:
        dropped = len(headings) - len(numbered)
        headings = numbered
        if dropped:
            warnings.append(
                f"This document has {len(numbered)} numbered section headings, so its own "
                f"numbering is used as the section structure and {dropped} font-only heading "
                "candidates were discarded. Set RAG_HEADING_NUMBERED_MIN higher to keep them.")

    if EXCLUDE_FRONT_MATTER:
        toc_pages = detect_toc_pages(raw_toc_density)
        if toc_pages:
            labels = [p.page_label for p in pages if p.page_number in (toc_pages[0], toc_pages[-1])]
            for record in pages:
                if record.page_number in set(toc_pages):
                    record.text = ""
                    record.is_empty = True
                    record.extraction_warning = "excluded: table of contents"
            printed = f" (printed {labels[0]}-{labels[-1]})" if all(labels) else ""
            warnings.append(
                f"Pages {toc_pages[0]}-{toc_pages[-1]}{printed} were identified as the table of "
                "contents and EXCLUDED. Contents entries duplicate every heading verbatim and "
                "outrank the sections they point to in retrieval. Set "
                "RAG_EXCLUDE_FRONT_MATTER=false to keep them.")

    if EXCLUDE_BIBLIOGRAPHY:
        biblio = detect_bibliography_tail(pages)
        if biblio:
            first, last = biblio[0], biblio[-1]
            labels = [p.page_label for p in pages if p.page_number in (first, last)]
            for record in pages:
                if record.page_number in set(biblio):
                    record.text = ""
                    record.is_empty = True
                    record.extraction_warning = "excluded: trailing reference list"
            printed = f" (printed {labels[0]}-{labels[-1]})" if all(labels) else ""
            warnings.append(
                f"Pages {first}-{last}{printed} were identified as the trailing reference list "
                f"({len(biblio)} of {len(pages)} pages) and EXCLUDED from the corpus. A "
                "bibliography contains no recommendations, and indexing it competes with the "
                "guideline text. Set RAG_EXCLUDE_BIBLIOGRAPHY=false to keep it.")

    if ambiguous_lines:
        warnings.append(
            f"{ambiguous_lines} numbered bold line(s) at body font size were NOT treated as "
            "headings (they are usually list items). If this document styles its headings that "
            "way, section attribution will be under-detected — check the verification sample."
        )

    if not headings:
        warnings.append(
            "No headings detected. Every chunk will carry section_provenance='unknown'. "
            "Section-aware chunking is degraded to page-aware chunking for this document."
        )

    if outline and not any(h.provenance == SectionProvenance.OUTLINE for h in headings):
        warnings.append(
            f"PDF declares an outline with {len(outline)} entries, but none matched detected "
            "heading text on the page it points to. Section attribution falls back to layout "
            "evidence and should be treated as inferred."
        )

    return pages, headings, label_provenance, warnings


def _line_text(line_chars: List[dict]) -> str:
    """Reconstruct a line's text from its characters, restoring word gaps."""
    ordered = sorted(line_chars, key=lambda c: float(c.get("x0", 0)))
    parts: List[str] = []
    previous_x1 = None
    for ch in ordered:
        text = ch.get("text", "")
        x0 = float(ch.get("x0", 0))
        if previous_x1 is not None and (x0 - previous_x1) > PDF_X_TOLERANCE:
            parts.append(" ")
        parts.append(text)
        previous_x1 = float(ch.get("x1", x0))
    return "".join(parts).strip()


def _line_font_stats(line_chars: List[dict]) -> Tuple[float, bool]:
    """Return ``(max_size, any_bold)`` for the characters of one visual line.

    Decorative glyphs are excluded. This journal overlays 11.8 pt leader dots
    across pages whose body text is 7-9 pt; letting a dot set the line's font
    size marked essentially every line as a heading.
    """
    content = [c for c in line_chars if (c.get("text") or "").strip()
               and (c.get("text") or "") not in DECORATIVE]
    if not content:
        return 0.0, False
    max_size = max(float(c.get("size", 0)) for c in content)
    bold = any("bold" in str(c.get("fontname", "")).lower() for c in content)
    return round(max_size, 1), bold


def _column_boxes(page) -> List[tuple]:
    """Return the crop boxes to scan for headings, in reading order."""
    if PDF_LAYOUT != "single":
        gutter = detect_gutter(page)
        if gutter is not None:
            return [(0, 0, gutter, page.height), (gutter, 0, page.width, page.height)]
    return [(0, 0, page.width, page.height)]


def _detect_headings_on_page(page, page_no: int, body_size: float,
                             outline_titles: dict) -> Tuple[List[Heading], int]:
    """Detect headings using numbering + font evidence.

    Every returned heading carries the evidence that justified it, so a human
    reviewing the verification sample can judge the call rather than trust it.

    Returns ``(headings, ambiguous_count)``. Ambiguous lines — numbered and bold
    but at body size, which in practice are usually numbered *list items* rather
    than headings — are counted and reported, never silently promoted.
    """
    found: List[Heading] = []
    ambiguous = 0
    try:
        _ = page.chars
    except Exception:  # noqa: BLE001
        return found, ambiguous

    # Scan each column separately. Grouping by y-coordinate across a two-column
    # page would splice unrelated left and right lines into one phantom heading.
    candidates: List[tuple] = []
    for box in _column_boxes(page):
        try:
            column_chars = page.crop(box).chars
        except Exception:  # noqa: BLE001
            continue

        by_top: dict = {}
        for ch in column_chars:
            by_top.setdefault(round(float(ch.get("top", 0)), 0), []).append(ch)
        # Build each line's text from its own characters, inserting a space where
        # the horizontal gap exceeds the word tolerance. Pairing pdfplumber's
        # extracted lines with char runs by position looked simpler but silently
        # misaligns whenever the two disagree on line breaks, which attaches one
        # line's font evidence to another line's words.
        for top in sorted(by_top):
            candidates.append((_line_text(by_top[top]), by_top[top]))

    for text, line_chars in candidates:
        if TOC_ENTRY_RE.search(text):
            ambiguous += 1
            continue
        text = TRAILING_LEADER_RE.sub("", LEADING_LEADER_RE.sub("", CID_RE.sub("", text))).strip()
        if not text or len(text) > HEADING_MAX_CHARS:
            continue
        if sum(ch.isalpha() for ch in text) < 4:
            continue
        if RUNNING_HEAD_RE.match(text):
            continue

        size, bold = _line_font_stats(line_chars)
        larger = size >= body_size * HEADING_SIZE_RATIO
        numbered = NUMBERED_HEADING_RE.match(text)

        # An outline entry matching this line is the strongest evidence available.
        if text.lower() in outline_titles:
            found.append(Heading(
                title=text, level=max(1, outline_titles[text.lower()]), page_number=page_no,
                provenance=SectionProvenance.OUTLINE,
                evidence="matches an entry in the PDF outline/bookmark tree",
            ))
            continue

        if numbered and not larger and bold:
            # Bold + numbered but the same size as body text. In guideline PDFs
            # this is far more often a numbered list item than a section
            # heading. Promoting it would fabricate section structure, so it is
            # counted and surfaced instead.
            ambiguous += 1
            continue

        if numbered and larger and not SENTENCE_TAIL_RE.search(text) and "." not in numbered.group(2)[:-1]:
            depth = numbered.group(1).count(".") + 1
            found.append(Heading(
                title=text, level=depth, page_number=page_no,
                provenance=SectionProvenance.NUMBERED_HEADING,
                evidence=(f"numbering '{numbered.group(1)}' + font size {size} "
                          f"vs body {body_size}{' + bold' if bold else ''}"),
            ))
            continue

        if larger and not SENTENCE_TAIL_RE.search(text) and size > body_size:
            found.append(Heading(
                title=text, level=1, page_number=page_no,
                provenance=SectionProvenance.STYLED_HEADING,
                evidence=f"font size {size} vs body {body_size}{' + bold' if bold else ''}",
            ))

    return found, ambiguous
