import json
import statistics
from collections import Counter,defaultdict
from pathlib import Path
from metrics import pass_metrics,wilson
def save(path,value):
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def records():
    return [json.loads(line) for line in Path('results.jsonl').read_text(encoding='utf-8').splitlines()]

def costs(rows):
    return {key:{'mean':statistics.mean(r[key] for r in rows),'median':statistics.median(r[key] for r in rows),
                 'min':min(r[key] for r in rows),'max':max(r[key] for r in rows)} if rows else None
            for key in ['model_calls','tool_calls','input_tokens','output_tokens','seconds']}

def canonical(event):
    if event['kind']=='model':
        response=event['response']
        return {'kind':'model','content':response.get('content'),
                'calls':[{'name':c['function']['name'],'arguments':c['function']['arguments']} for c in response.get('tool_calls',[])]}
    if event['kind']=='tool':
        return {k:event.get(k) for k in ['kind','name','arguments','output','error']}
    return None

def divergence(a,b):
    first=json.loads(Path(a['trace']).read_text(encoding='utf-8'))['events']
    second=json.loads(Path(b['trace']).read_text(encoding='utf-8'))['events']
    first=[e for e in first if canonical(e) is not None]
    second=[e for e in second if canonical(e) is not None]
    for i in range(max(len(first),len(second))):
        x=first[i] if i<len(first) else None;y=second[i] if i<len(second) else None
        if x is None or y is None or canonical(x)!=canonical(y):
            return {'event_number':i+1,'first':x,'second':y,'traces':[a['trace'],b['trace']]}
    return None

def analyze():
    rows=records()
    assert len(rows)==336 and len({r['key'] for r in rows})==336
    manifest=json.loads(Path('manifest.json').read_text(encoding='utf-8'))
    lookup={(t['suite'],t['id']):t for t in manifest['tasks']}
    base={r['task']:r for r in rows if r['configuration']=='t0' and r['run']==0}
    second={r['task']:r for r in rows if r['configuration']=='t0' and r['run']==1}
    differences=[i for i in base if base[i]['utility']!=second[i]['utility']]
    trace_difference=next(({'task':i,**d} for i in base if (d:=divergence(base[i],second[i]))),None)
    samples=defaultdict(list)
    for r in rows:
        if r['configuration']=='t07':samples[r['task']].append(r)
    counts={i:sum(r['utility'] for r in group) for i,group in samples.items()}
    unstable=[i for i,c in counts.items() if 0<c<5]
    curves={}
    for group in ['all','single','multi']:
        ids=[i for i in samples if group=='all' or (lookup['workspace',i]['ground_truth_calls']==1)==(group=='single')]
        curves[group]=[]
        for k in range(1,6):
            metrics=[pass_metrics(5,counts[i],k) for i in ids]
            curves[group].append({'k':k,'n':len(ids),**{key:statistics.mean(v[key] for v in metrics) for key in ['pass_all','pass_any']}})
    stability={'t0_successes':[sum(r['utility'] for r in values.values()) for values in [base,second]],
               'different_tasks_t0':differences,'unstable_tasks':unstable,'unstable_fraction':len(unstable)/30,
               'sample_success_counts':counts,'curves':curves,
               't0_first_trace_difference':trace_difference,
               't0_first_difference':divergence(base[differences[0]],second[differences[0]]) if differences else None}
    if unstable:
        chosen=unstable[0];group=sorted(samples[chosen],key=lambda r:r['run'])
        stability['unstable_example']={'task':chosen,'runs':group,
            'cost_success':costs([r for r in group if r['utility']]),'cost_failure':costs([r for r in group if not r['utility']])}
    faults={}
    for policy in ['P0','P1','P2']:
        group=[r for r in rows if r['configuration']=='fault_'+policy]
        faults[policy]={'successes':sum(r['utility'] for r in group),'n':30,
                       'injected_faults':sum(len(r['faults']) for r in group),
                       'fault_types':dict(Counter(a['fault'] for r in group for a in r['faults'])),
                       'extra_model_calls':sum(r['model_calls']-base[r['task']]['model_calls'] for r in group),
                       'extra_tool_calls':sum(r['tool_calls']-base[r['task']]['tool_calls'] for r in group),
                       'duplicate_writes':sum(r['duplicate_writes'] for r in group),
                       'lost':[r['task'] for r in group if base[r['task']]['utility'] and not r['utility']],
                       'gained':[r['task'] for r in group if not base[r['task']]['utility'] and r['utility']],
                       'costs':costs(group)}
    banking=[r for r in rows if r['suite']=='banking']
    transfer={}
    for name,group in [('workspace',list(base.values())),('banking',banking)]:
        success=sum(r['utility'] for r in group)
        transfer[name]={'successes':success,'n':len(group),'rate':success/len(group),'wilson':wilson(success,len(group))}
    cases={}
    cases['duplicate_P1']=next((r for r in rows if r['configuration']=='fault_P1' and r['duplicate_writes']),None)
    cases['recovered_P0']=next((r for r in rows if r['configuration']=='fault_P0' and r['faults'] and r['utility']),None)
    cases['banking_failures']=[r for r in banking if not r['utility']][:2]
    q7={}
    for probability in [.2,.5]:
        group=[r for r in rows if r['configuration']==f'dev_P2_p{probability}']
        assert len(group)==10
        q7[str(probability)]={'successes':sum(r['utility'] for r in group),'n':10,
                             'model_calls':sum(r['model_calls'] for r in group),'tool_calls':sum(r['tool_calls'] for r in group),
                             'faults':sum(len(r['faults']) for r in group)}
    summary={'stability':stability,'faults':faults,'transfer':transfer,'cases':cases,'question7':q7,
             'baseline_costs':costs(list(base.values()))}
    save('analysis/summary.json',summary)
    # Fixed selection by recorded order, stratified by suite and benchmark verdict.
    positives=[r for r in rows if r['suite']=='workspace' and r['configuration']=='t0' and r['run']==0 and r['utility']]
    bank_positive=[r for r in banking if r['utility']]
    selected=positives[:5]+bank_positive[:5]
    used={r['key'] for r in selected}
    selected.extend(r for r in positives+bank_positive if r['key'] not in used and len(selected)<10)
    negatives=[r for r in rows if r['configuration']=='t0' and r['run']==0 and not r['utility']]
    bank_negative=[r for r in banking if not r['utility']]
    selected.extend(negatives[:3]+bank_negative[:2])
    assert len(selected)==15 and sum(r['utility'] for r in selected)==10
    save('analysis/audit_candidates.json',[{'key':r['key'],'suite':r['suite'],'task':r['task'],
                                           'prompt':lookup[r['suite'],r['task']]['prompt'],'benchmark':r['utility'],
                                           'answer':r['answer'],'trace':r['trace'],'writes':r['writes']} for r in selected])
    save('analysis/verification.json',{'episodes':336,'main_episodes':316,'debug_episodes':20,
            'model_calls':sum(r['model_calls'] for r in rows),'max_tools':max(r['tool_calls'] for r in rows),
            'duplicates_in_keys':False,'reasons':dict(Counter(r['reason'] for r in rows))})
    assert all(r['model_calls']<=15 and r['tool_calls']<=15 and r['answer'] for r in rows)
    print('Analysis ready. Review analysis/audit_candidates.json.')
    return summary

def plots(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.7),layout='constrained')
    for ax,(group,values) in zip(axes,summary['stability']['curves'].items()):
        for key,label in [('pass_all','pass^k: все успешны'),('pass_any','pass@k: хотя бы один')]:
            ax.plot([v['k'] for v in values],[100*v[key] for v in values],'o-',label=label)
        ax.set(title={'all':'Все 30 задач','single':'Один эталонный вызов','multi':'Несколько вызовов'}[group],
               xlabel='Число повторов k',ylabel='Доля, %',xticks=range(1,6),ylim=(0,105))
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.savefig('analysis/stability.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(9,3.7),layout='constrained')
    items=[('Без сбоев',summary['transfer']['workspace']['rate'])]+[(p,v['successes']/30) for p,v in summary['faults'].items()]
    bars=axes[0].bar([i[0] for i in items],[100*i[1] for i in items],color=['#64748b','#2563eb','#b45309','#15956b'])
    axes[0].bar_label(bars,fmt='%.1f',padding=3)
    axes[0].set(title='Сбои: успешность',ylabel='%',ylim=(0,110))
    for j,(name,v) in enumerate(summary['transfer'].items()):
        low,high=v['wilson']
        axes[1].errorbar(j,100*v['rate'],yerr=[[100*(v['rate']-low)],[100*(high-v['rate'])]],fmt='o',capsize=6,label=name)
    axes[1].set(title='Перенос: 95% интервал Уилсона',xticks=[0,1],xticklabels=['workspace','banking'],ylim=(0,100),ylabel='%')
    fig.savefig('analysis/faults_transfer.png',dpi=170);plt.close(fig)

if __name__=='__main__':
    value=analyze()
    plots(value)
