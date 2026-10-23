"""Embed the ingested corpus and store the vectors.

    python -m rag.index [--model NAME] [--document-id ID] [--batch-size N]

Separate from ``rag.ingest`` on purpose: Phase 3 re-embeds the same chunks with
different models to compare them, and re-chunks without re-choosing a model.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import List, Optional

from rag.embeddings import get_provider
from rag.store import CorpusStore

logger = logging.getLogger(__name__)


def index_corpus(store: Optional[CorpusStore] = None, model: Optional[str] = None,
                 document_id: Optional[str] = None, batch_size: int = 32) -> dict:
    store = store or CorpusStore()
    provider = get_provider()
    if model:
        import os
        os.environ["EMBEDDING_MODEL"] = model
        from rag.embeddings import LocalSentenceTransformerProvider, reset_provider
        reset_provider()
        provider = LocalSentenceTransformerProvider(model)

    docs = store.documents()
    if document_id:
        docs = [d for d in docs if d["document_id"] == document_id]
    if not docs:
        raise RuntimeError("No ingested documents found. Run `python -m rag.ingest` first.")

    # A corpus-fitted provider (TF-IDF/LSA) must see the whole corpus first.
    from rag.embeddings import TfidfLexicalProvider, TfidfSvdProvider
    if isinstance(provider, (TfidfSvdProvider, TfidfLexicalProvider)):
        corpus_texts = [r["content"] for d in docs for r in store.chunks(d["document_id"])]
        if not corpus_texts:
            raise RuntimeError("No chunks to fit the embedding model on.")
        provider.fit(corpus_texts)

    started = time.perf_counter()
    total = 0
    for doc in docs:
        rows = store.chunks(doc["document_id"])
        if not rows:
            continue
        texts = [r["content"] for r in rows]
        indices = [r["chunk_index"] for r in rows]
        vectors = provider.encode(texts, batch_size=batch_size)
        store.store_embeddings(doc["document_id"], provider.model_id,
                               provider.dimension, indices, vectors)
        total += len(rows)
        logger.info("Indexed %d chunks of %s", len(rows), doc["document_id"])

    return {
        "modelId": provider.model_id,
        "dimension": provider.dimension,
        "isSemantic": provider.is_semantic,
        "documents": [d["document_id"] for d in docs],
        "chunksIndexed": total,
        "seconds": round(time.perf_counter() - started, 2),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="rag.index")
    parser.add_argument("--model", default=None)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = index_corpus(model=args.model, document_id=args.document_id,
                          batch_size=args.batch_size)
    for key, value in report.items():
        print(f"{key:>14}: {value}")
    if not report["isSemantic"]:
        print("\n!! The hashing provider is NOT semantic. Retrieval results are meaningless.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
