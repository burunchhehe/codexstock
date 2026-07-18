from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .indicators import INDICATORS, PROFILES, calculate


class HtsReferenceRegistry:
    """Immutable user-supplied HTS export evidence; verification is per profile and indicator."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def register(self, package: dict[str, Any]) -> dict[str, Any]:
        normalized = self._validate(package)
        canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        package_hash = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        verification = self._verify(normalized)
        payload = {"schema_version": 1, "package": normalized, "package_hash": package_hash, "evidence_grade": "user_supplied_hts_export", "verification": verification, "registered_at": datetime.now().astimezone().isoformat()}
        path = self.root / f"{normalized['export_id']}.json"
        if path.exists():
            existing = self._load(path)
            if existing.get("package_hash") != package_hash: raise ValueError("HTS export_id is immutable and already identifies different evidence")
            return self._summary(existing)
        self._atomic(path, payload)
        return self._summary(payload)

    def status(self, profile: str | None = None) -> dict[str, Any]:
        rows, invalid = [], []
        for path in sorted(self.root.glob("*.json")):
            try: rows.append(self._summary(self._load(path)))
            except Exception as exc: invalid.append({"path": str(path), "error": str(exc)})
        if profile: rows = [row for row in rows if row["profile"] == profile.upper()]
        profiles = {}
        for name in ("LS_HTS", "KIWOOM_HTS", "KIS"):
            evidence = [row for row in rows if row["profile"] == name]
            passed = sorted({row["indicator"] for row in evidence if row["passed"]})
            profiles[name] = {"verified_indicators": passed, "verified_indicator_count": len(passed), "required_indicator_count": len(INDICATORS), "fully_verified": set(passed) == set(INDICATORS), "evidence_package_count": len(evidence), "failed_package_count": sum(not row["passed"] for row in evidence)}
        return {"ok": not invalid, "profiles": profiles, "packages": rows, "package_count": len(rows), "invalid": invalid, "promotion_scope": "per_indicator_until_all_builtins_pass"}

    def _load(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("package"), dict):
            raise ValueError("unsupported HTS evidence package")
        normalized = self._validate(payload["package"])
        canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected_hash = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        if payload.get("package_hash") != expected_hash or payload.get("verification") != self._verify(normalized):
            raise ValueError("HTS evidence package integrity verification failed")
        return payload

    def _verify(self, package: dict[str, Any]) -> dict[str, Any]:
        result = calculate(package["indicator"], package["market_rows"], package["parameters"], package["profile"])
        timestamps = [str(row.get("timestamp") or row.get("date")) for row in package["market_rows"]]
        index_by_timestamp = {value: index for index, value in enumerate(timestamps)}
        tolerance = package["absolute_tolerance"]
        comparisons, errors = [], []
        squared = 0.0; maximum = 0.0
        for reference in package["reference_points"]:
            index = index_by_timestamp[reference["timestamp"]]
            for output, expected in reference["outputs"].items():
                series = result["outputs"].get(output)
                if not isinstance(series, list): raise ValueError(f"unknown indicator output in HTS reference: {output}")
                actual = series[index]
                difference = None if actual is None else abs(float(actual) - float(expected))
                passed = difference is not None and difference <= tolerance
                comparisons.append({"timestamp": reference["timestamp"], "output": output, "expected": float(expected), "actual": actual, "absolute_difference": difference, "passed": passed})
                if difference is None: errors.append(f"{reference['timestamp']} {output} is inside local warmup")
                else: squared += difference * difference; maximum = max(maximum, difference)
        mismatch = [row for row in comparisons if not row["passed"]]
        return {"passed": bool(comparisons) and not mismatch, "profile": package["profile"], "indicator": package["indicator"], "comparison_count": len(comparisons), "matched_count": len(comparisons) - len(mismatch), "mismatch_count": len(mismatch), "max_absolute_error": maximum, "rmse": math.sqrt(squared / len(comparisons)) if comparisons else None, "absolute_tolerance": tolerance, "errors": errors, "mismatch_samples": mismatch[:20], "all_reference_timestamps_checked": True, "profile_compatibility_verified": bool(comparisons) and not mismatch}

    def _validate(self, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"export_id", "profile", "indicator", "parameters", "symbol", "timeframe", "exported_at", "source_file_name", "source_file_hash", "market_rows", "reference_points", "absolute_tolerance", "notes"}
        if not isinstance(value, dict) or set(value) - allowed: raise ValueError("HTS reference package has invalid keys")
        export_id = str(value.get("export_id") or "")
        if not export_id or not export_id.replace("-", "").replace("_", "").isalnum(): raise ValueError("HTS export_id must be safe and non-empty")
        profile, indicator = str(value.get("profile") or "").upper(), str(value.get("indicator") or "").upper()
        if profile not in {"LS_HTS", "KIWOOM_HTS", "KIS"}: raise ValueError("HTS profile must be LS_HTS, KIWOOM_HTS, or KIS")
        if indicator not in INDICATORS: raise ValueError("HTS package indicator is unsupported")
        symbol, timeframe = str(value.get("symbol") or "").upper(), str(value.get("timeframe") or "")
        if not symbol.isalnum() or timeframe not in {"1d", "1m", "3m", "5m", "10m", "15m", "30m", "60m"}: raise ValueError("HTS package symbol or timeframe is invalid")
        exported_at = str(value.get("exported_at") or "")
        parsed = datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None: raise ValueError("HTS exported_at must include timezone")
        source_hash = str(value.get("source_file_hash") or "")
        if not source_hash.startswith("sha256:") or len(source_hash) != 71: raise ValueError("HTS package requires source file SHA-256")
        rows, references = value.get("market_rows"), value.get("reference_points")
        if not isinstance(rows, list) or not 20 <= len(rows) <= 100_000 or not isinstance(references, list) or len(references) < 10: raise ValueError("HTS package requires at least 20 market rows and 10 reference points")
        timestamps = [str(row.get("timestamp") or row.get("date") or "") for row in rows if isinstance(row, dict)]
        if len(timestamps) != len(rows) or len(timestamps) != len(set(timestamps)) or any(left >= right for left, right in zip(timestamps, timestamps[1:])): raise ValueError("HTS market rows require unique increasing timestamps")
        reference_timestamps = []
        for reference in references:
            if not isinstance(reference, dict) or set(reference) != {"timestamp", "outputs"} or not isinstance(reference["outputs"], dict) or not reference["outputs"]: raise ValueError("invalid HTS reference point")
            if reference["timestamp"] not in timestamps: raise ValueError("HTS reference timestamp is missing from market rows")
            reference_timestamps.append(reference["timestamp"])
            for expected in reference["outputs"].values():
                if not math.isfinite(float(expected)): raise ValueError("HTS expected value must be finite")
        if len(reference_timestamps) != len(set(reference_timestamps)): raise ValueError("duplicate HTS reference timestamp")
        tolerance = float(value.get("absolute_tolerance") if value.get("absolute_tolerance") is not None else 1e-6)
        if not 0 <= tolerance <= 1000: raise ValueError("invalid HTS absolute tolerance")
        return {"export_id": export_id, "profile": profile, "indicator": indicator, "parameters": dict(value.get("parameters") or {}), "symbol": symbol, "timeframe": timeframe, "exported_at": parsed.isoformat(), "source_file_name": Path(str(value.get("source_file_name") or "export")).name, "source_file_hash": source_hash, "market_rows": rows, "reference_points": references, "absolute_tolerance": tolerance, "notes": str(value.get("notes") or "")}

    @staticmethod
    def _summary(payload: dict[str, Any]) -> dict[str, Any]:
        package, verification = payload["package"], payload["verification"]
        return {"export_id": package["export_id"], "profile": package["profile"], "indicator": package["indicator"], "symbol": package["symbol"], "timeframe": package["timeframe"], "exported_at": package["exported_at"], "source_file_name": package["source_file_name"], "source_file_hash": package["source_file_hash"], "package_hash": payload["package_hash"], "evidence_grade": payload["evidence_grade"], "passed": verification["passed"], "verification": verification, "registered_at": payload["registered_at"]}

    @staticmethod
    def _atomic(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".json.tmp"); temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)
