from repopilot.cli import build_parser
import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


class DemoTestCases(unittest.TestCase):

    def setUp(self):
        self.parser = build_parser()

    # ---------------------------------------------------------
    # 1. PASSING TEST
    # ---------------------------------------------------------
    def test_passes(self):
        """Passes because valid arguments are parsed correctly."""
        args = self.parser.parse_args(["setup", "--dry-run"])
        self.assertEqual(args.command, "setup")
        self.assertTrue(args.dry_run)

    # ---------------------------------------------------------
    # 2. FAILING / ERRORING TEST
    # ---------------------------------------------------------
    def test_fails_invalid_flag(self):
        """Fails because --nonexistent-flag is not a valid flag."""
        # Running this will raise SystemExit(2) and fail the test!
        args = self.parser.parse_args(["setup", "--nonexistent-flag"])
        self.assertTrue(args.dry_run)

    # ---------------------------------------------------------
    # 3. EXPECTS AN ERROR & PASSES (Handling Expected Failures)
    # ---------------------------------------------------------
    def test_expected_error_passes(self):
        """Passes because we expect argparse to raise SystemExit on invalid input."""
        with self.assertRaises(SystemExit) as cm:
            self.parser.parse_args(["setup", "--invalid-arg"])

        # Verify that argparse exited with code 2 (user error code)
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
