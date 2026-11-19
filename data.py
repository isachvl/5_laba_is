import hashlib
import importlib.metadata
import json
from pathlib import Path
from agentdojo.task_suite.load_suites import get_suites

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
    config=json.loads(Path('config.json').read_text())
    old=json.loads(Path('lr4_reference/frozen.json').read_text())
    assert hashlib.sha256(Path('base_agent.py').read_bytes()).hexdigest()==old['hashes']['agent.py']
    for p in Path('prompts').glob('*.txt'):
        assert hashlib.sha256(p.read_bytes()).hexdigest()==old['hashes'][str(p)]
    reference=json.loads(Path('lr4_reference/manifest.json').read_text())
    suites=get_suites(config['benchmark'])
    records=[]
    for suite_name in ('workspace','banking'):
        suite=suites[suite_name]
        writes=set(config[suite_name+'_write_tools'])
        assert writes<=set(f.name for f in suite.tools)
        for key,task in suite.user_tasks.items():
            env=task.init_environment(suite.load_and_inject_default_environment({}))
            records.append({'suite':suite_name,'id':key,'prompt':task.PROMPT,'ground_truth_calls':len(task.ground_truth(env)),
                            'difficulty':str(task.DIFFICULTY)})
    ids={'workspace_main':reference['task_ids']['main'],'workspace_dev':reference['task_ids']['dev'],
         'banking':sorted(suites['banking'].user_tasks,key=lambda i:int(i.split('_')[-1]))}
    manifest={'agentdojo':importlib.metadata.version('agentdojo'),'benchmark':config['benchmark'],'ids':ids,
              'task_list_sha256':hashlib.sha256(json.dumps(ids,sort_keys=True).encode()).hexdigest(),
              'tasks':records,'source_lr4':old,
              'tools':{name:[{'name':f.name,'description':f.description,'parameters':f.parameters.model_json_schema()} for f in suites[name].tools]
                       for name in ('workspace','banking')}}
    save('manifest.json',manifest)
    return manifest
if __name__=='__main__':prepare()
