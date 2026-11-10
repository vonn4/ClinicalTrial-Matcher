"""Ephemeral progress for active matching runs; never stores patient or study data."""
from __future__ import annotations
from threading import Lock
from time import monotonic
from uuid import UUID

STAGES = ('profile', 'discovery', 'analyst', 'skeptic', 'clarification')
_LOCK = Lock()
_RUNS: dict[str, dict] = {}
TTL_SECONDS = 600
MAX_RUNS = 128

def _key(run_id: UUID | None) -> str | None:
    return str(run_id) if run_id is not None else None

def _trim(now: float) -> None:
    for key, value in list(_RUNS.items()):
        if now - value['started'] > TTL_SECONDS:
            _RUNS.pop(key, None)
    if len(_RUNS) >= MAX_RUNS:
        oldest = min(_RUNS, key=lambda key: _RUNS[key]['started'])
        _RUNS.pop(oldest, None)

def start_run(run_id: UUID | None) -> None:
    key = _key(run_id)
    if key is None:
        return
    now = monotonic()
    with _LOCK:
        _trim(now)
        _RUNS[key] = {'started': now, 'phase': 'queued',
                      'completed': 0, 'total': len(STAGES), 'status': 'running'}

def mark_stage(run_id: UUID | None, stage: str) -> None:
    key = _key(run_id)
    if key is None or stage not in STAGES:
        return
    with _LOCK:
        item = _RUNS.get(key)
        if item and item['status'] == 'running':
            item['phase'] = stage
            item['completed'] = STAGES.index(stage)

def finish_run(run_id: UUID | None, *, failed: bool = False) -> None:
    key = _key(run_id)
    if key is None:
        return
    with _LOCK:
        item = _RUNS.get(key)
        if item:
            item['status'] = 'failed' if failed else 'complete'
            item['phase'] = 'failed' if failed else 'complete'
            if not failed:
                item['completed'] = len(STAGES)

def read_run(run_id: UUID) -> dict | None:
    now = monotonic()
    with _LOCK:
        _trim(now)
        item = _RUNS.get(str(run_id))
        if not item:
            return None
        return {key: value for key, value in item.items() if key != 'started'} | {
            'elapsed_seconds': round(now - item['started'], 1)
        }
