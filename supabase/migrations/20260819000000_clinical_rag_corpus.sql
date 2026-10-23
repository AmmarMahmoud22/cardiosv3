-- Cardios RAG module — guideline corpus schema (adaptation plan Phase 1.6).
--
-- Additive only: no existing Cardios table is altered. Embedding columns and
-- the vector index are created here but stay empty until the embedding
-- provider is chosen (Phase 0.5) and Phase 1.7 runs.
--
-- NOTE ON EMBEDDING DIMENSION: vector(N) must match the chosen embedding
-- model's output dimension. It is intentionally left as a placeholder below —
-- do not guess it. Set it when the provider decision is made, then apply.

-- create extension if not exists vector;

create table if not exists public.clinical_documents (
    document_id     text primary key,
    title           text not null,
    publisher       text,
    source_url      text,
    version         text,
    licence_note    text,
    file_sha256     text not null,
    page_count      integer not null,
    corpus_version  text not null default 'v1',
    ingested_at     timestamptz not null default now()
);

create table if not exists public.clinical_chunks (
    id                       bigserial primary key,
    document_id              text not null references public.clinical_documents(document_id) on delete cascade,
    chunk_index              integer not null,
    content                  text not null,
    section_title            text,
    section_path             text,
    -- outline | numbered_heading | styled_heading | inherited | unknown
    section_provenance       text not null default 'unknown',
    page_number              integer not null,
    page_end                 integer not null,
    page_label               text,
    -- declared | none
    page_label_provenance    text not null default 'none',
    spans_pages              boolean not null default false,
    char_count               integer not null default 0,
    word_count               integer not null default 0,
    corpus_version           text not null default 'v1',
    -- embedding              vector(<SET_WHEN_PROVIDER_CHOSEN>),
    created_at               timestamptz not null default now(),
    unique (document_id, chunk_index)
);

create index if not exists idx_clinical_chunks_doc_page
    on public.clinical_chunks (document_id, page_number);
create index if not exists idx_clinical_chunks_section
    on public.clinical_chunks (document_id, section_title);

-- Vector index — create after the embedding column exists and is populated.
-- create index if not exists idx_clinical_chunks_embedding
--     on public.clinical_chunks using hnsw (embedding vector_cosine_ops);

create table if not exists public.rag_ingest_reports (
    document_id text primary key references public.clinical_documents(document_id) on delete cascade,
    report      jsonb not null,
    created_at  timestamptz not null default now()
);

-- RLS: the guideline corpus is shared, read-only reference data. Writes happen
-- through the ingestion CLI using the service role, never from the client.
alter table public.clinical_documents   enable row level security;
alter table public.clinical_chunks      enable row level security;
alter table public.rag_ingest_reports   enable row level security;

drop policy if exists "clinical_documents_read" on public.clinical_documents;
create policy "clinical_documents_read" on public.clinical_documents
    for select to authenticated using (true);

drop policy if exists "clinical_chunks_read" on public.clinical_chunks;
create policy "clinical_chunks_read" on public.clinical_chunks
    for select to authenticated using (true);

drop policy if exists "rag_ingest_reports_read" on public.rag_ingest_reports;
create policy "rag_ingest_reports_read" on public.rag_ingest_reports
    for select to authenticated using (true);
