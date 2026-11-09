"""Hard per-run and process-wide call guards, independent of workflow request counts.

All model calls from the new agent orchestration pass through this adapter.
A failure reserves a slot rather than retrying without limit. No billing fallback.
"""
import asyncio
import os
import time
from collections import deque
from ..llm import generate_json

_lock = asyncio.Lock()
_calls = deque()

class AgentBudgetExceeded(RuntimeError):
    pass

class AgentBudget:
    def __init__(self, maximum: int = 9):
        self.maximum = min(maximum, 9)
        self.calls = 0

    async def generate(self, *, model: str, system: str, payload: dict) -> dict:
        async with _lock:
            if self.calls >= self.maximum:
                raise AgentBudgetExceeded('Per-run model-call budget exhausted')
            now = time.monotonic()
            while _calls and now - _calls[0] >= 3600:
                _calls.popleft()
            try:
                hourly = min(max(int(os.getenv('MAX_AGENT_MODEL_CALLS_PER_HOUR', '24')), 1), 60)
            except ValueError:
                hourly = 24
            if len(_calls) >= hourly:
                raise AgentBudgetExceeded('Model-call budget exhausted; no paid fallback')
            self.calls += 1
            _calls.append(now)
        return await generate_json(model=model, system=system, payload=payload)
