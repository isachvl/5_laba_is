"""Validate complete LR5 measurements without rerunning the model."""
import hashlib,json
from pathlib import Path
from collections import Counter
from metrics import pass_metrics,wilson

def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]

def main():
    frozen=json.loads(Path('frozen.json').read_text())
    for path,digest in frozen['hashes'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
    result=rows('results.jsonl')
    assert len(result)==336 and len({r['key'] for r in result})==336
    schedule=json.loads(Path('schedule.json').read_text())
    assert len(schedule)==336
    assert Counter((r['suite'],r['configuration']) for r in result)==Counter((r['suite'],r['configuration']) for r in schedule)
    for row in result:
        trace=json.loads(Path(row['trace']).read_text(encoding='utf-8'))
        assert trace['utility']==row['utility']
        assert trace['episode']['seed']==row['seed']
        assert row['answer'] and row['model_calls']<=15 and row['tool_calls']<=15
        model=[e for e in trace['events'] if e['kind']=='model']
        assert sum(e['usage']['prompt_tokens'] for e in model)==row['input_tokens']
        assert sum(e['usage']['completion_tokens'] for e in model)==row['output_tokens']
        assert all(e['usage']['prompt_tokens']+1024<=16384 for e in model)
        log=trace['runtime_log']
        assert [a['number'] for a in log]==list(range(1,len(log)+1))
        assert row['tool_calls']>=len(log)
        assert row['faults']==[a for a in log if a['fault']]
        assert not any(a['fault']=='A' and a['executed'] for a in log)
        assert not any(a['fault']=='B' and not (a['executed'] and a['state_changing']) for a in log)
    assert pass_metrics(5,3,2)=={'pass_all':.3,'pass_any':.9}
    assert .38<wilson(10,16)[0]<.40
    print('PASS: 336 unique complete episodes; frozen configuration, budgets, token totals and fault journals match.')

if __name__=='__main__':main()
