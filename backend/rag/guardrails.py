"""Citation validation and unsupported-claim handling.

The central rule: a citation is valid only if it names an evidence id present
in THIS retrieval's evidence set. The validator's signature accepts only an
``EvidenceSet``, so patient context cannot reach it — and because patient
context is rendered without evidence ids, there is nothing for a model to cite
even if it tried.

Claims that cite nothing valid are DROPPED, not displayed with a warning. A
plausible-sounding sentence with no source is the exact failure mode grounding
is supposed to prevent, so it does not reach the user.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from rag.answer_contracts import (Citation, EvidenceSet, Recommendation, Refusal,
                                  RefusalReason)

logger = logging.getLogger(__name__)

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")
# PDF line-break hyphenation: "symp- toms" is one word split across a line.
# Genuine compounds ("co-transporter") carry no space after the hyphen and are
# left alone.
_DEHYPHEN = re.compile(r"(\w)[-\u2010\u2011]\s+(\w)")


def _norm(text: str) -> str:
    text = _DEHYPHEN.sub(r"\1\2", text or "")
    return _WS.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


def excerpt_is_verbatim(excerpt: str, evidence_text: str) -> bool:
    """Is ``excerpt`` genuinely present in the cited evidence?

    Normalised comparison, so PDF hyphenation and whitespace artefacts do not
    produce false negatives — but it is still containment, not similarity: a
    reworded 'excerpt' fails, which is the point.
    """
    excerpt_n, evidence_n = _norm(excerpt), _norm(evidence_text)
    return bool(excerpt_n) and excerpt_n in evidence_n


def build_recommendations(raw: List[dict],
                          evidence: EvidenceSet) -> Tuple[List[Recommendation], List[str]]:
    """Validate raw model recommendations against the closed evidence set.

    Returns ``(kept, dropped_claims)``.
    """
    kept: List[Recommendation] = []
    dropped: List[str] = []
    valid_ids = set(evidence.ids)

    for entry in raw or []:
        text = (entry.get("text") or "").strip()
        excerpt = (entry.get("excerpt") or "").strip()
        ids = [str(i).strip() for i in (entry.get("evidence_ids") or [])]
        if not text:
            continue

        good_ids = [i for i in ids if i in valid_ids]
        if not good_ids:
            dropped.append(text)
            logger.info("Dropped uncited claim (cited %s, valid %s)", ids, sorted(valid_ids))
            continue

        citations, verified = [], False
        for evidence_id in good_ids:
            item = evidence.by_id(evidence_id)
            if item is None:
                continue
            citations.append(Citation(
                evidence_id=evidence_id, document=item.document_title,
                section=item.section_title, page=item.page_display,
                page_index=item.page_number, page_index_end=item.page_end))
            if excerpt and excerpt_is_verbatim(excerpt, item.content):
                verified = True

        if not citations:
            dropped.append(text)
            continue

        kept.append(Recommendation(text=text, excerpt=excerpt, citations=citations,
                                   excerpt_verified=verified))

    return kept, dropped


def citation_coverage(recommendations: List[Recommendation]) -> float:
    if not recommendations:
        return 0.0
    with_citation = sum(1 for r in recommendations if r.citations)
    return round(with_citation / len(recommendations), 4)


def excerpt_accuracy(recommendations: List[Recommendation]) -> float:
    if not recommendations:
        return 0.0
    verified = sum(1 for r in recommendations if r.excerpt_verified)
    return round(verified / len(recommendations), 4)


def refusal_for_no_valid_citations(evidence: EvidenceSet, dropped: List[str],
                                   generator: str = "") -> Refusal:
    return Refusal(
        retrieval_id=evidence.retrieval_id,
        chunk_set_hash=evidence.chunk_set_hash,
        question=evidence.question,
        reason=RefusalReason.NO_VALID_CITATIONS,
        message=("An answer was produced but none of its statements could be traced to the "
                 "retrieved guideline text, so it has been withheld. Cardios does not show "
                 "clinical statements it cannot cite."),
        evidence_considered=len(evidence.items),
        generator=generator,
    )


def refusal_for_insufficient_evidence(evidence: EvidenceSet, verdict,
                                      generator: str = "",
                                      message: Optional[str] = None) -> Refusal:
    return Refusal(
        retrieval_id=evidence.retrieval_id,
        chunk_set_hash=evidence.chunk_set_hash,
        question=evidence.question,
        reason=RefusalReason.INSUFFICIENT_EVIDENCE,
        message=message or (
            "The guideline evidence retrieved for this question is not strong enough to "
            "answer safely. Please rephrase with more clinical detail, or consult the "
            "guideline directly."),
        sufficiency=verdict,
        evidence_considered=len(evidence.items),
        generator=generator,
    )
