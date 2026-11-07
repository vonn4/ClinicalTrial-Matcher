#!/usr/bin/env python3
"""One-command cross-platform local launcher + end-to-end interaction smoke test.

    python run_local.py          # install if needed, start both services, test inputs, open browser
    python run_local.py --check  # verify services already running and actual input responses
    python run_local.py --no-browser

Offline synthetic sandbox requires no API keys. Real registry search requires internet.
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
CUSTOM_SYNTHETIC = '29-year-old patient with sickle cell disease. Lives in Chicago, Illinois. Previous treatments are unknown.'


def request_json(url: str, payload: dict | None = None, timeout: float = 5) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, headers={'Content-Type': 'application/json'} if data else {}, method='POST' if data else 'GET')
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def verify_workflow(backend_url: str, frontend_url: str) -> None:
    """Prove changing a user description changes the response, not just server health."""
    health = request_json(f'{backend_url}/health')
    if health.get('status') != 'ok':
        raise RuntimeError('Backend health is not OK')
    cases = request_json(f'{backend_url}/api/v1/demo/cases')
    original = cases['profile']
    fixed = request_json(f'{backend_url}/api/v1/analysis/run', {
        'profile': original, 'mode': 'replay', 'limit': 3})
    if len(fixed['assessments']) != 3:
        raise RuntimeError('Original synthetic replay does not include its three pre-authored assessments')

    edited = request_json(f'{backend_url}/api/v1/profiles/parse', {
        'description': CUSTOM_SYNTHETIC, 'mode': 'replay'})
    if edited.get('age') != 29 or edited.get('diagnosis') != 'sickle cell disease':
        raise RuntimeError('Profile parser did not respond to modified patient input')
    result = request_json(f'{backend_url}/api/v1/analysis/run', {
        'profile': edited, 'mode': 'replay', 'limit': 3})
    if [t['nct_id'] for t in result.get('trials', [])] != ['DEMO-004']:
        raise RuntimeError('Trial matching did not respond to the new fictional diagnosis')
    if result.get('assessments'):
        raise RuntimeError('Unsafe result: custom synthetic patient incorrectly received pre-authored eligibility judgments')

    with urlopen(frontend_url, timeout=5) as response:
        page = response.read(30000).decode('utf8', errors='replace')
        if response.status != 200 or '<div id="root"></div>' not in page:
            raise RuntimeError('Vite did not serve the expected React application')
    print('PASS: React page, backend health, patient-input parsing, updated trial retrieval, and replay safety')


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
        print(f'\nREADY: {f}\nInteractive sandbox: edit the fictional patient text or select a scenario, then click Explore synthetic trials.\nLive registry: select Live registry, enter fictional details and search public ClinicalTrials.gov.\nLive AI: separately opt in with a free-tier Gemini key; the launcher does not enable paid features.\nStop both services with Ctrl+C.\n', flush=True)
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
