#!/usr/bin/env python3
"""Offline scoring from supplied criterion labels and agent predictions; no invented results."""
from __future__ import annotations
import argparse,csv,json
from collections import Counter,defaultdict
from pathlib import Path
STATUSES={'met','not_met','unknown','clinical_review'}
KINDS={'inclusion','exclusion'}
def read_rows(path:Path,required:set[str])->list[dict[str,str]]:
    with path.open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        missing=required-set(reader.fieldnames or [])
        if missing:raise ValueError(f'{path}: missing columns {sorted(missing)}')
        return list(reader)
def score(labels:list[dict],predictions:list[dict])->dict:
    gold={}
    for row in labels:
        k=(row['case_id'],row['nct_id'],row['criterion_id'])
        if k in gold:raise ValueError(f'Duplicate gold label: {k}')
        if row['kind'] not in KINDS or row['gold_status'] not in STATUSES:raise ValueError('Invalid gold label')
        gold[k]=(row['kind'],row['gold_status'])
    if not gold:raise ValueError('No reference criteria supplied')
    methods=defaultdict(dict)
    for row in predictions:
        k=(row['case_id'],row['nct_id'],row['criterion_id'])
        if k not in gold:raise ValueError(f'Prediction for unknown criterion: {k}')
        if row['status'] not in STATUSES:raise ValueError('Invalid prediction status')
        m=row['method'].strip()
        if not m:raise ValueError('Method must not be blank')
        if k in methods[m]:raise ValueError('Duplicate prediction')
        methods[m][k]=row['status']
    if not methods:raise ValueError('No predictions supplied')
    results={}
    for method,run in sorted(methods.items()):
        n=len(gold)
        answered=sum(run.get(k,'unknown') in {'met','not_met'} for k in gold)
        exclusions=[k for k,(kind,status) in gold.items() if kind=='exclusion' and status=='met']
        caught=sum(run.get(k,'unknown')=='met' for k in exclusions)
        missed_as_clear=sum(run.get(k,'unknown')=='not_met' for k in exclusions)
        unsupported=sum(
            (run.get(k)=='met' and kind=='inclusion' and status!='met') or
            (run.get(k)=='not_met' and kind=='exclusion' and status=='met')
            for k,(kind,status) in gold.items())
        results[method]={
            'total_reference_criteria':n,
            'submitted_predictions':len(run),
            'exact_status_accuracy':round(sum(run.get(k,'unknown')==status for k,(_,status) in gold.items())/n,6),
            'decisive_coverage':round(answered/n,6),
            'abstention_rate':round((n-answered)/n,6),
            'known_exclusion_triggers':len(exclusions),
            'exclusion_trigger_recall':round(caught/len(exclusions),6) if exclusions else None,
            'unsafe_exclusion_clearances':missed_as_clear,
            'unsupported_positive_conclusions':unsupported,
            'status_confusion':dict(Counter(f'{status}->{run.get(k,"unknown")}' for k,(_,status) in gold.items()))
        }
    return {'source':'supplied_labeled_predictions','case_count':len({k[0] for k in gold}),
            'criteria_count':len(gold),'methods':results,
            'limitations':'Labels may be team engineering references, not clinical expert ground truth.'}
def main():
    ap=argparse.ArgumentParser(description='Score labeled multi-agent ablations without inference')
    ap.add_argument('--labels',type=Path,required=True)
    ap.add_argument('--predictions',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    result=score(read_rows(args.labels,{'case_id','nct_id','criterion_id','kind','gold_status'}),
                 read_rows(args.predictions,{'method','case_id','nct_id','criterion_id','status'}))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
