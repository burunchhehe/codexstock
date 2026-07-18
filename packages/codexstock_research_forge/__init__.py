"""CodexStock's research-only strategy validation sub-engine."""

__version__ = "0.3.0"

from .models import ExperimentRecord, ExperimentStatus, ResearchPolicy, StrategyDefinition
from .service import ResearchForge

__all__ = [
    "ExperimentRecord",
    "ExperimentStatus",
    "ResearchForge",
    "ResearchPolicy",
    "StrategyDefinition",
]
