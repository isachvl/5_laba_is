import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from agentdojo.task_suite.load_suites import get_suites
from agentdojo.functions_runtime import FunctionsRuntime
from agent import PolicyRuntime
from faults import FaultyRuntime
from reference_checks import GroundTruthAgent

CONFIG=json.loads(Path('config.json').read_text())
SUITE=get_suites('v1.2.2')['workspace']
WRITES=CONFIG['workspace_write_tools']

def controller(runtime,policy):
    agent=SimpleNamespace(policy=policy,trace={'tool_calls':1},config={'max_tools':15},record=lambda event:None)
    return PolicyRuntime(runtime,agent)

class Checks(unittest.TestCase):
    def test_one_guaranteed_error_then_recovery(self):
        runtime=FaultyRuntime(SUITE.tools,'test',1,WRITES,forced={1:'A'})
        result,error=controller(runtime,'P2').run_function(SUITE.load_and_inject_default_environment({}),'get_sent_emails',{})
        self.assertIsNone(error)
        self.assertEqual(len(runtime.log),2)
        self.assertEqual([r['fault'] for r in runtime.log],['A',None])
        self.assertFalse(runtime.log[0]['executed'])
        self.assertTrue(runtime.log[1]['executed'])

    def test_permanent_error(self):
        runtime=FaultyRuntime(SUITE.tools,'test',1,WRITES)
        result,error=controller(runtime,'P2').run_function(SUITE.load_and_inject_default_environment({}),'get_sent_emails',{})
        self.assertIn('TemporaryError',error)
        self.assertEqual(len(runtime.log),3)
        self.assertFalse(any(r['executed'] for r in runtime.log))

    def test_lost_response_duplicates(self):
        counts={}
        for policy in ('P1','P2'):
            env=SUITE.load_and_inject_default_environment({})
            normal=FunctionsRuntime(SUITE.tools)
            before=len(normal.run_function(env,'get_sent_emails',{})[0])
            runtime=FaultyRuntime(SUITE.tools,'test',1,WRITES,forced={1:'B'})
            controller(runtime,policy).run_function(env,'send_email',{'recipients':['client@example.com'],'subject':'Controlled test','body':'Test'})
            counts[policy]=len(normal.run_function(env,'get_sent_emails',{})[0])-before
        self.assertEqual(counts,{'P1':2,'P2':1})

    def test_zero_fault_matches_lr4(self):
        result={}
        for key,task in SUITE.user_tasks.items():
            factory=lambda functions:FaultyRuntime(functions,key,0,WRITES)
            result[key]=bool(SUITE.run_task_with_pipeline(GroundTruthAgent(task),task,None,{},runtime_class=factory)[0])
        expected=json.loads(Path('lr4_reference/ground_truth.json').read_text(encoding='utf-8'))
        self.assertEqual(result,expected)
        self.assertEqual(sum(result.values()),36)

    def test_same_schedule(self):
        a=FaultyRuntime(SUITE.tools,'user_task_1',.2,WRITES)
        b=FaultyRuntime(SUITE.tools,'user_task_1',.2,WRITES)
        for runtime in (a,b):
            env=SUITE.load_and_inject_default_environment({})
            for _ in range(5):runtime.run_function(env,'get_sent_emails',{})
        self.assertEqual([r['random_draw'] for r in a.log],[r['random_draw'] for r in b.log])

if __name__=='__main__':unittest.main()
