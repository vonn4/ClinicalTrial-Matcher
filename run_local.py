#!/usr/bin/env python3
"""One-command cross-platform local launcher + end-to-end interaction smoke test.

    python run_local.py          # install if needed, start both services, test inputs, open browser
    python run_local.py --check  # verify services already running and actual input responses
    python run_local.py --no-browser

Startup requires no API key; real registry discovery requires internet.
Live eligibility LLM requires separate free-tier model opt-in; not enabled by launcher.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'


def request_json(url: str, payload: dict | None = None, timeout: float = 5) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, headers={'Content-Type': 'application/json'} if data else {}, method='POST' if data else 'GET')
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def verify_workflow(backend_url: str, frontend_url: str) -> None:
    """Check live-only UI contracts without requiring a registry network call."""
    health=request_json(f'{backend_url}/health')
    if health.get('status')!='ok' or health.get('mode_default')!='live':
        raise RuntimeError('Backend unhealthy or still defaults to fictional replay')
    caps=request_json(f'{backend_url}/api/v1/matching/capabilities')
    if caps.get('agent_roles')!=['profile','discovery','analyst','skeptic','clarification']:
        raise RuntimeError('Five-agent workflow is not registered')
    questions=request_json(f'{backend_url}/api/v1/intake/questions?include_all=true')
    if not any(q.get('id')=='condition' for q in questions.get('questions',[])):
        raise RuntimeError('Guided intake does not accept open disease names')
    profile=request_json(f'{backend_url}/api/v1/intake/profile',{
        'answers':{
            'condition':{'state':'answered','value':'multiple sclerosis'},
            'age':{'state':'answered','value':'31'}
        },'synthetic':True})
    if profile.get('diagnosis')!='multiple sclerosis' or profile.get('age')!=31:
        raise RuntimeError('Open disease input not preserved by canonical profile')
    with urlopen(frontend_url,timeout=5) as response:
        page=response.read(30000).decode('utf8',errors='replace')
        if response.status!=200 or '<div id="root"></div>' not in page:
            raise RuntimeError('Vite did not serve the expected React app')
    print('PASS: live-only frontend, backend default, open disease intake and five-agent routes')


def verify_live_registry(backend_url: str) -> None:
    """Explicit opt-in internet test: real registry studies, fake patient only."""
    status=request_json(f'{backend_url}/api/v1/registry/status', timeout=18)
    if not status.get('connected') or not status.get('data_timestamp'):
        raise RuntimeError('ClinicalTrials.gov version and refresh timestamp not verified')
    fake_profile=request_json(f'{backend_url}/api/v1/intake/profile', {
        'answers': {'condition': {'state':'answered','value':'sickle cell disease'},
                    'age': {'state':'answered','value':'29'}},
        'narrative':'Entirely fictional research example.', 'synthetic':True})
    matches=request_json(f'{backend_url}/api/v1/trials/search', {
        'profile':fake_profile,'mode':'live','limit':5}, timeout=35)
    trials=matches.get('trials') or []
    if not trials:
        raise RuntimeError('Official API reachable but returned no recruiting sickle-cell studies; try a different condition')
    for study in trials:
        id=study.get('nct_id','')
        if (study.get('source')!='clinicaltrials.gov' or len(id)!=11 or not id.startswith('NCT')
            or study.get('url')!=f'https://clinicaltrials.gov/study/{id}'):
            raise RuntimeError('Live response was not an authentic official NCT study record')
    ids=[trial['nct_id'] for trial in trials[:3]]
    plan=request_json(f'{backend_url}/api/v1/intake/followups', {
        'profile':fake_profile,'mode':'live','trial_ids':ids},timeout=35)
    if plan.get('reviewed_trial_ids')!=ids:
        raise RuntimeError('Live criterion mapping did not review the requested official study identifiers')
    refined=request_json(f'{backend_url}/api/v1/intake/reassess', {
        'profile':fake_profile,'mode':'live','trial_ids':ids,'updates':{}},timeout=35)
    if {a['nct_id'] for a in refined['assessments']}!=set(ids):
        raise RuntimeError('Live deterministic reassessment did not return original study IDs')
    if any(a['summary']=='potential_match' for a in refined['assessments']):
        raise RuntimeError('Unvalidated live studies were incorrectly declared potentially eligible')
    print('PASS: real ClinicalTrials.gov API, official NCT source URLs, live study follow-ups, safe partial reassessment')
    print('Official API version:',status['api_version'],'data timestamp:',status['data_timestamp'])
    print('Retrieved official NCT IDs:',', '.join(x['nct_id'] for x in trials))
    print('Unmapped requirements:',len(plan.get('unmapped_criteria') or []),'— not inferred or auto-cleared')
    agent_run=request_json(f'{backend_url}/api/v1/matching/analyze',{
        'profile':fake_profile,'mode':'live','depth':'tools','max_studies':3},timeout=65)
    roles=[step.get('agent') for step in agent_run.get('trace',[])]
    if roles!=['profile','discovery','analyst','skeptic','clarification']:
        raise RuntimeError('Live five-agent matching did not execute the expected roles')
    if not agent_run.get('trials') or any(
        t.get('source')!='clinicaltrials.gov' or not t.get('nct_id','').startswith('NCT')
        for t in agent_run.get('trials',[])):
        raise RuntimeError('Agent workflow returned no official studies or unexpected synthetic records')
    print('PASS: five-agent tool-only matching over official ClinicalTrials.gov studies')


def verify_model_readiness(backend_url: str) -> None:
    """Compare LOCAL ignored .env with RUNNING backend, without disclosing keys."""
    local = load_env(ROOT / '.env')
    local_enabled = local.get('ENABLE_LIVE_AI', '').strip().lower() in {'true', '1', 'yes', 'on'}
    local_key = len(local.get('GEMINI_API_KEY', '').strip()) >= 20
    local_team = len(local.get('LIVE_AI_ACCESS_TOKEN', '').strip()) >= 16
    print('Project root:', ROOT)
    print('Local ignored .env exists:', (ROOT / '.env').exists())
    print('Local AI enabled:', local_enabled)
    print('Local Gemini key present:', local_key)
    print('Local team access token present:', local_team)
    try:
        caps = request_json(f'{backend_url}/api/v1/matching/capabilities', timeout=5)
    except (URLError, HTTPError, TimeoutError, ConnectionError, OSError) as exc:
        raise RuntimeError('No matching backend was reachable on '+backend_url+
            '. Run python run_local.py in the first terminal, then retry --check-ai.') from exc
    roles = caps.get('agent_roles', [])
    print('Agent roles:', ', '.join(roles))
    print('Provider:', caps.get('model_provider', 'unconfigured'))
    server_ready = bool(caps.get('model_ready'))
    if local_enabled and local_key and local_team and not server_ready:
        raise RuntimeError(
            'STALE BACKEND CONFIGURATION: the local .env is enabled but the RUNNING server reports '
            + str(caps.get('model_readiness_message', 'Gemini disabled'))
            + '. Stop python run_local.py in the ORIGINAL server terminal (Ctrl+C), '
            'check that port 8000 is free, restart python run_local.py, then retry --check-ai. '
            'In Windows PowerShell, inspect the listener with: '
            'Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess'
        )
    if not (local_enabled and local_key and local_team):
        raise RuntimeError(
            'LOCAL CONFIGURATION INCOMPLETE: run python configure_local_ai.py '
            'with a replacement Gemini key, then restart the server.')
    if not server_ready:
        raise RuntimeError('Backend Gemini not ready: '+
                           str(caps.get('model_readiness_message', 'unknown reason')))
    print('READY: local .env and running backend both report Gemini configured.')
    print('Profile model:', caps.get('profile_model'))
    print('Analysis/skeptic model:', caps.get('analysis_model'))
    print('This is a CONFIGURATION check, not confirmation that Google inference works.')
    print('For an explicit provider test after verifying free-tier billing: '
          'python run_local.py --probe-ai --confirm-free-tier')


def list_available_models() -> None:
    """List model IDs permitted by the locally configured key, without inference.

    Google AI Studio billing, RPM and daily quota must still be verified
    separately. Do not print keys, raw URLs with credentials or response bodies.
    """
    local = load_env(ROOT / '.env')
    key = local.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Missing GEMINI_API_KEY in project .env; run configure_local_ai.py')
    address = 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=100'
    items = []
    token = ''
    for _ in range(3):
        url = address + (('&pageToken=' + token) if token else '')
        req = Request(url, headers={'x-goog-api-key':key}, method='GET')
        try:
            with urlopen(req, timeout=22) as response:
                data = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(
                'Gemini model listing failed (HTTP ' + str(exc.code) +
                '). Check the private key, its project permissions and API availability.'
            ) from None
        except (URLError,TimeoutError,OSError):
            raise RuntimeError('Cannot reach Gemini model listing; check network connectivity.') from None
        items.extend(data.get('models') or [])
        token = data.get('nextPageToken') or ''
        if not token: break
    supported = sorted({str(m.get('name','')).removeprefix('models/')
        for m in items if 'generateContent' in m.get('supportedGenerationMethods',[])
        and str(m.get('name','')).startswith('models/gemini-')})
    configured = (local.get('GEMINI_PROFILE_MODEL','gemini-3.5-flash-lite'),
                  local.get('GEMINI_MODEL','gemini-3.5-flash'))
    print('Models supporting generateContent for this API key:')
    for name in supported:
        print(' ',name)
    if not supported:
        raise RuntimeError('No compatible Gemini text models were returned; check API access.')
    for label,name in zip(('Profile model','Analyst/Skeptic model'),configured):
        print(label + ': ' + name + ' — ' +
              ('LISTED' if name in supported else 'NOT LISTED for this key'))
    print('The listing checks access metadata only, not free-tier quota or a successful inference.')
    print('If a configured model is NOT LISTED, select a supported free-tier model in .env,')
    print('then restart python run_local.py and run --probe-ai --confirm-free-tier.')


def probe_provider_models() -> None:
    """Deliberate real Gemini smoke test on NON-PATIENT synthetic JSON, never credentials."""
    import asyncio
    env = load_env(ROOT / '.env')
    if env.get('ENABLE_LIVE_AI', '').strip().lower() not in {'true', '1', 'yes', 'on'}:
        raise RuntimeError('Local .env has ENABLE_LIVE_AI disabled; run configure_local_ai.py')
    if not env.get('GEMINI_API_KEY', '').strip():
        raise RuntimeError('Missing local Gemini API key; run configure_local_ai.py')
    # Load only into this local process. Never print the API key or team token.
    os.environ.update(env)
    sys.path.insert(0, str(BACKEND))
    from app.agents.budget import AgentBudget
    from app.settings import GEMINI_MODEL, GEMINI_PROFILE_MODEL
    budget = AgentBudget(maximum=2)

    async def check():
        unique_models = list(dict.fromkeys((GEMINI_PROFILE_MODEL, GEMINI_MODEL)))
        for model in unique_models:
            try:
                response = await budget.generate(
                    model=model,
                    system='Connectivity test only. Return exactly a JSON object with ok set to true.',
                    payload={'purpose': 'health check', 'synthetic': True})
                if response.get('ok') is not True:
                    raise RuntimeError('Provider returned JSON but not the requested test schema.')
            except Exception as exc:
                # httpx can include sensitive request details in its exception;
                # report only a small safe class and HTTP status, not raw body/URL.
                status = getattr(getattr(exc, 'response', None), 'status_code', None)
                raise RuntimeError(
                    f'Gemini probe failed for model {model} ({type(exc).__name__}'
                    + (f', HTTP {status}' if status else '') +
                    '). Check model availability, free-tier quota, key validity and internet access.'
                ) from None
            print('PASS: real Gemini JSON response from', model)
        print('PASS: provider connectivity confirmed; this did not test the five-agent workflow.')

    asyncio.run(check())



def smoke_live_agent_workflow(backend_url: str) -> None:
    """Opt-in single-command live smoke test against one public NCT study.

    Makes REAL Gemini requests using only a fictional profile and the local
    server-side team token. Does not print credentials, payloads or patient facts.
    Requires a running backend and explicit user free-tier confirmation.
    """
    verify_model_readiness(backend_url)
    local = load_env(ROOT / '.env')
    caps = request_json(f'{backend_url}/api/v1/matching/capabilities')
    if (caps.get('profile_model') != local.get('GEMINI_PROFILE_MODEL', 'gemini-3.5-flash-lite')
        or caps.get('analysis_model') != local.get('GEMINI_MODEL', 'gemini-3.5-flash')):
        raise RuntimeError(
            'Running backend is using different model IDs than .env. Restart python run_local.py first.'
        )
    profile = request_json(f'{backend_url}/api/v1/intake/profile', {
        'synthetic': True,
        'answers': {
            'condition': {'state': 'answered', 'value': 'Cystic fibrosis'},
            'diagnosis_confirmation': {'state': 'answered', 'value': 'Confirmed'},
            'age': {'state': 'answered', 'value': '27'},
            'cftr_result': {'state': 'unknown', 'value': None},
            'location': {'state': 'answered', 'value': 'Seattle, Washington'},
            'travel': {'state': 'answered', 'value': 'Within 250 miles'},
        },
        'narrative': 'Entirely fictional CF research profile. Unknown genetic status; no clinical eligibility is presumed.',
    })
    payload = {
        'mode': 'live', 'depth': 'model', 'max_studies': 1,
        'study_ids': ['NCT06429176'], 'profile': profile,
    }
    token = local.get('LIVE_AI_ACCESS_TOKEN', '')
    if len(token) < 16:
        raise RuntimeError('Local team token missing; run configure_local_ai.py.')
    req = Request(
        f'{backend_url}/api/v1/matching/analyze',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'X-Live-Access-Token': token},
        method='POST',
    )
    with urlopen(req, timeout=245) as response:
        result = json.load(response)
    stages = {stage['agent']: stage for stage in result.get('trace', [])}
    for name in ('profile', 'discovery', 'analyst', 'skeptic', 'clarification'):
        stage = stages.get(name)
        if not stage:
            raise RuntimeError('Missing agent stage: ' + name)
        details = stage.get('details', {})
        print('Stage:', name, '| execution:', stage.get('execution'),
              '| model calls:', stage.get('model_calls', 0),
              '| failures:', details.get('model_failures', 0))
    analyst = stages['analyst'].get('details', {})
    skeptic = stages['skeptic'].get('details', {})
    if analyst.get('model_reviewed', 0) < 1 or skeptic.get('independent_trials', 0) < 1:
        for name in ('analyst', 'skeptic'):
            info = stages[name].get('details', {})
            print('Diagnostic:', name, info.get('model_error', 'no completed model review'),
                  info.get('model_http_status', ''))
        raise RuntimeError(
            'Live AI acceptance FAILED: Analyst or independent Skeptic did not complete a review.'
        )
    assert result.get('model_calls', 10) <= 9, 'Agent inference call budget exceeded'
    if not result.get('assessments') or not result['assessments'][0].get('skeptic'):
        raise RuntimeError('Independent criterion findings missing from response')
    print('PASS: REAL Gemini Analyst and independent Skeptic completed source-grounded criterion reviews')
    print('Official NCT study:', result['trials'][0]['nct_id'],
          '| assessed criteria:', len(result['assessments'][0]['criteria']),
          '| total model attempts:', result['model_calls'])

def wait_until(url: str, label: str, processes: list[subprocess.Popen], timeout: float = 35) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError(f'A {label} service exited before becoming ready; read the preceding server output')
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, HTTPError, TimeoutError, ConnectionError, OSError):
            pass
        time.sleep(.35)
    raise RuntimeError(f'{label} did not become ready at {url} after {timeout:.0f} seconds')


def ensure_dependencies(no_install: bool) -> None:
    missing = [x for x in ('fastapi', 'uvicorn', 'httpx', 'pydantic') if importlib.util.find_spec(x) is None]
    if missing:
        if no_install:
            raise RuntimeError(f'Missing Python packages: {missing}; run pip install -r backend/requirements-dev.txt')
        print('Installing required Python packages (free)...', flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements-dev.txt'], cwd=BACKEND, check=True)
    if not shutil.which('npm'):
        raise RuntimeError('Node.js/npm not found. Install Node.js 20+ from https://nodejs.org/ before running this script')
    if not (FRONTEND / 'node_modules' / '.bin' / 'vite').exists() and not (FRONTEND / 'node_modules' / '.bin' / 'vite.cmd').exists():
        if no_install:
            raise RuntimeError('Missing frontend dependencies. Run npm install inside frontend/')
        print('Installing frontend packages (free)...', flush=True)
        subprocess.run(['npm.cmd' if os.name == 'nt' else 'npm', 'install', '--no-audit', '--no-fund'], cwd=FRONTEND, check=True)


def load_env(path: Path) -> dict[str, str]:
    # Never log env values. Config here is a developer-local convenience only.
    values = {}
    if path.exists():
        for line in path.read_text(encoding='utf8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for proc in reversed(processes):
        if proc.poll() is not None:
            continue
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, check=False)
            else:
                proc.terminate()
                proc.wait(timeout=4)
        except (OSError, subprocess.TimeoutExpired):
            try: proc.kill()
            except OSError: pass


def main() -> int:
    parser = argparse.ArgumentParser(description='Start and interaction-test ClinicalTrial Matcher')
    parser.add_argument('--check', action='store_true', help='Test existing frontend/backend including custom profile submissions')
    parser.add_argument('--check-live', action='store_true', help='Test REAL ClinicalTrials.gov API and follow-up pipeline; requires internet and an already running backend')
    parser.add_argument('--check-ai', action='store_true', help='Check configured model names and local readiness without invoking Gemini (backend must be running)')
    parser.add_argument('--list-ai-models', action='store_true', help='List model IDs available to your local Gemini key; no inference calls')
    parser.add_argument('--probe-ai', action='store_true', help='OPT-IN: call real Gemini model(s) with a non-patient JSON probe')
    parser.add_argument('--smoke-ai-workflow', action='store_true', help='OPT-IN: run full five-agent workflow using one fictional patient and live registry study')
    parser.add_argument('--confirm-free-tier', action='store_true', help='Confirm that YOU verified the Google project has an eligible free tier with billing disabled')
    parser.add_argument('--no-browser', action='store_true', help='Do not open the browser')
    parser.add_argument('--no-install', action='store_true', help='Fail rather than install missing free dependencies')
    parser.add_argument('--backend-port', type=int, default=8000)
    parser.add_argument('--frontend-port', type=int, default=5173)
    args = parser.parse_args()
    b = f'http://127.0.0.1:{args.backend_port}'
    f = f'http://127.0.0.1:{args.frontend_port}'
    procs: list[subprocess.Popen] = []
    try:
        if args.check:
            verify_workflow(b, f)
            return 0
        if args.check_live:
            verify_live_registry(b)
            return 0
        if args.check_ai:
            verify_model_readiness(b)
            return 0
        if args.list_ai_models:
            list_available_models()
            return 0
        if args.smoke_ai_workflow:
            if not args.confirm_free_tier:
                raise RuntimeError('Live Gemini workflow test requires --confirm-free-tier after verifying billing is disabled.')
            smoke_live_agent_workflow(b)
            return 0
        if args.probe_ai:
            if not args.confirm_free_tier:
                raise RuntimeError('Real Gemini calls are disabled unless you explicitly use --confirm-free-tier after verifying billing is disabled.')
            probe_provider_models()
            return 0
        ensure_dependencies(args.no_install)
        env = {**os.environ, **load_env(ROOT / '.env')}
        env['CORS_ORIGINS'] = ','.join([f, f'http://localhost:{args.frontend_port}'])
        env['VITE_API_BASE_URL'] = b
        print(f'Launching API at {b} and dashboard at {f} ...', flush=True)
        procs.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(args.backend_port)], cwd=BACKEND, env=env))
        wait_until(f'{b}/health', 'FastAPI', procs)
        npm = 'npm.cmd' if os.name == 'nt' else 'npm'
        procs.append(subprocess.Popen([npm, 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(args.frontend_port), '--strictPort'], cwd=FRONTEND, env=env))
        wait_until(f, 'React/Vite', procs)
        verify_workflow(b, f)
        print((
            f'\nREADY: {f}\n'
            'Guided intake: enter a real disease; studies come exclusively from ClinicalTrials.gov.\n'
            'Quick description: fictional patient details, real registered studies, no demo fallback.\n'
            'Official registry: live searches need internet connectivity.\n'
            'Run `python run_local.py --check-live` from another terminal to verify the official API.\n'
            'Live AI: configure a verified free-tier Gemini key in project .env; run --check-ai to inspect readiness.\n'
            'Stop both services with Ctrl+C.\n'
        ), flush=True)
        if not args.no_browser:
            webbrowser.open(f)
        while all(p.poll() is None for p in procs):
            time.sleep(.5)
        raise RuntimeError('One of the application servers exited; see preceding output')
    except (RuntimeError, OSError, subprocess.CalledProcessError, URLError, HTTPError) as exc:
        print(f'\nERROR: {exc}', file=sys.stderr)
        print('If ports are already occupied, stop the previous servers or use: python run_local.py --check', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nShutting down...', flush=True)
        return 0
    finally:
        stop_processes(procs)


if __name__ == '__main__':
    raise SystemExit(main())
