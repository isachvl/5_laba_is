import argparse
from collections import Counter
from functools import partial
import hashlib
import json
from pathlib import Path
import time
from agentdojo.task_suite.load_suites import get_suites
from agent import Agent
from faults import FaultyRuntime
from data import save

def jobs(manifest):
    tasks=manifest['ids']['workspace_main']
    result=[]
    for repeat in range(2):
        for task in tasks:
            result.append(dict(suite='workspace',task=task,configuration='t0',run=repeat,seed=42,temperature=0,fault_p=0,policy='P0'))
    for repeat in range(5):
        for task in tasks:
            result.append(dict(suite='workspace',task=task,configuration='t07',run=repeat,seed=100+repeat,temperature=.7,fault_p=0,policy='P0'))
    for task in tasks:
        for policy in ('P0','P1','P2'):
            result.append(dict(suite='workspace',task=task,configuration='fault_'+policy,run=0,seed=42,temperature=0,fault_p=.2,policy=policy))
    for task in manifest['ids']['banking']:
        result.append(dict(suite='banking',task=task,configuration='transfer',run=0,seed=42,temperature=0,fault_p=0,policy='P0'))
    for p in (.2,.5):
        for task in manifest['ids']['workspace_dev']:
            result.append(dict(suite='workspace',task=task,configuration=f'dev_P2_p{p}',run=0,seed=42,temperature=0,fault_p=p,policy='P2'))
    return result

def key(job):
    return f"{job['suite']}__{job['task']}__{job['configuration']}__r{job['run']}__s{job['seed']}"

def run():
    config=json.loads(Path('config.json').read_text())
    manifest=json.loads(Path('manifest.json').read_text(encoding='utf-8'))
    frozen=json.loads(Path('frozen.json').read_text())
    for name,digest in frozen['hashes'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
    planned=jobs(manifest)
    save('schedule.json',planned)
    path=Path('results.jsonl')
    completed={r['key'] for r in map(json.loads,path.read_text(encoding='utf-8').splitlines())} if path.exists() else set()
    suites=get_suites(config['benchmark'])
    Path('traces').mkdir(exist_ok=True)
    for number,job in enumerate(planned,1):
        episode_key=key(job)
        if episode_key in completed:continue
        trace_path=Path('traces')/(episode_key+'.json')
        if trace_path.exists():
            raise RuntimeError('Partial episode requires review before retry: '+episode_key)
        agent=Agent(config,trace_path,job['policy'],job['temperature'],job['seed'])
        agent.trace.update(episode=job,key=episode_key)
        runtime_holder=[]
        def factory(functions):
            runtime=FaultyRuntime(functions,job['suite']+':'+job['task'],job['fault_p'],config[job['suite']+'_write_tools'],seed=job['seed'])
            runtime_holder.append(runtime)
            return runtime
        agent.save()
        started=time.perf_counter()
        evaluation_error=None
        try:
            success,_=suites[job['suite']].run_task_with_pipeline(agent,suites[job['suite']].get_user_task_by_id(job['task']),None,{},runtime_class=factory)
        except Exception as exc:
            success=False
            evaluation_error=repr(exc)
            agent.trace.update(reason='evaluation_error',evaluation_error=evaluation_error)
        finally:
            agent.client.close()
            agent.http.close()
        journal=[attempt for runtime in runtime_holder for attempt in runtime.log]
        writes=[a for a in journal if a['state_changing'] and a['executed']]
        counts=Counter((a['tool'],json.dumps(a['arguments'],sort_keys=True)) for a in writes)
        duplicates=sum(max(0,count-1) for count in counts.values())
        agent.trace.update(utility=bool(success),runtime_log=journal)
        agent.save()
        row={**job,'key':episode_key,'utility':bool(success),'reason':agent.trace['reason'],
             'model_calls':agent.trace['model_calls'],'tool_calls':agent.trace['tool_calls'],
             'input_tokens':agent.trace['input_tokens'],'output_tokens':agent.trace['output_tokens'],
             'seconds':agent.trace.get('seconds',time.perf_counter()-started),
             'faults':[a for a in journal if a['fault']],'writes':writes,'duplicate_writes':duplicates,
             'trace':str(trace_path),'answer':agent.trace.get('answer',''),'evaluation_error':evaluation_error}
        with path.open('a',encoding='utf-8') as output:
            output.write(json.dumps(row,ensure_ascii=False)+'\n')
            output.flush()
        print(number,len(planned),episode_key,success,row['reason'],flush=True)
if __name__=='__main__':run()
