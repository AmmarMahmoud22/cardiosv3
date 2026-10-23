"""CLI entry point: ``python -m wat <command>``.

Commands:
  run <workflow.yaml>   Execute a workflow and print the JSON result.
  tools                 List registered tools and their contracts.
  schemas               Export JSON Schema for every tool contract.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import registry
from .engine import run_workflow


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="wat", description="WAT workflow engine")
    sub = parser.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="run a workflow YAML")
    run_p.add_argument("workflow")
    run_p.add_argument("--input-json", dest="input_json", default=None,
                       help='JSON object of runtime params, referenced as ${params.x}')

    sub.add_parser("tools", help="list registered tools")
    sub.add_parser("schemas", help="export JSON schemas")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        params = json.loads(args.input_json) if args.input_json else None
        result = run_workflow(args.workflow, params=params)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 1 if result.status == "failed" else 0

    if args.cmd == "tools":
        for name, tool in sorted(registry.all_tools().items()):
            print(f"{name:30s} [{tool.kind:7s}] "
                  f"in={tool.Input.__name__} out={tool.Output.__name__} "
                  f"idempotent={tool.idempotent}")
        return 0

    if args.cmd == "schemas":
        from .schemas.export import export_all
        paths = export_all()
        print(f"Exported {len(paths)} schema files to wat/schemas/json/")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
