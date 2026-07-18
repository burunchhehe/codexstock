from __future__ import annotations


def audit_replay_completion(
    *,
    progress: dict[str, object],
    unique_source_replay_count: int,
    worker_status: dict[str, object],
    data_gap_status: dict[str, object],
    expected_total: int,
    evidence_audit: dict[str, object] | None = None,
    campaign_id_count: int | None = None,
) -> dict[str, object]:
    """Fail closed until the full Paper recovery scope is independently reconciled."""

    def number(value: object) -> int:
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return 0

    total = number(progress.get("total_candidate_count"))
    resolved = number(progress.get("resolved_count"))
    remaining = number(progress.get("remaining_candidate_count"))
    failed = number(progress.get("failed_count"))
    retryable_failed = number(progress.get("retryable_failure_count"))
    blocked_failed = number(progress.get("blocked_failure_count"))
    accounting = progress.get("accounting") if isinstance(progress.get("accounting"), dict) else {}
    gap_count = number(data_gap_status.get("request_count"))
    unresolved_gap_count = number(data_gap_status.get("unresolved_request_count"))
    if "unresolved_request_count" not in data_gap_status:
        unresolved_gap_count = gap_count
    manifest_id_count = expected_total if campaign_id_count is None else number(campaign_id_count)

    checks = [
        {
            "id": "campaign_scope_nonempty",
            "passed": expected_total > 0,
            "actual": expected_total,
            "expected": "> 0",
        },
        {
            "id": "campaign_scope_manifest_consistent",
            "passed": manifest_id_count == expected_total,
            "actual": manifest_id_count,
            "expected": expected_total,
        },
        {
            "id": "full_scope_bound",
            "passed": total == expected_total,
            "actual": total,
            "expected": expected_total,
        },
        {
            "id": "all_candidates_resolved",
            "passed": total == expected_total and resolved == expected_total and remaining == 0,
            "actual": resolved,
            "expected": expected_total,
        },
        {
            "id": "latest_verdict_unique_per_source",
            "passed": unique_source_replay_count == expected_total,
            "actual": unique_source_replay_count,
            "expected": expected_total,
        },
        {
            "id": "no_failed_or_blocked_verdicts",
            "passed": failed == 0 and retryable_failed == 0 and blocked_failed == 0,
            "actual": {
                "failed": failed,
                "retryable_failed": retryable_failed,
                "blocked_failed": blocked_failed,
            },
            "expected": 0,
        },
        {
            "id": "ledger_accounting_invariant",
            "passed": bool(accounting.get("invariant_ok")),
            "actual": accounting.get("accounted_count"),
            "expected": total,
        },
        {
            "id": "no_unresolved_data_gaps",
            "passed": unresolved_gap_count == 0,
            "actual": unresolved_gap_count,
            "expected": 0,
        },
        {
            "id": "paper_worker_idle_at_certificate",
            "passed": not bool(worker_status.get("busy")),
            "actual": worker_status.get("current_replay_id", ""),
            "expected": "",
        },
        {
            "id": "no_live_order_or_auto_promotion",
            "passed": worker_status.get("live_order_allowed") is False
            and worker_status.get("automatic_promotion") is False,
            "actual": {
                "live_order_allowed": worker_status.get("live_order_allowed"),
                "automatic_promotion": worker_status.get("automatic_promotion"),
            },
            "expected": False,
        },
    ]
    if evidence_audit is not None:
        evidence_verified = number(evidence_audit.get("verified_count"))
        evidence_quarantined = number(evidence_audit.get("quarantined_count"))
        evidence_failed = number(evidence_audit.get("failed_count"))
        audited_journals = number(evidence_audit.get("audited_journal_count"))
        comparison_accounted = (
            number(evidence_audit.get("comparison_review_required_count"))
            + number(evidence_audit.get("source_equivalence_claim_allowed_count"))
        )
        checks.append(
            {
                "id": "durable_trade_evidence_verified",
                "passed": bool(evidence_audit.get("ok"))
                and bool(evidence_audit.get("deep"))
                and evidence_verified == expected_total
                and evidence_quarantined == 0
                and evidence_failed == 0
                and audited_journals == expected_total,
                "actual": {
                    "issue_count": number(evidence_audit.get("issue_count")),
                    "verified_count": evidence_verified,
                    "quarantined_count": evidence_quarantined,
                    "failed_count": evidence_failed,
                    "audited_journal_count": audited_journals,
                    "audited_closed_trade_count": number(evidence_audit.get("audited_closed_trade_count")),
                    "deep": bool(evidence_audit.get("deep")),
                },
                "expected": {
                    "issue_count": 0,
                    "verified_count": expected_total,
                    "quarantined_count": 0,
                    "failed_count": 0,
                    "audited_journal_count": expected_total,
                    "deep": True,
                },
            }
        )
        checks.append(
            {
                "id": "source_comparison_accounted",
                "passed": comparison_accounted == expected_total,
                "actual": {
                    "comparison_review_required_count": number(
                        evidence_audit.get("comparison_review_required_count")
                    ),
                    "source_equivalence_claim_allowed_count": number(
                        evidence_audit.get("source_equivalence_claim_allowed_count")
                    ),
                    "accounted_count": comparison_accounted,
                },
                "expected": expected_total,
            }
        )
    else:
        checks.extend(
            [
                {
                    "id": "durable_trade_evidence_verified",
                    "passed": False,
                    "actual": "evidence_audit_missing",
                    "expected": {"verified_count": expected_total, "deep": True},
                },
                {
                    "id": "source_comparison_accounted",
                    "passed": False,
                    "actual": "evidence_audit_missing",
                    "expected": expected_total,
                },
            ]
        )
    blockers = [str(row["id"]) for row in checks if not row["passed"]]
    completion_verified = not blockers
    repair_blocked = blocked_failed > 0 or unresolved_gap_count > 0
    return {
        "schema": "codexstock_historical_replay_completion_audit_v3",
        "ok": completion_verified,
        "status": (
            "complete_verified"
            if completion_verified
            else "repair_required"
            if repair_blocked
            else "in_progress"
        ),
        "expected_total": expected_total,
        "progress_label": progress.get("label", ""),
        "resolved_count": resolved,
        "remaining_count": remaining,
        "completion_verified": completion_verified,
        "certificate_allowed": completion_verified,
        "checks": checks,
        "blockers": blockers,
        "paper_only": True,
        "automatic_promotion": False,
        "live_order_allowed": False,
        "safety": "Completion certificate only; no account, broker, promotion, or live order action.",
    }
