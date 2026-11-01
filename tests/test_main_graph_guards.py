"""Main graph boundary probes using actual commands and temporary authored hosts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import test_branch_setup as branch_fixtures
ROOT = branch_fixtures.ROOT

NODES = ["CheckLedger", "BranchSetup", "UnitValidate", "ForgeValidate", "RetryGate", "Commit", "MarkBlocked"]
STATE_NODES = [x for x in NODES if x != "CheckLedger"]

class MainGraphGuardTests(unittest.TestCase):
    def setUp(self):
        self.f = branch_fixtures.BranchSetupTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.host = self.f.a
        self.env = self.f.env
        self.donor = self.f.repo("donor")
        pipelines = self.host / "pipelines"
        pipelines.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "pipelines/ledger.py", pipelines / "ledger.py")
        self.ledger = pipelines / "fixture.tsv"
        self.ledger.write_text("feature-1\ta\tnew\n")
        self.f.git(self.host,"add","pipelines")
        self.f.git(self.host,"commit","-qm","fictional ledger fixture")
        self.forge = self.f.base / "fake-forge.py"
        self.forge.write_text("import os,sys\nfrom pathlib import Path\nPath(os.environ['FORGE_CALLS']).write_text('called')\n")
        self.forge_calls = self.f.base / "forge-called"
        self.env.update({"DONOR_PATH":str(self.donor),"HOST_A_KIND":"new:fixture","HOST_B_KIND":"new:fixture",
                         "FORGE_TOOL":str(self.forge),"FORGE_CALLS":str(self.forge_calls),"LEDGER_FILE":"pipelines/fixture.tsv"})

    def run_node(self, node):
        return subprocess.run(["bash","-c",self.f.node_command(node)],cwd=self.f.base,
                              env=self.env,text=True,capture_output=True,timeout=10)

    def blocked(self, node):
        result=self.run_node(node)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,"blocked",result.stderr)
        return result

    def gate(self, root, script="exit 0"):
        p=root/"ci";p.mkdir(exist_ok=True)
        (p/"gate.sh").write_text("#!/bin/sh\n"+script+"\n")
        (p/"gate.sh").chmod(0o755)

    def test_symlinked_ai_refused_before_any_node_mutates(self):
        shutil.rmtree(self.host/".ai")
        outside=self.f.base/"outside";outside.mkdir()
        (outside/"hgt_current.env").write_text("SLUG=feature-1\nTARGET=a\n")
        (outside/"hgt_retries").write_text("sentinel")
        (self.host/".ai").symlink_to(outside,target_is_directory=True)
        before={p.name:p.read_bytes() for p in outside.iterdir()}
        for node in NODES:
            with self.subTest(node=node):self.blocked(node)
        self.assertEqual({p.name:p.read_bytes() for p in outside.iterdir()},before)
        self.assertEqual(self.f.mutations(),[])
        self.assertFalse(self.forge_calls.exists())

    def test_symlinked_state_and_retry_files_refused_without_change(self):
        for name in ["hgt_current.env","hgt_retries"]:
            with self.subTest(name=name):
                path=self.host/".ai"/name
                if path.exists():path.unlink()
                outside=self.f.base/("outside-"+name)
                outside.write_text("SLUG=feature-1\nTARGET=a\n" if name.endswith("env") else "0\n")
                path.symlink_to(outside)
                before=outside.read_bytes()
                self.blocked("BranchSetup")
                self.assertEqual(outside.read_bytes(),before)
                path.unlink()
                if name.endswith("env"):path.write_text("SLUG=feature-1\nTARGET=a\n")
        self.assertEqual(self.f.mutations(),[])

    def test_bad_ledger_paths_and_data_are_blocked(self):
        outside=self.f.base/"external.tsv";outside.write_text("feature-1\ta\tnew\n")
        for path in [str(outside),"../external.tsv","pipelines/missing.tsv"]:
            with self.subTest(path=path):
                self.env["LEDGER_FILE"]=path
                self.blocked("CheckLedger")
        self.env["LEDGER_FILE"]="pipelines/fixture.tsv"
        for content in ["broken\n","feature-1\ta\tunknown\n","feature-1\ta\tnew\nfeature-1\tab\tnew\n"]:
            with self.subTest(content=content):
                self.ledger.write_text(content)
                self.blocked("CheckLedger")
        self.assertEqual(self.f.mutations(),[])

    def test_ledger_symlink_is_refused_before_execution(self):
        original=self.ledger.read_bytes();self.ledger.unlink()
        outside=self.f.base/"external.tsv";outside.write_bytes(original)
        self.ledger.symlink_to(outside)
        self.blocked("CheckLedger")
        self.assertEqual(outside.read_bytes(),original)

    def test_missing_or_same_donor_is_not_an_eligible_transfer(self):
        for donor in [self.f.base/"missing",self.host,self.f.b]:
            with self.subTest(donor=donor):
                self.env["DONOR_PATH"]=str(donor)
                if donor==self.f.b:
                    self.f.state.write_text("SLUG=feature-1\nTARGET=ab\n")
                    self.ledger.write_text("feature-1\tab\tnew\n")
                self.blocked("BranchSetup")
        self.assertEqual(self.f.mutations(),[])

    def test_empty_first_duplicate_fields_and_substitution_never_execute(self):
        marker=self.f.base/"never-executed"
        states=["SLUG=\nSLUG=feature-1\nTARGET=a\n","SLUG=feature-1\nTARGET=\nTARGET=a\n",
                "SLUG=$(touch "+str(marker)+")\nTARGET=a\n"]
        for state in states:
            self.f.state.write_text(state)
            for node in STATE_NODES:
                with self.subTest(state=state,node=node):self.blocked(node)
        self.assertFalse(marker.exists())
        self.assertEqual(self.f.mutations(),[])
        self.assertFalse(self.forge_calls.exists())

    def test_state_cannot_select_a_different_or_completed_ledger_row(self):
        for ledger in ["other\ta\tnew\n","feature-1\tab\tnew\n","feature-1\ta\timplemented\n"]:
            self.ledger.write_text(ledger)
            with self.subTest(ledger=ledger):self.blocked("BranchSetup")
        self.assertEqual(self.f.mutations(),[])

    def test_branch_setup_preserves_dirty_configured_queue_and_helper(self):
        queue="feature-1\ta\timplemented\nfeature-2\ta\tnew\n"
        self.ledger.write_text(queue)
        self.f.state.write_text("SLUG=feature-2\nTARGET=a\n")
        helper=self.host/"pipelines/ledger.py"
        helper_before=helper.read_bytes()
        result=self.run_node("BranchSetup")
        self.assertEqual(result.stdout,"ready",result.stderr)
        self.assertEqual(self.ledger.read_text(),queue)
        self.assertEqual(helper.read_bytes(),helper_before)
        self.assertEqual(self.f.git(self.host,"branch","--show-current"),"hgt/feature-2")

    def test_unit_logs_are_scoped_and_gate_failure_stays_fail(self):
        self.gate(self.host)
        self.assertEqual(self.run_node("UnitValidate").stdout,"pass")
        log=self.host/".ai/hgt_logs/feature-1.unit_a.log"
        self.assertTrue(log.exists())
        self.gate(self.host,"exit 7")
        self.assertEqual(self.run_node("UnitValidate").stdout,"fail")

    def test_validation_record_names_only_current_stage_and_target_logs(self):
        self.gate(self.host,"exit 7")
        logs=self.host/".ai/hgt_logs";logs.mkdir()
        (logs/"feature-1.unit_b.log").write_text("stale skipped host")
        (logs/"feature-1.forge.log").write_text("stale prior stage")
        self.assertEqual(self.run_node("UnitValidate").stdout,"fail")
        record=json.loads((self.host/".ai/hgt_validation.json").read_text())
        self.assertEqual(record,{"slug":"feature-1","target":"a","stage":"unit","result":"fail","logs":[".ai/hgt_logs/feature-1.unit_a.log"]})

    def test_two_host_validation_record_has_both_current_logs(self):
        self.f.state.write_text("SLUG=feature-1\nTARGET=ab\n")
        self.ledger.write_text("feature-1\tab\tnew\n")
        self.gate(self.host);self.gate(self.f.b)
        self.assertEqual(self.run_node("UnitValidate").stdout,"pass")
        record=json.loads((self.host/".ai/hgt_validation.json").read_text())
        self.assertEqual(record["target"],"ab")
        self.assertEqual(record["logs"],[".ai/hgt_logs/feature-1.unit_a.log",".ai/hgt_logs/feature-1.unit_b.log"])

    def test_failed_doctor_does_not_reuse_prior_forge_check_log(self):
        (self.host/".ai/hgt_forge_check.sh").write_text("exit 0\n")
        logs=self.host/".ai/hgt_logs";logs.mkdir()
        (logs/"feature-1.forge.log").write_text("stale success")
        self.forge.write_text("raise SystemExit(7)\n")
        self.assertEqual(self.run_node("ForgeValidate").stdout,"fail")
        record=json.loads((self.host/".ai/hgt_validation.json").read_text())
        self.assertEqual(record["logs"],[".ai/hgt_logs/feature-1.forge_doctor.log"])
        self.assertEqual((logs/"feature-1.forge.log").read_text(),"")

    @unittest.skipIf(os.geteuid()==0,"read-only log fixture requires ordinary user permissions")
    def test_unwritable_logs_block_before_gate_or_publication(self):
        self.gate(self.host,"touch gate-ran")
        self.f.git(self.host,"switch","-qc","hgt/feature-1")
        logs=self.host/".ai/hgt_logs";logs.mkdir()
        paths=[logs/"feature-1.unit_a.log",logs/"feature-1.pr_a.log"]
        try:
            for path in paths:path.write_text("preserve");path.chmod(0o400)
            self.blocked("UnitValidate")
            self.blocked("Commit")
            self.assertFalse((self.host/"gate-ran").exists())
            self.assertEqual(self.f.mutations(),[])
            for path in paths:self.assertEqual(path.read_text(),"preserve")
        finally:
            for path in paths:path.chmod(0o600)

    def test_missing_gate_is_blocked_infrastructure(self):
        self.blocked("UnitValidate")
        self.assertFalse((self.host/".ai/hgt_validation.json").exists())

    def test_retry_stops_after_third_attempt_without_resetting_allowance(self):
        self.assertEqual(self.run_node("RetryGate").stdout,"retry")
        self.assertEqual(self.run_node("RetryGate").stdout,"retry")
        self.assertEqual(self.run_node("RetryGate").stdout,"giveup")
        self.assertEqual(self.run_node("RetryGate").stdout,"giveup")
        self.assertEqual((self.host/".ai/hgt_retries").read_text(),"3\n")

    def test_pr_log_symlink_is_refused_before_commit_or_push(self):
        self.f.git(self.host,"switch","-qc","hgt/feature-1")
        logs=self.host/".ai/hgt_logs";logs.mkdir()
        outside=self.f.base/"private-pr-sentinel";outside.write_text("preserve")
        (logs/"feature-1.pr_a.log").symlink_to(outside)
        self.blocked("Commit")
        self.assertEqual(outside.read_text(),"preserve")
        self.assertEqual(self.f.mutations(),[])

    def test_wrong_primary_or_secondary_branch_preserves_existing_pr_receipts(self):
        logs=self.host/".ai/hgt_logs";logs.mkdir()
        primary=logs/"feature-1.pr_a.log";primary.write_text("PRIMARY RECEIPT\n")
        self.blocked("Commit")
        self.assertEqual(primary.read_text(),"PRIMARY RECEIPT\n")
        self.f.git(self.host,"switch","-qc","hgt/feature-1")
        self.f.state.write_text("SLUG=feature-1\nTARGET=ab\n")
        self.ledger.write_text("feature-1\tab\tnew\n")
        secondary=logs/"feature-1.pr_b.log";secondary.write_text("SECONDARY RECEIPT\n")
        self.blocked("Commit")
        self.assertEqual(primary.read_text(),"PRIMARY RECEIPT\n")
        self.assertEqual(secondary.read_text(),"SECONDARY RECEIPT\n")
        self.assertEqual(self.f.mutations(),[])

    def test_primary_staged_metadata_is_refused_without_unstaging_it(self):
        self.f.git(self.host,"switch","-qc","hgt/feature-1")
        private=self.host/".ai/private.txt";private.write_text("fictional private data")
        self.f.git(self.host,"add","--",".ai/private.txt")
        before=self.f.git(self.host,"diff","--cached","--name-status")
        self.blocked("Commit")
        self.assertEqual(self.f.git(self.host,"diff","--cached","--name-status"),before)
        self.assertEqual(self.f.mutations(),[])

    def test_secondary_staged_metadata_blocks_before_primary_commit(self):
        self.f.git(self.host,"switch","-qc","hgt/feature-1")
        self.f.git(self.f.b,"switch","-qc","hgt/feature-1")
        self.f.state.write_text("SLUG=feature-1\nTARGET=ab\n")
        self.ledger.write_text("feature-1\tab\tnew\n")
        private=self.f.b/".ai/private.txt";private.write_text("fictional private data")
        self.f.git(self.f.b,"add","--",".ai/private.txt")
        before=self.f.git(self.f.b,"diff","--cached","--name-status")
        self.blocked("Commit")
        self.assertEqual(self.f.git(self.f.b,"diff","--cached","--name-status"),before)
        self.assertEqual(self.f.mutations(),[])

    def test_log_file_symlink_cannot_overwrite_an_external_file(self):
        self.gate(self.host)
        logs=self.host/".ai/hgt_logs";logs.mkdir()
        outside=self.f.base/"private-sentinel";outside.write_text("preserve")
        (logs/"feature-1.unit_a.log").symlink_to(outside)
        self.blocked("UnitValidate")
        self.assertEqual(outside.read_text(),"preserve")

    def test_log_directory_symlink_is_refused_before_a_gate(self):
        self.gate(self.host,"touch gate-ran")
        outside=self.f.base/"outside-logs";outside.mkdir()
        (self.host/".ai/hgt_logs").symlink_to(outside,target_is_directory=True)
        self.blocked("UnitValidate")
        self.assertFalse((self.host/"gate-ran").exists())
        self.assertEqual(list(outside.iterdir()),[])

    def test_fake_forge_paths_are_scoped_and_check_symlink_is_refused(self):
        check=self.host/".ai/hgt_forge_check.sh";check.write_text("exit 0\n")
        self.assertEqual(self.run_node("ForgeValidate").stdout,"pass")
        self.assertTrue((self.host/".ai/hgt_logs/feature-1.forge.log").exists())
        self.assertTrue(self.forge_calls.exists());self.forge_calls.unlink()
        check.unlink();outside=self.f.base/"outside-check";outside.write_text("exit 0\n");check.symlink_to(outside)
        self.blocked("ForgeValidate")
        self.assertFalse(self.forge_calls.exists())

    def test_blocked_plan_copy_cannot_follow_a_symlink(self):
        (self.host/".ai/hgt_plan.md").write_text("fictional handoff")
        self.f.git(self.host,"switch","-qc","hgt/feature-1")
        outside=self.f.base/"outside-plans";outside.mkdir()
        (self.host/".ai/hgt_blocked").symlink_to(outside,target_is_directory=True)
        self.blocked("MarkBlocked")
        self.assertEqual(list(outside.iterdir()),[])
        self.assertIn("feature-1\ta\tnew",self.ledger.read_text())

    def test_invalid_infrastructure_has_explicit_stop_routes(self):
        text=(ROOT/"pipelines/hgt.dot").read_text()
        for node in NODES:
            with self.subTest(node=node):
                self.assertRegex(text,node+r' -> exit\s*\[condition="context.tool.last_line=blocked"\]')

if __name__=="__main__":unittest.main()
