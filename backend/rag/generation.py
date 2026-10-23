"""Generation providers for the grounded-answer layer.

Three providers:

  ``anthropic`` / ``openai``  hosted LLMs, called over plain HTTP so no vendor
                              SDK is added to the dependency set.
  ``extractive``              offline, deterministic, and grounded by
                              construction: it can only copy sentences out of
                              the retrieved evidence, so it cannot hallucinate.
                              It is NOT a language model and is labelled as an
                              extractive baseline everywhere it surfaces. It
                              exists so the full pipeline — citation validation,
                              refusal, evaluation, demo — runs with no API key,
                              and so faithfulness has a ceiling to compare
                              against.

Every provider returns the same JSON shape defined in ``rag.prompting``.
Provider failures raise ``GenerationUnavailable``; the caller converts that to a
``SystemFailure``, never to a refusal.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import List, Optional, Sequence

from rag.answer_contracts import EvidenceSet, PatientContext
from rag.prompting import build_messages, parse_model_json

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "is",
    "are", "be", "should", "what", "which", "does", "do", "how", "when", "who",
    "recommended", "recommend", "guideline", "guidelines", "patient", "patients",
}


class GenerationUnavailable(RuntimeError):
    """The generation provider could not produce a response. Infrastructure."""


class GenerationProvider:
    name: str = "unset"
    is_language_model: bool = True

    def generate(self, question: str, evidence: EvidenceSet,
                 patient_context: Optional[PatientContext] = None) -> dict:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# offline extractive baseline
# ---------------------------------------------------------------------------
def _singular(word: str) -> str:
    """Crude plural folding so 'diuretics' matches a query for 'diuretic'.

    Not a stemmer. Enough to stop trivial plural mismatches sinking the lexical
    baseline; anything more is the neural model's job.
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _terms(text: str) -> set:
    return {_singular(w) for w in _WORD.findall((text or "").lower())
            if w not in _STOP and len(w) > 2}


class ExtractiveProvider(GenerationProvider):
    """Selects the most question-relevant sentences from the retrieved evidence.

    Grounded by construction: the recommendation text IS the excerpt, copied
    verbatim, so it cannot assert anything the guideline does not say. The
    trade-off is that it cannot synthesise or reword — which is exactly why it
    is a baseline and not the target implementation.
    """

    name = "extractive-baseline"
    is_language_model = False

    def __init__(self, max_recommendations: int = 3, min_overlap: int = 1) -> None:
        self.max_recommendations = max_recommendations
        self.min_overlap = min_overlap

    def generate(self, question: str, evidence: EvidenceSet,
                 patient_context: Optional[PatientContext] = None) -> dict:
        # patient_context is accepted and deliberately ignored: it is context,
        # never a source, and this provider only ever copies from evidence.
        q_terms = _terms(question)
        scored = []
        for item in evidence.items:
            for sentence in _SENTENCE_SPLIT.split(item.content):
                sentence = sentence.strip()
                if len(sentence) < 25:
                    continue
                overlap = len(q_terms & _terms(sentence))
                if overlap >= self.min_overlap:
                    scored.append((overlap, item.score, item.evidence_id, sentence))

        scored.sort(key=lambda t: (-t[0], -t[1]))
        if not scored:
            return {
                "mode": "refusal",
                "reason": "insufficient_evidence",
                "message": ("The retrieved guideline passages do not contain text matching "
                            "this question."),
            }

        seen, recommendations = set(), []
        for _overlap, _score, evidence_id, sentence in scored:
            if sentence in seen:
                continue
            seen.add(sentence)
            recommendations.append({
                "text": sentence,
                "excerpt": sentence,
                "evidence_ids": [evidence_id],
            })
            if len(recommendations) >= self.max_recommendations:
                break

        return {"mode": "answer", "recommendations": recommendations}


# ---------------------------------------------------------------------------
# hosted providers
# ---------------------------------------------------------------------------
class _HttpLlmProvider(GenerationProvider):
    endpoint: str = ""
    timeout: int = 60

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key
        self.name = f"{self.__class__.__name__.replace('Provider', '').lower()}:{model}"

    def _post(self, headers: dict, payload: dict) -> dict:
        import requests
        try:
            response = requests.post(self.endpoint, headers=headers, json=payload,
                                     timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001
            raise GenerationUnavailable(f"provider request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise GenerationUnavailable(
                f"provider returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise GenerationUnavailable("provider returned non-JSON body") from exc


class AnthropicProvider(_HttpLlmProvider):
    endpoint = "https://api.anthropic.com/v1/messages"

    def generate(self, question, evidence, patient_context=None) -> dict:
        messages = build_messages(question, evidence, patient_context)
        body = self._post(
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
             "content-type": "application/json"},
            {"model": self.model, "max_tokens": 1500, "temperature": 0,
             "system": messages["system"],
             "messages": [{"role": "user", "content": messages["user"]}]})
        try:
            text = "".join(block.get("text", "") for block in body.get("content", []))
        except Exception as exc:  # noqa: BLE001
            raise GenerationUnavailable("unexpected provider response shape") from exc
        return parse_model_json(text)


class OpenAIProvider(_HttpLlmProvider):
    endpoint = "https://api.openai.com/v1/chat/completions"

    def generate(self, question, evidence, patient_context=None) -> dict:
        messages = build_messages(question, evidence, patient_context)
        body = self._post(
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            {"model": self.model, "temperature": 0,
             "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": messages["system"]},
                          {"role": "user", "content": messages["user"]}]})
        try:
            text = body["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            raise GenerationUnavailable("unexpected provider response shape") from exc
        return parse_model_json(text)


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------
def get_generation_provider(force: Optional[str] = None) -> GenerationProvider:
    """Build the configured provider.

    ``LLM_PROVIDER``: ``extractive`` (default when no key is present),
    ``anthropic``, or ``openai``.
    """
    name = (force or os.getenv("LLM_PROVIDER") or "").strip().lower()
    key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    if not name:
        name = "extractive"
    if name == "extractive":
        return ExtractiveProvider()
    if not key:
        raise GenerationUnavailable(
            f"LLM_PROVIDER='{name}' but LLM_API_KEY is not set. Set it, or use "
            "LLM_PROVIDER=extractive for the offline grounded baseline.")
    if name == "anthropic":
        return AnthropicProvider(model or "claude-sonnet-4-5", key)
    if name == "openai":
        return OpenAIProvider(model or "gpt-4o-mini", key)
    raise GenerationUnavailable(f"unknown LLM_PROVIDER: {name!r}")


def provider_state() -> str:
    """``ok`` | ``extractive_fallback`` | ``not_configured`` — for /rag/health."""
    name = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if not name or name == "extractive":
        return "extractive_fallback"
    return "ok" if os.getenv("LLM_API_KEY", "").strip() else "not_configured"
