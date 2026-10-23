# Cardios RAG module — guideline-grounded clinical evidence

Software-only. Requires no ESP32, no AD8232, and no connected device at any
point: ingestion, indexing, retrieval, evaluation, and the Evidence Advisor UI
all run from files and the local corpus.

Status: **measured on the real ESC corpus.** Ingestion, retrieval, grounded
generation, citation validation and the calibrated refusal gate are implemented and
evaluated end to end against a 20-case gold set built from the guideline itself.

## Measured results — 2021 ESC Heart Failure Guidelines

Corpus: 128 PDF pages, 95 retained (table of contents and reference list excluded),
181 sections, 734 chunks. Citations resolve to the printed journal pages 3599–3726,
recovered from the page headers and verified across all 128 pages.

| | |
|---|---|
| Chunk metadata verification | **20 / 20** |
| Precision@3 / @5 | 0.262 / 0.229 |
| Recall@5 / @10 | 0.571 / 0.786 |
| MRR | 0.448 |
| Citation coverage | 1.000 |
| Excerpt verbatim accuracy | 1.000 |
| Citation accuracy vs gold source | 0.429 |
| Refusal accuracy | 0.650 |
| **False-answer rate** | **0.000** |
| False-refusal rate | 0.500 |
| Retrieval latency (p50) | 2.3 ms |

Selected configuration: chunk 900 / overlap 200, TF-IDF lexical (4096-d, 1–2 grams),
top-k 5, sufficiency `top1 >= 0.2815` (calibrated). Chosen on measurement across 20
swept configurations — see `eval/results/sweep_results.json`.

The false-refusal rate is high, and that is a deliberate consequence of the
calibration rule: the operating point is the one producing **zero false answers** on
the gold negatives. On this corpus the in-scope and out-of-domain score distributions
overlap, so buying that safety costs recall. `eval/results/calibration_sweep.json`
holds the full curve if a different trade-off is wanted.

Measured with the offline TF-IDF provider, because the model hub was unreachable from
the build environment. Re-run with `EMBEDDING_PROVIDER=local` to obtain the
sentence-transformers numbers; the harness and gold set are unchanged.

## Layout

```
backend/rag/
  config.py       env-driven settings (chunking, corpus dir, providers)
  contracts.py    pydantic types; provenance enums
  pdf_extract.py  layout-aware parsing, page labels, heading detection
  chunking.py     section-aware chunking with page attribution
  store.py        SQLite corpus: documents, chunks, embeddings, retrieval log
  embeddings.py   local sentence-transformers | tfidf-svd | hashing (tests)
  index.py        CLI: embed the corpus
  ingest.py       CLI: parse -> chunk -> verify -> persist
  verify.py       the 20-chunk metadata verification gate
  answer_contracts.py  PatientContext / EvidenceSet / Answer / Refusal / SystemFailure
  prompting.py    strict grounding prompt; the two disjoint blocks
  generation.py   extractive baseline | anthropic | openai
  sufficiency.py  evidence-sufficiency signal + calibration record
  guardrails.py   closed-set citation validation, claim dropping
  answering.py    orchestration + the single-retrieval guarantee
  service.py      Flask blueprint: /rag/health, /rag/documents, /rag/retrieve, /rag/answer
eval/
  goldset.py      GOLD schema, validation, span/page matchers
  run_eval.py     Precision@k, Recall@k, MRR, latency
  sweep.py        chunk size x overlap x model comparison
  calibrate.py    sweep + choose the evidence-sufficiency threshold
  scaffold_gold.py  emit a GOLD skeleton from an ingested corpus
```

## Pipeline

```bash
# 1. ingest a guideline PDF and run the metadata gate
python -m rag.ingest path/to/guideline.pdf \
    --title "ESC Heart Failure Guideline" --id esc-hf \
    --publisher "European Society of Cardiology" --url "<source url>"
#    -> review backend/rag/corpus/reports/esc-hf_verification_sample.md
#       Gate: >=19/20 chunks must carry the correct document, page, and a
#       plausible section title. Do NOT continue if it fails.

# 2. embed and index
python -m rag.index

# 3. author the gold set
python -m eval.scaffold_gold --out eval/questions_v1.yaml
#    fill in every TODO with verbatim evidence spans from the PDF

# 4. measure the baseline, then tune
python -m eval.run_eval --gold eval/questions_v1.yaml --tag baseline
python -m eval.sweep --pdf path/to/guideline.pdf --title "..." --gold eval/questions_v1.yaml

# 5. calibrate the refusal threshold, then measure the full answer path
python -m eval.calibrate --gold eval/questions_v1.yaml --write-calibration
python -m eval.run_eval --gold eval/questions_v1.yaml --tag tuned --with-answers
```

Run the backend (`python backend/app.py`) and the frontend (`npm run dev`), then
open **/evidence**.

## Design rules this module holds to

**Nothing is invented.** Where the PDF does not declare a section or a page
label, the field stays empty and `section_provenance` / `page_label_provenance`
record why. A confident wrong citation is the one failure mode that is invisible
downstream, so it is blocked at the source.

**Gold labels reference source locations, not chunk IDs.** Chunk IDs are
regenerated by every re-ingest, and the sweep re-ingests repeatedly; ID-keyed
labels would be invalidated by the experiment they exist to measure. Span
containment is the primary matcher and is chunk-size invariant.

**Retrieval runs once per question.** Every retrieval carries a `retrievalId`
and a `chunkSetHash`, both persisted. Generation will load evidence by id rather
than searching again, so the evidence a judge sees is provably the evidence the
model receives.

**System failure is never dressed as an evidence judgement.** An unindexed
corpus, a missing model, or an unreachable API returns `state: "unavailable"`
with `isEvidenceRefusal: false`, and the UI renders it as a system error. A
statement that the guidelines lack relevant evidence is a clinical judgement and
will only ever come from the calibrated sufficiency layer.

**Refusal is a first-class outcome, and it is cheap.** The sufficiency gate runs
*before* the generator, so a weak-evidence question never reaches a provider.
Until `eval.calibrate` has been run, every verdict is stamped
`calibrated: false` and the threshold is labelled provisional in the API and the
UI — a raw similarity score is not a calibrated confidence and is not presented
as one.

**Uncited claims are dropped, not flagged.** A plausible sentence with no
traceable source is precisely what grounding exists to prevent, so it never
reaches the user. If nothing survives validation, the outcome becomes a refusal.

## Embedding providers

| `EMBEDDING_PROVIDER` | Use |
|---|---|
| `local` (default) | sentence-transformers, the project baseline. Downloads once. |
| `tfidf` | TF-IDF + SVD fitted on the corpus. Zero download; works offline. Also a fair lexical baseline the neural model should beat. |
| `hashing` | Deterministic token hashing. **Tests only** — not semantic. |

## Generation providers

| `LLM_PROVIDER` | Use |
|---|---|
| `extractive` (default) | Offline. Copies sentences from the retrieved evidence, so it is grounded by construction and cannot hallucinate. Not a language model — it cannot synthesise or reword. Lets the whole pipeline run and demo with no API key. |
| `anthropic` / `openai` | Hosted LLM over plain HTTP (no vendor SDK added). Requires `LLM_API_KEY`. |
