# Chunk metadata verification — AI Clinical Decision Support Lite

**Document ID:** `parser-fixture`  
**File SHA-256:** `45c4121e6caaf55596d68d2c79f739de…`  
**Sample size:** 12 chunks (evenly spaced, deterministic)

## Gate criterion

At least **19 of 20** sampled chunks must carry the correct document, the correct page,
and a plausible section title. Confirm each row against the PDF. The *Claimed page text*
column is the actual extracted text of the page the citation points at — if the chunk
excerpt does not appear there, the attribution is wrong.

| Auto-check | Meaning |
|---|---|
| `present_on_claimed_page` | The chunk's opening words were found verbatim on the page it cites. |
| `needs_human_check` | Not found automatically (often a page-spanning chunk). Verify by hand. |

**Automated pre-check:** 12/12 located on their claimed page; 0 need a human look.  
**Chunks with no section attribution in this sample:** 0 (these are reported, not guessed).

---

### 0. `AI Clinical Decision Support Lite › 1. Executive Overview › p.1`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 1. Executive Overview
- **Pages:** 1 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 279 chars

**Chunk text (start):**

> The AI Clinical Decision Support Lite Hackathon is a specialized 5-day technical competition. The goal is to design and implement a Retrieval-Augmented Generation (RAG) system that delivers evidence-based clinical recommendations grounded strictly in official medical guidelines.

**Claimed page text (start):**

> AI Clinical Decision Support Lite 1. Executive Overview The AI Clinical Decision Support Lite Hackathon is a specialized 5-day technical competition. The goal is to design and implement a Retrieval-Augmented Generation (RAG) system that delivers evidence-based clinical recommendations grounded strictly in official medical guidelines. 2. The Challenge Large Language Models (LLMs) can generate fluent medical advice, bu

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 1. `AI Clinical Decision Support Lite › 2. The Challenge › p.1`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 2. The Challenge
- **Pages:** 1 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 366 chars

**Chunk text (start):**

> Large Language Models (LLMs) can generate fluent medical advice, but they often "hallucinate" or provide unsupported claims. Participants must build a system that: • Ingests official medical PDFs. • Retrieves only relevant, high-quality evidence. • Generates responses strictly based on that evidence. • Provides transparent citations (Document Name, Section, Page).

**Claimed page text (start):**

> AI Clinical Decision Support Lite 1. Executive Overview The AI Clinical Decision Support Lite Hackathon is a specialized 5-day technical competition. The goal is to design and implement a Retrieval-Augmented Generation (RAG) system that delivers evidence-based clinical recommendations grounded strictly in official medical guidelines. 2. The Challenge Large Language Models (LLMs) can generate fluent medical advice, bu

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 2. `AI Clinical Decision Support Lite › 3. Content & Technical Requirements › p.1`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 3. Content & Technical Requirements
- **Pages:** 1 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 381 chars

**Chunk text (start):**

> Teams must develop a 4-layer architecture: 1. Document Ingestion Layer: PDF parsing, section-aware chunking, and vector indexing. 2. Retrieval Layer: Semantic search optimization and transparent chunk display. 3. Generation Layer: Strict grounding prompts and structured citation formatting. 4. Safety Layer: Hallucination detection and refusal mechanisms for out-of-scope queries.

**Claimed page text (start):**

> AI Clinical Decision Support Lite 1. Executive Overview The AI Clinical Decision Support Lite Hackathon is a specialized 5-day technical competition. The goal is to design and implement a Retrieval-Augmented Generation (RAG) system that delivers evidence-based clinical recommendations grounded strictly in official medical guidelines. 2. The Challenge Large Language Models (LLMs) can generate fluent medical advice, bu

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 3. `AI Clinical Decision Support Lite › 4. 5-Day Timeline › p.2`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 4. 5-Day Timeline
- **Pages:** 2 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 1189 chars

**Chunk text (start):**

> Day 1 — Research, Scope & Document Ingestion Objective: Define clinical scope and build a reliable ingestion pipeline. Tasks: • Select 1–2 official guideline PDFs. • Verify public accessibility and legal usability. • Parse PDF content (structured extraction preferred). • Implement section-aware chunking. • Generate embeddings. • Index chunks in vector database. • Store metadata (document name, section, page number). 

**Claimed page text (start):**

> 4. 5-Day Timeline Day 1 — Research, Scope & Document Ingestion Objective: Define clinical scope and build a reliable ingestion pipeline. Tasks: • Select 1–2 official guideline PDFs. • Verify public accessibility and legal usability. • Parse PDF content (structured extraction preferred). • Implement section-aware chunking. • Generate embeddings. • Index chunks in vector database. • Store metadata (document name, secti

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 4. `AI Clinical Decision Support Lite › 4. 5-Day Timeline › p.2-3`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 4. 5-Day Timeline
- **Pages:** 2–3 (spans a page break) · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 1162 chars

**Chunk text (start):**

> Tasks: • Design strict grounding prompts. • Prohibit external knowledge use. • Format citations clearly (document name, section, page number). • Structure response (recommendation, excerpt, citation). • Implement refusal behavior when context is insufficient. End-of-Day Outcome:Fully functional RAG pipeline with proper citation and refusal mechanism. Day 4 — Safety, Guardrails & Internal Evaluation Objective: Improve

**Claimed page text (start):**

> 4. 5-Day Timeline Day 1 — Research, Scope & Document Ingestion Objective: Define clinical scope and build a reliable ingestion pipeline. Tasks: • Select 1–2 official guideline PDFs. • Verify public accessibility and legal usability. • Parse PDF content (structured extraction preferred). • Implement section-aware chunking. • Generate embeddings. • Index chunks in vector database. • Store metadata (document name, secti

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 5. `AI Clinical Decision Support Lite › 4. 5-Day Timeline › p.3`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 4. 5-Day Timeline
- **Pages:** 3 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 327 chars

**Chunk text (start):**

> Presentation Requirements (15–30 minutes per team): • Problem & Scope (clinical topic and guideline source). • System Architecture (ingestion, retrieval, generation, safety). • Live Demonstration with judge-provided query. • Display retrieved chunks. • Generated structured response with citation. • Refusal case demonstration.

**Claimed page text (start):**

> • Implement refusal behavior when context is insufficient. End-of-Day Outcome:Fully functional RAG pipeline with proper citation and refusal mechanism. Day 4 — Safety, Guardrails & Internal Evaluation Objective: Improve reliability and quantify performance. Tasks: • Add retrieval confidence threshold. • Implement unsupported claim detection. • Test with in-scope, ambiguous, and out-of-domain queries. • Measure Retrie

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 6. `AI Clinical Decision Support Lite › 5. Selection Stages › p.3-4`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 5. Selection Stages
- **Pages:** 3–4 (spans a page break) · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 416 chars

**Chunk text (start):**

> 1. Initial Screening: Verification of technical skills (Python/APIs) and team composition (2–4 members). 2. Scope Approval (Day 1): Mentors review and approve the chosen clinical guidelines for legal and technical suitability. 3. Technical Milestone (Day 3): Internal review of the functional RAG pipeline and citation accuracy. 4. Final Evaluation (Day 5): Live presentation and stress-testing by the judging panel.

**Claimed page text (start):**

> • Implement refusal behavior when context is insufficient. End-of-Day Outcome:Fully functional RAG pipeline with proper citation and refusal mechanism. Day 4 — Safety, Guardrails & Internal Evaluation Objective: Improve reliability and quantify performance. Tasks: • Add retrieval confidence threshold. • Implement unsupported claim detection. • Test with in-scope, ambiguous, and out-of-domain queries. • Measure Retrie

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 7. `AI Clinical Decision Support Lite › 6. Judging Criteria (100 Points) › p.4`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 6. Judging Criteria (100 Points)
- **Pages:** 4 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 448 chars

**Chunk text (start):**

> • Retrieval Precision (30 pts): Accuracy of the evidence surfaced. • Answer Grounding & Citations (25 pts): No hallucinations and precise source tracking. • Architecture Design (15 pts): Technical clarity and modularity. • Evaluation Metrics (15 pts): Quality of the team’s internal testing methodology. • Clinical Safety (10 pts): Proper handling of insufficient evidence. • UX & Live Demo (5 pts): System usability and

**Claimed page text (start):**

> 4. Final Evaluation (Day 5): Live presentation and stress-testing by the judging panel. 6. Judging Criteria (100 Points) • Retrieval Precision (30 pts): Accuracy of the evidence surfaced. • Answer Grounding & Citations (25 pts): No hallucinations and precise source tracking. • Architecture Design (15 pts): Technical clarity and modularity. • Evaluation Metrics (15 pts): Quality of the team’s internal testing methodol

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 8. `AI Clinical Decision Support Lite › 7. Staff Roles › p.4`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 7. Staff Roles
- **Pages:** 4 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 284 chars

**Chunk text (start):**

> • Mentor: Provides technical guidance on RAG logic and ensures teams stay within the medical scope. • Trainer: Conducts workshops on prompt engineering, embeddings, and medical AI safety. • Operations: Manages the event schedule, logistics, and communication between teams and judges.

**Claimed page text (start):**

> 4. Final Evaluation (Day 5): Live presentation and stress-testing by the judging panel. 6. Judging Criteria (100 Points) • Retrieval Precision (30 pts): Accuracy of the evidence surfaced. • Answer Grounding & Citations (25 pts): No hallucinations and precise source tracking. • Architecture Design (15 pts): Technical clarity and modularity. • Evaluation Metrics (15 pts): Quality of the team’s internal testing methodol

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 9. `AI Clinical Decision Support Lite › 8. Recommended Data Sources › p.4-5`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 8. Recommended Data Sources
- **Pages:** 4–5 (spans a page break) · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 1135 chars

**Chunk text (start):**

> U.S. Preventive Services Task Force (USPSTF) Recommendations What it is: The gold standard for preventive medicine in the United States, covering screenings, counseling, and preventive medications. Why it’s perfect for RAG: The documents are strictly structured, publicly funded (no copyright hurdles for educational use), and feature explicit letter grades (A, B, C, D, I) for the strength of the evidence. Where to fin

**Claimed page text (start):**

> 4. Final Evaluation (Day 5): Live presentation and stress-testing by the judging panel. 6. Judging Criteria (100 Points) • Retrieval Precision (30 pts): Accuracy of the evidence surfaced. • Answer Grounding & Citations (25 pts): No hallucinations and precise source tracking. • Architecture Design (15 pts): Technical clarity and modularity. • Evaluation Metrics (15 pts): Quality of the team’s internal testing methodol

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 10. `AI Clinical Decision Support Lite › 8. Recommended Data Sources › p.5`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 8. Recommended Data Sources
- **Pages:** 5 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 1190 chars

**Chunk text (start):**

> What it is: The official digital library of the World Health Organization's published material and clinical guidelines. Why it’s perfect for RAG: It offers a massive array of global health topics. The PDFs are open-access, clearly cited, and often come with executive summaries that are great for testing retrieval accuracy. Where to find it: WHO IRIS Portal European Society of Cardiology (ESC) Clinical Practice Guidel

**Claimed page text (start):**

> NICE Guidance Portals (UK) What it is: The UK’s National Institute for Health and Care Excellence provides comprehensive, evidence-based guidance for health and social care. Why it’s perfect for RAG: NICE documents are legendary for their rigorous formatting. They separate 'Recommendations' from 'Context' and 'Evidence,' making chunking and embedding highly predictable. Where to find it: NICE Published Guidance WHO I

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---

### 11. `AI Clinical Decision Support Lite › 8. Recommended Data Sources › p.5`

- **Section provenance:** `numbered_heading`  ⚠️ inferred from layout, not declared by the PDF
- **Section path:** 8. Recommended Data Sources
- **Pages:** 5 · label: _none declared_ (`none`)
- **Auto-check:** `present_on_claimed_page` · 341 chars

**Chunk text (start):**

> evidence- based guidelines. Many organizations (like BMJ Rapid Recommendations) publish here. Why it’s perfect for RAG: It uses the GRADE methodology for assessing evidence certainty. While it is a web platform, most guidelines have a clean, highly structured PDF export option suitable for text chunking. Where to find it: MAGICapp Platform

**Claimed page text (start):**

> NICE Guidance Portals (UK) What it is: The UK’s National Institute for Health and Care Excellence provides comprehensive, evidence-based guidance for health and social care. Why it’s perfect for RAG: NICE documents are legendary for their rigorous formatting. They separate 'Recommendations' from 'Context' and 'Evidence,' making chunking and embedding highly predictable. Where to find it: NICE Published Guidance WHO I

**Verdict:** ☐ correct  ☐ wrong page  ☐ wrong section  ☐ other: ______

---
