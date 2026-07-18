from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .imports import import_from_source
from .registry import get_project


@dataclass
class AILab:
    """AI finance facade backed by FinRL."""

    def module(self) -> Any:
        project = get_project("finrl")
        return import_from_source("finrl", project.path)
