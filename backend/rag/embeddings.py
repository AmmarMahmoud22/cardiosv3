"""Embedding providers.

Baseline is local ``sentence-transformers`` — no API key, no budget, no network
at query time. The provider is abstracted so Phase 3 can compare models by
changing ``EMBEDDING_MODEL`` rather than editing code.

A deterministic hashing provider is included for tests: it produces stable,
normalised vectors with no model download, so the retrieval, storage, and
evaluation code paths are testable in CI without a 90 MB model on disk. It is
NOT a semantic embedder and must never be used for real retrieval — selecting
it emits a warning and it is tagged as ``testing_only`` in the model id.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingProvider:
    """Interface: encode text to L2-normalised float32 vectors."""

    model_id: str = "unset"
    dimension: int = 0
    is_semantic: bool = True

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> np.ndarray:
        raise NotImplementedError

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


class LocalSentenceTransformerProvider(EmbeddingProvider):
    """sentence-transformers running in-process. The Phase-2 baseline."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "sentence-transformers is not installed. Install it with "
                "`pip install -r requirements.txt`, or set EMBEDDING_PROVIDER=hashing "
                "for tests only."
            ) from exc
        self.model_id = model_name or os.getenv("EMBEDDING_MODEL") or DEFAULT_LOCAL_MODEL
        self._model = SentenceTransformer(self.model_id)
        self.dimension = int(self._model.get_sentence_embedding_dimension())
        logger.info("Embedding provider: %s (dim=%d)", self.model_id, self.dimension)

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> np.ndarray:
        vectors = self._model.encode(
            list(texts), batch_size=batch_size, convert_to_numpy=True,
            normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)


class HashingProvider(EmbeddingProvider):
    """Deterministic token-hashing vectors. Tests only — not semantic."""

    def __init__(self, dimension: int = 256) -> None:
        self.model_id = f"hashing-{dimension}d (testing_only)"
        self.dimension = dimension
        self.is_semantic = False
        logger.warning("Using the hashing embedding provider — NOT semantic. Tests only.")

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> np.ndarray:
        out = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in (text or "").lower().split():
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                out[row, idx] += sign
            norm = float(np.linalg.norm(out[row]))
            if norm:
                out[row] /= norm
        return out


class TfidfSvdProvider(EmbeddingProvider):
    """TF-IDF + truncated SVD (latent semantic analysis) fitted on the corpus.

    Zero-download: uses scikit-learn, which Cardios already depends on. Two uses:

      1. A working offline baseline in environments that cannot reach the model
         hub, so the retrieval and evaluation paths stay measurable.
      2. A legitimate lexical baseline row in the Phase-3 comparison — a
         sentence-transformer that cannot beat TF-IDF on this corpus is not
         earning its cost.

    Unlike the hashing provider this IS semantic in the distributional sense,
    but it must be fitted on the corpus before use (``fit``), and the fitted
    state belongs to one corpus version.
    """

    def __init__(self, dimension: int = 256) -> None:
        self.model_id = f"tfidf-svd-{dimension}d"
        self.dimension = dimension
        self.is_semantic = True
        self._vectorizer = None
        self._svd = None

    def fit(self, corpus: Sequence[str]) -> "TfidfSvdProvider":
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english", ngram_range=(1, 2),
            sublinear_tf=True, min_df=1)
        matrix = self._vectorizer.fit_transform(list(corpus))
        n_components = int(min(self.dimension, max(2, min(matrix.shape) - 1)))
        self._svd = TruncatedSVD(n_components=n_components, random_state=0)
        self._svd.fit(matrix)
        self.dimension = n_components
        self.model_id = f"tfidf-svd-{n_components}d"
        logger.info("Fitted %s on %d documents", self.model_id, len(corpus))
        return self

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> np.ndarray:
        if self._vectorizer is None or self._svd is None:
            raise RuntimeError("TfidfSvdProvider must be fitted on the corpus before encoding")
        reduced = self._svd.transform(self._vectorizer.transform(list(texts)))
        reduced = np.asarray(reduced, dtype=np.float32)
        norms = np.linalg.norm(reduced, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (reduced / norms).astype(np.float32)


class TfidfLexicalProvider(EmbeddingProvider):
    """TF-IDF term vectors, corpus-fitted, with NO dimensionality reduction.

    Measured on the ESC corpus, truncated SVD roughly halved recall and — more
    importantly — collapsed the gap between in-scope and out-of-domain top
    scores to about zero, because the leading singular vectors capture the
    corpus-wide "cardiology prose" direction that every query projects onto.
    Keeping the term space intact preserves the rare clinical terms
    ("ivabradine", "ferric carboxymaltose") that actually discriminate, and
    restores a usable separation for the refusal gate.

    ``max_features`` caps the vector width so the existing fixed-width dense
    store works unchanged; cosine over the capped term space is identical to
    cosine over the sparse matrix restricted to those terms.
    """

    def __init__(self, max_features: int = 4096, ngram_max: int = 2,
                 min_df: int = 2, max_df: float = 0.35) -> None:
        self.max_features = max_features
        self.ngram_max = ngram_max
        self.min_df = min_df
        self.max_df = max_df
        self.model_id = f"tfidf-lexical-{max_features}d-ng{ngram_max}"
        self.dimension = max_features
        self.is_semantic = True
        self._vectorizer = None

    def fit(self, corpus: Sequence[str]) -> "TfidfLexicalProvider":
        from sklearn.feature_extraction.text import TfidfVectorizer

        corpus = list(corpus)
        min_df = self.min_df if len(corpus) > 20 else 1
        max_df = self.max_df if len(corpus) > 20 else 1.0
        self._vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english", ngram_range=(1, self.ngram_max),
            sublinear_tf=True, min_df=min_df, max_df=max_df,
            max_features=self.max_features)
        matrix = self._vectorizer.fit_transform(corpus)
        self.dimension = int(matrix.shape[1])
        self.model_id = f"tfidf-lexical-{self.dimension}d-ng{self.ngram_max}"
        logger.info("Fitted %s on %d documents", self.model_id, len(corpus))
        return self

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> np.ndarray:
        if self._vectorizer is None:
            raise RuntimeError("TfidfLexicalProvider must be fitted on the corpus before encoding")
        from sklearn.preprocessing import normalize

        return normalize(self._vectorizer.transform(list(texts))).toarray().astype(np.float32)


_provider: Optional[EmbeddingProvider] = None
_lock = threading.Lock()


def get_provider(force: Optional[str] = None) -> EmbeddingProvider:
    """Return the configured provider (cached).

    ``EMBEDDING_PROVIDER`` selects ``local`` (default, sentence-transformers),
    ``tfidf`` (offline lexical baseline), ``tfidf-svd`` (the reduced variant,
    kept for comparison), or ``hashing`` (tests only).
    """
    global _provider
    name = (force or os.getenv("EMBEDDING_PROVIDER") or "local").strip().lower()
    with _lock:
        if _provider is not None and force is None and _provider_matches(name):
            return _provider
        if name == "hashing":
            provider = HashingProvider()
        elif name == "tfidf":
            provider = TfidfLexicalProvider(
                max_features=int(os.getenv("EMBEDDING_DIM", "4096")),
                ngram_max=int(os.getenv("EMBEDDING_NGRAM_MAX", "2")),
                min_df=int(os.getenv("EMBEDDING_MIN_DF", "2")),
                max_df=float(os.getenv("EMBEDDING_MAX_DF", "0.35")))
        elif name == "tfidf-svd":
            provider = TfidfSvdProvider(int(os.getenv("EMBEDDING_DIM", "256")))
        else:
            provider = LocalSentenceTransformerProvider()
        if force is None:
            _provider = provider
        return provider


def _provider_matches(name: str) -> bool:
    if _provider is None:
        return False
    expected = {"hashing": HashingProvider, "tfidf": TfidfLexicalProvider,
                "tfidf-svd": TfidfSvdProvider}.get(name, LocalSentenceTransformerProvider)
    return isinstance(_provider, expected)


def reset_provider() -> None:
    """Drop the cached provider (used by tests that switch models)."""
    global _provider
    with _lock:
        _provider = None
