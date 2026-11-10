"""Conservative location preference matching without inventing driving distances.

ClinicalTrials.gov location strings are public site labels, not geocoded points.
City/state matches help prioritize results; mileage is explicitly NOT verified.
"""
from __future__ import annotations
import re
from .schemas import PatientProfile, TrialRecord

STATES = {
    'al':'alabama','ak':'alaska','az':'arizona','ar':'arkansas','ca':'california',
    'co':'colorado','ct':'connecticut','de':'delaware','fl':'florida','ga':'georgia',
    'hi':'hawaii','id':'idaho','il':'illinois','in':'indiana','ia':'iowa',
    'ks':'kansas','ky':'kentucky','la':'louisiana','me':'maine','md':'maryland',
    'ma':'massachusetts','mi':'michigan','mn':'minnesota','ms':'mississippi',
    'mo':'missouri','mt':'montana','ne':'nebraska','nv':'nevada','nh':'new hampshire',
    'nj':'new jersey','nm':'new mexico','ny':'new york','nc':'north carolina',
    'nd':'north dakota','oh':'ohio','ok':'oklahoma','or':'oregon','pa':'pennsylvania',
    'ri':'rhode island','sc':'south carolina','sd':'south dakota','tn':'tennessee',
    'tx':'texas','ut':'utah','vt':'vermont','va':'virginia','wa':'washington',
    'wv':'west virginia','wi':'wisconsin','wy':'wyoming','dc':'district of columbia',
}
STATE_NAMES = set(STATES.values())


def normalize_place(value: str) -> str:
    text = re.sub(r'\s+', ' ', value.strip().lower().replace('.', ''))
    return STATES.get(text, text)


def location_priority(profile: PatientProfile, study: TrialRecord) -> int:
    """Annotate a study and return ranking boost; never claim distance or eligibility."""
    requested = (profile.location or '').strip()
    if not requested:
        study.location_fit = 'unknown'
        study.location_explanation = ''
        return 0
    terms = [normalize_place(part) for part in requested.split(',') if part.strip()]
    if not terms:
        return 0
    wanted_city = terms[0]
    wanted_state = terms[1] if len(terms) > 1 else ''
    city_matches = []
    state_matches = []
    for site in study.locations:
        parts = [normalize_place(part) for part in site.split(',') if part.strip()]
        if not parts:
            continue
        site_city = parts[0]
        site_state = parts[1] if len(parts) > 1 else ''
        if site_city == wanted_city and (not wanted_state or site_state == wanted_state):
            city_matches.append(site)
        elif wanted_state and site_state == wanted_state:
            state_matches.append(site)
    if city_matches:
        study.location_fit = 'preferred_city'
        study.location_explanation = 'Listed study site in preferred city: ' + city_matches[0] + '. Travel distance not verified.'
        return 8
    if state_matches:
        study.location_fit = 'preferred_state'
        study.location_explanation = 'Listed study site in preferred state: ' + state_matches[0] + '. Travel distance not verified.'
        return 3
    study.location_fit = 'other_location' if study.locations else 'unknown'
    study.location_explanation = (
        'No listed study site in preferred city/state; distance limit not verified.'
        if study.locations else
        'Study locations not listed; travel distance cannot be verified.'
    )
    return 0
