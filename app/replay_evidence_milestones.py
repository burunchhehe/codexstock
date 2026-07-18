from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
EVIDENCE_BUNDLE_HASH_CONTRACT = "sha256-canonical-json-replay-evidence-bundle-v2"


def _nonnegative_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def evidence_scope_hash(campaign_ids: Iterable[object]) -> str:
    normalized = sorted({
        str(value or "").strip().upper()
        for value in campaign_ids
        if str(value or "").strip()
    })
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()


def replay_evidence_bundle_hash(
    *,
    audited_scope_hash: object,
    evidence_schema_version: object,
    execution_timing_model_version: object,
    artifact_hash_contract: object,
    ledger_evidence_hash: object,
    journal_evidence_hash: object,
    replay_evidence_hash: object,
    replay_data_bundle_evidence_schema: object = None,
) -> str:
    """Bind an evidence scope and its three artifact digests into one stable hash."""
    payload = {
        "artifact_hash_contract": str(artifact_hash_contract or "not_required"),
        "audited_scope_hash": str(audited_scope_hash or ""),
        "contract": EVIDENCE_BUNDLE_HASH_CONTRACT,
        "evidence_schema_version": str(evidence_schema_version or "any"),
        "execution_timing_model_version": str(execution_timing_model_version or "any"),
        "replay_data_bundle_evidence_schema": str(
            replay_data_bundle_evidence_schema or "any"
        ),
        "journal_evidence_hash": str(journal_evidence_hash or "shallow"),
        "ledger_evidence_hash": str(ledger_evidence_hash or ""),
        "replay_evidence_hash": str(replay_evidence_hash or "shallow"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def valid_evidence_milestone_record(
    record: Mapping[str, Any],
    *,
    required_evidence_schema_version: str,
    required_execution_timing_model_version: str,
    required_replay_data_bundle_evidence_schema: str,
    required_artifact_hash_contract: str,
    required_campaign_scope_hash: str,
    currently_verified_source_ids: Iterable[object],
    required_target_count: int,
) -> bool:
    """Accept only complete, safe and internally consistent passed checkpoints."""
    milestone = _nonnegative_int(record.get("milestone"))
    resolved = _nonnegative_int(record.get("resolved_count"))
    verified = _nonnegative_int(record.get("verified_count"))
    audited = _nonnegative_int(record.get("audited_journal_count"))
    target_count = _nonnegative_int(record.get("target_count"))
    if not milestone or resolved is None or verified is None or audited is None:
        return False
    if resolved < milestone or verified < milestone or audited < verified:
        return False
    if target_count != int(required_target_count) or milestone > int(required_target_count):
        return False
    if any(
        _nonnegative_int(record.get(field)) != 0
        for field in ("quarantined_count", "failed_count", "issue_count")
    ):
        return False
    if record.get("paper_only") is not True or record.get("live_order_allowed") is not False:
        return False
    if str(record.get("schema") or "") != "codexstock_replay_evidence_milestone_v8":
        return False
    if str(record.get("evidence_schema_version") or "") != str(required_evidence_schema_version):
        return False
    if str(record.get("execution_timing_model_version") or "") != str(
        required_execution_timing_model_version
    ):
        return False
    if str(record.get("replay_data_bundle_evidence_schema") or "") != str(
        required_replay_data_bundle_evidence_schema
    ):
        return False
    if str(record.get("campaign_scope_hash") or "") != str(required_campaign_scope_hash):
        return False
    audited_source_ids = record.get("audited_source_ids")
    if not isinstance(audited_source_ids, list):
        return False
    normalized_audited_source_ids = [
        str(value or "").strip().upper()
        for value in audited_source_ids
        if str(value or "").strip()
    ]
    if len(normalized_audited_source_ids) != milestone:
        return False
    if len(set(normalized_audited_source_ids)) != milestone:
        return False
    current_verified = {
        str(value or "").strip().upper()
        for value in currently_verified_source_ids
        if str(value or "").strip()
    }
    if not set(normalized_audited_source_ids).issubset(current_verified):
        return False
    audited_scope_hash = evidence_scope_hash(normalized_audited_source_ids)
    if str(record.get("audited_scope_hash") or "") != audited_scope_hash:
        return False
    if str(record.get("evidence_bundle_hash_contract") or "") != EVIDENCE_BUNDLE_HASH_CONTRACT:
        return False
    if str(record.get("artifact_hash_contract") or "") != str(required_artifact_hash_contract):
        return False
    artifact_required = _nonnegative_int(record.get("artifact_anchor_required_count"))
    artifact_verified = _nonnegative_int(record.get("artifact_anchor_verified_count"))
    artifact_mismatch = _nonnegative_int(record.get("artifact_anchor_mismatch_count"))
    if artifact_required != milestone or artifact_verified != milestone or artifact_mismatch != 0:
        return False
    if record.get("artifact_anchor_deep_verified") is not True:
        return False
    if any(
        _SHA256_PATTERN.fullmatch(str(value or "")) is None
        for value in (required_campaign_scope_hash, audited_scope_hash)
    ):
        return False
    if str(record.get("status") or "") != "passed" or not str(record.get("campaign_id") or ""):
        return False
    hashes_are_valid = all(
        _SHA256_PATTERN.fullmatch(str(record.get(field) or "")) is not None
        for field in (
            "ledger_evidence_hash",
            "journal_evidence_hash",
            "replay_evidence_hash",
            "evidence_bundle_hash",
        )
    )
    if not hashes_are_valid:
        return False
    expected_bundle_hash = replay_evidence_bundle_hash(
        audited_scope_hash=record.get("audited_scope_hash"),
        evidence_schema_version=record.get("evidence_schema_version"),
        execution_timing_model_version=record.get("execution_timing_model_version"),
        artifact_hash_contract=record.get("artifact_hash_contract"),
        ledger_evidence_hash=record.get("ledger_evidence_hash"),
        journal_evidence_hash=record.get("journal_evidence_hash"),
        replay_evidence_hash=record.get("replay_evidence_hash"),
        replay_data_bundle_evidence_schema=record.get(
            "replay_data_bundle_evidence_schema"
        ),
    )
    return str(record.get("evidence_bundle_hash") or "") == expected_bundle_hash


def evidence_milestones(target_count: int) -> list[int]:
    target = max(0, int(target_count))
    return sorted({value for value in (10, 25, 100, 300, 500, target) if 0 < value <= target})


def due_evidence_milestones(
    *,
    resolved_count: int,
    target_count: int,
    passed_milestones: Iterable[int],
) -> list[int]:
    resolved = max(0, int(resolved_count))
    passed = {int(value) for value in passed_milestones}
    return [
        milestone
        for milestone in evidence_milestones(target_count)
        if milestone <= resolved and milestone not in passed
    ]
