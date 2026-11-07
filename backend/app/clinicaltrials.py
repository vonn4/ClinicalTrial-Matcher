"""NCT API v2 client; input is constrained to server-selected URLs only."""
from datetime import datetime, timezone
import httpx
from .schemas import TrialRecord

BASE = 'https://clinicaltrials.gov/api/v2/studies'
STATUSES = 'RECRUITING,NOT_YET_RECRUITING'


def parse_study(study: dict) -> TrialRecord:
    p = study.get('protocolSection') or {}
    ident = p.get('identificationModule') or {}
    status = p.get('statusModule') or {}
    cond = p.get('conditionsModule') or {}
    design = p.get('designModule') or {}
    eligibility = p.get('eligibilityModule') or {}
    contacts = p.get('contactsLocationsModule') or {}
    description = p.get('descriptionModule') or {}
    nct = ident['nctId']
    locations = []
    for loc in contacts.get('locations') or []:
        label = ', '.join(filter(None, [loc.get('city'),loc.get('state'),loc.get('country')]))
        if label and label not in locations:
            locations.append(label)
    updated = status.get('studyFirstPostDateStruct') or {}
    last_update = status.get('studyLastUpdatePostDateStruct') or {}
    return TrialRecord(
        nct_id=nct, title=ident.get('briefTitle','Untitled study'),
        conditions=cond.get('conditions') or [], status=status.get('overallStatus','UNKNOWN'),
        phase=design.get('phases') or [], locations=locations[:25],
        eligibility_text=eligibility.get('eligibilityCriteria',''),
        brief_summary=description.get('briefSummary',''),
        updated=last_update.get('date') or updated.get('date'),
        url=f'https://clinicaltrials.gov/study/{nct}',
        source='clinicaltrials.gov',
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )

async def search_trials(condition: str, limit: int=20) -> list[TrialRecord]:
    if not condition or not condition.strip():
        raise ValueError('A confirmed diagnosis or search condition is required')
    # The query is a parameter, not interpolated into the hostname/path.
    params={'query.cond':condition[:160], 'pageSize': min(max(limit,1),40),
            'filter.overallStatus': STATUSES, 'format':'json'}
    async with httpx.AsyncClient(timeout=18,follow_redirects=False) as client:
        response=await client.get(BASE,params=params)
        response.raise_for_status()
        return [parse_study(s) for s in response.json().get('studies',[]) if s.get('protocolSection',{}).get('identificationModule',{}).get('nctId')]

async def fetch_trial(nct_id: str) -> TrialRecord:
    import re
    if not re.fullmatch(r'NCT\d{8}',nct_id):
        raise ValueError('Invalid NCT identifier')
    async with httpx.AsyncClient(timeout=18,follow_redirects=False) as client:
        response=await client.get(f'{BASE}/{nct_id}',params={'format':'json'})
        response.raise_for_status()
        return parse_study(response.json())
