from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


TRUE_VALUES = frozenset({"1", "true", "yes", "y", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "n", "off"})


@dataclass(frozen=True)
class StartupPolicy:
    profile: str
    clean_install_safe: bool
    always_on_research: bool
    heavy_research_workers: bool
    source: str


def resolve_startup_policy(environ: Mapping[str, str], *, saved_research_enabled: bool) -> StartupPolicy:
    profile = str(environ.get("CODEXSTOCK_STARTUP_PROFILE", "safe") or "safe").strip().lower()
    always_raw = str(environ.get("CODEXSTOCK_ALWAYS_ON_RESEARCH", "") or "").strip().lower()
    heavy_raw = str(environ.get("CODEXSTOCK_HEAVY_RESEARCH_ENABLED", "") or "").strip().lower()
    always_on = saved_research_enabled
    source = "saved_research_state" if saved_research_enabled else "safe_default"
    if always_raw in TRUE_VALUES | FALSE_VALUES:
        always_on = always_raw in TRUE_VALUES
        source = "CODEXSTOCK_ALWAYS_ON_RESEARCH"
    heavy = bool(saved_research_enabled or profile in {"operator", "research", "full"})
    if heavy_raw in TRUE_VALUES | FALSE_VALUES:
        heavy = heavy_raw in TRUE_VALUES
        source = "CODEXSTOCK_HEAVY_RESEARCH_ENABLED"
    return StartupPolicy(profile, not saved_research_enabled and profile == "safe" and not heavy, always_on, heavy, source)
