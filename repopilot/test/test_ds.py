from repopilot.commands.setup import handle, _scan, _resolve, _sanitise_llm_response
from argparse import Namespace
from unittest.mock import patch, MagicMock
import unittest
import tempfile
import shutil
import sys
import os
# Auto-add root repository folder to sys.path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


class TestRepoPilotSetup(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory before each test."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up the temporary directory after each test."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Rule-Based Detection Tests
    # -------------------------------------------------------------------------
    def test_python_requirements_detection(self):
        """Test that requirements.txt is mapped to pip install."""
        req_file = os.path.join(self.test_dir, "requirements.txt")
        with open(req_file, "w") as f:
            f.write("requests==2.28.0\npytest\n")

        detected = _scan(self.test_dir)
        plan = _resolve(detected, self.test_dir)

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][0], "Python (pip)")
        self.assertEqual(plan[0][1], "pip install -r requirements.txt")
        self.assertEqual(plan[0][2], "requirements.txt")

    def test_node_package_json_detection(self):
        """Test that package.json is mapped to npm install."""
        pkg_file = os.path.join(self.test_dir, "package.json")
        with open(pkg_file, "w") as f:
            f.write('{"name": "test-app", "version": "1.0.0"}\n')

        detected = _scan(self.test_dir)
        plan = _resolve(detected, self.test_dir)

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][0], "Node.js")
        self.assertEqual(plan[0][1], "npm install")

    # -------------------------------------------------------------------------
    # 2. Script Auto-Detection Tests (.ps1, .bat, .sh)
    # -------------------------------------------------------------------------
    def test_powershell_script_detection(self):
        """Test that .ps1 scripts are detected and mapped to powershell invocation."""
        ps1_file = os.path.join(self.test_dir, "build.ps1")
        with open(ps1_file, "w") as f:
            f.write('Write-Host "Building project..."\n')

        detected = _scan(self.test_dir)
        plan = _resolve(detected, self.test_dir)

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][0], "PowerShell Script")
        self.assertEqual(
            plan[0][1], f"powershell {os.path.join('.', 'build.ps1')}")

    # -------------------------------------------------------------------------
    # 3. English Text File & LLM Fallback Tests
    # -------------------------------------------------------------------------
    def test_english_text_file_passes_to_llm(self):
        """Test that English text files (.txt/.md) are sent to LLM candidate list."""
        txt_file = os.path.join(self.test_dir, "INSTALL_GUIDE.txt")
        with open(txt_file, "w") as f:
            f.write("To setup this application, run cargo build in terminal.\n")

        detected = _scan(self.test_dir)
        # Should classify INSTALL_GUIDE.txt as an 'llm' candidate
        self.assertIn(("INSTALL_GUIDE.txt", "llm"), detected)

    @patch("urllib.request.urlopen")
    def test_llm_resolve_success(self, mock_urlopen):
        """Test that Ollama LLM mock response is resolved correctly."""
        txt_file = os.path.join(self.test_dir, "INSTALL.txt")
        with open(txt_file, "w") as f:
            f.write("Run cargo build to compile.\n")

        # Mock Ollama API response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "cargo build"}}]}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        detected = [("INSTALL.txt", "llm")]
        plan = _resolve(detected, self.test_dir)

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][0], "INSTALL.txt (LLM-resolved)")
        self.assertEqual(plan[0][1], "cargo build")

    # -------------------------------------------------------------------------
    # 4. Security & Error Handling Tests
    # -------------------------------------------------------------------------
    def test_dangerous_llm_command_rejected(self):
        """Test that dangerous LLM commands like 'rm -rf' are rejected."""
        self.assertIsNone(_sanitise_llm_response("rm -rf /"))
        self.assertIsNone(_sanitise_llm_response("sudo format c:"))
        self.assertEqual(_sanitise_llm_response("npm install"), "npm install")

    def test_empty_directory_raises_system_exit(self):
        """Test that running setup on an empty directory exits cleanly with error."""
        args = Namespace(dir=self.test_dir, dry_run=True, yes=True)
        with self.assertRaises(SystemExit) as cm:
            handle(args)
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
