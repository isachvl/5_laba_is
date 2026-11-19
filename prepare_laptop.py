"""Restore the saved LR5 measurements and traces in local MLflow."""
import json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    os.chdir(ROOT)
    import mlflow
    from mlflow.tracking import MlflowClient
    records=[json.loads(line) for line in Path('results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(records)==336
    mlflow.set_tracking_uri('sqlite:///'+(ROOT/'mlflow.db').as_posix())
    mlflow.set_experiment('lr5')
    client=MlflowClient()
    exp=mlflow.get_experiment_by_name('lr5')
    groups={}
    for row in records:
        name=row['configuration']+(f"_r{row['run']}" if row['configuration']=='t0' else '')
        groups.setdefault(name,[]).append(row)
    for name,group in groups.items():
        prior=client.search_runs([exp.experiment_id],filter_string=f"tags.configuration = '{name}'")
        with mlflow.start_run(run_id=prior[0].info.run_id if prior else None,run_name=name):
            mlflow.set_tag('configuration',name)
            mlflow.log_params({k:group[0][k] for k in ['suite','temperature','policy','fault_p']})
            metrics={'success':sum(r['utility'] for r in group)/len(group),
                     'mean_input_tokens':sum(r['input_tokens'] for r in group)/len(group),
                     'duplicate_writes':sum(r['duplicate_writes'] for r in group)}
            old=prior[0].data.metrics if prior else {}
            pending={k:v for k,v in metrics.items() if old.get(k)!=v}
            if pending:mlflow.log_metrics(pending)
            for row in group:mlflow.log_artifact(row['trace'],'traces')
            if name=='t0_r0':
                for path in Path('analysis').glob('*'):
                    if path.is_file():mlflow.log_artifact(str(path),'analysis')
                if Path('report.pdf').exists():mlflow.log_artifact('report.pdf','report')
    print('MLflow ready: lr5, three metric names; plots and traces in Artifacts.')

if __name__=='__main__':main()
