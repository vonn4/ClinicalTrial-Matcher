"""MVP 2.4: official-radius discovery, safe geocoding and bounded 503 recovery.

All external providers use mocks; no patient data or real API key is transmitted.
"""
from __future__ import annotations
import asyncio
import httpx
import pytest
from app import clinicaltrials as ct, geo
from app.agents import discovery_agent
from app.agents.budget import AgentBudget, _calls
from app.intake import build_profile
from app.schemas import IntakeSubmission, Mode, TrialRecord


def profile(location='Seattle, Washington', travel='Within 250 miles'):
    return build_profile(IntakeSubmission(answers={
        'condition': {'state': 'answered', 'value': 'Cystic fibrosis'},
        'age': {'state': 'answered', 'value': '27'},
        'location': {'state': 'answered', 'value': location},
        'travel': {'state': 'answered', 'value': travel},
    }, synthetic=True))


def study(nct, sites):
    return TrialRecord(
        nct_id=nct, title='Official format research record',
        status='RECRUITING', source='clinicaltrials.gov',
        conditions=['Cystic Fibrosis'], eligibility_text='Inclusion Criteria:\n- Confirmed disease',
        locations=[s[0] for s in sites],
        location_geopoints=[s[1] for s in sites],
    )


def test_known_city_geocoding_and_straight_line_distance():
    assert asyncio.run(geo.resolve_city('Seattle, Washington')) == (47.6062, -122.3321)
    assert geo.travel_radius(profile()) == 250
    assert geo.travel_radius(profile(travel='Flexible / anywhere')) is None
    assert geo.miles_between((47.6062,-122.3321), (47.6062,-122.3321)) < 0.001
    assert 20 < geo.miles_between((47.6062,-122.3321), (47.25,-122.444)) < 40


def test_arbitrary_city_resolution_requires_matching_name_and_region(monkeypatch):
    geo._cache.clear()
    seen=[]
    def respond(req: httpx.Request):
        seen.append(str(req.url))
        return httpx.Response(200, json={'results': [
            {'name':'Portland','admin1':'Maine','latitude':43.6,'longitude':-70.2},
            {'name':'Portland','admin1':'Oregon','latitude':45.52,'longitude':-122.68},
        ]})
    original=httpx.AsyncClient
    monkeypatch.setattr(geo.httpx, 'AsyncClient', lambda **kw:
                        original(transport=httpx.MockTransport(respond), **kw))
    coordinates=asyncio.run(geo.resolve_city('Portland, Oregon'))
    assert coordinates==(45.52,-122.68)
    assert len(seen)==1 and 'Portland' in seen[0]
    assert asyncio.run(geo.resolve_city('Portland, Oregon'))==coordinates
    assert len(seen)==1  # cached without another public request


def test_geofilter_queries_official_registry_and_retains_actual_sites(monkeypatch):
    sent=[]
    raw={'protocolSection':{
        'identificationModule':{'nctId':'NCT12345678','briefTitle':'Cystic Fibrosis study'},
        'statusModule':{'overallStatus':'RECRUITING'},
        'conditionsModule':{'conditions':['Cystic Fibrosis']},
        'contactsLocationsModule':{'locations':[
            {'city':'Paris','country':'France','geoPoint':{'lat':48.8566,'lon':2.3522}},
            {'city':'Tacoma','state':'Washington','country':'United States',
             'geoPoint':{'lat':47.2529,'lon':-122.4443}},
        ]},
    }}
    def reply(req: httpx.Request):
        sent.append(req)
        return httpx.Response(200,json={'studies':[raw]})
    original=httpx.AsyncClient
    monkeypatch.setattr(ct.httpx,'AsyncClient',lambda **kw:
                        original(transport=httpx.MockTransport(reply), **kw))
    studies=asyncio.run(ct.search_trials_geo('Cystic fibrosis',47.6062,-122.3321,250))
    assert len(studies)==1 and studies[0].location_geopoints[1]==(47.2529,-122.4443)
    assert sent[0].url.params['filter.geo']=='distance(47.60620,-122.33210,250mi)'
    assert sent[0].url.params['filter.overallStatus']=='RECRUITING,NOT_YET_RECRUITING'
    assert '27' not in str(sent[0].url)  # no age or other patient fields forwarded


def test_discovery_uses_geo_first_and_selects_nearest_multisite_location(monkeypatch):
    calls=[]
    nearby=study('NCT12345678',[
        ('Paris, France',(48.8566,2.3522)),
        ('Tacoma, Washington, United States',(47.2529,-122.4443)),
    ])
    async def near(q,lat,lon,miles,limit=80):
        calls.append((q,lat,lon,miles))
        return [nearby.model_copy(deep=True)]
    async def no_global(*args,**kwargs):
        raise AssertionError('Geocoded radius query must not call broad registry search')
    monkeypatch.setattr(discovery_agent,'search_trials_geo',near)
    monkeypatch.setattr(discovery_agent,'search_trials',no_global)
    found,meta=asyncio.run(discovery_agent.execute(profile(),Mode.live,count=3,
                         selected_ids=[],model=False,budget=AgentBudget()))
    assert len(calls)>=1 and all(row[-1]==250 for row in calls)
    assert [v.nct_id for v in found]==['NCT12345678']
    assert found[0].locations[0].startswith('Tacoma, Washington')
    assert found[0].location_fit=='preferred_radius'
    assert 'within selected 250-mile radius' in found[0].location_explanation
    assert 'Road travel not verified' in found[0].location_explanation
    assert meta['geographic_radius_applied'] is True


def test_empty_radius_does_not_backfill_with_overseas_studies(monkeypatch):
    async def near(*_args,**_kw): return []
    async def no_global(*_args,**_kw):
        raise AssertionError('No fallback to geographically unrelated studies')
    monkeypatch.setattr(discovery_agent,'search_trials_geo',near)
    monkeypatch.setattr(discovery_agent,'search_trials',no_global)
    found,meta=asyncio.run(discovery_agent.execute(profile(),Mode.live,count=3,
                         selected_ids=[],model=False,budget=AgentBudget()))
    assert found==[]
    assert meta['geographic_radius_applied'] is True


def test_geocoder_failure_uses_city_text_not_false_radius(monkeypatch):
    async def no_origin(_value): return None
    async def city_only(condition,city,limit=80):
        assert city=='Kansas City'
        return [study('NCT12345678',[('Kansas City, Missouri, United States',(None,None))])]
    async def no_global(*_args,**_kw):
        raise AssertionError('Fallback must be geographically constrained to city name')
    monkeypatch.setattr(discovery_agent,'resolve_city',no_origin)
    monkeypatch.setattr(discovery_agent,'search_trials_location',city_only)
    monkeypatch.setattr(discovery_agent,'search_trials',no_global)
    found,meta=asyncio.run(discovery_agent.execute(profile('Kansas City, Missouri'),Mode.live,count=3,
                         selected_ids=[],model=False,budget=AgentBudget()))
    assert len(found)==1
    assert meta['geographic_radius_applied'] is False
    assert 'could not be verified' in meta['location_filter_status']
    assert 'distance' in found[0].location_explanation.lower()


def _error_503():
    request=httpx.Request('POST','https://generativelanguage.googleapis.com/v1beta/models/fake:generateContent')
    return httpx.HTTPStatusError('do not return raw upstream details',request=request,
                                 response=httpx.Response(503,request=request))


def test_budget_retries_one_503_with_no_unmetered_attempts(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('GEMINI_API_KEY','mock-key-only')
    monkeypatch.setenv('MAX_AGENT_MODEL_CALLS_PER_HOUR','60')
    _calls.clear()
    calls=[]
    async def provider(**kw):
        calls.append(kw)
        if len(calls)==1: raise _error_503()
        return {'ok':True}
    async def no_delay(_seconds): pass
    monkeypatch.setattr('app.agents.budget.generate_json',provider)
    monkeypatch.setattr('app.agents.budget.asyncio.sleep',no_delay)
    budget=AgentBudget(maximum=9)
    result=asyncio.run(budget.generate(model='test',system='test',payload={}))
    assert result=={'ok':True}
    assert budget.calls==2 and len(calls)==2


def test_repeated_503_stops_other_agent_calls(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('GEMINI_API_KEY','mock-key-only')
    monkeypatch.setenv('MAX_AGENT_MODEL_CALLS_PER_HOUR','60')
    _calls.clear()
    calls=[]
    async def provider(**kw):
        calls.append(kw)
        raise _error_503()
    async def no_delay(_seconds): pass
    monkeypatch.setattr('app.agents.budget.generate_json',provider)
    monkeypatch.setattr('app.agents.budget.asyncio.sleep',no_delay)
    budget=AgentBudget(maximum=9)
    async def check():
        with pytest.raises(httpx.HTTPStatusError) as e:
            await budget.generate(model='test',system='test',payload={})
        assert e.value.response.status_code==503
        with pytest.raises(httpx.HTTPStatusError):
            await budget.generate(model='test',system='test',payload={})
    asyncio.run(check())
    assert budget.calls==2 and len(calls)==2
