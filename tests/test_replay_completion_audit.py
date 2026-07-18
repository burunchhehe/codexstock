import unittest

from app.replay_completion_audit import audit_replay_completion


class ReplayCompletionAuditTests(unittest.TestCase):
    @staticmethod
    def worker(**overrides):
        payload = {
            "busy": False,
            "current_replay_id": "",
            "live_order_allowed": False,
            "automatic_promotion": False,
        }
        payload.update(overrides)
        return payload

    @staticmethod
    def evidence(total=756, **overrides):
        payload = {
            "ok": True,
            "issue_count": 0,
            "verified_count": total,
            "quarantined_count": 0,
            "failed_count": 0,
            "audited_journal_count": total,
            "audited_closed_trade_count": 1000,
            "comparison_review_required_count": total,
            "source_equivalence_claim_allowed_count": 0,
            "deep": True,
        }
        payload.update(overrides)
        return payload

    def test_in_progress_never_issues_certificate(self):
        result = audit_replay_completion(
            progress={
                "label": "31/756 (4.10%)",
                "total_candidate_count": 756,
                "resolved_count": 31,
                "remaining_candidate_count": 725,
                "failed_count": 0,
                "retryable_failure_count": 0,
                "blocked_failure_count": 0,
                "accounting": {"invariant_ok": True, "accounted_count": 756},
            },
            unique_source_replay_count=31,
            worker_status=self.worker(),
            data_gap_status={"request_count": 0},
            expected_total=756,
        )

        self.assertEqual("in_progress", result["status"])
        self.assertFalse(result["completion_verified"])
        self.assertFalse(result["certificate_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_complete_requires_every_independent_gate(self):
        result = audit_replay_completion(
            progress={
                "label": "756/756 (100.00%)",
                "total_candidate_count": 756,
                "resolved_count": 756,
                "remaining_candidate_count": 0,
                "failed_count": 0,
                "retryable_failure_count": 0,
                "blocked_failure_count": 0,
                "accounting": {"invariant_ok": True, "accounted_count": 756},
            },
            unique_source_replay_count=756,
            worker_status=self.worker(),
            data_gap_status={"request_count": 0},
            expected_total=756,
            evidence_audit=self.evidence(),
        )

        self.assertEqual("complete_verified", result["status"])
        self.assertTrue(result["completion_verified"])
        self.assertTrue(result["certificate_allowed"])
        self.assertEqual([], result["blockers"])

    def test_data_gap_or_blocked_failure_requires_repair(self):
        result = audit_replay_completion(
            progress={
                "total_candidate_count": 756,
                "resolved_count": 755,
                "remaining_candidate_count": 1,
                "failed_count": 1,
                "retryable_failure_count": 0,
                "blocked_failure_count": 1,
                "accounting": {"invariant_ok": True, "accounted_count": 756},
            },
            unique_source_replay_count=756,
            worker_status=self.worker(),
            data_gap_status={"request_count": 1},
            expected_total=756,
        )

        self.assertEqual("repair_required", result["status"])
        self.assertIn("no_failed_or_blocked_verdicts", result["blockers"])
        self.assertIn("no_unresolved_data_gaps", result["blockers"])

    def test_completion_certificate_rejects_missing_durable_evidence(self):
        result = audit_replay_completion(
            progress={
                "total_candidate_count": 756,
                "resolved_count": 756,
                "remaining_candidate_count": 0,
                "failed_count": 0,
                "retryable_failure_count": 0,
                "blocked_failure_count": 0,
                "accounting": {"invariant_ok": True, "accounted_count": 756},
            },
            unique_source_replay_count=756,
            worker_status=self.worker(),
            data_gap_status={"request_count": 0},
            expected_total=756,
            evidence_audit={
                "ok": False,
                "issue_count": 1,
                "audited_journal_count": 755,
                "audited_closed_trade_count": 1000,
                "deep": True,
            },
        )

        self.assertFalse(result["completion_verified"])
        self.assertIn("durable_trade_evidence_verified", result["blockers"])

    def test_completion_certificate_rejects_shallow_or_partial_evidence(self):
        result = audit_replay_completion(
            progress={
                "total_candidate_count": 756,
                "resolved_count": 756,
                "remaining_candidate_count": 0,
                "failed_count": 0,
                "retryable_failure_count": 0,
                "blocked_failure_count": 0,
                "accounting": {"invariant_ok": True, "accounted_count": 756},
            },
            unique_source_replay_count=756,
            worker_status=self.worker(),
            data_gap_status={"request_count": 0},
            expected_total=756,
            evidence_audit=self.evidence(deep=False, audited_journal_count=755),
        )

        self.assertFalse(result["completion_verified"])
        self.assertIn("durable_trade_evidence_verified", result["blockers"])

    def test_completion_certificate_requires_every_source_comparison(self):
        result = audit_replay_completion(
            progress={
                "total_candidate_count": 756,
                "resolved_count": 756,
                "remaining_candidate_count": 0,
                "failed_count": 0,
                "retryable_failure_count": 0,
                "blocked_failure_count": 0,
                "accounting": {"invariant_ok": True, "accounted_count": 756},
            },
            unique_source_replay_count=756,
            worker_status=self.worker(),
            data_gap_status={"request_count": 0},
            expected_total=756,
            evidence_audit=self.evidence(comparison_review_required_count=755),
        )

        self.assertFalse(result["completion_verified"])
        self.assertIn("source_comparison_accounted", result["blockers"])

    def test_completion_certificate_rejects_campaign_denominator_mismatch(self):
        result = audit_replay_completion(
            progress={
                "total_candidate_count": 756,
                "resolved_count": 756,
                "remaining_candidate_count": 0,
                "failed_count": 0,
                "retryable_failure_count": 0,
                "blocked_failure_count": 0,
                "accounting": {"invariant_ok": True, "accounted_count": 756},
            },
            unique_source_replay_count=756,
            worker_status=self.worker(),
            data_gap_status={"request_count": 0},
            evidence_audit=self.evidence(),
            expected_total=756,
            campaign_id_count=757,
        )

        self.assertFalse(result["completion_verified"])
        self.assertFalse(result["certificate_allowed"])
        self.assertIn("campaign_scope_manifest_consistent", result["blockers"])

    def test_empty_campaign_cannot_receive_completion_certificate(self):
        result = audit_replay_completion(
            progress={
                "total_candidate_count": 0,
                "resolved_count": 0,
                "remaining_candidate_count": 0,
                "failed_count": 0,
                "retryable_failure_count": 0,
                "blocked_failure_count": 0,
                "accounting": {"invariant_ok": True, "accounted_count": 0},
            },
            unique_source_replay_count=0,
            worker_status=self.worker(),
            data_gap_status={"request_count": 0},
            evidence_audit=self.evidence(total=0),
            expected_total=0,
            campaign_id_count=0,
        )

        self.assertFalse(result["completion_verified"])
        self.assertFalse(result["certificate_allowed"])
        self.assertIn("campaign_scope_nonempty", result["blockers"])


if __name__ == "__main__":
    unittest.main()
