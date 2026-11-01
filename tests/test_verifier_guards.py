"""Actual verifier graph guards, exercised only with authored temporary helpers."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "pipelines/verify.dot"

class VerifierGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = Path(self.temp.name) / "host"
        self.host.mkdir()
        subprocess.run(["git", "-c", "core.fsmonitor=false", "init", "-q", str(self.host)], check=True, capture_output=True)
        (self.host / "pipelines").mkdir()
        self.state = self.host / ".ai/verify_current.env"
        self.calls = self.host / "calls.jsonl"
        (self.host / "pipelines/ledger.py").write_text(
            'import json,os,sys\nfrom pathlib import Path\n'
            'args=sys.argv[1:]\n'
            'if args[0]=="earliest-implemented":\n'
            ' if os.environ.get("QUEUE_FAIL"): raise SystemExit(19)\n'
            ' print(os.environ.get("ROW", "pause a"))\n'
            'elif args[0]=="update":\n'
            ' if os.environ.get("UPDATE_FAIL"): raise SystemExit(19)\n'
            ' with Path(os.environ["CALLS"]).open("a") as f: f.write(json.dumps(args)+"\\n")\n'
        )
        donor = Path(self.temp.name) / "donor"
        donor.mkdir()
        subprocess.run(["git", "-c", "core.fsmonitor=false", "init", "-q", str(donor)], check=True, capture_output=True)
        self.ledger = self.host / "fixture.tsv"
        self.ledger.write_text("pause\ta\timplemented\n")
        (self.host / "not-called-forge.py").write_text("pass\n")
        self.env = {**os.environ, "HOST_A_PATH": str(self.host), "DONOR_PATH": str(donor),
                    "FORGE_TOOL": str(self.host / "not-called-forge.py"), "LEDGER_FILE": "fixture.tsv",
                    "CALLS": str(self.calls), "ROW": "pause a"}

    def command(self, node):
        raw = re.search(node + r' \[shape=parallelogram,\s*tool_command=("(?:\\.|[^"\\])*")', GRAPH.read_text()).group(1)
        return json.loads(raw)

    def run_node(self, node):
        return subprocess.run(["bash", "-c", self.command(node)], cwd=self.host, env=self.env,
                              capture_output=True, text=True, timeout=10)

    def state_text(self, text="SLUG=pause\nTARGET=a\n"):
        self.state.parent.mkdir(exist_ok=True)
        self.state.write_text(text)

    def assert_blocked(self, node):
        result = self.run_node(node)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "blocked", result.stderr)
        return result

    def test_queue_error_is_blocked_not_process(self):
        self.env["QUEUE_FAIL"] = "1"
        self.assert_blocked("CheckQueue")

    def test_selection_error_preserves_existing_state(self):
        self.state_text("sentinel\n")
        self.env["QUEUE_FAIL"] = "1"
        self.assert_blocked("SelectRow")
        self.assertEqual(self.state.read_text(), "sentinel\n")

    def test_valid_queue_and_selection(self):
        self.assertEqual(self.run_node("CheckQueue").stdout, "process")
        self.assertEqual(self.run_node("SelectRow").stdout, "ready")
        self.assertEqual(self.state.read_text(), "SLUG=pause\nTARGET=a\n")

    def test_empty_queue_is_done_and_cannot_select(self):
        self.env["ROW"] = "NONE"
        self.ledger.write_text("")
        self.assertEqual(self.run_node("CheckQueue").stdout, "done")
        self.assert_blocked("SelectRow")
        self.assertFalse(self.state.exists())

    def test_malformed_or_unsafe_row_never_becomes_ready(self):
        for row in ["pause", "pause a extra", "pause invalid", "$(id) a", "../escape a"]:
            with self.subTest(row=row):
                self.env["ROW"] = row
                self.assert_blocked("CheckQueue")
                self.assert_blocked("SelectRow")
                self.assertFalse(self.state.exists())

    def test_state_substitution_is_never_interpreted_as_shell(self):
        marker = self.host / "must-not-exist"
        self.state_text("SLUG=$(touch " + shlex.quote(str(marker)) + ")\nTARGET=a\n")
        for node in ["RunChecks", "MarkVerified", "ReopenGate"]:
            with self.subTest(node=node):
                self.assert_blocked(node)
                self.assertFalse(marker.exists(), "state contents executed as shell")
        self.assertFalse(self.calls.exists())

    def test_all_state_nodes_reject_missing_duplicate_extra_or_invalid_state(self):
        for state in ["SLUG=pause\n", "SLUG=pause\nTARGET=a\nTARGET=a\n", "SLUG=pause\nTARGET=a\nEXTRA=x\n", "SLUG=../../bad\nTARGET=a\n", "SLUG=pause\nTARGET=bad\n"]:
            for node in ["RunChecks", "MarkVerified", "ReopenGate"]:
                with self.subTest(state=state,node=node):
                    self.state_text(state)
                    self.assert_blocked(node)
        self.assertFalse(self.calls.exists())

    def test_update_failure_never_reports_next(self):
        self.state_text()
        self.env["UPDATE_FAIL"] = "1"
        self.assert_blocked("MarkVerified")
        self.assertFalse(self.calls.exists())

    def test_empty_first_assignment_cannot_hide_duplicate_fields(self):
        self.state_text()
        scripts = self.host / ".ai/verify_checks"
        scripts.mkdir()
        (scripts / "pause.sh").write_text("#!/bin/sh\nexit 0\n")
        Path(self.env["FORGE_TOOL"]).write_text("pass\n")
        findings = self.host / ".ai/verify_findings"
        findings.mkdir()
        (findings / "pause.md").write_text("DEFECT\nfixture\n")
        for state in ["SLUG=\nSLUG=pause\nTARGET=a\n", "SLUG=pause\nTARGET=\nTARGET=a\n"]:
            for node in ["RunChecks", "MarkVerified", "ReopenGate"]:
                with self.subTest(state=state,node=node):
                    self.state_text(state)
                    self.assert_blocked(node)
        self.assertFalse(self.calls.exists())

    def test_verified_update_passes_only_after_ledger_success(self):
        self.state_text()
        self.assertEqual(self.run_node("MarkVerified").stdout, "next")
        self.assertEqual(json.loads(self.calls.read_text().strip()), ["update", "pause", "verified"])

    def test_failed_reopen_update_retains_reserved_allowance_and_stops(self):
        self.state_text()
        findings = self.host / ".ai/verify_findings"
        findings.mkdir()
        (findings / "pause.md").write_text("DEFECT\nfictional mismatch\n")
        self.env["UPDATE_FAIL"] = "1"
        self.assert_blocked("ReopenGate")
        self.assertTrue((self.host / ".ai/verify_reopened_pause").exists())
        self.assertFalse(self.calls.exists())
        self.env.pop("UPDATE_FAIL")
        self.assertEqual(self.run_node("ReopenGate").stdout, "next")
        self.assertEqual(json.loads(self.calls.read_text().strip()), ["update", "pause", "acknowledged"])

    def test_missing_configured_ledger_is_blocked_but_existing_empty_is_done(self):
        self.ledger.unlink()
        self.assert_blocked("CheckQueue")
        self.assert_blocked("SelectRow")
        self.ledger.write_text("")
        self.env["ROW"] = "NONE"
        self.assertEqual(self.run_node("CheckQueue").stdout, "done")

    def test_all_verifier_descendant_symlinks_are_refused_without_changes(self):
        self.state_text()
        relatives = ["verify_checks/pause.sh", "verify_findings/pause.md", "verify_logs/pause.doctor.log", "verify_logs/pause.checks.log", "verify_flake_pause", "verify_reopened_pause"]
        for relative in relatives:
            with self.subTest(relative=relative):
                link=self.host/".ai"/relative
                link.parent.mkdir(exist_ok=True)
                outside=Path(self.temp.name)/"outside-sentinel"
                outside.write_text("preserve")
                link.symlink_to(outside)
                for node in ["CheckQueue", "SelectRow", "RunChecks", "MarkVerified", "ReopenGate"]:
                    with self.subTest(node=node):self.assert_blocked(node)
                self.assertEqual(outside.read_text(),"preserve")
                link.unlink()
        self.assertFalse(self.calls.exists())

    @unittest.skipIf(os.geteuid()==0, "read-only directory fixture requires ordinary user permissions")
    def test_marker_write_failure_does_not_advance_the_ledger(self):
        self.state_text()
        findings=self.host/".ai/verify_findings";findings.mkdir()
        (findings/"pause.md").write_text("DEFECT\nfixture\n")
        directory=self.host/".ai"
        directory.chmod(0o500)
        try:
            self.assert_blocked("ReopenGate")
            self.assertFalse(self.calls.exists())
            self.assertFalse((directory/"verify_reopened_pause").exists())
        finally:
            directory.chmod(0o700)

    def test_failed_doctor_cannot_leave_stale_check_evidence(self):
        self.state_text()
        scripts=self.host/".ai/verify_checks";scripts.mkdir()
        (scripts/"pause.sh").write_text("exit 0\n")
        logs=self.host/".ai/verify_logs";logs.mkdir()
        (logs/"pause.checks.log").write_text("stale prior success")
        Path(self.env["FORGE_TOOL"]).write_text("raise SystemExit(7)\n")
        self.assertEqual(self.run_node("RunChecks").stdout,"fail")
        self.assertEqual((logs/"pause.checks.log").read_text(),"")

    def test_missing_or_invalid_findings_do_not_reopen(self):
        self.state_text()
        self.assert_blocked("ReopenGate")
        findings = self.host / ".ai/verify_findings"
        findings.mkdir()
        (findings / "pause.md").write_text("MAYBE\n")
        self.assert_blocked("ReopenGate")
        self.assertFalse(self.calls.exists())

    def test_wrong_host_is_blocked_before_state_or_ledger_actions(self):
        wrong = self.host / "subdirectory"
        wrong.mkdir()
        self.env["HOST_A_PATH"] = str(wrong)
        for node in ["CheckQueue", "SelectRow", "RunChecks", "MarkVerified", "ReopenGate"]:
            with self.subTest(node=node):
                self.assert_blocked(node)
        self.assertFalse(self.calls.exists())

    def test_missing_second_host_cannot_select_a_two_host_target(self):
        self.env["ROW"] = "pause ab"
        self.ledger.write_text("pause\tab\timplemented\n")
        self.env.pop("HOST_B_PATH", None)
        self.assert_blocked("CheckQueue")
        self.assert_blocked("SelectRow")
        self.assertFalse(self.state.exists())

    def test_symlinked_state_directory_is_not_used(self):
        other = Path(self.temp.name) / "other"
        other.mkdir()
        (self.host / ".ai").symlink_to(other, target_is_directory=True)
        self.assert_blocked("SelectRow")
        self.assertEqual(list(other.iterdir()), [])

    def test_run_checks_uses_only_authored_fixture_tools_and_scoped_logs(self):
        self.state_text()
        scripts = self.host / ".ai/verify_checks"
        scripts.mkdir()
        check = scripts / "pause.sh"
        check.write_text("#!/bin/sh\nexit 0\n")
        forge = Path(self.env["FORGE_TOOL"])
        forge.write_text("import sys\nassert sys.argv[1:] == ['doctor']\n")
        self.assertEqual(self.run_node("RunChecks").stdout, "pass")
        self.assertTrue((self.host / ".ai/verify_logs/pause.doctor.log").exists())
        self.assertTrue((self.host / ".ai/verify_logs/pause.checks.log").exists())
        check.write_text("#!/bin/sh\nexit 1\n")
        self.assertEqual(self.run_node("RunChecks").stdout, "fail")

    def test_flake_recheck_and_single_reopen_remain_bounded(self):
        self.state_text()
        findings = self.host / ".ai/verify_findings"
        findings.mkdir()
        (findings / "pause.md").write_text("FLAKE\nfictional timing issue\n")
        self.assertEqual(self.run_node("ReopenGate").stdout, "recheck")
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.run_node("ReopenGate").stdout, "next")
        self.assertEqual(self.run_node("ReopenGate").stdout, "next")
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls, [["update", "pause", "new"], ["update", "pause", "acknowledged"]])

    def test_blocked_tokens_have_explicit_exit_edges(self):
        text = GRAPH.read_text()
        for node in ["CheckQueue", "SelectRow", "RunChecks", "MarkVerified", "ReopenGate"]:
            with self.subTest(node=node):
                self.assertRegex(text, node + r' -> exit\s*\[condition="context.tool.last_line=blocked"\]')

if __name__ == "__main__":
    unittest.main()
