#!/usr/bin/env python3
"""Deterministic retrieval metrics. Actual benchmark inputs required."""
from collections import defaultdict
from pathlib import Path
import argparse,csv,json,math


def dcg(grades:list[int])->float:
    return sum((2**grade-1)/math.log2(i+2) for i,grade in enumerate(grades))

def metrics_for(qrels:dict[str,int],ranking:list[str],k:int=10)->dict[str,float]:
    ranked=[qrels.get(nct,0) for nct in ranking[:k]]
    ideal=sorted(qrels.values(),reverse=True)[:k]
    denom=dcg(ideal)
    eligible_total=sum(g==2 for g in qrels.values())
    return {
      f'ndcg@{k}':dcg(ranked)/denom if denom else 0.,
      f'precision@{k}':sum(g>0 for g in ranked)/k,
      f'eligible_recall@{k}':sum(g==2 for g in ranked)/eligible_total if eligible_total else 0.,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--qrels',type=Path,required=True);ap.add_argument('--ranking',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    qrels=defaultdict(dict)
    with args.qrels.open(newline='') as f:
        for row in csv.DictReader(f):
            if int(row['grade']) not in {0,1,2}:raise ValueError('Expected grades 0/1/2')
            qrels[row['query_id']][row['nct_id']]=int(row['grade'])
    run=defaultdict(list)
    with args.ranking.open(newline='') as f:
        for row in csv.DictReader(f):
            run[(row['method'],row['query_id'])].append((int(row['rank']),row['nct_id']))
    methods=sorted({method for method,_ in run})
    result={'source':'actual_supplied_inputs','sample_size_queries':len(qrels),'results':{}}
    for method in methods:
        per_query=[]
        for qid,truth in qrels.items():
            ids=[x[1] for x in sorted(run.get((method,qid),[]))]
            per_query.append(metrics_for(truth,ids,10))
        keys=per_query[0].keys() if per_query else []
        result['results'][method]={k:round(sum(q[k] for q in per_query)/len(per_query),6) for k in keys}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
