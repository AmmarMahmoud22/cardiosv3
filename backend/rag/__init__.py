"""Cardios RAG module — guideline-grounded clinical evidence retrieval.

Phase 1 scope: document ingestion and metadata verification only.
Retrieval, generation, and safety layers are added in later phases.

This package is additive: it does not modify or depend on the existing ECG,
heart-failure risk, hardware, or WAT components.
"""
from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
