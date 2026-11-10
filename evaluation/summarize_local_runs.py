#!/usr/bin/env python3
"""Aggregate *measured* anonymous browser-run stage timings for poster figures."""
from __future__ import annotations
import argparse
import json
import statistics
from pathlib import Path

STAGES=('profile','discovery','analyst','skeptic','clarification')

def percentile(values:list[float],percent:float)->float:
    if not values:
        raise ValueError('No measured values')
    ordered=sorted(values)
    rank=(len(ordered)-1)*percent/100
    lower=int(rank)
    upper=min(lower+1,len(ordered)-1)
    return ordered[lower]+(ordered[upper]-ordered[lower])*(rank-lower)

def summarize(files:list[Path])->dict:
    if not files:
        raise ValueError('At least one exported run-metrics JSON file is required')
    records=[]
    for path in files:
        run=json.loads(path.read_text(encoding='utf8'))
        if run.get('schema')!='clinicaltrial-matcher-metrics-v1':
            raise ValueError(f'{path}: not a recognized sanitized run-metrics export')
        stages=run.get('stages',[])
        if {x.get('agent') for x in stages}!=set(STAGES) or len(stages)!=len(STAGES):
            raise ValueError(f'{path}: incomplete stage telemetry')
        times={stage['agent']:float(stage['duration_ms']) for stage in stages}
        if any(t<0 or t>3600000 for t in times.values()):
            raise ValueError(f'{path}: implausible stage timing')
        records.append((run,times))
    by_stage={}
    for stage in STAGES:
        measurements=[r[1][stage]/1000 for r in records]
        by_stage[stage]={
            'median_seconds':round(statistics.median(measurements),2),
            'p95_seconds':round(percentile(measurements,95),2),
            'observations':len(measurements),
        }
    totals=[sum(times.values())/1000 for _,times in records]
    return {
        'source':'measured_anonymous_local_browser_exports',
        'run_count':len(records),
        'total_seconds':{
            'median':round(statistics.median(totals),2),
            'p95':round(percentile(totals,95),2),
        },
        'per_stage':by_stage,
        'model_attempts_total':sum(int(r[0].get('model_calls',0)) for r in records),
        'caveat':('Descriptive performance only. Comparison to a baseline requires paired runs '
                  'on the same hardware, model settings, patient scenarios and study snapshots. '
                  'With fewer than 5 runs, percentiles are illustrative, not stable.')
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('files',nargs='+',type=Path)
    parser.add_argument('--out',type=Path,default=Path('evaluation/results/local_latency_summary.json'))
    args=parser.parse_args()
    report=summarize(args.files)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
