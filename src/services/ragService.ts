import { getApiBaseUrl, getAuthHeaders } from '../lib/api';

/**
 * Client for the Cardios RAG evidence layer.
 *
 * Phase 2/3: retrieval only. Generation is not implemented yet, which is
 * deliberate — the hackathon requires that retrieved evidence is displayed
 * BEFORE any answer is generated, so the evidence panel is built and verified
 * first and generation is wired into the same retrieval afterwards.
 */

export type SectionProvenance =
  | 'outline'
  | 'numbered_heading'
  | 'styled_heading'
  | 'inherited'
  | 'unknown';

export interface EvidenceChunk {
  evidenceId: string;
  rank: number;
  score: number;
  content: string;
  citation: string;
  documentId: string;
  documentTitle: string;
  chunkIndex: number;
  sectionTitle: string | null;
  sectionPath: string | null;
  sectionProvenance: SectionProvenance;
  pageNumber: number;
  pageEnd: number;
  pageLabel: string | null;
  pageLabelProvenance: 'declared' | 'none';
  spansPages: boolean;
}

export interface RetrievalResult {
  state: 'ok';
  retrievalId: string;
  chunkSetHash: string;
  question: string;
  k: number;
  modelId: string;
  corpusSize: number;
  latencyMs: number;
  chunks: EvidenceChunk[];
  scores: number[];
  generation: 'not_implemented';
}

/**
 * An infrastructure failure — no vector index, no embedding model, backend
 * unreachable. This is NOT the same as "the guidelines do not cover this
 * question", which is an evidence judgement introduced in a later phase. The
 * `isEvidenceRefusal: false` flag makes the distinction explicit on the wire so
 * the UI can never present a technical outage as a clinical conclusion.
 */
export interface RetrievalUnavailable {
  state: 'unavailable' | 'invalid_request';
  error: string;
  detail?: string;
  remedy?: string;
  isEvidenceRefusal: false;
}

export type RetrievalResponse = RetrievalResult | RetrievalUnavailable;

export interface RagHealth {
  module: string;
  version: string;
  phase: string;
  components: Record<string, string>;
  corpus: {
    documents: number;
    chunks: number;
    embeddedChunks?: number;
    embeddingModels?: { model_id: string; dimension: number; n: number }[];
  };
  chunkConfig: Record<string, unknown>;
}

export interface RagDocument {
  document_id: string;
  title: string;
  publisher: string | null;
  source_url: string | null;
  version: string | null;
  page_count: number;
  chunk_count: number;
  corpus_version: string;
  ingestWarnings?: string[];
  sectionProvenanceCounts?: Record<string, number>;
  pageCoverageGaps?: number[];
}

/* ------------------------------------------------------------------ *
 * Grounded answers
 *
 * Three outcome shapes, kept separate all the way to the UI:
 *   answer          the guidelines supported a cited recommendation
 *   refusal         a clinical judgement about evidence sufficiency
 *   system_failure  infrastructure broke — never a claim about the guidelines
 * ------------------------------------------------------------------ */

export interface Citation {
  evidence_id: string;
  document: string;
  section: string | null;
  page: string;
}

export interface Recommendation {
  text: string;
  excerpt: string;
  citations: Citation[];
  excerpt_verified: boolean;
}

export interface SufficiencyVerdict {
  signal: string;
  value: number;
  threshold: number;
  sufficient: boolean;
  calibrated: boolean;
  calibration_id: string | null;
  note: string;
}

interface AnswerBase {
  retrieval_id: string | null;
  chunk_set_hash: string | null;
  question: string;
  generator: string;
  latency_ms: number;
  disclaimer: string;
  not_medical_advice: boolean;
  evidence?: {
    retrieval_id: string;
    chunk_set_hash: string;
    items: {
      evidence_id: string;
      content: string;
      document_title: string;
      section_title: string | null;
      section_provenance: string;
      page_number: number;
      page_end: number;
      page_label: string | null;
      score: number;
    }[];
  };
}

export interface GroundedAnswer extends AnswerBase {
  mode: 'answer';
  recommendations: Recommendation[];
  citation_coverage: number;
  excerpt_accuracy: number;
  dropped_claims: string[];
  sufficiency: SufficiencyVerdict | null;
}

export interface EvidenceRefusal extends AnswerBase {
  mode: 'refusal';
  reason: 'insufficient_evidence' | 'out_of_scope' | 'no_valid_citations';
  message: string;
  sufficiency: SufficiencyVerdict | null;
  evidence_considered: number;
  is_evidence_refusal: true;
}

export interface AnswerSystemFailure {
  mode: 'system_failure';
  kind: string;
  message: string;
  detail: string;
  remedy: string;
  question: string;
  retrieval_id: string | null;
  is_evidence_refusal: false;
  not_medical_advice: boolean;
}

export type AnswerResponse = GroundedAnswer | EvidenceRefusal | AnswerSystemFailure;

const jsonHeaders = { 'Content-Type': 'application/json' };

/**
 * Authorization header, if a session happens to exist.
 *
 * The evidence endpoints do not require a signed-in user, so a Supabase outage
 * must not stop a guideline lookup. `getSession()` can hang or reject when the
 * project is paused or unreachable, which would otherwise take this page down
 * with it — so it is bounded by a short timeout and any failure degrades to
 * sending no header at all.
 */
const optionalAuthHeaders = async (): Promise<Record<string, string>> => {
  try {
    return await Promise.race([
      getAuthHeaders(),
      new Promise<Record<string, string>>((resolve) => setTimeout(() => resolve({}), 2000)),
    ]);
  } catch {
    return {};
  }
};

export const retrieveEvidence = async (
  question: string,
  k = 5,
): Promise<RetrievalResponse> => {
  const auth = await optionalAuthHeaders();
  const response = await fetch(`${getApiBaseUrl()}/rag/retrieve`, {
    method: 'POST',
    headers: { ...jsonHeaders, ...auth },
    body: JSON.stringify({ question, k }),
  });
  return (await response.json()) as RetrievalResponse;
};

export const fetchRagHealth = async (): Promise<RagHealth> => {
  const response = await fetch(`${getApiBaseUrl()}/rag/health`);
  if (!response.ok) throw new Error(`RAG health check failed (${response.status})`);
  return (await response.json()) as RagHealth;
};

export const fetchRagDocuments = async (): Promise<{ documents: RagDocument[] }> => {
  const response = await fetch(`${getApiBaseUrl()}/rag/documents`);
  if (!response.ok) throw new Error(`Could not load corpus (${response.status})`);
  return (await response.json()) as { documents: RagDocument[] };
};

export const isRetrievalOk = (r: RetrievalResponse): r is RetrievalResult =>
  r.state === 'ok';

/**
 * Ask for a grounded answer.
 *
 * Pass `retrievalId` to generate from evidence the user has already seen — the
 * backend reloads that exact chunk set and never searches again, so the
 * displayed evidence is provably the evidence the generator received.
 */
export const requestAnswer = async (
  params: { question?: string; retrievalId?: string; k?: number },
): Promise<AnswerResponse> => {
  const auth = await optionalAuthHeaders();
  const response = await fetch(`${getApiBaseUrl()}/rag/answer`, {
    method: 'POST',
    headers: { ...jsonHeaders, ...auth },
    body: JSON.stringify({
      question: params.question,
      retrievalId: params.retrievalId,
      k: params.k ?? 5,
    }),
  });
  return (await response.json()) as AnswerResponse;
};

export const isGroundedAnswer = (a: AnswerResponse): a is GroundedAnswer =>
  a.mode === 'answer';
export const isEvidenceRefusal = (a: AnswerResponse): a is EvidenceRefusal =>
  a.mode === 'refusal';
export const isSystemFailure = (a: AnswerResponse): a is AnswerSystemFailure =>
  a.mode === 'system_failure';
