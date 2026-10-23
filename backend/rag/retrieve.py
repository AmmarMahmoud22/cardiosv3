"""Dense semantic retrieval over the ingested guideline corpus.

Phase 2 scope: dense top-k only. Hybrid retrieval, BM25/RRF, and reranking are
deliberately NOT implemented — they are gated behind measured Phase-6 weakness.

Every retrieval produces a ``retrieval_id`` and a ``chunk_set_hash`` and is
persisted. That is what makes the later single-retrieval guarantee possible:
generation will load a chunk set by id rather than retrieving a second time, so
the evidence a judge sees is provably the evidence the model receives.

Similarity is exact brute-force cosine over normalised vectors. For a one- or
two-guideline corpus (thousands of chunks, not millions) this is sub-millisecond
and, unlike an ANN index, introduces no recall loss — so retrieval precision
measurements reflect the embedding model rather than index approximation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import List, Optional, Sequence

import numpy as np

from rag.embeddings import EmbeddingProvider, get_provider
from rag.store import CorpusStore

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
MAX_TOP_K = 50


def chunk_set_hash(items: Sequence[dict]) -> str:
    """Stable hash over the ordered evidence set (ids + content).

    Recomputed at generation time and compared, so a mismatch between what was
    displayed and what was used is detectable rather than assumed away.
    """
    h = hashlib.sha256()
    for item in items:
        h.update(f"{item['documentId']}\x1f{item['chunkIndex']}\x1f".encode("utf-8"))
        h.update(item["content"].encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


class Retriever:
    """Loads a model's vectors once and serves top-k queries against them."""

    def __init__(self, store: Optional[CorpusStore] = None,
                 provider: Optional[EmbeddingProvider] = None,
                 document_id: Optional[str] = None) -> None:
        self.store = store or CorpusStore()
        self.provider = provider or get_provider()
        self.document_id = document_id
        self._refs: List[tuple] = []
        self._matrix: Optional[np.ndarray] = None
        self.load()

    def load(self) -> int:
        self._fit_corpus_provider_if_needed()
        refs, vectors = self.store.load_embeddings(self.provider.model_id, self.document_id)
        self._refs = refs
        self._matrix = (np.asarray(vectors, dtype=np.float32)
                        if vectors else np.zeros((0, self.provider.dimension), dtype=np.float32))
        logger.info("Retriever loaded %d vectors for model %s", len(refs), self.provider.model_id)
        return len(refs)

    def _fit_corpus_provider_if_needed(self) -> None:
        """Corpus-fitted providers (TF-IDF/LSA) need the corpus at query time too.

        Fitting is deterministic (fixed random_state) over the same chunk set, so
        the query-time space matches the space the vectors were indexed in. If the
        corpus changes, re-run `python -m rag.index`.
        """
        from rag.embeddings import TfidfLexicalProvider, TfidfSvdProvider
        if isinstance(self.provider, TfidfLexicalProvider):
            if self.provider._vectorizer is not None:
                return
        elif isinstance(self.provider, TfidfSvdProvider):
            if self.provider._svd is not None:
                return
        else:
            return
        docs = self.store.documents()
        if self.document_id:
            docs = [d for d in docs if d["document_id"] == self.document_id]
        texts = [r["content"] for d in docs for r in self.store.chunks(d["document_id"])]
        if texts:
            self.provider.fit(texts)

    @property
    def size(self) -> int:
        return len(self._refs)

    def is_ready(self) -> bool:
        return self.size > 0

    def retrieve(self, question: str, k: int = DEFAULT_TOP_K, *,
                 log: bool = True) -> dict:
        """Return the top-``k`` evidence chunks for ``question``.

        Raises ``RuntimeError`` if the corpus has no vectors for the active
        model — an infrastructure state, deliberately distinct from an
        evidence-insufficiency refusal (which arrives in Phase 5).
        """
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string")
        k = max(1, min(int(k), MAX_TOP_K))
        if not self.is_ready():
            raise RuntimeError(
                f"No embeddings indexed for model '{self.provider.model_id}'. "
                "Run `python -m rag.index` after ingestion.")

        started = time.perf_counter()
        query_vec = self.provider.encode_one(question)
        # Vectors are L2-normalised on both sides, so the dot product IS cosine.
        scores = self._matrix @ query_vec
        top = np.argsort(-scores)[:k]

        refs = [self._refs[i] for i in top]
        rows = self.store.chunks_by_ref(refs)

        items: List[dict] = []
        for rank, idx in enumerate(top, start=1):
            ref = self._refs[idx]
            row = rows.get((ref[0], int(ref[1])))
            if row is None:          # embedding without its chunk: corpus drift
                logger.warning("Embedding %s has no chunk row; skipping", ref)
                continue
            items.append({
                "evidenceId": f"E{rank}",
                "rank": rank,
                "score": round(float(scores[idx]), 6),
                "documentId": row["document_id"],
                "chunkIndex": row["chunk_index"],
                "content": row["content"],
                "sectionTitle": row["section_title"],
                "sectionPath": row["section_path"],
                "sectionProvenance": row["section_provenance"],
                "pageNumber": row["page_number"],
                "pageEnd": row["page_end"],
                "pageLabel": row["page_label"],
                "pageLabelProvenance": row["page_label_provenance"],
                "spansPages": bool(row["spans_pages"]),
            })

        titles = {d["document_id"]: d["title"] for d in self.store.documents()}
        for item in items:
            item["documentTitle"] = titles.get(item["documentId"], item["documentId"])
            page = item["pageLabel"] or str(item["pageNumber"])
            if item["pageEnd"] != item["pageNumber"]:
                page = f"{page}-{item['pageEnd']}"
            section = item["sectionTitle"] or "(section not determined)"
            item["citation"] = f"{item['documentTitle']} › {section} › p.{page}"

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        set_hash = chunk_set_hash(items)
        retrieval_id = uuid.uuid4().hex

        result = {
            "retrievalId": retrieval_id,
            "chunkSetHash": set_hash,
            "question": question,
            "k": k,
            "modelId": self.provider.model_id,
            "corpusSize": self.size,
            "latencyMs": latency_ms,
            "chunks": items,
            "scores": [i["score"] for i in items],
        }

        if log:
            try:
                self.store.log_retrieval(
                    retrieval_id, question, k,
                    {"modelId": self.provider.model_id, "corpusSize": self.size},
                    [(i["documentId"], i["chunkIndex"]) for i in items],
                    set_hash, [i["score"] for i in items], latency_ms)
            except Exception:  # noqa: BLE001 — logging must never break retrieval
                logger.exception("Failed to log retrieval %s", retrieval_id)

        return result
