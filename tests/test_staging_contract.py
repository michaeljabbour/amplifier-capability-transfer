"""Execute the graph's actual staging argv with native Git in owned repositories."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
GIT=shutil.which('git')

class NativeStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)
        self.env={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,'HOST_A_PATH':str(self.repo),'LEDGER_FILE':'pipelines/queue.tsv'}
        self.git('init','-q','-b','main')
        self.git('config','user.name','Fixture')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgsign','false')
        for relative,text in [('change.txt','before'),('delete.txt','delete me'),('.ai/tracked.txt','legacy metadata'),('nested/.ai/tracked.txt','legacy nested metadata')]:
            self.write(relative,text)
        self.git('add','--','change.txt','delete.txt','.ai/tracked.txt','nested/.ai/tracked.txt')
        self.git('commit','-qm','fictional baseline')

    def write(self,relative,text):
        p=self.repo/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)

    def git(self,*args,check=True):
        p=subprocess.run([GIT,'-c','core.fsmonitor=false',*args],cwd=self.repo,env=self.env,text=True,capture_output=True,timeout=10)
        if check:self.assertEqual(p.returncode,0,p.stderr)
        return p

    def run_stage(self):
        text=(ROOT/'pipelines/hgt.dot').read_text()
        command=json.loads(re.search(r'Commit \[shape=parallelogram,\s*tool_command=("(?:\\.|[^"\\])*")',text).group(1))
        function=re.search(r'stage_host\(\)\{.*?; \};',command,re.S).group(0)
        return subprocess.run(['bash','-c',function+' stage_host "$PWD"'],cwd=self.repo,
            env=self.env,capture_output=True,text=True,timeout=10)

    def run_stash(self,ledger='pipelines/queue.tsv'):
        text=(ROOT/'pipelines/hgt.dot').read_text()
        command=json.loads(re.search(r'BranchSetup \[shape=parallelogram,\s*tool_command=("(?:\\.|[^"\\])*")',text).group(1))
        function=re.search(r'stash_host\(\)\{.*?; \};',command,re.S).group(0)
        return subprocess.run(['bash','-c',function+' stash_host "$PWD" primary'],cwd=self.repo,
            env={**self.env,'LEDGER_FILE':ledger},capture_output=True,text=True,timeout=10)

    def assert_stash_preserves_metadata(self,ignored):
        if ignored:
            self.write('.gitignore','.ai/\n')
            self.git('add','.gitignore');self.git('commit','-qm','fictional ignore')
        metadata=['.ai/tracked.txt','nested/.ai/tracked.txt','.ai/new.txt','nested/.ai/new.txt','nested/as-file/.ai']
        for name in metadata:self.write(name,'preserve metadata')
        self.write('pipelines/queue.tsv','preserve queue')
        self.write('pipelines/ledger.py','preserve helper')
        self.write('change.txt','changed work');self.write('new.txt','new work')
        (self.repo/'delete.txt').unlink()
        result=self.run_stash()
        self.assertEqual(result.returncode,0,result.stderr)
        for name in metadata:self.assertEqual((self.repo/name).read_text(),'preserve metadata')
        self.assertEqual((self.repo/'change.txt').read_text(),'before')
        self.assertFalse((self.repo/'new.txt').exists())
        self.assertTrue((self.repo/'delete.txt').exists())
        names=self.git('stash','show','--name-only','--include-untracked').stdout.splitlines()
        self.assertEqual(set(names),{'change.txt','new.txt','delete.txt'})

    def test_stash_preserves_control_files_tracked_or_ignored_without_pathspec_errors(self):
        for tracked in [False,True]:
            for ignored in [False,True]:
                with self.subTest(tracked=tracked,ignored=ignored):
                    fixture=NativeStagingTests();fixture.setUp()
                    try:
                        for name in ['pipelines/queue[1].tsv','pipelines/ledger.py']:fixture.write(name,'initial')
                        if tracked:fixture.git('add','pipelines');fixture.git('commit','-qm','fictional controls')
                        if ignored:
                            fixture.write('.gitignore','pipelines/*\n')
                            fixture.git('add','.gitignore');fixture.git('commit','-qm','fictional ignore')
                        for name in ['pipelines/queue[1].tsv','pipelines/ledger.py']:fixture.write(name,'preserve controls')
                        fixture.write('change.txt','ordinary change')
                        result=fixture.run_stash('pipelines/queue[1].tsv')
                        self.assertEqual(result.returncode,0,result.stderr)
                        for name in ['pipelines/queue[1].tsv','pipelines/ledger.py']:self.assertEqual((fixture.repo/name).read_text(),'preserve controls')
                        self.assertEqual((fixture.repo/'change.txt').read_text(),'before')
                    finally:fixture.doCleanups()

    def test_stash_handles_ignored_metadata_and_preserves_work(self):
        self.assert_stash_preserves_metadata(True)

    def test_stash_preserves_unignored_root_and_nested_metadata(self):
        self.assert_stash_preserves_metadata(False)

    def assert_staging(self,ignored):
        if ignored:
            self.write('.gitignore','.ai/\n')
            self.git('add','--','.gitignore')
            self.git('commit','-qm','fictional metadata ignore')
        for relative,text in [('change.txt','after'),('new.txt','new work'),('nested/normal.txt','nested work'),('.ai/tracked.txt','changed legacy metadata'),('nested/.ai/tracked.txt','changed nested metadata'),('.ai/new.txt','private fixture'),('nested/.ai/new.txt','private nested fixture'),('cache.pyc','bytecode'),('nested/cache.pyc','nested bytecode'),('__pycache__/cache.bin','cache'),('nested/__pycache__/cache.bin','nested cache')]:
            self.write(relative,text)
        (self.repo/'delete.txt').unlink()
        p=self.run_stage()
        self.assertEqual(p.returncode,0,p.stderr)
        staged=self.git('diff','--cached','--name-status').stdout.splitlines()
        actual={line.split('\t',1)[1]:line.split('\t',1)[0] for line in staged}
        self.assertEqual(actual,{'change.txt':'M','delete.txt':'D','new.txt':'A','nested/normal.txt':'A'})
        self.assertEqual((self.repo/'.ai/new.txt').read_text(),'private fixture')
        self.assertEqual((self.repo/'nested/.ai/new.txt').read_text(),'private nested fixture')

    def test_ignored_metadata_does_not_error_or_enter_index(self):
        self.assert_staging(True)

    def test_unignored_and_nested_metadata_do_not_enter_index(self):
        self.assert_staging(False)

    def test_metadata_file_and_symlink_nodes_do_not_enter_index(self):
        self.write('new.txt','ordinary work')
        self.write('nested/as-file/.ai','private fixture')
        self.write('nested/cache-as-file/__pycache__','cache fixture')
        link=self.repo/'nested/as-link/.ai';link.parent.mkdir(parents=True)
        link.symlink_to('/fictional-private-location')
        result=self.run_stage()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.git('diff','--cached','--name-only').stdout.splitlines(),['new.txt'])

if __name__=='__main__':unittest.main()
