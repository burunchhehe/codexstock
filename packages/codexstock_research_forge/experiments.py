from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import ExperimentRecord


class ExperimentRegistry:
    """Append-safe-enough local registry with atomic per-experiment writes."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, record: ExperimentRecord) -> Path:
        target = self.root / f"{record.id}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

    def get(self, experiment_id: str) -> ExperimentRecord:
        safe_id = self._safe_id(experiment_id)
        payload = json.loads((self.root / f"{safe_id}.json").read_text(encoding="utf-8"))
        return ExperimentRecord.from_dict(payload)

    def list(self) -> Iterable[ExperimentRecord]:
        for path in sorted(self.root.glob("exp_*.json")):
            yield ExperimentRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def _safe_id(value: str) -> str:
        if not value.startswith("exp_") or not value.replace("_", "").isalnum():
            raise ValueError("invalid experiment id")
        return value
