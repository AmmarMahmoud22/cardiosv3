# CARDIOS — SOFTWARE HANDOFF

**For:** the next coding agent continuing Cardios
**Written:** 19 Aug 2026
**Status of this document:** single source of truth. Every number here was verified against
the repository or measured on the real ESC corpus. Where a figure could not be verified, it
is marked. Older project documents (`NOVELTY.md`, `WORK_REPORT.md`, `GRADUATION_GUIDE.md`,
`THESIS_OUTLINE.md`) predate this work and contain claims that conflict with the code — this
file wins.

Evidence labels used throughout:

| Label | Meaning |
|---|---|
| `IMPLEMENTED` | Code exists and runs |
| `TESTED` | Covered by the automated suite |
| `MEASURED (REAL)` | Measured against the real ESC corpus / real Supabase project |
| `BASELINE ONLY` | Works, but is explicitly not the final solution |
| `NOT FINAL` | Implemented but expected to change |
| `NOT IMPLEMENTED` | Does not exist |
| `MANUAL CHECK REQUIRED` | Needs a human or a browser |

---

## 1. Executive Status

Cardios is one cardiac clinical software platform with three intelligence areas:

1. **Heart Risk Intelligence** — XGBoost risk estimation from structured health indicators.
2. **ECG Intelligence** — CNN-LSTM beat classification over a signal-processing pipeline.
3. **Clinical Evidence Intelligence** — retrieval over official clinical guidelines with
   grounded, cited answers and an explicit refusal path.

All three run in the same React + Flask application, share one navigation, and are reachable
today. The current hackathon effort is concentrated almost entirely on **Clinical Evidence
Intelligence**, because that is what the competition scores.

**Maturity.** The evidence pipeline is end-to-end complete: a real 128-page ESC guideline is
parsed, chunked, indexed, retrieved, displayed, gated for sufficiency, answered with validated
citations, and refused when evidence is thin. It has been measured on a real 20-case gold set,
not on fixtures. Ingestion passed its metadata gate at **20/20**, and citations resolve to real
printed journal pages (3599–3726), not PDF indices.

The single most important thing to understand: **retrieval quality is the binding constraint on
everything downstream, and the current retriever is a lexical placeholder.** TF-IDF was used only
because the previous environment could not download sentence-transformer weights. Recall@5 is
0.571 and the false-refusal rate is ~0.50 — both are retrieval-limited, not
architecture-limited. Replacing the embedder is Priority 1 and everything else should wait
behind it.

Heart Risk and ECG are stable and should not be touched. Their models are unchanged.

---

## 2. Verified Project Provenance

### 2.1 Heart Risk — `MEASURED (REAL)`

**Source:** Kaggle — *Personal Key Indicators of Heart Disease*
(https://www.kaggle.com/datasets/kamilpytlak/personal-key-indicators-of-heart-disease)

Verified directly against `E:\hakason\Heart_Dis_Data.csv`:

| Fact | Value |
|---|---|
| Rows | 319,795 |
| Columns | 18 (target `HeartDisease` + 17 features) |
| Feature match with `backend/risk_model.py` | Exact — all 17 names align |
| `HeartDisease = No` | 292,422 |
| `HeartDisease = Yes` | 27,372 |
| Majority-class proportion | **91.44 %** |

**Why the old "~99 % accuracy" claim was removed.** No artefact in the repository supports it —
there is no evaluation script, metrics file, or confusion matrix for the risk model. More
importantly, a model predicting "No" for everyone scores 91.44 % on this dataset, so a headline
accuracy near 99 % is uninformative without positive-class recall and precision. **Do not repeat
that figure.** If a number is needed, run a proper evaluation reporting positive-class recall,
precision and PR-AUC.

**Do not retrain the risk model.** It is out of scope.

### 2.2 ECG — `IMPLEMENTED`, provenance partially verified

- Model artefact: `backend/ECG model/ECG_Heart Failure Project_best_model_cnn_lstm.keras` (961 KB)
- Architecture: CNN-LSTM, 180 timesteps, 5 AAMI classes
  (`Normal`, `Atrial Premature`, `PVC`, `Fusion of Ventricular and Normal`, `Fusion of Paced and Normal`)
- Pipeline: `backend/ecg_analysis.py` — band-pass 0.5–40 Hz → R-peak detection → beat
  segmentation (resample to 180) → classification → rhythm aggregation
- Signal-quality gate: `backend/signal_quality.py` — lead-off, flatline, clipping and noise are
  flagged and left unclassified rather than confidently labelled

**Evaluation figures recorded in `WORK_REPORT.md`:** 97.98 % accuracy, macro-F1 0.90 on 21,892
MIT-BIH beats, produced by `analysis/evaluate_ecg_model.py`, with
`analysis/outputs/confusion_matrix.png`. The script and the confusion matrix exist in the repo.
These figures were **not independently re-run** in this session — treat as
`MANUAL CHECK REQUIRED` if they are going to be quoted competitively.

**Do not retrain the ECG model.**

### 2.3 Clinical Evidence — `MEASURED (REAL)`

**Corpus:** 2021 ESC Guidelines for the diagnosis and treatment of acute and chronic heart
failure. *European Heart Journal* 2021;42:3599–3726. doi:10.1093/eurheartj/ehab368.
Source PDF: `E:\hakason\ESC_Heart_Failure_Guideline_2021.pdf` (5.07 MB).
SHA-256 recorded in `backend/rag/corpus/reports/esc-hf-2021_ingest_report.json`.

This is the real corpus that is indexed and serving queries right now.

---

## 3. Current Software Architecture

### Frontend — React 18 + TypeScript + Vite 5 + Tailwind

Routes in `src/App.tsx`:

| Route | Guard | Purpose |
|---|---|---|
| `/` | public | Home (Unified 3 Intelligence Areas) |
| `/auth` | public | Login / signup |
| `/about`, `/contact` | public | Static |
| **`/evidence`** | **public** | **Clinical Evidence Advisor** |
| `/predict` | `RequireAuth` | Heart Risk form (AI Assessment) |
| `/predict-ecg` | `RequireAuth` | ECG Lab (Upload-only file analysis) |
| `/profile` | `RequireAuth` | History |
| `/admin` | `RequireAuth` | Admin dashboard |
| `/doctor`, `/doctor/patients/:id`, `/doctor/devices` | `RequireRole['doctor']` | Doctor portal |
| `/app` | `RoleRedirect` | Role-based landing |

`/evidence` is intentionally public: it reads only published guideline text and holds no patient
data, and gating it made the hackathon feature depend on Supabase for no reason. The `/ecg-test`
experimental route and Live Device mode were removed to present a unified, mentor-ready platform.

### Backend — Flask 3.1

`backend/app.py` registers three blueprints and loads `.env` at startup via `python-dotenv`.

| Endpoint | Module |
|---|---|
| `POST /predict` | `backend/risk_model.py` (XGBoost) |
| `POST /predict-ecg` | `backend/ecg_service.py` + `ecg_analysis.py` |
| `GET /health`, `/health/ready` | `backend/app.py` |
| `POST /chatbot/chat` | `backend/chatbot_service.py` (legacy keyword responder, not part of RAG) |
| `GET /rag/health` | `backend/rag/service.py` |
| `GET /rag/documents` | `backend/rag/service.py` |
| `GET /rag/documents/<id>/chunks` | `backend/rag/service.py` |
| `POST /rag/retrieve` | `backend/rag/service.py` → `retrieve.py` |
| `POST /rag/answer` | `backend/rag/service.py` → `answering.py` |

The backend imports Supabase **nowhere**. It is completely database-independent; only two
comments mention Supabase. Backend auth is an opt-in JWT gate (`backend/auth.py`,
`AUTH_ENABLED`, default off).

### Data

- **Application/user data** → Supabase (profiles, roles, predictions, ECG analyses, check-ins,
  doctor/patient links, notes). See §14.
- **RAG corpus and index** → local SQLite at `backend/rag/corpus/corpus.db`. Not in Supabase.

### AI/ML

| Component | Implementation |
|---|---|
| Heart risk | XGBoost + scikit-learn encoders/scaler, `backend/model/*` |
| ECG | TensorFlow/Keras CNN-LSTM |
| RAG embedding | TF-IDF lexical, 4096-d, 1–2 grams (`BASELINE ONLY`) |
| RAG generation | Extractive baseline; OpenAI and Anthropic providers implemented |

---

## 4. Clinical Evidence / RAG Architecture

Full pipeline with the file responsible for each stage:

```
ESC PDF
  ↓  backend/rag/pdf_extract.py     parse, column ordering, word-gap repair,
  │                                 heading detection, folio recovery,
  │                                 ToC + bibliography exclusion
  ↓  backend/rag/chunking.py        section-aware chunking, page attribution
  ↓  backend/rag/contracts.py       Chunk / PageRecord / Heading, provenance enums
  ↓  backend/rag/ingest.py          orchestration + CLI  (python -m rag.ingest)
  ↓  backend/rag/verify.py          20-chunk metadata verification gate
  ↓  backend/rag/store.py           SQLite: documents, chunks, embeddings, retrieval log
  ↓  backend/rag/embeddings.py      provider abstraction (local ST | tfidf | tfidf-svd | hashing)
  ↓  backend/rag/index.py           embed the corpus       (python -m rag.index)
  ↓  backend/rag/retrieve.py        top-k cosine, evidence IDs, retrievalId, chunkSetHash
  ↓  backend/rag/service.py         POST /rag/retrieve  → UI evidence panel
  ↓  backend/rag/sufficiency.py     calibrated evidence-sufficiency gate
  ↓  backend/rag/prompting.py       strict grounding prompt, two disjoint blocks
  ↓  backend/rag/generation.py      extractive | anthropic | openai
  ↓  backend/rag/guardrails.py      closed-set citation validation, claim dropping
  ↓  backend/rag/answering.py       orchestration; answer / refusal / system_failure
  ↓  backend/rag/service.py         POST /rag/answer
```

### The single-retrieval guarantee — `IMPLEMENTED`, `TESTED`

This is the most important design property in the module and must not be broken.

Retrieval happens **exactly once per user question**. Every retrieval produces:

- a `retrievalId` (UUID), persisted with its chunk references and scores in `rag_retrievals`
- a `chunkSetHash` — SHA-256 over the ordered `(documentId, chunkIndex, content)` triples

`POST /rag/answer` accepts **either** `{question, k}` (one fresh retrieval) **or**
`{retrievalId}`. With a `retrievalId` it reloads that exact chunk set from the store,
recomputes the hash, and **fails closed** with `EVIDENCE_SET_CHANGED` if the corpus moved
underneath. It never searches a second time.

The UI therefore shows the evidence panel first, then generates from that same set by passing
the `retrievalId` back. The hash is echoed in the answer and compared client-side. **The
evidence a judge sees is provably the evidence the generator received.** Covered by
`tests/test_rag_generation.py::test_evidence_set_reloads_identically_from_a_retrieval_id`,
`::test_corpus_change_invalidates_a_pending_evidence_set` and
`::test_generation_uses_the_exact_displayed_evidence`.

### Patient context vs guideline evidence — `IMPLEMENTED`, `TESTED`

`backend/rag/answer_contracts.py` defines `PatientContext` and `EvidenceSet` as **distinct
types**. Patient context renders without evidence IDs, so there is no token a model could emit
that resolves to it, and the citation validator's signature accepts only an `EvidenceSet`.
A model output citing `PATIENT_CONTEXT` is dropped — see
`test_patient_context_reaches_the_provider_but_never_becomes_a_citation`.

Patient-context **injection** into the UI is `NOT IMPLEMENTED` — the plumbing exists, the
feature does not.

---

## 5. Real ESC Corpus Status — `MEASURED (REAL)`

From `backend/rag/corpus/reports/esc-hf-2021_ingest_report.json`:

| Fact | Value |
|---|---|
| PDF pages | 128 |
| Pages retained | **95** |
| Sections detected | **181** (all `numbered_heading`) |
| Chunks | **734** |
| Section attribution | 691 / 734 = **94.1 %** (43 `unknown`) |
| Page-label provenance | `derived_folio` — printed pages **3599–3726** |
| Metadata verification gate | **20 / 20 PASS** |
| Chunk config | size 900, overlap 200, min 120 |

**Excluded content, deliberately and reported at ingest time:**

- **Pages 3–4** (printed 3601–3602) — table of contents. Contents entries reproduce every
  heading verbatim and, being short and keyword-dense, outrank the sections they point to.
  Removing them measurably improved P@3 from 0.286 → 0.309 at the time of the test.
- **Pages 98–128** (printed 3696–3726) — the reference list, 31 of 128 pages. A bibliography
  contains no recommendations and dilutes the index.

Both are config-gated: `RAG_EXCLUDE_FRONT_MATTER`, `RAG_EXCLUDE_BIBLIOGRAPHY`.

### Parser problems that were actually solved

Useful context — these were real, and each fix is general rather than ESC-specific:

1. **No word spacing.** The PDF text layer produced `patientswithHFrEF`. pdfplumber's default
   `x_tolerance=3.0` was too coarse; **1.5** restores gaps. Config: `RAG_PDF_X_TOLERANCE`.
2. **Two-column interleaving.** Left and right columns were spliced line-by-line. `detect_gutter()`
   finds the empty vertical channel by binning character centres and requires real text on both
   sides; columns are then cropped and read in order. Config: `RAG_PDF_LAYOUT=auto`.
3. **False heading detection — 5,921 headings on 128 pages.** Two causes. (a) The journal overlays
   **11.8 pt decorative leader dots** on pages whose body text is 7–9 pt, so any line containing a
   dot looked like a heading; `_line_font_stats()` now excludes decorative glyphs. (b) Heading text
   was matched to font runs *by position*, which silently misaligned; `_line_text()` now
   reconstructs each line from its own characters using x-gaps. Result: **181 clean headings.**
4. **ToC pollution.** `TOC_ENTRY_RE` strips contents lines; whole ToC pages are excluded.
5. **Page-label mismatch.** The PDF's own label tree said "1–128" while the printed folios read
   3599–3726. Citing the index would send a clinician to the wrong page.
6. **Journal folio recovery.** `detect_printed_folios()` reads standalone integers from the top
   and bottom margins, then checks they all fit **one linear mapping** `folio = index + offset`.
   Verified at **99 % agreement across 128 pages** before being applied. If the folios disagree,
   nothing is applied — a partially-correct page number is worse than none.

---

## 6. GOLD-v1 Evaluation Set — `MEASURED (REAL)`

**File:** `eval/questions_v1.yaml`
**Loader / validator / matchers:** `eval/goldset.py`
**Scaffolding tool:** `eval/scaffold_gold.py`

| Category | Count |
|---|---|
| `in_scope` | 11 |
| `ambiguous` | 3 |
| `out_of_domain` | 4 |
| `unsafe_request` | 2 |
| **Total** | **20** |

14 cases carry gold evidence (11 in-scope + 3 ambiguous). The 6 negatives carry none **by
design** — they are the negative distribution for sufficiency calibration, and the validator
rejects a negative case that has gold evidence.

### How gold evidence is represented

Labels anchor to **stable source locations**, never database chunk IDs:

```yaml
gold_evidence:
  - document: 2021 ESC Guidelines for the diagnosis and treatment of acute and chronic heart failure
    pages: [19]                    # PDF page indices
    evidence_span: Plasma concentrations of NPs are recommended as initial diagnostic tests
```

Chunk IDs are regenerated by every re-ingest, and the tuning sweep re-ingests repeatedly — ID-keyed
labels would be invalidated by the very experiment they exist to measure.

**Matchers** (`eval/goldset.py`), reported separately:

- **Span containment (primary)** — normalised text comparison, invariant to chunk size and
  overlap. Handles PDF line-break hyphenation (`symp- toms` → `symptoms`) and punctuation. A span
  split across two *adjacent* retrieved chunks still counts (`span_hit_adjacent`).
- **Page overlap (secondary)** — document match plus page-range intersection, ±1 page tolerance.

Divergence between them is diagnostic: high page-overlap with low span-containment means the
chunker is landing on the right page but splitting recommendations badly.

**All 14 gold spans were verified present in the real corpus before evaluation** (recall-ceiling
check) — 0 missing.

**Anti-authoring-bias measures already applied:** 4 in-scope questions are marked
`paraphrased_blind: true`; out-of-domain cases are deliberately *plausibly cardiac* near-misses
(e.g. rheumatoid arthritis, which the guideline mentions only as a comorbidity) rather than
obviously unrelated.

---

## 7. Retrieval — Current Measured Baseline

> **Read this before changing anything.**
> The current retrieval baseline is **`BASELINE ONLY`** and is **NOT the final semantic retrieval
> solution.** It is lexical TF-IDF, selected because the previous environment could not download
> sentence-transformer weights. Its numbers are the bar to beat, not the target.

### Current configuration

| Setting | Value |
|---|---|
| Provider | `tfidf` → `TfidfLexicalProvider` |
| Model id | `tfidf-lexical-4096d-ng2` |
| Dimensions | 4096 |
| N-grams | 1–2 |
| `min_df` / `max_df` | 2 / 0.35 |
| Chunk size | 900 |
| Overlap | 200 |
| k | 5 |

### Measured on the real ESC corpus + GOLD-v1

| Metric | Baseline (TF-IDF + SVD) | **Current tuned (lexical)** |
|---|---|---|
| P@3 | 0.167 | **0.262** |
| P@5 | 0.171 | **0.229** |
| R@5 | 0.357 | **0.571** |
| R@10 | 0.786 | **0.786** |
| MRR | 0.268 | **0.448** |
| in/out score separation | −0.008 | **+0.176** |
| Retrieval latency p50 | — | **2.3 ms** |

**20 configurations were evaluated** across two sweeps (chunk size × overlap × embedding
variant). Results: `eval/results/sweep_results.json`.

### The SVD finding — important

Truncated SVD (latent semantic analysis) was the original dimensionality reduction. It
**collapsed the in-scope vs out-of-domain score separation to approximately zero** at every
dimension tested (64, 128, 256, 400, 500 — separation ranged −0.012 to +0.039). The cause is
that the leading singular vectors capture the corpus-wide "cardiology prose" direction that
every query projects onto, including irrelevant ones.

Consequence: **refusal could not work at all**, because there was no usable gap between relevant
and irrelevant. Removing SVD and keeping the full term space restored separation to +0.176 and
nearly doubled R@5. SVD remains available as `EMBEDDING_PROVIDER=tfidf-svd` for comparison but
must not be the default.

### Result files

| File | Contents |
|---|---|
| `eval/results/sweep_results.json` | All swept configurations, ranked, with the selected config |
| `eval/results/eval_esc-final.json` | Final retrieval + answer-path metrics, per-case detail |
| `eval/results/calibration_sweep.json` | Full sufficiency threshold sweep curve |

---

## 8. THE MAIN NEXT TASK — Semantic Retrieval

**This is the highest-value work available. Do it first.**

### The situation

`sentence-transformers` is installed and `LocalSentenceTransformerProvider` is implemented and
wired (`backend/rag/embeddings.py`). The previous environment could install the package but its
proxy blocked `huggingface.co`, so model weights could never be downloaded. **This is an
environmental limitation, not an architectural one.** No code change is required to run semantic
retrieval — only a working network.

### Step 1 — compare semantic models, holding everything else constant

Hold **chunk size = 900, overlap = 200, k = 5** fixed. Vary only the embedding model.

Suggested candidates (any sentence-transformers model works):

- `sentence-transformers/all-MiniLM-L6-v2` (fast, 384-d, the default)
- `sentence-transformers/all-mpnet-base-v2` (stronger, 768-d)
- A biomedical model, e.g. `pritamdeka/S-PubMedBert-MS-MARCO` — clinical text is the domain

```powershell
cd "E:\hakason\Cardios V3"
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt      # first run downloads weights

# for each candidate model:
$env:EMBEDDING_PROVIDER="local"
$env:EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
cd backend; ..\.venv311\Scripts\python.exe -m rag.index; cd ..
.\.venv311\Scripts\python.exe -m eval.run_eval --gold eval\questions_v1.yaml --k 3 5 10 --tag semantic-minilm
```

Vectors for different models coexist in the store (`store_embeddings` keys on `model_id`), so
**re-indexing a new model does not require re-ingesting the corpus** and does not destroy the
TF-IDF vectors. You can flip between them by changing `EMBEDDING_MODEL`.

### Metrics to record for every model

Precision@3 · Precision@5 · Recall@5 · Recall@10 · MRR · in/out score separation · latency.

The harness prints all of these and writes `eval/results/eval_<tag>.json`.

**Compare against the documented TF-IDF baseline in §7.** A semantic model that cannot beat
P@3 0.262 / R@5 0.571 / MRR 0.448 / separation +0.176 is not earning its cost — that is exactly
why the lexical baseline is kept.

### Step 2 — limited sweep around the winner

Only after a model is chosen, run a **small** chunk/overlap/k sweep around it:

```powershell
.\.venv311\Scripts\python.exe -m eval.sweep --pdf "E:\hakason\ESC_Heart_Failure_Guideline_2021.pdf" `
  --title "2021 ESC Guidelines for the diagnosis and treatment of acute and chronic heart failure" `
  --document-id esc-hf-2021 --gold eval\questions_v1.yaml `
  --chunk-sizes 600 900 1200 --overlaps 100 200 --k 3 5 10 --select-on "k=5"
```

Each sweep configuration re-ingests the full 128-page PDF, so 6 configurations take roughly
10 minutes. Do not sweep 20 configurations again without reason.

### Constraints

- **Do NOT implement hybrid retrieval (dense + BM25/RRF) yet.** Only consider it if semantic
  retrieval remains measurably weak after Step 2. If it is ever added, RRF is a *ranking* score
  and must never be used as a confidence signal — see §10.
- **Do NOT modify GOLD-v1 to improve results.** Changing the measuring instrument to flatter the
  system invalidates every number in this document. If a gold label is genuinely wrong, fix it
  and say so explicitly in the results.
- **Re-calibrate sufficiency afterwards** — see §10. The current threshold is meaningless in a
  different embedding space.

---

## 9. Retrieval Failure Analysis — `NOT IMPLEMENTED`, do this

After the semantic experiment, inspect **every in-scope GOLD case where the correct evidence does
not appear in the top 5.** With R@5 = 0.571 on 11 in-scope cases, roughly 4–5 cases currently
fail; that set is where the remaining retrieval gain lives.

`eval/results/eval_<tag>.json` contains `perCase` entries with `topScore`, `topCitation` and
per-k metrics — use it to identify failures rather than re-running queries by hand.

Classify each failure by cause:

| Cause | Signal | Likely fix |
|---|---|---|
| **Embedding similarity** | Right chunk exists and is retrievable at k=20, but ranks low | Different/better model |
| **Chunk boundary** | Span split across chunks; `span_hit_adjacent` fires but rank is poor | Adjust chunk size/overlap |
| **Query wording** | Gold question uses different vocabulary from the guideline | Note it; consider a paraphrase in GOLD-v2 |
| **Parser/section issue** | Chunk text is garbled, or `section_provenance = unknown` | Parser fix |
| **Gold-label issue** | The span is wrong, ambiguous, or appears in several places | Fix the label and document it |

This classification should drive the next retrieval change. Do not tune blindly.

---

## 10. Evidence Sufficiency / Refusal

### Current calibration — `MEASURED (REAL)`, `NOT FINAL`

`backend/rag/corpus/calibration.json`:

```json
{ "calibrationId": "cal-20260819-d79a38", "signal": "top1", "threshold": 0.281473,
  "modelId": "tfidf-lexical-4096d-ng2", "corpusVersion": "v1", "k": 5 }
```

> **This threshold belongs ONLY to the `tfidf-lexical-4096d-ng2` configuration.**
> Similarity scores are not comparable across embedding spaces. **It MUST NOT be reused after
> changing the embedding model.** `backend/rag/sufficiency.py` binds the record to
> `modelId` + `corpusVersion` and **fails closed** if they do not match at runtime, so a stale
> calibration degrades to refusing rather than to answering unsafely — but you must still
> recalibrate.

### Measured results

| Metric | Value | Source |
|---|---|---|
| Refusal accuracy | **0.650** | answer-path eval, 20 cases |
| **False-answer rate** | **0.000** | 6 negatives |
| False-refusal rate | **0.500** | answer-path eval (positives incl. ambiguous) |
| False-refusal rate (calibration sweep, 11 in-scope only) | 0.4545 (5/11) | `calibration_sweep.json` |

### Why false refusal is this high

The operating-point rule is deliberately safety-weighted: *minimise false refusals subject to
**zero** false answers on the gold negatives.* On this corpus the in-scope and out-of-domain
score distributions **overlap** (in-scope top1 ranged 0.187–0.767; negatives 0.000–0.297), so
buying zero false answers costs half the recall.

**This is a retrieval problem, not a threshold problem.** Widening the gap requires a better
embedder. The full sweep curve is preserved in `eval/results/calibration_sweep.json` if a
different trade-off is wanted.

A known fragility: the out-of-domain colon-cancer case sits almost exactly on the boundary
(top1 0.281 vs threshold 0.281) and a one-word paraphrase flips it to answering (0.320). ESC
§13.13 discusses cardiotoxicity of cancer therapies, so the lexical overlap is real. This is the
classic symptom of fitting a threshold on the same set used to evaluate it — GOLD-v1 is both the
development and the calibration set.

### After changing the embedding model

```powershell
.\.venv311\Scripts\python.exe -m eval.calibrate --gold eval\questions_v1.yaml --k 5 `
  --signals top1 margin --write-calibration
```

`eval/calibrate.py` sweeps both candidate signals (`top1`, `margin`), plots false-answer against
false-refusal, picks the safety-weighted operating point, and writes a new record bound to the
new model. It flags explicitly when the distributions are **not separable** — that flag is a
finding about retrieval, not a detail.

---

## 11. Generation Layer

### Implemented providers — `backend/rag/generation.py`

| `LLM_PROVIDER` | Status | Notes |
|---|---|---|
| `extractive` (default when unset) | `IMPLEMENTED`, `TESTED`, `MEASURED (REAL)` | Offline. Selects the most question-relevant sentences from retrieved evidence. **Not a language model.** |
| `anthropic` | `IMPLEMENTED`, `NOT TESTED against a live API` | Plain HTTPS to `/v1/messages`, no vendor SDK added |
| `openai` | `IMPLEMENTED`, `NOT TESTED against a live API` | Plain HTTPS to `/v1/chat/completions`, JSON response format |

### Environment variables

```
LLM_PROVIDER=            # extractive | anthropic | openai   (empty ⇒ extractive)
LLM_MODEL=               # provider model id
LLM_API_KEY=             # required for anthropic/openai
```

**No API key is currently present** in `.env` or `.env.example` — the fields exist and are empty.
No key value appears anywhere in the repository. Selecting a hosted provider without a key raises
`GenerationUnavailable`, which surfaces as a `system_failure`, never as a refusal.

### Why the extractive generator must be PRESERVED

1. **Zero-dependency baseline** — the entire pipeline, including the live demo, runs with no API
   key, no network and no cost. If a provider is down mid-demo, this still works.
2. **Grounded by construction** — the recommendation text *is* the excerpt, copied verbatim. It
   physically cannot assert anything the guideline does not say, which gives faithfulness a
   ceiling of 1.0.
3. **A comparison floor** — an LLM whose citation accuracy or faithfulness falls below the
   extractive baseline is actively harmful. Keep it to measure against.

Do not delete it when an LLM is wired up. Add the LLM alongside and compare.

### Measured results (extractive, real ESC corpus)

| Metric | Value |
|---|---|
| Citation coverage | **1.000** |
| Excerpt-verbatim accuracy | **1.000** |
| **Citation accuracy vs GOLD** | **0.429** |
| Claims dropped | 0 |
| System failures | 0 |
| Answer latency p50 | 0.24 ms |

### The distinction that matters

**Citation coverage 1.000 does NOT mean citation selection is correct.** Coverage measures
whether every recommendation carries at least one *resolvable* citation — with the extractive
generator that is 1.0 by construction, since it only ever quotes retrieved chunks. Excerpt
accuracy 1.000 likewise only proves the quoted text really appears in the cited passage.

**Citation accuracy vs gold — 0.429 — is the honest number**, and it is limited mainly by
retrieval: if the right passage is not in the top-k, no generator can cite it.

> **Improve retrieval BEFORE spending substantial time on answer style or prompt engineering.**
> Answer quality is currently capped by what retrieval surfaces.

---

## 12. Citation Integrity — `IMPLEMENTED`, `TESTED`

| Mechanism | File | Behaviour |
|---|---|---|
| Evidence IDs | `retrieve.py` | `E1…En` assigned in rank order, scoped to one retrieval |
| `retrievalId` | `retrieve.py` | UUID, persisted with chunk refs + scores |
| `chunkSetHash` | `retrieve.py::chunk_set_hash` | SHA-256 over ordered `(documentId, chunkIndex, content)` |
| Closed-set validation | `guardrails.py::build_recommendations` | A citation must name an evidence ID in **this** set |
| Verbatim excerpt check | `guardrails.py::excerpt_is_verbatim` | Normalised containment; tolerant of PDF hyphenation/whitespace, but containment — a reworded excerpt fails |
| Invalid citation | `guardrails.py` | Claim is **dropped**, not shown with a warning |
| No valid claims survive | `answering.py` | Outcome becomes `refusal` with reason `no_valid_citations` |
| Same-retrieval enforcement | `answering.py::load_evidence_set` | Hash recomputed on reload; mismatch ⇒ `EVIDENCE_SET_CHANGED` system failure |

### The PDF-index vs printed-page evaluation bug — do not reintroduce

**What happened.** GOLD labels record `pages` as **PDF page indices** (e.g. 19). Citations
display the **printed journal folio** (e.g. 3617). The evaluator compared the gold index against
the displayed folio string, so almost nothing matched: citation accuracy read **0.056**.

**The fix.** `Citation` in `backend/rag/answer_contracts.py` now carries **both**: `page` (the
folio shown to the reader) and `page_index` / `page_index_end` (the physical PDF index).
`eval/run_eval.py::_citations_match_gold` compares in the index space, falling back to the
displayed string for documents where the two coincide. True figure: **0.429**.

**Trap for the next agent:** any new corpus whose printed pagination differs from its PDF
pagination will hit this again. Keep both fields populated, and keep gold labels in PDF-index
space.

---

## 13. Evidence Advisor UI — `IMPLEMENTED`

| Item | Value |
|---|---|
| Page | `src/pages/EvidenceAdvisor.tsx` (~520 lines) |
| Client | `src/services/ragService.ts` (~265 lines) |
| Route | `/evidence`, **public** (no `RequireAuth`) |
| Nav entry | `src/components/layout/Header.tsx` — "Evidence Advisor" |

### Currently working

- **Question input** with a `k` control (1–20)
- **Retrieved Evidence panel**, rendered *before* any answer exists, showing per chunk:
  evidence ID (`E1`…), colour-coded similarity score, rank, document title, section title **plus
  how the section was determined** (`outline` / `numbered_heading` / `styled_heading` /
  `inherited` / `unknown`), page or page range with a note when it is a physical index, full
  chunk text, and the formatted citation
- **Header strip** — latency, model id, truncated `chunkSetHash` with an explanatory tooltip
- **"Generate grounded answer from this evidence"** — passes the `retrievalId` back, so no second
  search happens
- **Grounded answer panel** — recommendations, verbatim excerpt block, citation chips carrying
  evidence IDs, per-recommendation verbatim-verified tick, coverage and excerpt-accuracy
  percentages, withheld-claims notice, provisional-threshold notice when uncalibrated
- **Refusal state** — amber, states the reason and the sufficiency comparison, and says
  explicitly that it is a clinical safety decision and *not* a system error
- **System-failure state** — red, distinct, states that no clinical judgement was made and
  nothing was fabricated
- **Integrity indication** — client compares the answer's `chunk_set_hash` against the
  retrieval's and shows a warning card on mismatch
- **Corpus panel** — ingested documents with publisher, page/chunk counts and ingest warnings
- **Guest resilience** — the auth header is optional and bounded at 2 s
  (`optionalAuthHeaders`), so a paused Supabase cannot stall a guideline lookup. Verified across
  five scenarios: healthy (5 ms) and slow (1.5 s) sessions keep their token; only a hung or
  throwing Supabase falls back

**Do not redesign this UI as a task in itself.** Improve it only where it helps the live demo
(§21 Priority 6).

---

## 14. Supabase / Application Data — Current State

| Fact | Value |
|---|---|
| Live project ref | **`ktjjsdlcpeinxmqdpsls`** (ACTIVE_HEALTHY, eu-central-1, Postgres 17.6) |
| Previous stale ref | `ataiqwgfjffwcnsrnlse` — **deleted** (no DNS record) |
| `.env` | Corrected to the live project; backup at `.env.bak.<timestamp>` |

No key values appear in this document or in any committed file beyond `.env` itself.

### Verified against the real database — `MEASURED (REAL)`

| Check | Result |
|---|---|
| Existing users | 3 (preserved) |
| Predictions | 4 (preserved) |
| ECG analyses | 13 (preserved) |
| Tables / RLS / policies | 15 / 15 enabled / 48 |
| Signup provisioning | **PASS** — trigger creates `profiles`, `extended_profiles`, default `patient` role |
| Patient isolation | **PASS** — A and B see only their own rows; forged writes blocked |
| Doctor access | **PASS** — sees assigned patient only, zero rows from unassigned |
| Clinician notes | **PASS** — patient sees shared notes, internal notes hidden; doctor sees both |

**Important:** the signup trigger is named **`on_auth_user_created_cardios`** (calling
`handle_new_cardios_user()`), not the `on_auth_user_created` in `supabase/bootstrap.sql`.
The live function is more complete than bootstrap's. **Do not run `bootstrap.sql` against the
live project** — it would install a second, duplicate provisioning trigger. No database change
was made in this session.

### RAG storage — local, and that is fine

The RAG corpus is **NOT** in Supabase. It lives in:

```
backend/rag/corpus/corpus.db        SQLite, ~13 MB
```

Current contents: **1 ESC document, 734 chunks, 734 embeddings** (`tfidf-lexical-4096d-ng2`).
`clinical_documents` / `clinical_chunks` / `rag_ingest_reports` do **not** exist in the live
project, and pgvector is **not** installed (available, v0.8.0).

**Do not migrate to pgvector as an immediate task.** Local SQLite is acceptable for the
hackathon demo, retrieval is sub-3 ms, and the migration would add risk with no scored benefit.
`supabase/migrations/20260819000000_clinical_rag_corpus.sql` holds the schema if it is ever wanted.

### Still outstanding

**Browser login / session-restore / logout: `MANUAL CHECK REQUIRED`.** The previous agent's
sandbox could not reach Supabase over HTTPS, so the browser auth round-trip was never exercised.
Everything database-side is verified. Start the app, sign in, confirm the session persists across
a refresh, and log out.

---

## 15. Testing Status — `TESTED`

| Suite | Count |
|---|---|
| Existing Cardios tests | **54** |
| RAG tests | **90** |
| **Total** | **144 passed, 0 failed** |

Breakdown:

| File | Tests |
|---|---|
| `tests/test_api_validation.py` | 4 |
| `tests/test_auth.py` | 6 |
| `tests/test_device_store.py` | 7 |
| `tests/test_qa_endpoints.py` | 4 |
| `tests/test_security.py` | 14 |
| `tests/test_signal_quality.py` | 8 |
| `tests/test_wat.py` | 11 |
| **`tests/test_rag_ingest.py`** | **29** |
| **`tests/test_rag_retrieval.py`** | **31** |
| **`tests/test_rag_generation.py`** | **30** |

Frontend: **TypeScript typecheck PASS · ESLint PASS · Vite production build PASS.**

Note: `backend/test_api.py` is a manual script that makes an HTTP call at import time and errors
during collection unless a server is running. It is **not** part of the 144 and predates this work.

RAG tests use the deterministic `hashing` embedding provider, so they need no model download and
no network.

---

## 16. Important Files Created / Modified

### `backend/rag/` — the RAG module (all new)

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker, version |
| `config.py` | Env-driven settings: chunking, PDF extraction, exclusions, corpus dir |
| `contracts.py` | Ingestion types: `Chunk`, `PageRecord`, `Heading`, provenance enums |
| `pdf_extract.py` | PDF parsing: columns, word gaps, headings, folio recovery, ToC/bibliography exclusion |
| `chunking.py` | Section-aware chunking with page attribution |
| `verify.py` | 20-chunk metadata verification gate (markdown + JSON) |
| `store.py` | SQLite: documents, chunks, embeddings, retrieval log |
| `embeddings.py` | Providers: `local` (sentence-transformers), `tfidf`, `tfidf-svd`, `hashing` |
| `index.py` | CLI: embed the corpus |
| `ingest.py` | CLI: parse → chunk → verify → persist |
| `retrieve.py` | Top-k cosine, evidence IDs, `retrievalId`, `chunkSetHash`, logging |
| `sufficiency.py` | Evidence-sufficiency signal + calibration record binding |
| `answer_contracts.py` | `PatientContext`, `EvidenceSet`, `GroundedAnswer`, `Refusal`, `SystemFailure` |
| `prompting.py` | Strict grounding prompt with two disjoint blocks; model-JSON parsing |
| `generation.py` | Extractive baseline + Anthropic + OpenAI providers |
| `guardrails.py` | Closed-set citation validation, claim dropping, refusal builders |
| `answering.py` | Orchestration + single-retrieval guarantee |
| `service.py` | Flask blueprint: `/rag/health`, `/documents`, `/retrieve`, `/answer` |
| `README.md` | Module documentation with measured results |
| `corpus/corpus.db` | The indexed ESC corpus (SQLite) |
| `corpus/calibration.json` | Active sufficiency calibration record |
| `corpus/reports/esc-hf-2021_*.{md,json}` | Verification sample + ingest report |

### `eval/` — evaluation harness (all new)

| File | Responsibility |
|---|---|
| `goldset.py` | GOLD schema, validation, span/page matchers |
| `questions_v1.yaml` | **GOLD-v1**, 20 real ESC cases |
| `run_eval.py` | Precision@k, Recall@k, MRR, latency; `--with-answers` adds the answer path |
| `sweep.py` | Chunk size × overlap × model comparison |
| `calibrate.py` | Sufficiency threshold sweep + operating-point selection |
| `scaffold_gold.py` | Emits a GOLD skeleton from an ingested corpus |
| `results/*.json` | Measured outputs (see §7) |

### `tests/` — new

| File | Responsibility |
|---|---|
| `test_rag_ingest.py` | Chunking, metadata honesty, verification sample, store, blueprint |
| `test_rag_retrieval.py` | Embeddings, vector storage, retrieval, gold matchers, harness |
| `test_rag_generation.py` | Prompting, citation validation, refusal, single-retrieval guarantee |
| `fixtures/synthetic_hf_guideline.pdf` | Synthetic test-fixture PDF |
| `fixtures/synthetic_gold.yaml` | Fixture gold set — **not** Cardios metrics |

### Frontend

| File | Change |
|---|---|
| `src/pages/EvidenceAdvisor.tsx` | Clinical Evidence Advisor page (header & clinical notice updated) |
| `src/pages/Home.tsx` | Redesigned Home page unifying the 3 intelligence areas |
| `src/pages/ECGPrediction.tsx` | ECG Lab rewritten to upload-only workflow (live mode & device polling removed) |
| `src/components/PredictionForm.tsx` | Heart Risk form updated with clinical notice and unified header |
| `src/components/ui/ClinicalNotice.tsx` | **New** — reusable clinical context notice component (info, caution, limitation, error) |
| `src/components/layout/Header.tsx` | Cleaned navigation (Home, Heart Risk, ECG Lab, Evidence Advisor, About) |
| `src/components/layout/Footer.tsx` | Aligned footer navigation links with header |
| `src/services/ragService.ts` | Typed RAG client, bounded optional auth |
| `src/App.tsx` | Cleaned routes (removed /ecg-test route) |
| `vite.config.ts` | Host/port pinned (see §18) |

### Backend (existing files, minimally modified)

| File | Change |
|---|---|
| `backend/app.py` | `.env` loading; RAG blueprint registration (defensive); `ragCorpus` in `/health/ready` |
| `backend/safety.py` | Added `RAG_EVIDENCE_DISCLAIMER` + `attach_evidence_disclaimer()` |

### Supabase / documentation

| File | Responsibility |
|---|---|
| `supabase/bootstrap.sql` | Full from-scratch schema — **do not run against the live project** (§14) |
| `supabase/bootstrap_verify.sql` | Read-only schema verifier |
| `supabase/demo_seed.sql` | Demo clinical history seed (requires accounts to exist first) |
| `SUPABASE_SETUP.md` | Setup walkthrough |
| `run_cardios.ps1` | Windows launcher with venv repair |
| `README.md` | Updated — three intelligence layers, Evidence Advisor |
| `Cardios_Project_Summary_Report.md` (repo root, one level up) | Corrected provenance |

---

## 17. Dependencies

### Already present before this work

`Flask 3.1`, `flask-cors`, `flask-limiter`, `flasgger`, `python-dotenv`, `requests`, `pydantic 2`,
`PyJWT`, `joblib`, `numpy 1.26.4`, `pandas`, `scikit-learn 1.6.1`, `scipy`, `xgboost 3.0`,
`tensorflow 2.16.2`, `keras 3.5`, `zeroconf`.

### Newly added for the RAG module

| Package | Version | Why |
|---|---|---|
| `pdfplumber` | 0.11.9 | Layout-aware PDF extraction with per-character font metrics; bundles `pdfminer.six`, which also exposes the outline and page-label tree. One dependency covers all of ingestion. Chosen over PyMuPDF (AGPL) |
| `sentence-transformers` | 3.3.1 | Local semantic embedding baseline — **installed but weights never downloaded** (§8) |
| `PyYAML` | 6.0.2 | Gold sets are YAML; declared explicitly because the harness imports it directly |

The TF-IDF providers added **no** new dependency — they use scikit-learn, already present.

Frontend: **no new npm packages.**

---

## 18. Environment / Runtime Notes

Project root: `E:\hakason\Cardios V3`
Source PDF: `E:\hakason\ESC_Heart_Failure_Guideline_2021.pdf`

### Start everything (recommended)

```powershell
cd "E:\hakason\Cardios V3"
powershell -ExecutionPolicy Bypass -File .\run_cardios.ps1
```

Frees the ports, repairs the venv if it points at a missing base Python, starts the backend,
**waits until `/health` actually answers** (the ECG model takes 20–60 s to load), starts the
frontend, opens the browser.

### Start manually (two windows)

```powershell
# Window 1 — backend on :49232
.\.venv311\Scripts\python.exe backend\app.py

# Window 2 — frontend on :5176 (host/port are pinned in vite.config.ts)
npm run dev
```

> Do **not** pass `--port` on the command line. PowerShell strips the leading dashes from
> arguments after `npm run dev --`, so Vite received bare positional values, ignored them, and
> started on its default 5173. That is why host and port now live in `vite.config.ts`.

App: `http://127.0.0.1:5176/` · Evidence Advisor: `http://127.0.0.1:5176/evidence`

### RAG operations

```powershell
# Ingest a guideline PDF (writes the verification sample)
cd backend
..\.venv311\Scripts\python.exe -m rag.ingest "E:\hakason\ESC_Heart_Failure_Guideline_2021.pdf" `
  --title "2021 ESC Guidelines for the diagnosis and treatment of acute and chronic heart failure" `
  --id esc-hf-2021 --publisher "European Society of Cardiology" --version "2021" `
  --url "https://doi.org/10.1093/eurheartj/ehab368"
# GATE: review backend\rag\corpus\reports\esc-hf-2021_verification_sample.md
#       at least 19 of 20 sampled chunks must carry the correct document, page and section

# Embed / index the corpus
..\.venv311\Scripts\python.exe -m rag.index
cd ..

# Evaluate retrieval
.\.venv311\Scripts\python.exe -m eval.run_eval --gold eval\questions_v1.yaml --k 3 5 10 --tag baseline

# Full evaluation including the answer path
.\.venv311\Scripts\python.exe -m eval.run_eval --gold eval\questions_v1.yaml --k 3 5 10 `
  --tag full --with-answers

# Sweep chunk size / overlap / model
.\.venv311\Scripts\python.exe -m eval.sweep --pdf "E:\hakason\ESC_Heart_Failure_Guideline_2021.pdf" `
  --title "2021 ESC Guidelines for the diagnosis and treatment of acute and chronic heart failure" `
  --document-id esc-hf-2021 --gold eval\questions_v1.yaml `
  --chunk-sizes 600 900 1200 --overlaps 100 200 --k 3 5 10 --select-on "k=5"

# Calibrate the sufficiency threshold (writes backend\rag\corpus\calibration.json)
.\.venv311\Scripts\python.exe -m eval.calibrate --gold eval\questions_v1.yaml --k 5 `
  --signals top1 margin --write-calibration

# Scaffold a gold skeleton from an ingested corpus
.\.venv311\Scripts\python.exe -m eval.scaffold_gold --out eval\questions_v2_draft.yaml
```

### Tests

```powershell
.\.venv311\Scripts\python.exe -m pytest tests\ -q        # 144 tests
npx tsc --noEmit
npx eslint .
npx vite build
```

### Key environment variables (`.env`)

```
EMBEDDING_PROVIDER=tfidf        # local | tfidf | tfidf-svd | hashing
EMBEDDING_MODEL=                # sentence-transformers model id when provider=local
LLM_PROVIDER=extractive         # extractive | anthropic | openai
RAG_CHUNK_SIZE=900
RAG_CHUNK_OVERLAP=200
AUTH_ENABLED=false              # backend JWT gate, off for local demo
```

`.env` is loaded by `backend/app.py` at startup (added this session) — before that, only shell
variables reached Flask, which silently broke the RAG configuration.

---

## 19. What Is COMPLETE

- [x] **ESC PDF ingestion** — real 128-page guideline, `MEASURED (REAL)`
- [x] **Parser** — two-column ordering, word-gap repair, heading detection, ToC + bibliography exclusion
- [x] **Metadata** — section attribution 94.1 %, provenance recorded per chunk, uncertainty surfaced not hidden
- [x] **Real journal page citations** — folios 3599–3726, verified at 99 % agreement across 128 pages
- [x] **20/20 metadata verification gate PASS**
- [x] **GOLD-v1** — 20 real cases, all 14 gold spans verified present in the corpus
- [x] **Evaluation harness** — Precision@k, Recall@k, MRR, latency, span + page matchers
- [x] **Lexical retrieval baseline** — measured, tuned, documented (`BASELINE ONLY`)
- [x] **Retrieval tuning framework** — 20 configurations swept, results persisted
- [x] **Retrieved Evidence UI** — public, complete, shows score/rank/document/section/page/evidence ID
- [x] **Single-retrieval integrity** — `retrievalId` + `chunkSetHash`, fails closed, tested
- [x] **Extractive generator** — grounded by construction, coverage 1.000, verbatim 1.000
- [x] **Citation validator** — closed-set, verbatim excerpt check, uncited claims dropped
- [x] **Sufficiency / refusal framework** — calibrated, model-bound, fails closed on mismatch
- [x] **Answer evaluation** — refusal accuracy, false-answer/false-refusal, citation accuracy
- [x] **Refusal vs system-failure separation** — distinct types, distinct HTTP codes, distinct UI
- [x] **Patient-context / evidence type separation** — structural, tested
- [x] **Real Supabase provenance correction** — stale project ref fixed, live DB verified
- [x] **Mentor-ready UI unification** — Home landing page redesigned around the 3 intelligence areas; clean navigation; public Evidence Advisor access
- [x] **ECG Lab simplification** — removed experimental Live Mode, ESP32 device polling, and separate ECG test page to provide a clean, reliable upload-only workflow
- [x] **Clinical safety notices** — structured disclaimer banners and non-diagnostic framing integrated across Heart Risk, ECG Lab, and Evidence Advisor
- [x] **Regression tests & build** — 142 passing, 2 skipped; typecheck (tsc), lint (eslint), and production build (vite) all green

---

## 20. What Is NOT FINAL

| Item | Status | Priority |
|---|---|---|
| **Semantic retrieval model selection** | `NOT IMPLEMENTED` (blocked only by weight download) | **HIGH** |
| **Semantic retrieval metrics** | `NOT MEASURED` | **HIGH** |
| **Final chunk / overlap / k configuration** | `NOT FINAL` — current values tuned for TF-IDF only | **HIGH** |
| **Sufficiency recalibration after embedding change** | `NOT DONE` — mandatory once the model changes | **HIGH** |
| **False-refusal reduction** (currently 0.500) | `NOT FINAL` — retrieval-limited | **HIGH** |
| **Citation accuracy vs gold** (currently 0.429) | `NOT FINAL` — retrieval-limited | **HIGH** |
| Retrieval failure analysis | `NOT IMPLEMENTED` | **HIGH** |
| Final LLM provider / model choice | `NOT SELECTED` — no key present | MEDIUM |
| Final generated-answer quality | `BASELINE ONLY` — extractive | MEDIUM |
| Browser auth / session smoke test | `MANUAL CHECK REQUIRED` | MEDIUM |
| GOLD-v2 / expanded evaluation | `NOT IMPLEMENTED` — GOLD-v1 is both dev and calibration set | MEDIUM |
| Patient-context injection into the UI | `NOT IMPLEMENTED` — plumbing exists | LOW |
| Hybrid retrieval (dense + BM25) | `NOT IMPLEMENTED` — deliberately deferred | LOW |
| ECG evaluation figures re-verified | `MANUAL CHECK REQUIRED` | LOW |

The six **HIGH** items are one connected chain: better embeddings → better retrieval → wider
score separation → recalibrated threshold → fewer false refusals → higher citation accuracy.
Working them in that order is what moves every downstream number at once.

---

## 21. Prioritised Next-Agent Work

**Strict execution order. Do not reopen completed work without evidence of a bug.**

### Priority 1 — Semantic retrieval experiment
Install weights, index 2–3 sentence-transformer models, evaluate each against GOLD-v1 holding
chunk 900 / overlap 200 / k 5 constant. Compare to the §7 TF-IDF baseline. (§8)

### Priority 2 — Retrieval failure analysis and limited tuning
Inspect every in-scope case missing from top-5, classify the cause, then run a **small** sweep
around the winning model. (§9)

### Priority 3 — Recalibrate evidence sufficiency
`python -m eval.calibrate --write-calibration` on the new embedding space. The old threshold is
invalid. Report the new false-answer / false-refusal rates and whether the distributions
separate. (§10)

### Priority 4 — Re-run the full answer / citation / refusal evaluation
`python -m eval.run_eval --with-answers`. Record the new citation accuracy vs gold, refusal
accuracy, and latency. Compare against §7 and §11.

### Priority 5 — Select and evaluate a final LLM generation provider
Set `LLM_PROVIDER` + `LLM_API_KEY`, then compare **against the extractive baseline** on the same
gold set: citation coverage, excerpt accuracy, citation accuracy vs gold, faithfulness, refusal
behaviour. Keep the extractive provider either way. (§11)

### Priority 6 — Improve the Evidence Advisor UX only where it helps the live demo
Judge-query affordances, clearer refusal presentation. Do not redesign. (§13)

### Priority 7 — Expand evaluation / GOLD-v2 if the hackathon requires it
Add held-out cases so the calibration threshold can be validated on data it was not fitted on —
this is the cleanest fix for the threshold-fragility noted in §10.

### Priority 8 — Final documentation and presentation preparation
Only after the numbers are final.

---

## 22. Things the Next Agent Should NOT Work On

Explicitly out of scope. Do **not** spend time on:

- ESP32, firmware, AD8232, hardware integration, device acquisition improvements
- Retraining the heart-risk model or the ECG model
- New disease modules (diabetes, hypertension) — Supabase tables exist but no code does, and
  building them scores nothing
- Mobile app
- Production deployment
- Large security-hardening projects
- Migrating the RAG corpus to Supabase/pgvector for architectural purity
- Rebuilding working RAG components
- Unnecessary architecture rewrites or further planning documents

The priority is winning the software/AI hackathon through **measurable retrieval, grounding,
evaluation and demo quality.**

---

## 23. Known Engineering Lessons / Traps

Practical traps discovered during implementation. Re-learning these costs hours.

1. **PDF page index ≠ journal page number.** The ESC PDF's own label tree says 1–128 while the
   printed folios read 3599–3726. Citations must use the folio; gold labels use the index; the
   `Citation` type carries both. This caused a real evaluation bug (§12).
2. **Two-column journal extraction interleaves lines** unless columns are cropped and read in
   order. Detect the gutter; do not assume `width/2`.
3. **Missing spaces in PDF text.** `patientswithHFrEF` — pdfplumber's default `x_tolerance=3.0`
   is too coarse for journal typesetting; 1.5 fixes it.
4. **ToC pollution.** Contents entries reproduce every heading verbatim and, being short and
   keyword-dense, outrank the real sections in retrieval. Exclude whole ToC pages, not just lines.
5. **Heading-detector bug — twice.** Decorative 11.8 pt leader dots inflated every line's font
   size; and matching extracted text lines to char runs *by position* silently misaligned words
   with the wrong font evidence. Build line text from the line's own characters.
6. **Over-fragmented sections reduce retrieval quality.** Fixing heading detection raised sections
   72 → 181, which *worsened* P@3 from 0.309 to 0.167 because chunks never cross section
   boundaries and became fragments. Re-tune chunk size whenever section granularity changes.
7. **SVD harmed score separation.** Latent semantic reduction collapsed in-scope vs out-of-domain
   top scores to ~0, making refusal impossible. Measure separation, not just precision.
8. **Citation coverage ≠ citation correctness.** Coverage was 1.000 while accuracy vs gold was
   0.429. Always report both.
9. **Retrieval quality currently limits answer quality.** No generator can cite a passage that was
   never retrieved. Fix retrieval before prompt engineering.
10. **Thresholds are configuration-specific.** A sufficiency threshold is bound to one embedding
    model + corpus version. Reusing it across models is meaningless; the code fails closed, but
    you must recalibrate.
11. **Synthetic fixture metrics are NOT Cardios metrics.** `tests/fixtures/synthetic_*` exists to
    exercise the harness. Never report those numbers as results.
12. **Fitting and evaluating on the same set flatters you.** GOLD-v1 is both the development and
    the calibration set; the threshold landed exactly on a borderline negative, and a one-word
    paraphrase flipped it. Held-out cases are the fix.
13. **`.env` was not read by the backend** until `python-dotenv` loading was added to
    `backend/app.py`. Configuration written to `.env` reached Vite but never Flask.
14. **Windows venvs are neither user-portable nor relocatable.** A venv built by another user or
    in another folder fails with `No Python at '...'`. `run_cardios.ps1` detects and repairs this.
15. **PowerShell strips dashes** from arguments after `npm run dev --`. Put host/port in
    `vite.config.ts`.

---

## NEXT AGENT — START HERE

1. **Read this handoff.** It is the source of truth; older repo docs conflict with the code.
2. **Inspect the current repository state** — `backend/rag/`, `eval/`, `tests/`,
   `src/pages/EvidenceAdvisor.tsx`.
3. **Do not re-analyse the completed architecture.** Ingestion, chunking, retrieval plumbing,
   citation integrity, refusal handling and the UI are done and tested.
4. **Run the existing tests** to confirm a clean starting point.
5. **Run semantic sentence-transformer retrieval against the real ESC corpus.**
6. **Compare against the documented TF-IDF baseline** (§7).
7. **Continue based on measured weaknesses**, following the Priority order in §21.

### Exact first commands

```powershell
cd "E:\hakason\Cardios V3"

# 4. confirm a clean baseline  (expect: 144 passed)
.\.venv311\Scripts\python.exe -m pytest tests\ -q

# 5. install deps and index a semantic model (first run downloads ~90 MB of weights)
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt
$env:EMBEDDING_PROVIDER="local"
$env:EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
cd backend
..\.venv311\Scripts\python.exe -m rag.index
cd ..

# 6. evaluate and compare against the TF-IDF baseline in section 7
.\.venv311\Scripts\python.exe -m eval.run_eval --gold eval\questions_v1.yaml --k 3 5 10 `
  --tag semantic-minilm

# beat these numbers:  P@3 0.262 | P@5 0.229 | R@5 0.571 | R@10 0.786 | MRR 0.448 | sep +0.176
```

Then: Priority 2 (failure analysis) → Priority 3 (recalibrate) → Priority 4 (full re-evaluation).
