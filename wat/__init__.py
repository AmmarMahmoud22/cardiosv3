"""WAT — Workflows · Agents · Tools.

A small, transparent orchestration layer for the cardios project:
- Workflows are machine-readable YAML DAGs (the operational SOP).
- Tools are deterministic, contract-validated Python adapters that WRAP existing
  cardios backend logic (they import it; they do not reimplement it).
- The engine resolves step references, validates I/O against pydantic contracts,
  classifies failures, retries by error category, checkpoints state, and traces
  every step.

See wat/README.md for the design and how to run a workflow.
"""

__all__ = ["engine", "registry", "errors", "paths"]
