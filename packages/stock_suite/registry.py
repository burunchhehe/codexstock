from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import third_party_path


@dataclass(frozen=True)
class Project:
    name: str
    folder: str
    upstream: str
    role: str
    language: str

    @property
    def path(self) -> Path:
        return third_party_path(self.folder)

    @property
    def exists(self) -> bool:
        return self.path.exists()


PROJECTS: tuple[Project, ...] = (
    Project(
        name="yfinance",
        folder="yfinance",
        upstream="https://github.com/ranaroussi/yfinance",
        role="market data",
        language="python",
    ),
    Project(
        name="vectorbt",
        folder="vectorbt",
        upstream="https://github.com/polakowo/vectorbt",
        role="fast vectorized research",
        language="python",
    ),
    Project(
        name="backtrader",
        folder="backtrader",
        upstream="https://github.com/mementum/backtrader",
        role="event-driven backtesting",
        language="python",
    ),
    Project(
        name="zipline",
        folder="zipline",
        upstream="https://github.com/quantopian/zipline",
        role="classic event-driven backtesting",
        language="python",
    ),
    Project(
        name="finrl",
        folder="finrl",
        upstream="https://github.com/AI4Finance-Foundation/FinRL",
        role="reinforcement learning research",
        language="python",
    ),
    Project(
        name="lean",
        folder="lean",
        upstream="https://github.com/QuantConnect/Lean",
        role="production-grade trading engine",
        language="csharp/dotnet",
    ),
    Project(
        name="freqtrade",
        folder="freqtrade",
        upstream="https://github.com/freqtrade/freqtrade",
        role="automated trading bot",
        language="python",
    ),
)


def available_projects() -> list[Project]:
    return list(PROJECTS)


def get_project(name: str) -> Project:
    normalized = name.lower()
    for project in PROJECTS:
        if project.name == normalized:
            return project
    known = ", ".join(project.name for project in PROJECTS)
    raise KeyError(f"Unknown project {name!r}. Known projects: {known}")
