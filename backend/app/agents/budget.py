"""Hard per-run and process-wide call guards, independent of workflow request counts.

All model calls from the new agent orchestration pass through this adapter.
A failure reserves a slot rather than retrying without limit. No billing fallback.
"""
import asyncio
import httpx
import os
import time
from collections import deque
from ..llm import generate_json, ModelUnavailable

_lock = asyncio.Lock()
_calls = deque()

class AgentBudgetExceeded(RuntimeError):
    pass

class AgentBudget:
    def __init__(self, maximum: int = 9):
        self.maximum = min(maximum, 9)
        self.calls = 0
        # Per-workflow 503 breaker; do not burn the remaining cap trying
        # multiple studies after repeated upstream service failures.
        self._unavailable_error: httpx.HTTPStatusError | None = None

    async def generate(self, *, model: str, system: str, payload: dict) -> dict:
        # A missing key/disabled provider is NOT counted as a completed or attempted API call.
        provider = os.getenv('AI_PROVIDER', 'gemini').strip().lower()
        if os.getenv('ENABLE_LIVE_AI','').strip().lower() not in {'true','1','yes','on'}:
            raise ModelUnavailable('ENABLE_LIVE_AI=true is required')
        if provider == 'ollama':
            pass  # Loopback inference requires no API key or billable opt-in.
        elif provider == 'openai':
            if not os.getenv('OPENAI_API_KEY','').strip():
                raise ModelUnavailable('OPENAI_API_KEY is required')
            if os.getenv('OPENAI_ALLOW_BILLABLE','').strip().lower() not in {'true','1','yes','on'}:
                raise ModelUnavailable('Explicit OPENAI_ALLOW_BILLABLE=true is required; API calls may incur charges')
        elif provider == 'gemini':
            if not os.getenv('GEMINI_API_KEY','').strip():
                raise ModelUnavailable('GEMINI_API_KEY is required')
        else:
            raise ModelUnavailable('Unknown AI_PROVIDER')
        if self._unavailable_error is not None:
            raise self._unavailable_error
        # Only HTTP 503 gets one short bounded retry. Every outbound attempt
        # consumes both per-run and hourly budget. Never retry invalid schemas,
        # authentication errors or 429 quota failures.
        for retry in range(2):
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
            try:
                return await generate_json(model=model, system=system, payload=payload)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 503:
                    raise
                if retry or self.calls >= self.maximum:
                    self._unavailable_error = exc
                    raise
                await asyncio.sleep(1.0)
        raise RuntimeError('Unreachable provider retry state')
