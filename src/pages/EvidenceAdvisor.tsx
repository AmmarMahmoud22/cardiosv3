import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileText,
  Hash,
  Quote,
  Search,
  ServerCrash,
  ShieldAlert,
  Timer,
} from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import MedicalDisclaimer from '../components/ui/MedicalDisclaimer';
import {
  AnswerResponse,
  EvidenceChunk,
  GroundedAnswer,
  RagDocument,
  RagHealth,
  RetrievalResponse,
  RetrievalResult,
  fetchRagDocuments,
  fetchRagHealth,
  isEvidenceRefusal,
  isGroundedAnswer,
  isRetrievalOk,
  isSystemFailure,
  requestAnswer,
  retrieveEvidence,
} from '../services/ragService';

/**
 * Retrieved Evidence panel.
 *
 * The hackathon requires that retrieved chunks are displayed BEFORE generation,
 * with their document, section, page, score, and evidence ID visible. This page
 * is that surface, and it is deliberately complete and usable on its own with no
 * generation layer behind it.
 *
 * It never invents an answer and never presents a technical failure as a
 * clinical conclusion: a backend/index outage renders as a system-unavailable
 * state, visually and textually distinct from any statement about evidence.
 */

const PROVENANCE_LABEL: Record<string, string> = {
  outline: 'declared by the PDF outline',
  numbered_heading: 'inferred from numbering + font',
  styled_heading: 'inferred from font styling',
  inherited: 'inherited from an earlier heading',
  unknown: 'not determined',
};

const scoreTone = (score: number): string => {
  if (score >= 0.6) return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  if (score >= 0.35) return 'bg-amber-100 text-amber-800 border-amber-200';
  return 'bg-slate-100 text-slate-700 border-slate-200';
};

const EvidenceCard: React.FC<{ chunk: EvidenceChunk }> = ({ chunk }) => {
  const pageText = chunk.spansPages
    ? `p.${chunk.pageLabel ?? chunk.pageNumber}–${chunk.pageEnd}`
    : `p.${chunk.pageLabel ?? chunk.pageNumber}`;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-900 px-2.5 py-1 font-mono text-xs font-semibold text-white">
          {chunk.evidenceId}
        </span>
        <span
          className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreTone(chunk.score)}`}
          title="Cosine similarity between the question and this chunk"
        >
          score {chunk.score.toFixed(4)}
        </span>
        <span className="text-xs text-slate-500">rank {chunk.rank}</span>
      </header>

      <dl className="mb-3 grid gap-1.5 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-400">Document</dt>
          <dd className="flex items-start gap-1.5 text-slate-800">
            <FileText className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden="true" />
            <span>{chunk.documentTitle}</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-400">Section</dt>
          <dd className="text-slate-800">
            {chunk.sectionTitle ?? (
              <em className="text-slate-500">not determined</em>
            )}
            <span className="ml-1 text-xs text-slate-400">
              ({PROVENANCE_LABEL[chunk.sectionProvenance] ?? chunk.sectionProvenance})
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-400">Page</dt>
          <dd className="text-slate-800">
            {pageText}
            {chunk.pageLabelProvenance === 'none' && (
              <span className="ml-1 text-xs text-slate-400">(physical index)</span>
            )}
          </dd>
        </div>
      </dl>

      <p className="whitespace-pre-wrap rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">
        {chunk.content}
      </p>

      <footer className="mt-3 font-mono text-xs text-slate-500">{chunk.citation}</footer>
    </article>
  );
};

const AnswerPanel: React.FC<{ answer: GroundedAnswer }> = ({ answer }) => (
  <section className="space-y-4" aria-label="Grounded answer">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900">
        <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-hidden="true" />
        Grounded answer
      </h2>
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>citations {(answer.citation_coverage * 100).toFixed(0)}%</span>
        <span>excerpts verified {(answer.excerpt_accuracy * 100).toFixed(0)}%</span>
        <span className="flex items-center gap-1">
          <Timer className="h-3.5 w-3.5" aria-hidden="true" />
          {answer.latency_ms} ms
        </span>
        <span>via {answer.generator}</span>
      </div>
    </div>

    {answer.recommendations.map((rec, i) => (
      <article key={i} className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5">
        <p className="text-sm leading-6 text-slate-900">{rec.text}</p>

        <div className="mt-3 flex gap-2 rounded-xl bg-white p-3">
          <Quote className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-300" aria-hidden="true" />
          <p className="text-sm italic leading-6 text-slate-600">{rec.excerpt}</p>
        </div>

        <footer className="mt-3 flex flex-wrap items-center gap-2">
          {rec.citations.map((c) => (
            <span
              key={c.evidence_id}
              className="rounded-full border border-slate-200 bg-white px-3 py-1 font-mono text-xs text-slate-700"
            >
              {c.document} › {c.section ?? '(section not determined)'} › p.{c.page}
              <span className="ml-2 rounded bg-slate-900 px-1.5 py-0.5 text-white">
                {c.evidence_id}
              </span>
            </span>
          ))}
          {rec.excerpt_verified ? (
            <span className="text-xs font-medium text-emerald-700">
              ✓ excerpt found verbatim in the cited passage
            </span>
          ) : (
            <span className="text-xs font-medium text-amber-700">
              ! excerpt not matched verbatim — check the source
            </span>
          )}
        </footer>
      </article>
    ))}

    {answer.dropped_claims.length > 0 && (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <p className="font-semibold">
          {answer.dropped_claims.length} statement(s) withheld
        </p>
        <p className="mt-1">
          These could not be traced to any retrieved guideline passage, so they were removed
          rather than shown. Cardios does not display clinical statements it cannot cite.
        </p>
      </div>
    )}

    {answer.sufficiency && !answer.sufficiency.calibrated && (
      <p className="rounded-xl bg-slate-100 p-3 text-xs text-slate-600">
        Evidence-sufficiency threshold is <strong>provisional</strong> ({answer.sufficiency.signal}{' '}
        {answer.sufficiency.value.toFixed(3)} ≥ {answer.sufficiency.threshold.toFixed(3)}). It has
        not yet been calibrated against a labelled gold set for this corpus and embedding model.
      </p>
    )}

    <MedicalDisclaimer text={answer.disclaimer} />
  </section>
);

const EvidenceAdvisor: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<RetrievalResponse | null>(null);
  const [transportError, setTransportError] = useState<string | null>(null);
  const [health, setHealth] = useState<RagHealth | null>(null);
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [answering, setAnswering] = useState(false);

  useEffect(() => {
    fetchRagHealth().then(setHealth).catch(() => setHealth(null));
    fetchRagDocuments()
      .then((d) => setDocuments(d.documents))
      .catch(() => setDocuments([]));
  }, []);

  const onSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (!question.trim() || loading) return;
      setLoading(true);
      setTransportError(null);
      setResponse(null);
      setAnswer(null);
      try {
        setResponse(await retrieveEvidence(question.trim(), k));
      } catch (error) {
        setTransportError(
          error instanceof Error ? error.message : 'Could not reach the Cardios API.',
        );
      } finally {
        setLoading(false);
      }
    },
    [question, k, loading],
  );

  const result: RetrievalResult | null =
    response && isRetrievalOk(response) ? response : null;

  /**
   * Generate from the evidence already on screen. The retrievalId binds the
   * request to that exact chunk set, so no second search happens and the user
   * (or a judge) is looking at precisely what the generator receives.
   */
  const onGenerate = useCallback(async () => {
    if (!result || answering) return;
    setAnswering(true);
    setAnswer(null);
    try {
      setAnswer(await requestAnswer({ retrievalId: result.retrievalId }));
    } catch (error) {
      setTransportError(
        error instanceof Error ? error.message : 'Could not reach the Cardios API.',
      );
    } finally {
      setAnswering(false);
    }
  }, [result, answering]);

  const corpusReady = useMemo(
    () => (health?.corpus?.embeddedChunks ?? 0) > 0,
    [health],
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-10">
      <header className="space-y-3">
        <p className="cardios-kicker">Clinical Evidence Intelligence</p>
        <h1 className="font-sora text-3xl font-semibold text-slate-900">
          Evidence Advisor
        </h1>
        <p className="max-w-2xl text-sm leading-6 text-slate-600">
          Search the ESC Heart Failure guideline and review traceable clinical evidence.
        </p>
      </header>

      <div role="note" className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
        <BookOpen className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden="true" />
        <p>
          <span className="font-semibold text-slate-700">Not a medical recommendation. </span>
          Retrieved passages come from the indexed ESC guideline and are evidence references only.
          They are not automatically a recommendation for a specific patient. Grounded answers are
          limited to retrieved evidence.
        </p>
      </div>

      <Card>
        <form onSubmit={onSubmit} className="space-y-4">
          <label htmlFor="rag-question" className="block text-sm font-semibold text-slate-700">
            Question
          </label>
          <textarea
            id="rag-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            autoFocus
            placeholder="e.g. What does the guideline recommend as initial diuretic therapy in acute decompensated heart failure?"
            className="w-full rounded-2xl border border-slate-200 p-4 text-sm leading-6 text-slate-800 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-100"
          />
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label htmlFor="rag-k" className="text-sm text-slate-600">
                Top-k
              </label>
              <input
                id="rag-k"
                type="number"
                min={1}
                max={20}
                value={k}
                onChange={(e) => setK(Number(e.target.value) || 5)}
                className="w-20 rounded-full border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
            <Button type="submit" disabled={loading || !question.trim()}>
              <Search className="h-4 w-4" aria-hidden="true" />
              {loading ? 'Retrieving…' : 'Retrieve evidence'}
            </Button>
            {health && (
              <span className="text-xs text-slate-500">
                corpus: {health.corpus.documents} document(s) ·{' '}
                {health.corpus.chunks} chunks ·{' '}
                {health.corpus.embeddedChunks ?? 0} indexed
              </span>
            )}
          </div>
        </form>
      </Card>

      {!corpusReady && health && (
        <Card className="border border-amber-200 bg-amber-50">
          <div className="flex items-start gap-3 text-sm text-amber-900">
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" aria-hidden="true" />
            <div>
              <p className="font-semibold">No guideline corpus is indexed yet.</p>
              <p className="mt-1">
                Ingest a guideline PDF and build the index before retrieval will work:
                <code className="mx-1 rounded bg-white px-1.5 py-0.5">python -m rag.ingest &lt;pdf&gt; --title "…"</code>
                then
                <code className="mx-1 rounded bg-white px-1.5 py-0.5">python -m rag.index</code>.
              </p>
            </div>
          </div>
        </Card>
      )}

      {transportError && (
        <Card className="border border-rose-200 bg-rose-50">
          <div className="flex items-start gap-3 text-sm text-rose-900">
            <ServerCrash className="mt-0.5 h-5 w-5 flex-shrink-0 text-rose-600" aria-hidden="true" />
            <div>
              <p className="font-semibold">Cardios API unreachable — this is a system error.</p>
              <p className="mt-1">{transportError}</p>
              <p className="mt-1 text-xs">
                This is not a statement about the guidelines. No evidence judgement was made.
              </p>
            </div>
          </div>
        </Card>
      )}

      {response && !isRetrievalOk(response) && (
        <Card className="border border-rose-200 bg-rose-50">
          <div className="flex items-start gap-3 text-sm text-rose-900">
            <ServerCrash className="mt-0.5 h-5 w-5 flex-shrink-0 text-rose-600" aria-hidden="true" />
            <div>
              <p className="font-semibold">Retrieval unavailable — system error.</p>
              <p className="mt-1">{response.error}</p>
              {response.remedy && <p className="mt-1 font-mono text-xs">{response.remedy}</p>}
              <p className="mt-2 text-xs">
                The system could not search the guidelines. It has <strong>not</strong> concluded
                that the guidelines lack relevant evidence.
              </p>
            </div>
          </div>
        </Card>
      )}

      {result && (
        <section className="space-y-4" aria-label="Retrieved evidence">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold text-slate-900">
              Retrieved evidence ({result.chunks.length})
            </h2>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <Timer className="h-3.5 w-3.5" aria-hidden="true" />
                {result.latencyMs} ms
              </span>
              <span>model: {result.modelId}</span>
              <span
                className="flex items-center gap-1 font-mono"
                title="Hash of the exact evidence set. Generation will be bound to this set, so what is shown here is what the model receives."
              >
                <Hash className="h-3.5 w-3.5" aria-hidden="true" />
                {result.chunkSetHash.slice(0, 12)}…
              </span>
            </div>
          </div>

          <p className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            One retrieval was performed for this question. The evidence below is the exact set
            that any generated answer will use — verified by retrieval&nbsp;
            <code className="font-mono">{result.retrievalId.slice(0, 12)}…</code> and chunk-set
            hash above.
          </p>

          {result.chunks.length === 0 ? (
            <Card>
              <p className="text-sm text-slate-600">
                The search returned no passages. This is a retrieval result, not a clinical
                judgement — evidence-sufficiency handling arrives with the generation layer.
              </p>
            </Card>
          ) : (
            <div className="space-y-4">
              {result.chunks.map((chunk) => (
                <EvidenceCard key={chunk.evidenceId} chunk={chunk} />
              ))}
            </div>
          )}
        </section>
      )}

      {result && result.chunks.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={onGenerate} disabled={answering}>
            {answering ? 'Generating…' : 'Generate grounded answer from this evidence'}
          </Button>
          <span className="text-xs text-slate-500">
            Uses retrieval <code className="font-mono">{result.retrievalId.slice(0, 8)}…</code> —
            no second search.
          </span>
        </div>
      )}

      {answer && isGroundedAnswer(answer) && (
        <>
          {answer.chunk_set_hash && result && answer.chunk_set_hash !== result.chunkSetHash && (
            <Card className="border border-rose-300 bg-rose-50">
              <p className="text-sm font-semibold text-rose-900">
                Integrity check failed: the answer was generated from a different evidence set
                than the one displayed. Do not rely on this output.
              </p>
            </Card>
          )}
          <AnswerPanel answer={answer} />
        </>
      )}

      {answer && isEvidenceRefusal(answer) && (
        <Card className="border-2 border-amber-300 bg-amber-50">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 h-6 w-6 flex-shrink-0 text-amber-600" aria-hidden="true" />
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-amber-900">
                Refused — insufficient guideline evidence
              </h2>
              <p className="text-sm text-amber-900">{answer.message}</p>
              <p className="text-xs text-amber-800">
                Reason: <code className="font-mono">{answer.reason}</code> ·{' '}
                {answer.evidence_considered} passage(s) considered
                {answer.sufficiency &&
                  ` · ${answer.sufficiency.signal} ${answer.sufficiency.value.toFixed(3)} < ${answer.sufficiency.threshold.toFixed(3)}`}
              </p>
              <p className="text-xs font-medium text-amber-800">
                This is a deliberate clinical safety decision about the evidence — not a
                system error.
              </p>
              {answer.disclaimer && <MedicalDisclaimer text={answer.disclaimer} />}
            </div>
          </div>
        </Card>
      )}

      {answer && isSystemFailure(answer) && (
        <Card className="border-2 border-rose-300 bg-rose-50">
          <div className="flex items-start gap-3">
            <ServerCrash className="mt-0.5 h-6 w-6 flex-shrink-0 text-rose-600" aria-hidden="true" />
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-rose-900">System error</h2>
              <p className="text-sm text-rose-900">{answer.message}</p>
              {answer.remedy && <p className="font-mono text-xs text-rose-800">{answer.remedy}</p>}
              <p className="text-xs font-medium text-rose-800">
                No clinical judgement was made. This is <strong>not</strong> a statement that the
                guidelines lack relevant evidence, and nothing was fabricated to fill the gap.
              </p>
            </div>
          </div>
        </Card>
      )}

      {documents.length > 0 && (
        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Indexed corpus
          </h2>
          <ul className="space-y-3 text-sm">
            {documents.map((doc) => (
              <li key={doc.document_id} className="border-l-2 border-emerald-200 pl-3">
                <p className="font-medium text-slate-800">{doc.title}</p>
                <p className="text-xs text-slate-500">
                  {doc.publisher ? `${doc.publisher} · ` : ''}
                  {doc.page_count} pages · {doc.chunk_count} chunks · corpus {doc.corpus_version}
                </p>
                {doc.ingestWarnings && doc.ingestWarnings.length > 0 && (
                  <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-amber-700">
                    {doc.ingestWarnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
};

export default EvidenceAdvisor;
