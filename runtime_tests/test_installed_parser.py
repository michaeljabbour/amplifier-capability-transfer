"""Required native-runtime regressions: use a host-supplied Amplifier environment.

No fallback parser or string repair is used. Missing loop-pipeline is a missing
native test prerequisite, not a skipped success. Fixtures are temporary/fictional.
"""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import unittest

from amplifier_module_loop_pipeline.dot_parser import parse_dot

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import test_branch_setup as branch_fixtures
import test_verifier_guards as verifier_fixtures
import test_control_lifecycle as control_fixtures


def commands(name):
    graph=parse_dot((ROOT/'pipelines'/name).read_text())
    return {node.id:node.attrs['tool_command'] for node in graph.nodes.values() if node.attrs.get('tool_command')}


def python_payloads(command):
    lexer=shlex.shlex(command,posix=True,punctuation_chars=';&|()')
    lexer.whitespace_split=True
    lexer.commenters=''
    tokens=list(lexer)
    return [tokens[i+2] for i,word in enumerate(tokens[:-2]) if word=='python3' and tokens[i+1]=='-c']


class InstalledParserTests(unittest.TestCase):
    def branch_fixture(self):
        fixture=branch_fixtures.BranchSetupTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def verifier_fixture(self):
        fixture=verifier_fixtures.VerifierGuardTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def run_actual(self,command,cwd,env):
        result=subprocess.run(['bash','-c',command],cwd=cwd,env=env,text=True,capture_output=True,timeout=15)
        self.assertNotIn('SyntaxError',result.stderr)
        self.assertEqual(result.returncode,0,result.stderr)
        return result

    def test_every_actual_parsed_python_payload_compiles_without_repair(self):
        count=0
        for graph in ['hgt.dot','verify.dot']:
            for node,command in commands(graph).items():
                for payload in python_payloads(command):
                    with self.subTest(graph=graph,node=node):
                        compile(payload,graph+':'+node,'exec')
                        count+=1
        self.assertEqual(count,20)

    def test_actual_checkledger_accepts_valid_and_blocks_missing_input(self):
        fixture=self.branch_fixture();command=commands('hgt.dot')['CheckLedger']
        self.assertEqual(self.run_actual(command,fixture.base,fixture.env).stdout,'process')
        (fixture.a/'pipelines/fixture-ledger.tsv').unlink()
        result=self.run_actual(command,fixture.base,fixture.env)
        self.assertEqual(result.stdout,'blocked')
        self.assertIn('required pipeline input missing',result.stderr)

    def test_actual_retry_keeps_exact_digit_newline_and_budget_gates(self):
        fixture=self.branch_fixture();command=commands('hgt.dot')['RetryGate']
        counter=fixture.a/'.ai/hgt_retries'
        for text in ['0','0\n','1','1\n','2','2\n','3','3\n']:
            with self.subTest(valid=text):
                counter.write_text(text)
                result=self.run_actual(command,fixture.base,fixture.env)
                self.assertEqual(result.stdout,'retry' if text[0] in '01' else 'giveup')
                self.assertEqual(counter.read_text(),str(int(text[0])+1)+'\n' if text[0] in '012' else text)
        for text in ['', '4', '-1', '00', '01', '1\n\n', '1 ', ' 1', '1\t', '3x', '１']:
            with self.subTest(invalid=text):
                counter.write_text(text)
                self.assertEqual(self.run_actual(command,fixture.base,fixture.env).stdout,'blocked')
                self.assertEqual(counter.read_text(),text)

    def test_actual_unit_and_fake_forge_status_writer_keeps_one_final_lf(self):
        fixture=self.branch_fixture();parsed=commands('hgt.dot')
        ci=fixture.a/'ci';ci.mkdir();gate=ci/'gate.sh';gate.write_text('#!/bin/sh\nprintf "authored fixture\\n"\n');gate.chmod(0o755)
        for node,stage in [('UnitValidate','unit'),('ForgeValidate','forge')]:
            with self.subTest(node=node):
                (fixture.a/'.ai/hgt_forge_check.sh').write_text('exit 0\n')
                result=self.run_actual(parsed[node],fixture.base,fixture.env)
                self.assertEqual(result.stdout,'pass',result.stderr)
                raw=(fixture.a/'.ai/hgt_validation.json').read_bytes()
                self.assertTrue(raw.endswith(b'\n'))
                self.assertFalse(raw.endswith(b'\n\n'))
                record=json.loads(raw)
                self.assertEqual((record['slug'],record['target'],record['stage'],record['result']),('feature-1','a',stage,'pass'))

    def test_actual_verifier_roundtrip_and_duplicate_state_refusal(self):
        fixture=self.verifier_fixture();parsed=commands('verify.dot')
        self.assertEqual(self.run_actual(parsed['CheckQueue'],fixture.host,fixture.env).stdout,'process')
        self.assertEqual(self.run_actual(parsed['SelectRow'],fixture.host,fixture.env).stdout,'ready')
        self.assertEqual(fixture.state.read_text(),'SLUG=pause\nTARGET=a\n')
        fixture.state.write_text('SLUG=\nSLUG=pause\nTARGET=a\n')
        result=self.run_actual(parsed['MarkVerified'],fixture.host,fixture.env)
        self.assertEqual(result.stdout,'blocked')
        self.assertIn('invalid or duplicate state field',result.stderr)
        self.assertFalse(fixture.calls.exists())

    def test_actual_parsed_commit_refuses_native_control_rename(self):
        factory=control_fixtures.ControlLifecycleTests()
        fixture,controls=factory.fixture(True,False)
        self.addCleanup(fixture.doCleanups)
        fixture.git(fixture.a,'switch','-qc','hgt/feature-1')
        helper=fixture.a/'pipelines/ledger.py';content=helper.read_bytes()
        fixture.git(fixture.a,'mv','pipelines/ledger.py','app_helper.py');helper.write_bytes(content)
        before=fixture.git(fixture.a,'diff','--cached','--name-status')
        result=self.run_actual(commands('hgt.dot')['Commit'],fixture.base,fixture.env)
        self.assertEqual(result.stdout,'blocked')
        self.assertIn('staged metadata or control files refused',result.stderr)
        self.assertEqual(fixture.git(fixture.a,'diff','--cached','--name-status'),before)
        self.assertEqual(fixture.mutations(),[])

if __name__=='__main__':unittest.main()
