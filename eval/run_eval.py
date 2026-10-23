"""Retrieval evaluation harness (Phase 3).

    python -m eval.run_eval --gold eval/questions_v1.yaml --k 3 5 10
    python -m eval.run_eval --sweep --gold eval/questions_v1.yaml --pdf <guideline.pdf>

Retrieval-only: no LLM is involved anywhere in this file. That is the point —
retrieval can be measured and tuned before the generation provider exists.
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from eval.goldset import GoldCase, evaluate_case, load_goldset  # noqa: E402

logger = logging.getLogger(__name__)


def _mean(values: Sequence[float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def run_evaluation(retriever, cases: Sequence[GoldCase], ks: Sequence[int] = (3, 5, 10),
                   max_k: Optional[int] = None) -> Dict:
    """Score ``cases`` against ``retriever``. Retrieves once per case at max(ks)."""
    top_k = max_k or max(ks)
    retrievable = [c for c in cases if c.is_retrievable]
    per_case: List[Dict] = []
    latencies: List[float] = []

    for case in retrievable:
        result = retriever.retrieve(case.question, k=top_k, log=False)
        latencies.append(result["latencyMs"])
        row = {"caseId": case.id, "category": case.category,
               "question": case.question, "metrics": {}}
        for k in ks:
            row["metrics"][f"k={k}"] = evaluate_case(case, result["chunks"], k)
        row["topScore"] = result["chunks"][0]["score"] if result["chunks"] else None
        row["topCitation"] = result["chunks"][0]["citation"] if result["chunks"] else None
        per_case.append(row)

    summary: Dict = {"cases": len(retrievable), "byK": {}, "byCategory": {}}
    for k in ks:
        key = f"k={k}"
        rows = [c["metrics"][key] for c in per_case]
        summary["byK"][key] = {
            "precisionAtK": _mean([r["precisionAtK"] for r in rows]),
            "precisionAtK_span": _mean([r["precisionAtK_span"] for r in rows]),
            "precisionAtK_page": _mean([r["precisionAtK_page"] for r in rows]),
            "recallAtK": _mean([r["recallAtK"] for r in rows]),
            "recallAtK_span": _mean([r["recallAtK_span"] for r in rows]),
            "mrr": _mean([r["reciprocalRank"] for r in rows]),
            "hitRate": _mean([1.0 if r["hit"] else 0.0 for r in rows]),
        }

    for category in sorted({c.category for c in retrievable}):
        rows = [c["metrics"][f"k={max(ks)}"] for c in per_case if c["category"] == category]
        if rows:
            summary["byCategory"][category] = {
                "n": len(rows),
                "hitRate": _mean([1.0 if r["hit"] else 0.0 for r in rows]),
                "recallAtK": _mean([r["recallAtK"] for r in rows]),
            }

    # Non-retrievable cases (out_of_domain / unsafe) carry no retrieval labels.
    # They exist for Phase-5 threshold calibration; their score distribution is
    # recorded here so that work has data ready.
    negatives = [c for c in cases if not c.is_retrievable]
    negative_scores = []
    for case in negatives:
        result = retriever.retrieve(case.question, k=top_k, log=False)
        if result["chunks"]:
            negative_scores.append({"caseId": case.id, "category": case.category,
                                    "topScore": result["chunks"][0]["score"]})

    positives = [c["topScore"] for c in per_case if c["topScore"] is not None]
    summary["latencyMs"] = {
        "p50": round(statistics.median(latencies), 2) if latencies else None,
        "max": round(max(latencies), 2) if latencies else None,
    }
    summary["scoreSeparation"] = {
        "positiveTopScoreMean": _mean(positives),
        "negativeTopScoreMean": _mean([n["topScore"] for n in negative_scores]),
        "note": ("Recorded for Phase-5 threshold calibration. NOT a calibrated "
                 "confidence and not used for any decision in Phase 3."),
    }

    return {
        "modelId": getattr(retriever.provider, "model_id", "unknown"),
        "corpusSize": retriever.size,
        "ks": list(ks),
        "summary": summary,
        "perCase": per_case,
        "negatives": negative_scores,
    }


def run_answer_evaluation(cases: Sequence[GoldCase], *, k: int = 5,
                          retriever=None, provider=None) -> Dict:
    """Score the full answer path: refusal behaviour, citations, faithfulness.

    Every case runs through the same code path the UI uses, including the
    sufficiency gate and the citation validator.
    """
    from rag.answer_contracts import EvidenceSet
    from rag.answering import answer_from_evidence

    rows = []
    for case in cases:
        result = retriever.retrieve(case.question, k=k, log=False)
        evidence = EvidenceSet.from_retrieval(result)
        outcome = answer_from_evidence(evidence, provider=provider)
        payload = outcome.model_dump(mode="json")
        mode = payload.get("mode")

        expected_refuse = case.expected_behaviour == "refuse"
        actually_refused = mode == "refusal"
        row = {
            "caseId": case.id, "category": case.category,
            "expectedBehaviour": case.expected_behaviour, "mode": mode,
            "correctBehaviour": (expected_refuse == actually_refused)
            if mode != "system_failure" else None,
            "latencyMs": payload.get("latency_ms", 0.0),
        }

        if mode == "answer":
            recs = payload.get("recommendations", [])
            row.update({
                "recommendations": len(recs),
                "citationCoverage": payload.get("citation_coverage", 0.0),
                "excerptAccuracy": payload.get("excerpt_accuracy", 0.0),
                "droppedClaims": len(payload.get("dropped_claims", [])),
                "citationsMatchGold": _citations_match_gold(recs, case),
            })
        elif mode == "refusal":
            row["refusalReason"] = payload.get("reason")
        else:
            row["failureKind"] = payload.get("kind")
        rows.append(row)

    positives = [r for r in rows if r["expectedBehaviour"] == "answer"]
    negatives = [r for r in rows if r["expectedBehaviour"] == "refuse"]
    answered = [r for r in rows if r["mode"] == "answer"]
    scored = [r for r in rows if r["correctBehaviour"] is not None]

    summary = {
        "cases": len(rows),
        "systemFailures": sum(1 for r in rows if r["mode"] == "system_failure"),
        "refusalAccuracy": _mean([1.0 if r["correctBehaviour"] else 0.0 for r in scored]),
        "falseAnswerRate": _mean([1.0 if r["mode"] == "answer" else 0.0 for r in negatives]),
        "falseRefusalRate": _mean([1.0 if r["mode"] == "refusal" else 0.0 for r in positives]),
        "citationCoverage": _mean([r.get("citationCoverage", 0.0) for r in answered]),
        "excerptAccuracy": _mean([r.get("excerptAccuracy", 0.0) for r in answered]),
        "citationAccuracyVsGold": _mean(
            [r["citationsMatchGold"] for r in answered if r.get("citationsMatchGold") is not None]),
        "droppedClaimsTotal": sum(r.get("droppedClaims", 0) for r in answered),
        "latencyMs": {
            "p50": round(statistics.median([r["latencyMs"] for r in rows]), 2) if rows else None,
            "max": round(max([r["latencyMs"] for r in rows]), 2) if rows else None,
        },
    }
    return {"summary": summary, "perCase": rows}


def _citations_match_gold(recommendations, case) -> Optional[float]:
    """Fraction of citations that point at a gold source location.

    ``None`` for cases with no gold evidence — there is nothing to match against,
    and scoring them zero would silently penalise correct refusals.
    """
    if not case.gold_evidence:
        return None
    citations = [c for r in recommendations for c in r.get("citations", [])]
    if not citations:
        return 0.0
    from eval.goldset import normalise
    hits = 0
    for citation in citations:
        doc = normalise(citation.get("document", ""))
        section = normalise(citation.get("section") or "")
        page_text = str(citation.get("page", ""))
        for gold in case.gold_evidence:
            if normalise(gold.document) not in doc and doc not in normalise(gold.document):
                continue
            page_ok = True
            if gold.pages:
                allowed = set(gold.page_range())
                # Gold pages are PDF indices; a citation displays the printed
                # folio. Compare in the index space, falling back to the
                # displayed string for documents where the two coincide.
                index_span = set(range(int(citation.get("page_index") or 0),
                                       int(citation.get("page_index_end") or 0) + 1))
                page_ok = bool(index_span & allowed) or any(
                    part.isdigit() and int(part) in allowed for part in page_text.split("-"))
            section_ok = (not gold.section) or normalise(gold.section) in section \
                or section in normalise(gold.section)
            if page_ok and section_ok:
                hits += 1
                break
    return round(hits / len(citations), 4)


def print_report(report: Dict) -> None:
    s = report["summary"]
    print(f"\nmodel      : {report['modelId']}")
    print(f"corpus     : {report['corpusSize']} vectors · {s['cases']} retrievable cases")
    print(f"latency    : p50 {s['latencyMs']['p50']} ms · max {s['latencyMs']['max']} ms")
    print(f"\n{'k':<6}{'P@k':>8}{'P@k span':>11}{'P@k page':>11}{'R@k':>8}{'MRR':>8}{'hit':>8}")
    for key, m in s["byK"].items():
        print(f"{key:<6}{m['precisionAtK']:>8.3f}{m['precisionAtK_span']:>11.3f}"
              f"{m['precisionAtK_page']:>11.3f}{m['recallAtK']:>8.3f}{m['mrr']:>8.3f}"
              f"{m['hitRate']:>8.3f}")
    if s["byCategory"]:
        print("\nby category:")
        for cat, m in s["byCategory"].items():
            print(f"  {cat:<16} n={m['n']:<4} hit={m['hitRate']:.3f}  R@k={m['recallAtK']:.3f}")
    sep = s["scoreSeparation"]
    print(f"\ntop-score mean — in-scope {sep['positiveTopScoreMean']:.3f} · "
          f"out-of-domain {sep['negativeTopScoreMean']:.3f}  (for Phase-5 calibration only)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.run_eval")
    parser.add_argument("--gold", type=Path, default=ROOT / "eval" / "questions_v1.yaml")
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5, 10])
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    parser.add_argument("--tag", default="baseline")
    parser.add_argument("--with-answers", action="store_true",
                        help="also run the full answer path (refusal, citations, faithfulness)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    from rag.retrieve import Retriever

    cases = load_goldset(args.gold)
    retriever = Retriever(document_id=args.document_id)
    report = run_evaluation(retriever, cases, ks=args.k)
    report["tag"] = args.tag
    report["goldSet"] = str(args.gold)
    report["generatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if args.with_answers:
        report["answers"] = run_answer_evaluation(cases, k=max(args.k), retriever=retriever)
        a = report["answers"]["summary"]
        print(f"\n--- answer path ({a['cases']} cases) ---")
        print(f"refusal accuracy      : {a['refusalAccuracy']:.3f}")
        print(f"false-answer rate     : {a['falseAnswerRate']:.3f}")
        print(f"false-refusal rate    : {a['falseRefusalRate']:.3f}")
        print(f"citation coverage     : {a['citationCoverage']:.3f}")
        print(f"excerpt accuracy      : {a['excerptAccuracy']:.3f}  (verbatim in cited evidence)")
        print(f"citation acc vs gold  : {a['citationAccuracyVsGold']:.3f}")
        print(f"claims dropped        : {a['droppedClaimsTotal']}")
        print(f"system failures       : {a['systemFailures']}")
        print(f"latency p50 / max     : {a['latencyMs']['p50']} / {a['latencyMs']['max']} ms")

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"eval_{args.tag}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_report(report)
    print(f"\nwritten: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
