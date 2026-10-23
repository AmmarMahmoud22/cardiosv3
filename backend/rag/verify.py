"""The Phase-1 metadata verification gate.

Produces a human-reviewable sample of chunks. For each sampled chunk it prints
the citation the system WOULD emit, alongside the text of the page that
citation points at — so a reviewer can confirm the attribution without
reverse-engineering the parser, and can catch a confident-but-wrong citation,
which is the one failure mode that stays invisible downstream.

The sample is deterministic (evenly spaced across the document) so re-running
after a parser change compares like with like.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

from rag.contracts import Chunk, PageRecord, SectionProvenance, SourceDocument

PAGE_EXCERPT_CHARS = 420
CHUNK_EXCERPT_CHARS = 420


def select_sample(chunks: List[Chunk], sample_size: int = 20) -> List[Chunk]:
    """Evenly spaced, deterministic sample across the whole document."""
    if not chunks:
        return []
    if len(chunks) <= sample_size:
        return list(chunks)
    step = len(chunks) / sample_size
    return [chunks[min(len(chunks) - 1, int(i * step))] for i in range(sample_size)]


def build_sample(document: SourceDocument, chunks: List[Chunk],
                 pages: List[PageRecord], sample_size: int = 20) -> dict:
    page_text = {p.page_number: (p.text or "") for p in pages}
    sample = select_sample(chunks, sample_size)

    items = []
    for c in sample:
        head = " ".join(c.content.split())[:CHUNK_EXCERPT_CHARS]
        # Does the start of the chunk actually appear on the page it claims?
        probe = " ".join(c.content.split())[:60].lower()
        claimed = " ".join(page_text.get(c.page_number, "").split()).lower()
        auto = "present_on_claimed_page" if probe and probe in claimed else "needs_human_check"
        items.append({
            "chunkIndex": c.chunk_index,
            "citation": c.citation,
            "documentTitle": c.document_title,
            "sectionTitle": c.section_title,
            "sectionPath": c.section_path,
            "sectionProvenance": c.section_provenance.value,
            "pageNumber": c.page_number,
            "pageEnd": c.page_end,
            "pageLabel": c.page_label,
            "pageLabelProvenance": c.page_label_provenance.value,
            "spansPages": c.spans_pages,
            "charCount": c.char_count,
            "autoCheck": auto,
            "chunkExcerpt": head,
            "claimedPageExcerpt": " ".join(page_text.get(c.page_number, "").split())[:PAGE_EXCERPT_CHARS],
        })

    auto_ok = sum(1 for i in items if i["autoCheck"] == "present_on_claimed_page")
    unknown_section = sum(1 for i in items if i["sectionProvenance"] == SectionProvenance.UNKNOWN.value)
    return {
        "documentId": document.document_id,
        "documentTitle": document.title,
        "fileSha256": document.file_sha256,
        "sampleSize": len(items),
        "autoCheckPassed": auto_ok,
        "autoCheckNeedsHuman": len(items) - auto_ok,
        "sampleChunksWithoutSection": unknown_section,
        "humanVerdict": None,
        "items": items,
    }


def render_markdown(sample: dict) -> str:
    lines = [
        f"# Chunk metadata verification — {sample['documentTitle']}",
        "",
        f"**Document ID:** `{sample['documentId']}`  ",
        f"**File SHA-256:** `{sample['fileSha256'][:32]}…`  ",
        f"**Sample size:** {sample['sampleSize']} chunks (evenly spaced, deterministic)",
        "",
        "## Gate criterion",
        "",
        "At least **19 of 20** sampled chunks must carry the correct document, the correct page,",
        "and a plausible section title. Confirm each row against the PDF. The *Claimed page text*",
        "column is the actual extracted text of the page the citation points at — if the chunk",
        "excerpt does not appear there, the attribution is wrong.",
        "",
        "| Auto-check | Meaning |",
        "|---|---|",
        "| `present_on_claimed_page` | The chunk's opening words were found verbatim on the page it cites. |",
        "| `needs_human_check` | Not found automatically (often a page-spanning chunk). Verify by hand. |",
        "",
        f"**Automated pre-check:** {sample['autoCheckPassed']}/{sample['sampleSize']} located on their claimed page; "
        f"{sample['autoCheckNeedsHuman']} need a human look.  ",
        f"**Chunks with no section attribution in this sample:** {sample['sampleChunksWithoutSection']} "
        "(these are reported, not guessed).",
        "",
        "---",
        "",
    ]
    for item in sample["items"]:
        lines += [
            f"### {item['chunkIndex']}. `{item['citation']}`",
            "",
            f"- **Section provenance:** `{item['sectionProvenance']}`"
            f"{'  ⚠️ inferred from layout, not declared by the PDF' if item['sectionProvenance'] in ('styled_heading', 'numbered_heading') else ''}",
            f"- **Section path:** {item['sectionPath'] or '_(not determined)_'}",
            f"- **Pages:** {item['pageNumber']}"
            + (f"–{item['pageEnd']} (spans a page break)" if item["spansPages"] else "")
            + f" · label: {item['pageLabel'] or '_none declared_'} (`{item['pageLabelProvenance']}`)",
            f"- **Auto-check:** `{item['autoCheck']}` · {item['charCount']} chars",
            "",
            "**Chunk text (start):**",
            "",
            f"> {item['chunkExcerpt']}",
            "",
            "**Claimed page text (start):**",
            "",
            f"> {item['claimedPageExcerpt']}",
            "",
            "**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def write_verification_sample(document: SourceDocument, chunks: List[Chunk],
                              pages: List[PageRecord], out_dir: Path,
                              sample_size: int = 20) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = build_sample(document, chunks, pages, sample_size)
    md_path = out_dir / f"{document.document_id}_verification_sample.md"
    json_path = out_dir / f"{document.document_id}_verification_sample.json"
    md_path.write_text(render_markdown(sample), encoding="utf-8")
    json_path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
    return md_path, json_path
