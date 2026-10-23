"""Local SQLite staging store for the ingested guideline corpus.

Phase 1 scope. Embeddings are NOT stored here — the pgvector schema in
``supabase/migrations/`` becomes the system of record once the embedding
provider is chosen (Phase 1.7). This store exists so that ingestion, metadata
verification, and ``GET /rag/documents`` work with no external dependency and
no provider decision.

Follows the same SQLite-with-WAL pattern already used by
``backend/device_store.py`` so operational behaviour is familiar.
"""
from __future__ import annotations

import json
import sqlite3
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from rag.config import CORPUS_DB, CORPUS_DIR
from rag.contracts import Chunk, SourceDocument

_SCHEMA = """
create table if not exists documents (
    document_id     text primary key,
    title           text not null,
    publisher       text,
    source_url      text,
    version         text,
    licence_note    text,
    file_sha256     text not null,
    page_count      integer not null,
    corpus_version  text not null,
    ingested_at     text not null
);
create table if not exists chunks (
    document_id             text not null references documents(document_id),
    chunk_index             integer not null,
    content                 text not null,
    section_title           text,
    section_path            text,
    section_provenance      text not null,
    page_number             integer not null,
    page_end                integer not null,
    page_label              text,
    page_label_provenance   text not null,
    spans_pages             integer not null,
    char_count              integer not null,
    word_count              integer not null,
    corpus_version          text not null,
    primary key (document_id, chunk_index)
);
create index if not exists idx_chunks_page on chunks(document_id, page_number);
create table if not exists embeddings (
    document_id  text not null,
    chunk_index  integer not null,
    model_id     text not null,
    dimension    integer not null,
    vector       blob not null,
    primary key (document_id, chunk_index, model_id)
);
create table if not exists rag_retrievals (
    retrieval_id    text primary key,
    question        text not null,
    k               integer not null,
    params_json     text not null,
    chunk_refs_json text not null,
    chunk_set_hash  text not null,
    scores_json     text not null,
    latency_ms      real not null,
    created_at      text not null
);
create table if not exists ingest_reports (
    document_id text primary key references documents(document_id),
    report_json text not null,
    created_at  text not null
);
"""


class CorpusStore:
    """Thread-safe SQLite store for documents, chunks, and ingest reports."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else CORPUS_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("pragma journal_mode=WAL")
            conn.executescript(_SCHEMA)

    # --- writes -------------------------------------------------------
    def replace_document(self, document: SourceDocument, chunks: List[Chunk],
                         report_json: str = "") -> None:
        """Insert or replace a document and all of its chunks atomically.

        Raises ``ValueError`` if any chunk belongs to a different document. A
        mismatch here would silently orphan chunks and corrupt citations, so it
        fails loudly rather than writing inconsistent provenance.
        """
        mismatched = sorted({c.document_id for c in chunks} - {document.document_id})
        if mismatched:
            raise ValueError(
                f"chunk document_id mismatch: document is '{document.document_id}' but "
                f"chunks reference {mismatched}")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("delete from embeddings where document_id = ?", (document.document_id,))
            conn.execute("delete from chunks where document_id = ?", (document.document_id,))
            conn.execute("delete from ingest_reports where document_id = ?", (document.document_id,))
            conn.execute("delete from documents where document_id = ?", (document.document_id,))
            conn.execute(
                """insert into documents (document_id, title, publisher, source_url, version,
                       licence_note, file_sha256, page_count, corpus_version, ingested_at)
                   values (?,?,?,?,?,?,?,?,?,?)""",
                (document.document_id, document.title, document.publisher, document.source_url,
                 document.version, document.licence_note, document.file_sha256,
                 document.page_count, document.corpus_version, document.ingested_at or now))
            conn.executemany(
                """insert into chunks (document_id, chunk_index, content, section_title,
                       section_path, section_provenance, page_number, page_end, page_label,
                       page_label_provenance, spans_pages, char_count, word_count, corpus_version)
                   values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(c.document_id, c.chunk_index, c.content, c.section_title, c.section_path,
                  c.section_provenance.value, c.page_number, c.page_end, c.page_label,
                  c.page_label_provenance.value, int(c.spans_pages), c.char_count,
                  c.word_count, c.corpus_version) for c in chunks])
            if report_json:
                conn.execute(
                    "insert into ingest_reports (document_id, report_json, created_at) values (?,?,?)",
                    (document.document_id, report_json, now))

    # --- reads --------------------------------------------------------
    def documents(self) -> List[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """select d.*, (select count(*) from chunks c where c.document_id = d.document_id)
                          as chunk_count
                   from documents d order by d.ingested_at""").fetchall()
            return [dict(r) for r in rows]

    def chunks(self, document_id: str, limit: Optional[int] = None) -> List[dict]:
        sql = "select * from chunks where document_id = ? order by chunk_index"
        if limit:
            sql += f" limit {int(limit)}"
        with self._lock, self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (document_id,)).fetchall()]

    def stats(self) -> dict:
        with self._lock, self._connect() as conn:
            docs = conn.execute("select count(*) from documents").fetchone()[0]
            chunks = conn.execute("select count(*) from chunks").fetchone()[0]
            prov = conn.execute(
                "select section_provenance, count(*) from chunks group by section_provenance"
            ).fetchall()
        models = self.embedding_models()
        return {
            "documents": docs,
            "chunks": chunks,
            "embeddingModels": models,
            "embeddedChunks": sum(m["n"] for m in models),
            "sectionProvenance": {r[0]: r[1] for r in prov},
            "dbPath": str(self.db_path),
        }

    # --- embeddings -------------------------------------------------
    def store_embeddings(self, document_id: str, model_id: str, dimension: int,
                         chunk_indices, vectors) -> None:
        """Persist one vector per chunk for a given embedding model.

        Vectors for different models coexist, so a Phase-3 model comparison does
        not require re-ingesting the corpus.
        """
        rows = [(document_id, int(i), model_id, int(dimension),
                 struct.pack(f"<{dimension}f", *[float(x) for x in vec]))
                for i, vec in zip(chunk_indices, vectors)]
        with self._lock, self._connect() as conn:
            conn.execute("delete from embeddings where document_id = ? and model_id = ?",
                         (document_id, model_id))
            conn.executemany(
                "insert into embeddings (document_id, chunk_index, model_id, dimension, vector)"
                " values (?,?,?,?,?)", rows)

    def load_embeddings(self, model_id: str, document_id: str = None):
        """Return ``(refs, matrix)`` for a model. ``refs`` are (document_id, chunk_index)."""
        sql = ("select document_id, chunk_index, dimension, vector from embeddings "
               "where model_id = ?")
        args = [model_id]
        if document_id:
            sql += " and document_id = ?"
            args.append(document_id)
        sql += " order by document_id, chunk_index"
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        refs = [(r["document_id"], r["chunk_index"]) for r in rows]
        vectors = [struct.unpack(f"<{r['dimension']}f", r["vector"]) for r in rows]
        return refs, vectors

    def embedding_models(self) -> List[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "select model_id, dimension, count(*) as n from embeddings group by model_id, dimension"
            ).fetchall()
        return [dict(r) for r in rows]

    def chunks_by_ref(self, refs) -> dict:
        """Fetch chunk rows for ``[(document_id, chunk_index), ...]``."""
        if not refs:
            return {}
        out = {}
        with self._lock, self._connect() as conn:
            for doc_id, idx in refs:
                row = conn.execute(
                    "select * from chunks where document_id = ? and chunk_index = ?",
                    (doc_id, int(idx))).fetchone()
                if row:
                    out[(doc_id, int(idx))] = dict(row)
        return out

    # --- retrieval log ------------------------------------------------
    def log_retrieval(self, retrieval_id: str, question: str, k: int, params: dict,
                      chunk_refs, chunk_set_hash: str, scores, latency_ms: float) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """insert or replace into rag_retrievals (retrieval_id, question, k, params_json,
                       chunk_refs_json, chunk_set_hash, scores_json, latency_ms, created_at)
                   values (?,?,?,?,?,?,?,?,?)""",
                (retrieval_id, question, int(k), json.dumps(params),
                 json.dumps([[d, int(i)] for d, i in chunk_refs]), chunk_set_hash,
                 json.dumps([float(s) for s in scores]), float(latency_ms), now))

    def get_retrieval(self, retrieval_id: str) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute("select * from rag_retrievals where retrieval_id = ?",
                               (retrieval_id,)).fetchone()
        if not row:
            return None
        rec = dict(row)
        rec["chunk_refs"] = [(d, int(i)) for d, i in json.loads(rec.pop("chunk_refs_json"))]
        rec["params"] = json.loads(rec.pop("params_json"))
        rec["scores"] = json.loads(rec.pop("scores_json"))
        return rec

    def retrieval_count(self) -> int:
        with self._lock, self._connect() as conn:
            return conn.execute("select count(*) from rag_retrievals").fetchone()[0]

    def healthcheck(self) -> bool:
        try:
            with self._lock, self._connect() as conn:
                conn.execute("select 1").fetchone()
            return True
        except Exception:  # noqa: BLE001
            return False

    def ingest_report(self, document_id: str) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "select report_json from ingest_reports where document_id = ?",
                (document_id,)).fetchone()
        return json.loads(row[0]) if row else None
