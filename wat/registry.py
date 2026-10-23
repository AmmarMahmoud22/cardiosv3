"""Tool registry + the Tool contract.

Every tool is a deterministic adapter with an explicit contract:
- ``Input`` / ``Output`` pydantic models (schema + validation),
- ``kind``: "cli" (stateless, fresh each call) or "service" (warm, holds a
  loaded model — the heavy ML tools),
- ``idempotent`` and ``retryable`` metadata the engine consults.

Tools register themselves at import time via ``@register``. ``load_tools()``
imports every module under ``wat.tools`` so they are discoverable.
"""
from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from .errors import WatError


class Tool:
    name: ClassVar[str]
    Input: ClassVar[type[BaseModel]]
    Output: ClassVar[type[BaseModel]]
    kind: ClassVar[str] = "cli"            # "cli" | "service"
    idempotent: ClassVar[bool] = True
    retryable: ClassVar[tuple[str, ...]] = ("transient",)

    def run(self, inp: BaseModel) -> BaseModel:  # pragma: no cover - interface
        raise NotImplementedError


_REGISTRY: dict[str, Tool] = {}
_loaded = False


def register(tool_cls: type[Tool]) -> type[Tool]:
    """Class decorator: instantiate and register a tool by its ``name``."""
    if not getattr(tool_cls, "name", None):
        raise ValueError(f"{tool_cls.__name__} must define a 'name'")
    _REGISTRY[tool_cls.name] = tool_cls()
    return tool_cls


def load_tools() -> None:
    global _loaded
    if _loaded:
        return
    import importlib
    import pkgutil

    from . import tools as tools_pkg

    for module in pkgutil.iter_modules(tools_pkg.__path__):
        importlib.import_module(f"{tools_pkg.__name__}.{module.name}")
    _loaded = True


def get(name: str) -> Tool:
    load_tools()
    if name not in _REGISTRY:
        raise WatError(f"Unknown tool: {name!r}", category="dependency")
    return _REGISTRY[name]


def all_tools() -> dict[str, Tool]:
    load_tools()
    return dict(_REGISTRY)
