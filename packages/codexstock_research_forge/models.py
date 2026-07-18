from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from .dsl import validate_typed_rules


class ExperimentStatus(str, Enum):
    DRAFT = "DRAFT"
    DATA_CHECK = "DATA_CHECK"
    BACKTESTING = "BACKTESTING"
    FAILED = "FAILED"
    VALIDATION = "VALIDATION"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class ResearchPolicy:
    decision_scope: str = "research_only"
    live_order_allowed: bool = False
    requires_codexstock_validation: bool = True

    def assert_safe(self) -> None:
        if self.decision_scope != "research_only" or self.live_order_allowed:
            raise ValueError("Research Forge must remain research-only and cannot place live orders")


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    version: str
    rules: dict[str, Any]
    description: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("strategy name is required")
        if not self.version.strip():
            errors.append("strategy version is required")
        if not self.rules:
            errors.append("strategy rules are required")
        forbidden = {"live_order", "submit_order", "broker_order"}
        if forbidden.intersection(self.rules):
            errors.append("live-order directives are forbidden")
        errors.extend(validate_typed_rules(self.rules))
        return errors


@dataclass
class ExperimentRecord:
    strategy: StrategyDefinition
    data_snapshot: dict[str, Any]
    execution_model: dict[str, Any]
    id: str = field(default_factory=lambda: f"exp_{uuid4().hex}")
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    code_version: str = "unknown"
    backtest_adapter: str = "unknown"
    random_seed: int = 0
    validation: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperimentRecord":
        strategy = StrategyDefinition(**dict(payload["strategy"]))
        return cls(
            id=str(payload["id"]),
            strategy=strategy,
            data_snapshot=dict(payload.get("data_snapshot") or {}),
            execution_model=dict(payload.get("execution_model") or {}),
            status=ExperimentStatus(str(payload.get("status", "DRAFT"))),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            code_version=str(payload.get("code_version") or "unknown"),
            backtest_adapter=str(payload.get("backtest_adapter") or "unknown"),
            random_seed=int(payload.get("random_seed") or 0),
            validation=dict(payload.get("validation") or {}),
            result=dict(payload.get("result") or {}),
        )
