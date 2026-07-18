import json
import tempfile
import unittest
from pathlib import Path

from app.runtime_storage_audit import audit_runtime_storage


class RuntimeStorageAuditTests(unittest.TestCase):
    def test_retention_preserves_baseline_newest_and_contract_pin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = root / "data"
            backups = data / "backups" / "jsonl_compaction"
            backups.mkdir(parents=True)
            paths = []
            for index, size in enumerate((100, 20, 30, 40), start=1):
                path = backups / f"history.jsonl.2026010{index}-000000.bak"
                path.write_bytes(b"x" * size)
                paths.append(path)
            (data / "events.jsonl").write_text('{"ok": true}\n', encoding="utf-8")
            index_path = data / "contract_index.json"
            index_path.write_text(
                json.dumps({"entries": {"R1": {"source_backup_path": str(paths[1])}}}),
                encoding="utf-8",
            )

            result = audit_runtime_storage(
                root,
                data_root=data,
                contract_index_path=index_path,
            )

        retention = result["backup_retention"]
        preserved_names = {row["name"] for row in retention["preserved"]}
        self.assertTrue(result["ok"])
        self.assertEqual(4, retention["backup_count"])
        self.assertIn(paths[0].name, preserved_names)
        self.assertIn(paths[1].name, preserved_names)
        self.assertIn(paths[-1].name, preserved_names)
        self.assertEqual(1, retention["removable_count"])
        self.assertFalse(result["cleanup_applied"])
        self.assertFalse(result["live_order_allowed"])

    def test_missing_contract_pin_requires_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = root / "data"
            backups = data / "backups" / "jsonl_compaction"
            backups.mkdir(parents=True)
            backup = backups / "history.jsonl.20260101-000000.bak"
            backup.write_bytes(b"x")
            index_path = data / "contract_index.json"
            index_path.write_text(
                json.dumps({"entries": {"R1": {"source_backup_path": str(backups / 'missing.bak')}}}),
                encoding="utf-8",
            )

            result = audit_runtime_storage(root, data_root=data, contract_index_path=index_path)

        self.assertFalse(result["ok"])
        self.assertEqual("review_required", result["status"])
        self.assertEqual(1, result["backup_retention"]["missing_contract_pin_count"])


if __name__ == "__main__":
    unittest.main()
