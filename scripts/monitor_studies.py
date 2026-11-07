#!/usr/bin/env python3
"""Track only public NCT study metadata. Never process patient data or send notifications.

Uses a manually curated NCT ID file; empty by default. The job records changes to a
Git-tracked public JSON snapshot for later in-app notices.
"""
from __future__ import annotations
import hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
IDS=ROOT/'monitor'/'tracked_nct_ids.json'
SNAPSHOT=ROOT/'monitor'/'public_snapshot.json'


def normalize(payload:dict)->dict:
    p=payload.get('protocolSection',{})
    ident=p.get('identificationModule',{})
    status=p.get('statusModule',{})
    eligibility=p.get('eligibilityModule',{})
    locs=p.get('contactsLocationsModule',{}).get('locations') or []
    e=eligibility.get('eligibilityCriteria','')
    digest=hashlib.sha256(e.encode('utf-8')).hexdigest()
    return {'nct_id':ident.get('nctId'), 'updated':(status.get('studyLastUpdatePostDateStruct') or {}).get('date'),
            'recruitment_status':status.get('overallStatus'), 'eligibility_sha256':digest,
            'locations':sorted(set(', '.join(filter(None,[l.get('city'),l.get('state'),l.get('country')])) for l in locs))}


def diff(old:dict,new:dict)->list[dict]:
    changes=[]
    for nct,rec in new.items():
        prev=old.get(nct)
        if prev is None:
            changes.append({'nct_id':nct,'changed_fields':['newly_tracked'],'previous_updated':None,'current_updated':rec.get('updated')})
        else:
            fields=[k for k in ('updated','recruitment_status','eligibility_sha256','locations') if prev.get(k)!=rec.get(k)]
            if fields:changes.append({'nct_id':nct,'changed_fields':fields,'previous_updated':prev.get('updated'),'current_updated':rec.get('updated')})
    return changes


def main():
    ids=json.loads(IDS.read_text())
    if not isinstance(ids,list) or len(ids)>20 or any(not isinstance(x,str) or not re.fullmatch(r'NCT\d{8}',x) for x in ids):
        raise ValueError('Tracked public NCT IDs must be a list of <=20 official IDs')
    if not ids:
        print('No public trial IDs configured. Monitoring inactive; no records or alerts fabricated.')
        return
    previous=json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {'studies':{}}
    out={}
    with httpx.Client(timeout=15,follow_redirects=False) as client:
        for nct in ids:
            response=client.get(f'https://clinicaltrials.gov/api/v2/studies/{nct}',params={'format':'json'})
            response.raise_for_status()
            out[nct]=normalize(response.json())
    changes=diff(previous.get('studies',{}),out)
    SNAPSHOT.write_text(json.dumps({'snapshot_at':datetime.now(timezone.utc).isoformat(),
                  'studies':out,'changes':changes},indent=2)+'\n')
    print(f'Recorded {len(out)} public studies, {len(changes)} changed entries.')

if __name__=='__main__':main()
