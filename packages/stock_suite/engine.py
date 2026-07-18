from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .registry import get_project


@dataclass
class LeanBridge:
    """Path-level bridge for the QuantConnect Lean engine."""

    @property
    def root(self) -> Path:
        return get_project("lean").path

    @property
    def solution_file(self) -> Path:
        return self.root / "QuantConnect.Lean.sln"

    def is_available(self) -> bool:
        return self.solution_file.exists()
