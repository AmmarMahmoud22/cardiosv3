"""Contracts for grounded generation, refusal, and system failure.

Three top-level outcomes, and they are DELIBERATELY separate types:

    GroundedAnswer   the guidelines supported an answer
    Refusal          a clinical judgement: the retrieved evidence is not
                     sufficient, or the question is out of scope
    SystemFailure    infrastructure broke (no model, provider down, corpus
                     unreachable). Never a statement about the guidelines.

Collapsing the last two would let an outage read as "the guidelines do not
cover this", which is a clinical claim the system has no basis to make.

``PatientContext`` and ``EvidenceSet`` are separate types on purpose. The
citation validator accepts only ``EvidenceSet``, so passing patient context
where evidence is expected is a type error rather than a silent grounding
breach. Patient context is also rendered without evidence IDs, so there is no
token a model could emit that would resolve to it.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RefusalReason(str, Enum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    OUT_OF_SCOPE = "out_of_scope"
    NO_VALID_CITATIONS = "no_valid_citations"


class FailureKind(str, Enum):
    NO_INDEX = "no_index"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    MALFORMED_MODEL_OUTPUT = "malformed_model_output"
    EVIDENCE_SET_CHANGED = "evidence_set_changed"
    CORPUS_UNAVAILABLE = "corpus_unavailable"


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
class PatientContext(BaseModel):
    """Clinical context for interpreting the question. NEVER evidence.

    Has no evidence identifier by construction. Cardios' own risk and ECG
    outputs may populate this; they can shape what is asked, never what is
    recommended.
    """

    summary: str
    source: str = Field(..., description="e.g. synthetic-demo, cardios-risk-model, cardios-ecg")
    is_synthetic: bool = True

    def render(self) -> str:
        origin = "Synthetic demo data" if self.is_synthetic else f"Source: {self.source}"
        return (f"{origin}. {self.summary.strip()}\n"
                "These are automated screening outputs, not guideline evidence.")


class EvidenceItem(BaseModel):
    """One retrieved guideline passage. The only citable unit."""

    evidence_id: str
    content: str
    document_id: str
    document_title: str
    chunk_index: int
    section_title: Optional[str] = None
    section_path: Optional[str] = None
    section_provenance: str = "unknown"
    page_number: int
    page_end: int
    page_label: Optional[str] = None
    score: float = 0.0

    @property
    def page_display(self) -> str:
        page = self.page_label or str(self.page_number)
        return f"{page}-{self.page_end}" if self.page_end != self.page_number else page

    def render(self) -> str:
        section = self.section_title or "(section not determined)"
        return (f"[{self.evidence_id}] {self.document_title} > {section} > "
                f"p.{self.page_display}\n\"{self.content.strip()}\"")


class EvidenceSet(BaseModel):
    """The exact evidence bound to one retrieval. Citations close over this."""

    retrieval_id: str
    chunk_set_hash: str
    question: str
    model_id: str = ""
    items: List[EvidenceItem] = Field(default_factory=list)

    @property
    def ids(self) -> List[str]:
        return [i.evidence_id for i in self.items]

    def by_id(self, evidence_id: str) -> Optional[EvidenceItem]:
        for item in self.items:
            if item.evidence_id == evidence_id:
                return item
        return None

    @property
    def top_score(self) -> float:
        return max((i.score for i in self.items), default=0.0)

    def render(self) -> str:
        return "\n\n".join(i.render() for i in self.items)

    @classmethod
    def from_retrieval(cls, result: dict) -> "EvidenceSet":
        return cls(
            retrieval_id=result["retrievalId"],
            chunk_set_hash=result["chunkSetHash"],
            question=result["question"],
            model_id=result.get("modelId", ""),
            items=[EvidenceItem(
                evidence_id=c["evidenceId"], content=c["content"],
                document_id=c["documentId"], document_title=c["documentTitle"],
                chunk_index=c["chunkIndex"], section_title=c.get("sectionTitle"),
                section_path=c.get("sectionPath"),
                section_provenance=c.get("sectionProvenance", "unknown"),
                page_number=c["pageNumber"], page_end=c["pageEnd"],
                page_label=c.get("pageLabel"), score=c.get("score", 0.0),
            ) for c in result["chunks"]],
        )


# ---------------------------------------------------------------------------
# outputs
# ---------------------------------------------------------------------------
class Citation(BaseModel):
    evidence_id: str
    document: str
    section: Optional[str] = None
    page: str = Field(..., description="Page as displayed to the reader (printed folio if known)")
    page_index: int = Field(
        0, description="Physical PDF page index. Kept alongside `page` because the two differ "
                       "whenever a document is paginated independently of its PDF (a journal "
                       "reprint runs 3599-3726 over PDF pages 1-128), and evaluation labels "
                       "must be comparable to one of them without guessing which.")
    page_index_end: int = 0

    def render(self) -> str:
        section = self.section or "(section not determined)"
        return f"{self.document} > {section} > p.{self.page} [{self.evidence_id}]"


class Recommendation(BaseModel):
    text: str = Field(..., description="The recommendation, in the system's own words")
    excerpt: str = Field(..., description="Verbatim supporting text from the cited evidence")
    citations: List[Citation] = Field(default_factory=list)
    excerpt_verified: bool = Field(
        False, description="The excerpt was found verbatim in the cited evidence")


class SufficiencyVerdict(BaseModel):
    """Why the system judged the evidence sufficient (or not)."""

    signal: str
    value: float
    threshold: float
    sufficient: bool
    calibrated: bool = Field(
        False, description="False until a calibration record exists for this corpus + model")
    calibration_id: Optional[str] = None
    note: str = ""


class GroundedAnswer(BaseModel):
    mode: Literal["answer"] = "answer"
    retrieval_id: str
    chunk_set_hash: str
    question: str
    recommendations: List[Recommendation] = Field(default_factory=list)
    citation_coverage: float = Field(
        0.0, description="Fraction of recommendations carrying >=1 valid citation")
    excerpt_accuracy: float = Field(
        0.0, description="Fraction of recommendations whose excerpt was verified verbatim")
    dropped_claims: List[str] = Field(
        default_factory=list,
        description="Claims removed because they cited nothing in this evidence set")
    generator: str = ""
    sufficiency: Optional[SufficiencyVerdict] = None
    latency_ms: float = 0.0
    disclaimer: str = ""
    disclaimer_version: str = ""
    not_medical_advice: bool = True


class Refusal(BaseModel):
    """A clinical judgement about the evidence. NOT an error."""

    mode: Literal["refusal"] = "refusal"
    retrieval_id: Optional[str] = None
    chunk_set_hash: Optional[str] = None
    question: str = ""
    reason: RefusalReason
    message: str
    sufficiency: Optional[SufficiencyVerdict] = None
    evidence_considered: int = 0
    generator: str = ""
    latency_ms: float = 0.0
    disclaimer: str = ""
    disclaimer_version: str = ""
    is_evidence_refusal: bool = True
    not_medical_advice: bool = True


class SystemFailure(BaseModel):
    """Infrastructure failure. Explicitly NOT an evidence judgement."""

    mode: Literal["system_failure"] = "system_failure"
    kind: FailureKind
    message: str
    detail: str = ""
    remedy: str = ""
    question: str = ""
    retrieval_id: Optional[str] = None
    is_evidence_refusal: bool = False
    not_medical_advice: bool = True
