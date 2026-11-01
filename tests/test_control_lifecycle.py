"""Native Git control-plane lifecycle; push and PR are authored fixture stubs."""
import subprocess
from pathlib import Path
import unittest
import test_branch_setup as fixtures

class ControlLifecycleTests(unittest.TestCase):
    def fixture(self,tracked,ignored):
        f=fixtures.BranchSetupTests();f.setUp()
        controls=['pipelines/fixture-ledger.tsv','pipelines/ledger.py']
        if not tracked:
            f.git(f.a,'rm','--cached','--',*controls)
            f.git(f.a,'commit','-qm','fictional external controls')
        if ignored:
            (f.a/'.gitignore').write_text('pipelines/\n')
            f.git(f.a,'add','.gitignore');f.git(f.a,'commit','-qm','fictional control ignore')
        gh=f.base/'bin/gh';gh.write_text('#!/bin/sh\nprintf "fictional PR receipt\\n"\n');gh.chmod(0o755)
        return f,controls

    def test_controls_survive_stash_commit_and_main_checkout_without_app_tree_changes(self):
        for tracked in [True,False]:
            for ignored in [True,False]:
                with self.subTest(tracked=tracked,ignored=ignored):
                    f,controls=self.fixture(tracked,ignored)
                    try:
                        base=f.git(f.a,'rev-parse','HEAD')
                        before={name:f.git(f.a,'rev-parse',base+':'+name) if tracked else None for name in controls}
                        ledger=f.a/controls[0];helper=f.a/controls[1]
                        ledger.write_text('feature-1\ta\timplemented\nfeature-2\ta\tnew\nfeature-3\ta\tnew\n')
                        helper.write_text(helper.read_text()+'\n# fictional local control update\n')
                        helper_bytes=helper.read_bytes()
                        f.state.write_text('SLUG=feature-2\nTARGET=a\n')
                        (f.a/'f').write_text('previous unrelated work')
                        setup=f.run_setup();self.assertEqual(setup.stdout,'ready',setup.stderr)
                        self.assertEqual((f.a/'f').read_text(),'base\n')
                        self.assertEqual(helper.read_bytes(),helper_bytes)
                        (f.a/'f').write_text('application feature2')
                        result=subprocess.run(['bash','-c',f.node_command('Commit')],cwd=f.base,env=f.env,text=True,capture_output=True,timeout=20)
                        self.assertEqual(result.stdout,'next',result.stderr)
                        self.assertEqual(f.git(f.a,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines(),['f'])
                        for name in controls:
                            if tracked:self.assertEqual(f.git(f.a,'rev-parse','HEAD:'+name),before[name])
                            else:self.assertEqual(f.git(f.a,'ls-tree','--name-only','HEAD','--',name),'')
                        expected='feature-1\ta\timplemented\nfeature-2\ta\timplemented\nfeature-3\ta\tnew\n'
                        self.assertEqual(ledger.read_text(),expected)
                        checkout=subprocess.run([fixtures.REAL_GIT,'-c','core.fsmonitor=false','-C',str(f.a),'checkout','-q','main'],text=True,capture_output=True,timeout=10)
                        self.assertEqual(checkout.returncode,0,checkout.stderr)
                        self.assertEqual(ledger.read_text(),expected)
                        self.assertEqual(helper.read_bytes(),helper_bytes)
                        self.assertEqual(f.git(f.a,'diff','--cached','--name-only'),'')
                        self.assertTrue(f.git(f.a,'stash','list'))
                    finally:f.doCleanups()

    def test_staged_primary_controls_are_refused_without_unstaging(self):
        for name in ['pipelines/fixture-ledger.tsv','pipelines/ledger.py']:
            with self.subTest(name=name):
                f,controls=self.fixture(True,False)
                try:
                    f.git(f.a,'switch','-qc','hgt/feature-1')
                    path=f.a/name
                    if name.endswith('.tsv'):path.write_text('feature-1\ta\tnew\nfeature-2\ta\tnew\n')
                    else:path.write_text(path.read_text()+'\n# fictional staged control update\n')
                    f.git(f.a,'add','--',name)
                    before=f.git(f.a,'diff','--cached','--name-status')
                    result=subprocess.run(['bash','-c',f.node_command('Commit')],cwd=f.base,env=f.env,text=True,capture_output=True,timeout=20)
                    self.assertEqual(result.stdout,'blocked',result.stderr)
                    self.assertEqual(f.git(f.a,'diff','--cached','--name-status'),before)
                    self.assertEqual(f.mutations(),[])
                finally:f.doCleanups()

    def test_staged_control_rename_is_refused_even_with_restored_runtime_helper(self):
        f,controls=self.fixture(True,False)
        try:
            f.git(f.a,'switch','-qc','hgt/feature-1')
            helper=f.a/'pipelines/ledger.py'
            content=helper.read_bytes()
            f.git(f.a,'mv','pipelines/ledger.py','app_helper.py')
            helper.write_bytes(content)
            before=f.git(f.a,'diff','--cached','--name-status')
            self.assertIn('pipelines/ledger.py',before)
            result=subprocess.run(['bash','-c',f.node_command('Commit')],cwd=f.base,env=f.env,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.stdout,'blocked',result.stderr)
            self.assertEqual(f.git(f.a,'diff','--cached','--name-status'),before)
            self.assertEqual(f.mutations(),[])
        finally:f.doCleanups()

if __name__=='__main__':unittest.main()
