"""Official ClinicalTrials.gov REST API v2 client — public study metadata only.

No patient data is sent to the registry: requests contain a condition search
term or registered NCT identifiers only. A bounded, in-memory TTL cache stores
public studies to avoid eight redundant HTTP requests per follow-up answer.
"""
from __future__ import annotations
from collections import OrderedDict
from datetime import datetime, timezone
import math
import re
import time
import httpx
from .schemas import TrialRecord

BASE = 'https://clinicaltrials.gov/api/v2/studies'
VERSION = 'https://clinicaltrials.gov/api/v2/version'
STATUSES = 'RECRUITING,NOT_YET_RECRUITING'
CACHE_SECONDS = 10 * 60
MAX_CACHE = 300
_cache: OrderedDict[str, tuple[float, TrialRecord]] = OrderedDict()


def _cached(nct_id: str) -> TrialRecord | None:
    entry = _cache.get(nct_id)
    if entry is None:
        return None
    timestamp, study = entry
    if time.monotonic() - timestamp > CACHE_SECONDS:
        del _cache[nct_id]
        return None
    _cache.move_to_end(nct_id)
    return study.model_copy(deep=True)


def _save(study: TrialRecord) -> None:
    _cache[study.nct_id] = (time.monotonic(), study.model_copy(deep=True))
    _cache.move_to_end(study.nct_id)
    while len(_cache) > MAX_CACHE:
        _cache.popitem(last=False)


def parse_study(study: dict) -> TrialRecord:
    """Normalize the official protocolSection; never synthesize trial criteria."""
    p = study.get('protocolSection') or {}
    ident = p.get('identificationModule') or {}
    status = p.get('statusModule') or {}
    cond = p.get('conditionsModule') or {}
    design = p.get('designModule') or {}
    eligibility = p.get('eligibilityModule') or {}
    contacts = p.get('contactsLocationsModule') or {}
    description = p.get('descriptionModule') or {}
    nct = ident['nctId']
    locations: list[str] = []
    geopoints: list[tuple[float | None, float | None]] = []
    for loc in contacts.get('locations') or []:
        label = ', '.join(filter(None, [loc.get('city'), loc.get('state'), loc.get('country')]))
        if label and label not in locations:
            locations.append(label)
            point = loc.get('geoPoint') or {}
            try:
                lat, lon = float(point['lat']), float(point['lon'])
                if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError('Invalid study-site coordinates')
                geopoints.append((lat, lon))
            except (KeyError, TypeError, ValueError):
                geopoints.append((None, None))
    first = status.get('studyFirstPostDateStruct') or {}
    updated = status.get('studyLastUpdatePostDateStruct') or {}
    return TrialRecord(
        nct_id=nct, title=ident.get('briefTitle', 'Untitled study'),
        conditions=cond.get('conditions') or [],
        status=status.get('overallStatus', 'UNKNOWN'),
        phase=design.get('phases') or [], locations=locations[:25],
        eligibility_text=eligibility.get('eligibilityCriteria') or '',
        brief_summary=description.get('briefSummary') or '',
        updated=updated.get('date') or first.get('date'),
        url=f'https://clinicaltrials.gov/study/{nct}',
        source='clinicaltrials.gov',
        minimum_age=eligibility.get('minimumAge'), maximum_age=eligibility.get('maximumAge'),
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )


def validate_condition(condition: str) -> str:
    """Bound an untrusted search string; do not accept Essie operator syntax."""
    value = ' '.join(condition.strip().split())
    if not 3 <= len(value) <= 120 or re.search(r'[\[\]{}<>\\;]', value):
        raise ValueError('Enter a condition name (3–120 characters); advanced search syntax is not supported')
    return value


def validate_ids(ids: list[str]) -> list[str]:
    if not 1 <= len(ids) <= 8 or len(ids) != len(set(ids)):
        raise ValueError('Specify between one and eight distinct registered NCT study IDs')
    if any(not re.fullmatch(r'NCT\d{8}', nct) for nct in ids):
        raise ValueError('Invalid NCT identifier')
    return ids


async def _search_studies(condition: str, limit: int = 80, *,
                          geo: tuple[float, float, int] | None = None,
                          city_query: str | None = None) -> list[TrialRecord]:
    """Only sends a public disease search term plus optional geographic preference."""
    condition = validate_condition(condition)
    params = {
        'query.cond': condition,
        'pageSize': min(max(limit, 1), 100),
        'filter.overallStatus': STATUSES,
        'format': 'json',
    }
    if geo is not None:
        lat, lon, radius = geo
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and radius in (50, 100, 250)):
            raise ValueError('Invalid geographic search radius')
        params['filter.geo'] = f'distance({lat:.5f},{lon:.5f},{radius}mi)'
    if city_query:
        params['query.locn'] = city_query
    async with httpx.AsyncClient(timeout=22, follow_redirects=False) as client:
        response = await client.get(BASE, params=params)
        response.raise_for_status()
        data = response.json()
    studies = []
    for raw in data.get('studies') or []:
        try:
            parsed = parse_study(raw)
        except (KeyError, TypeError, ValueError):
            continue  # malformed individual public records never become made-up trials
        _save(parsed)
        studies.append(parsed)
    return studies


async def search_trials(condition: str, limit: int = 80) -> list[TrialRecord]:
    """Broad public-registry study search for patients with no verified geographic radius."""
    return await _search_studies(condition, limit)


async def search_trials_geo(condition: str, lat: float, lon: float, miles: int,
                            limit: int = 80) -> list[TrialRecord]:
    """Official registry geofilter: study has a registered site within a radial distance."""
    return await _search_studies(condition, limit, geo=(lat, lon, miles))


async def search_trials_location(condition: str, city: str, limit: int = 80) -> list[TrialRecord]:
    """Textual city filter when an exact radius cannot be verified."""
    return await _search_studies(condition, limit, city_query=city)


async def fetch_trials_by_ids(ids: list[str]) -> list[TrialRecord]:
    """One bounded request for missing official studies; preserve original ID order."""
    validate_ids(ids)
    found: dict[str, TrialRecord] = {}
    missing = []
    for nct in ids:
        cached = _cached(nct)
        if cached is not None:
            found[nct] = cached
        else:
            missing.append(nct)
    if missing:
        params = {'filter.ids': ','.join(missing), 'pageSize': len(missing), 'format': 'json'}
        async with httpx.AsyncClient(timeout=22, follow_redirects=False) as client:
            response = await client.get(BASE, params=params)
            response.raise_for_status()
            result = response.json()
        for raw in result.get('studies') or []:
            try:
                parsed = parse_study(raw)
            except (KeyError, TypeError, ValueError):
                continue
            if parsed.nct_id in missing:
                _save(parsed)
                found[parsed.nct_id] = parsed
    if set(ids) - set(found):
        raise ValueError('One or more requested official studies were not found')
    return [found[nct].model_copy(deep=True) for nct in ids]


async def fetch_trial(nct_id: str) -> TrialRecord:
    validate_ids([nct_id])
    cached = _cached(nct_id)
    if cached:
        return cached
    async with httpx.AsyncClient(timeout=22, follow_redirects=False) as client:
        response = await client.get(f'{BASE}/{nct_id}', params={'format': 'json'})
        response.raise_for_status()
        trial = parse_study(response.json())
        _save(trial)
        return trial


async def registry_status() -> dict:
    """Verify the official registry is reachable; do not equate API health to eligibility."""
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.get(VERSION)
        response.raise_for_status()
        data = response.json()
    if not data.get('apiVersion') or not data.get('dataTimestamp'):
        raise ValueError('Unexpected ClinicalTrials.gov version response')
    return {'connected': True, 'provider': 'ClinicalTrials.gov',
            'api_version': data['apiVersion'], 'data_timestamp': data['dataTimestamp'],
            'no_api_key_required': True, 'synthetic_patients_only': True}
