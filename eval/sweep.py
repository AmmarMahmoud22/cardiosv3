"""Chunking + embedding-model sweep (Phase 3).

    python -m eval.sweep --pdf <guideline.pdf> --title "..." --gold eval/questions_v1.yaml

Re-ingests and re-indexes the corpus for each configuration, then scores it
against the gold set. Every configuration tested is recorded — including the
ones that lost — so the final choice rests on measurement rather than intuition.

Only the four variables the plan authorises are swept: chunk size, chunk
overlap, k, and embedding model.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from eval.goldset import load_goldset          # noqa: E402
from eval.run_eval import run_evaluation       # noqa: E402

logger = logging.getLogger(__name__)


def run_config(pdf: Path, title: str, document_id: str, cases, *, chunk_size: int,
               overlap: int, model: str, ks, store_path: Path) -> dict:
    """Ingest → index → evaluate one configuration in an isolated corpus."""
    import os
    os.environ["RAG_CORPUS_DIR"] = str(store_path)
    os.environ["EMBEDDING_MODEL"] = model
    os.environ["EMBEDDING_PROVIDER"] = os.getenv("EMBEDDING_PROVIDER", "local")

    for mod in [m for m in list(sys.modules) if m.startswith("rag.")]:
        del sys.modules[mod]

    from rag.ingest import ingest_pdf
    from rag.store import CorpusStore
    from rag.index import index_corpus
    from rag.retrieve import Retriever
    from rag.embeddings import reset_provider, get_provider

    reset_provider()
    store = CorpusStore(store_path / "corpus.db")

    started = time.perf_counter()
    document, chunks, report, _pages = ingest_pdf(
        pdf, title=title, document_id=document_id,
        target_chars=chunk_size, overlap_chars=overlap)
    store.replace_document(document, chunks, report.model_dump_json())
    index_report = index_corpus(store=store)
    retriever = Retriever(store=store, provider=get_provider())
    result = run_evaluation(retriever, cases, ks=ks)

    return {
        "config": {"chunkSize": chunk_size, "overlap": overlap, "model": model},
        "chunks": len(chunks),
        "dimension": index_report["dimension"],
        "ingestSeconds": round(time.perf_counter() - started, 1),
        "summary": result["summary"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.sweep")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--document-id", default="guideline")
    parser.add_argument("--gold", type=Path, default=ROOT / "eval" / "questions_v1.yaml")
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=[600, 900, 1200, 1800])
    parser.add_argument("--overlaps", type=int, nargs="+", default=[100, 200, 300])
    parser.add_argument("--models", nargs="+",
                        default=["sentence-transformers/all-MiniLM-L6-v2"])
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5, 10])
    parser.add_argument("--select-on", default="k=5",
                        help="which k to rank configurations by")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    parser.add_argument("--workdir", type=Path, default=Path("/tmp/rag_sweep"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    cases = load_goldset(args.gold)
    rows = []
    n = 0
    total = len(args.chunk_sizes) * len(args.overlaps) * len(args.models)

    for model in args.models:
        for size in args.chunk_sizes:
            for overlap in args.overlaps:
                if overlap >= size:
                    continue
                n += 1
                tag = f"{Path(model).name}_s{size}_o{overlap}"
                print(f"[{n}/{total}] {tag} ...", flush=True)
                try:
                    row = run_config(args.pdf, args.title, args.document_id, cases,
                                     chunk_size=size, overlap=overlap, model=model,
                                     ks=args.k, store_path=args.workdir / tag)
                    rows.append(row)
                    m = row["summary"]["byK"][args.select_on]
                    print(f"      chunks={row['chunks']:<6} P@5={m['precisionAtK']:.3f} "
                          f"R@5={m['recallAtK']:.3f} MRR={m['mrr']:.3f}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"      FAILED: {type(exc).__name__}: {exc}", flush=True)
                    rows.append({"config": {"chunkSize": size, "overlap": overlap,
                                            "model": model},
                                 "error": f"{type(exc).__name__}: {exc}"})

    ok = [r for r in rows if "summary" in r]
    ok.sort(key=lambda r: (r["summary"]["byK"][args.select_on]["recallAtK"],
                           r["summary"]["byK"][args.select_on]["mrr"],
                           r["summary"]["byK"][args.select_on]["precisionAtK"]), reverse=True)

    args.out.mkdir(parents=True, exist_ok=True)
    payload = {"selectOn": args.select_on, "goldSet": str(args.gold),
               "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "configurations": rows,
               "ranked": [r["config"] for r in ok],
               "selected": ok[0]["config"] if ok else None}
    path = args.out / "sweep_results.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n{'model':<26}{'size':>6}{'ovl':>6}{'chunks':>8}{'P@5':>8}{'R@5':>8}{'MRR':>8}")
    for r in ok:
        c, m = r["config"], r["summary"]["byK"][args.select_on]
        print(f"{Path(c['model']).name[:25]:<26}{c['chunkSize']:>6}{c['overlap']:>6}"
              f"{r['chunks']:>8}{m['precisionAtK']:>8.3f}{m['recallAtK']:>8.3f}{m['mrr']:>8.3f}")
    print(f"\nselected: {payload['selected']}")
    print(f"written : {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
