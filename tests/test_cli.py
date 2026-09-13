from repopilot.cli import build_parser
import unittest
import sys
import os
# Auto-add root repository folder to sys.path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


class TestRepoPilotCLI(unittest.TestCase):

    def setUp(self):
        self.parser = build_parser()

    def test_version_flag(self):
        """Test --version flag exits zero."""
        with self.assertRaises(SystemExit) as cm:
            self.parser.parse_args(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_setup_subcommand_parsing(self):
        """Test setup subcommand arguments."""
        args = self.parser.parse_args(
            ["setup", "--dry-run", "--yes", "--dir", "./my_app"])
        self.assertEqual(args.command, "setup")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.yes)
        self.assertEqual(args.dir, "./my_app")

    def test_env_subcommand_parsing(self):
        """Test env subcommand arguments."""
        args = self.parser.parse_args(["env", "switch", "staging"])
        self.assertEqual(args.command, "env")
        self.assertEqual(args.env_subcommand, "switch")
        self.assertEqual(args.name, "staging")

    def test_clean_subcommand_parsing(self):
        """Test clean subcommand arguments."""
        args = self.parser.parse_args(["clean", "--dry-run", "--force"])
        self.assertEqual(args.command, "clean")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.force)

    def test_logs_subcommand_parsing(self):
        """Test logs subcommand arguments."""
        args = self.parser.parse_args(["logs"])
        self.assertEqual(args.command, "logs")


if __name__ == "__main__":
    unittest.main()
