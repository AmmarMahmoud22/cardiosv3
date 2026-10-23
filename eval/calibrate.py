"""Evidence-sufficiency threshold calibration (Phase 5).

    python -m eval.calibrate --gold eval/questions_v1.yaml

Sweeps the sufficiency signal over the labelled gold set and picks an operating
point. The positive distribution comes from ``in_scope`` cases, the negative
from ``out_of_domain`` and ``unsafe_request``. ``ambiguous`` cases are reported
but excluded from fitting.

Operating point rule (safety-weighted, and stated rather than implied):
minimise false refusals subject to a zero false-answer rate on the negatives.
Answering when the system should have refused is the costlier error, because
"proper handling of insufficient evidence" is what the safety criterion scores.

The whole sweep is written out, not just the chosen point, and the record is
bound to the embedding model and corpus version it was fitted against — a
threshold fitted for one embedding space is meaningless in another.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from eval.goldset import load_goldset  # noqa: E402

POSITIVE = {"in_scope"}
NEGATIVE = {"out_of_domain", "unsafe_request"}


def collect_signals(retriever, cases, k: int = 5, signal: str = "top1") -> dict:
    from rag.answer_contracts import EvidenceSet
    from rag.sufficiency import compute_signal

    rows = []
    for case in cases:
        evidence = EvidenceSet.from_retrieval(retriever.retrieve(case.question, k=k, log=False))
        rows.append({"caseId": case.id, "category": case.category,
                     "value": compute_signal(evidence, signal)})
    return {"signal": signal, "k": k, "rows": rows}


def sweep(rows: List[dict], steps: int = 200) -> List[dict]:
    positives = [r["value"] for r in rows if r["category"] in POSITIVE]
    negatives = [r["value"] for r in rows if r["category"] in NEGATIVE]
    if not positives or not negatives:
        raise ValueError(
            "calibration needs both in_scope cases and out_of_domain/unsafe_request cases")

    lo, hi = min(positives + negatives), max(positives + negatives)
    out = []
    for i in range(steps + 1):
        threshold = lo + (hi - lo) * i / steps
        false_answers = sum(1 for v in negatives if v >= threshold)
        false_refusals = sum(1 for v in positives if v < threshold)
        out.append({
            "threshold": round(threshold, 6),
            "falseAnswerRate": round(false_answers / len(negatives), 4),
            "falseRefusalRate": round(false_refusals / len(positives), 4),
            "falseAnswers": false_answers,
            "falseRefusals": false_refusals,
        })
    return out


def choose_operating_point(curve: List[dict]) -> dict:
    """Lowest false-refusal rate among points with zero false answers.

    Falls back to minimising the summed error rate if no point separates the two
    distributions cleanly — and the fallback is flagged, because a threshold that
    cannot achieve zero false answers is a finding, not a detail.
    """
    clean = [p for p in curve if p["falseAnswers"] == 0]
    if clean:
        best = min(clean, key=lambda p: (p["falseRefusalRate"], p["threshold"]))
        best["rule"] = "min false-refusal subject to zero false-answer"
        best["separable"] = True
        return best
    best = min(curve, key=lambda p: p["falseAnswerRate"] + p["falseRefusalRate"])
    best["rule"] = "min total error (distributions NOT separable)"
    best["separable"] = False
    return best


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.calibrate")
    parser.add_argument("--gold", type=Path, default=ROOT / "eval" / "questions_v1.yaml")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--signals", nargs="+", default=["top1", "margin"])
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    parser.add_argument("--write-calibration", action="store_true",
                        help="write backend/rag/corpus/calibration.json for the best signal")
    args = parser.parse_args(argv)

    from rag.config import CORPUS_VERSION
    from rag.retrieve import Retriever

    cases = load_goldset(args.gold)
    retriever = Retriever()
    results = {}

    for signal in args.signals:
        data = collect_signals(retriever, cases, k=args.k, signal=signal)
        curve = sweep(data["rows"])
        point = choose_operating_point(curve)
        results[signal] = {"rows": data["rows"], "curve": curve, "operatingPoint": point}
        print(f"\nsignal={signal}")
        print(f"  threshold      : {point['threshold']:.4f}")
        print(f"  false-answer   : {point['falseAnswerRate']:.3f} ({point['falseAnswers']})")
        print(f"  false-refusal  : {point['falseRefusalRate']:.3f} ({point['falseRefusals']})")
        print(f"  rule           : {point['rule']}")
        if not point["separable"]:
            print("  !! the distributions do not separate cleanly — retrieval quality, not "
                  "the threshold, is the limiting factor here")

    best_signal = min(results, key=lambda s: (
        results[s]["operatingPoint"]["falseAnswerRate"]
        + results[s]["operatingPoint"]["falseRefusalRate"]))

    calibration_id = f"cal-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    record = {
        "calibrationId": calibration_id,
        "signal": best_signal,
        "threshold": results[best_signal]["operatingPoint"]["threshold"],
        "modelId": getattr(retriever.provider, "model_id", ""),
        "corpusVersion": CORPUS_VERSION,
        "k": args.k,
        "goldSet": str(args.gold),
        "operatingPoint": results[best_signal]["operatingPoint"],
        "note": ("Fitted on GOLD-v1, which is also the development set. Validate on "
                 "held-out GOLD-v2 cases before treating these rates as unbiased."),
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "calibration_sweep.json").write_text(
        json.dumps({"record": record, "signals": results}, indent=2), encoding="utf-8")
    print(f"\nselected signal: {best_signal} @ {record['threshold']:.4f}  [{calibration_id}]")
    print(f"sweep written  : {args.out / 'calibration_sweep.json'}")

    if args.write_calibration:
        from rag.sufficiency import calibration_path
        path = calibration_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"calibration    : {path}")
    else:
        print("(re-run with --write-calibration to activate it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
