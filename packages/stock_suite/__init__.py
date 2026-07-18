"""Unified facade for the bundled stock open source projects."""

from .registry import Project, available_projects, get_project
from .suite import StockSuite

__all__ = [
    "Project",
    "StockSuite",
    "available_projects",
    "get_project",
]
