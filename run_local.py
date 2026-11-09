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
    """Inspect configuration only; do NOT send a paid or free-tier inference request."""
    caps=request_json(f'{backend_url}/api/v1/matching/capabilities')
    roles=caps.get('agent_roles',[])
    print('Agent roles:',', '.join(roles))
    print('Provider:',caps.get('model_provider','unconfigured'))
    if not caps.get('model_ready'):
        raise RuntimeError('Gemini not configured on this backend: '+
                           str(caps.get('model_readiness_message','unknown reason'))+
                           '. Edit the project .env file, restart python run_local.py and retry.')
    print('READY: Gemini configuration found on backend.')
    print('Profile model:',caps.get('profile_model'))
    print('Analysis/skeptic model:',caps.get('analysis_model'))
    print('To verify ACTUAL inference, select Model-assisted analysis before searching a fictional profile.')
    print('This check performs zero inference calls and does not validate provider quota.')


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
