import unittest

from app import stock_suite_app as stock_app


class InstanceLockPolicyTests(unittest.TestCase):
    def test_paper_replay_child_may_import_while_server_owns_lock(self):
        allowed = stock_app._instance_lock_bypass_allowed(
            argv=["replay-worker"],
            environ={"CODEXSTOCK_REPLAY_CHILD": "1"},
        )

        self.assertTrue(allowed)

    def test_plain_second_server_does_not_bypass_lock(self):
        allowed = stock_app._instance_lock_bypass_allowed(
            argv=["stock_suite_app.py"],
            environ={},
        )

        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
