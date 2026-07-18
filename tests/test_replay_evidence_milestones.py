import unittest

from app.replay_evidence_milestones import (
    EVIDENCE_BUNDLE_HASH_CONTRACT,
    due_evidence_milestones,
    evidence_scope_hash,
    evidence_milestones,
    replay_evidence_bundle_hash,
    valid_evidence_milestone_record,
)


class ReplayEvidenceMilestoneTests(unittest.TestCase):
    def test_target_is_always_the_final_unique_milestone(self):
        self.assertEqual([10, 25, 100, 300, 500, 757], evidence_milestones(757))
        self.assertEqual([10, 25, 100], evidence_milestones(100))
        self.assertEqual([10, 12], evidence_milestones(12))

    def test_only_unrecorded_reached_milestones_are_due(self):
        self.assertEqual(
            [300],
            due_evidence_milestones(
                resolved_count=320,
                target_count=757,
                passed_milestones=[10, 25, 100],
            ),
        )

    def test_valid_record_requires_all_hashes_counts_and_paper_safety(self):
        campaign_hash = evidence_scope_hash(["HREPLAY-1", "HREPLAY-2"])
        audited_source_ids = [f"HREPLAY-{index}" for index in range(1, 501)]
        audited_scope_hash = evidence_scope_hash(audited_source_ids)
        artifact_contract = "sha256-canonical-replay-v1+exact-journal-bytes-v1"
        record = {
            "schema": "codexstock_replay_evidence_milestone_v8",
            "campaign_id": "campaign-1",
            "target_count": 757,
            "campaign_scope_hash": campaign_hash,
            "evidence_schema_version": "historical-replay-evidence.v2",
            "execution_timing_model_version": "prior-bar-signal-next-close.v2",
            "replay_data_bundle_evidence_schema": "codexstock_replay_data_bundle_slice_evidence_v3",
            "milestone": 500,
            "status": "passed",
            "resolved_count": 500,
            "verified_count": 500,
            "audited_journal_count": 500,
            "quarantined_count": 0,
            "failed_count": 0,
            "issue_count": 0,
            "ledger_evidence_hash": "a" * 64,
            "journal_evidence_hash": "b" * 64,
            "replay_evidence_hash": "c" * 64,
            "audited_source_ids": audited_source_ids,
            "audited_scope_hash": audited_scope_hash,
            "evidence_bundle_hash_contract": EVIDENCE_BUNDLE_HASH_CONTRACT,
            "artifact_hash_contract": artifact_contract,
            "artifact_anchor_required_count": 500,
            "artifact_anchor_verified_count": 500,
            "artifact_anchor_mismatch_count": 0,
            "artifact_anchor_deep_verified": True,
            "paper_only": True,
            "live_order_allowed": False,
        }
        record["evidence_bundle_hash"] = replay_evidence_bundle_hash(
            audited_scope_hash=record["audited_scope_hash"],
            evidence_schema_version=record["evidence_schema_version"],
            execution_timing_model_version=record["execution_timing_model_version"],
            artifact_hash_contract=record["artifact_hash_contract"],
            ledger_evidence_hash=record["ledger_evidence_hash"],
            journal_evidence_hash=record["journal_evidence_hash"],
            replay_evidence_hash=record["replay_evidence_hash"],
            replay_data_bundle_evidence_schema=record[
                "replay_data_bundle_evidence_schema"
            ],
        )
        validation_args = {
            "required_evidence_schema_version": "historical-replay-evidence.v2",
            "required_execution_timing_model_version": "prior-bar-signal-next-close.v2",
            "required_replay_data_bundle_evidence_schema": "codexstock_replay_data_bundle_slice_evidence_v3",
            "required_artifact_hash_contract": artifact_contract,
            "required_campaign_scope_hash": campaign_hash,
            "currently_verified_source_ids": audited_source_ids,
            "required_target_count": 757,
        }
        self.assertTrue(valid_evidence_milestone_record(record, **validation_args))

        for field, unsafe_value in (
            ("schema", "codexstock_replay_evidence_milestone_v7"),
            ("target_count", 756),
            ("campaign_scope_hash", "d" * 64),
            ("evidence_schema_version", "historical-replay-evidence.v1"),
            ("execution_timing_model_version", "prior-bar-signal-next-close.v1"),
            ("replay_data_bundle_evidence_schema", "codexstock_replay_data_bundle_slice_evidence_v2"),
            ("ledger_evidence_hash", ""),
            ("journal_evidence_hash", "bad"),
            ("replay_evidence_hash", ""),
            ("evidence_bundle_hash", "A" * 64),
            ("audited_scope_hash", "e" * 64),
            ("evidence_bundle_hash_contract", "legacy"),
            ("audited_source_ids", audited_source_ids[:-1]),
            ("audited_journal_count", 499),
            ("artifact_hash_contract", "legacy"),
            ("artifact_anchor_required_count", 499),
            ("artifact_anchor_verified_count", 499),
            ("artifact_anchor_mismatch_count", 1),
            ("artifact_anchor_deep_verified", False),
            ("issue_count", 1),
            ("paper_only", False),
            ("live_order_allowed", True),
        ):
            damaged = {**record, field: unsafe_value}
            self.assertFalse(
                valid_evidence_milestone_record(damaged, **validation_args),
                field,
            )
        self.assertEqual(
            [],
            due_evidence_milestones(
                resolved_count=299,
                target_count=757,
                passed_milestones=[10, 25, 100],
            ),
        )

    def test_early_deep_audit_is_due_at_ten(self):
        self.assertEqual(
            [],
            due_evidence_milestones(
                resolved_count=9,
                target_count=757,
                passed_milestones=[],
            ),
        )
        self.assertEqual(
            [10],
            due_evidence_milestones(
                resolved_count=10,
                target_count=757,
                passed_milestones=[],
            ),
        )


if __name__ == "__main__":
    unittest.main()
