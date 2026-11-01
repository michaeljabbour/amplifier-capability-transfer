"""Invoke the actual ledger CLI only on isolated fictional files."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LEDGER = Path(__file__).resolve().parents[1] / "pipelines" / "ledger.py"

class LedgerCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fictional.tsv"
        self.path.write_text("pause\thostA\tnew\nresume\thostB\timplemented\n")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(LEDGER), *args],
            env={**os.environ, "LEDGER_FILE": str(self.path)},
            capture_output=True, text=True, timeout=10)

    def assert_refused_without_write(self, *args):
        before = self.path.read_bytes()
        result = self.run_cli(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.path.read_bytes(), before)
        return result

    def test_valid_queue_selection_and_update(self):
        self.assertEqual(self.run_cli("earliest").stdout.strip(), "pause hostA")
        self.assertEqual(self.run_cli("earliest-implemented").stdout.strip(), "resume hostB")
        self.assertEqual(self.run_cli("update", "pause", "implemented").returncode, 0)
        self.assertEqual(self.run_cli("earliest").stdout.strip(), "NONE")

    def test_invalid_state_update_is_not_success_or_a_write(self):
        self.assert_refused_without_write("update", "pause", "unknown")

    def test_unknown_key_update_is_not_success(self):
        self.assert_refused_without_write("update", "missing", "implemented")

    def test_verified_is_terminal_but_idempotent_update_is_valid(self):
        self.path.write_text("pause\thostA\tverified\n")
        self.assert_refused_without_write("update", "pause", "new")
        self.assertEqual(self.run_cli("update", "pause", "verified").returncode, 0)

    def test_verifier_reopen_of_implemented_is_permitted(self):
        self.assertEqual(self.run_cli("update", "resume", "new").returncode, 0)
        self.assertIn("resume\thostB\tnew", self.path.read_text())

    def test_duplicate_or_malformed_snapshot_never_becomes_empty_queue(self):
        for text in ["a\thostA\tnew\na\thostB\tnew\n", "a\thostA\n", "a\thostA\tunknown\n", "a\t\tnew\n"]:
            for cmd in ("earliest", "stats", "sort"):
                with self.subTest(text=text, cmd=cmd):
                    self.path.write_text(text)
                    result = self.assert_refused_without_write(cmd)
                    self.assertNotEqual(result.stdout.strip(), "NONE")

    def test_add_is_idempotent_for_identical_key_and_target(self):
        before = self.path.read_bytes()
        self.assertEqual(self.run_cli("add", "pause", "hostA").returncode, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_key_cannot_change_target(self):
        self.assert_refused_without_write("add", "pause", "hostZ")

    def test_add_rejects_empty_or_multiline_fields(self):
        for key, target in [("", "host"), ("new", ""), (" pause", "host"), ("new", "host "), ("new\nforged", "host"), ("new", "host\tnew")]:
            with self.subTest(key=key,target=target):
                self.assert_refused_without_write("add", key, target)

    def test_new_valid_key_is_appended(self):
        self.assertEqual(self.run_cli("add", "cancel", "hostB").returncode, 0)
        self.assertIn("cancel\thostB\tnew\n", self.path.read_text())

    def test_add_cannot_create_an_invisible_comment_key(self):
        self.assert_refused_without_write("add", "#hidden", "host")

    def test_add_rejects_all_line_boundaries_and_token_ambiguity(self):
        boundaries = ["\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029", " ", "\u00a0"]
        for separator in boundaries:
            for key, target in [("alpha" + separator + "forged", "host"), ("new", "host" + separator + "a")]:
                with self.subTest(key=key,target=target):
                    self.assert_refused_without_write("add", key, target)

    def test_empty_missing_ledger_remains_a_valid_empty_queue(self):
        self.path.unlink()
        result = self.run_cli("earliest")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "NONE")
        self.assertFalse(self.path.exists())

if __name__ == "__main__":
    unittest.main()
