"""
Inverted extension registry — the Extension Host.

Maps an extension id to a dotted "module.path:function" target and imports it
LAZILY at lookup time. The core never imports an agent by name; adding an
extension is a one-line table entry (or a runtime register() call), not an
edit to the runtime loop. This is the seam that replaces coordinator.py's
hardcoded `from agents.python_dev import python_agent`.
"""
from __future__ import annotations

import importlib
from typing import Dict, FrozenSet

from core.contract import Context, Result  # noqa: F401  (documents the callable shape)


class ExtensionRegistry:
    def __init__(self, table: Dict[str, str] | None = None) -> None:
        # ext_id -> "module.path:function"
        self._table: Dict[str, str] = dict(table or {})

    def register(self, ext_id: str, target: str) -> None:
        self._table[ext_id] = target

    def ids(self) -> FrozenSet[str]:
        return frozenset(self._table)

    def get(self, ext_id: str):
        if ext_id not in self._table:
            raise KeyError(
                f"Extension '{ext_id}' not registered. Known: {sorted(self._table)}"
            )
        mod_path, sep, fn_name = self._table[ext_id].partition(":")
        if not sep:
            raise ValueError(
                f"Bad target for '{ext_id}': {self._table[ext_id]!r} "
                f"(expected 'module.path:function')"
            )
        module = importlib.import_module(mod_path)
        return getattr(module, fn_name)
