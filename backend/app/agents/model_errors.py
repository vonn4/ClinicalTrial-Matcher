"""Safe, non-secret model-failure classification for user-facing research traces."""
from __future__ import annotations
import httpx
from pydantic import ValidationError
from ..llm import ModelUnavailable
from .budget import AgentBudgetExceeded

def explain_model_error(exc: Exception) -> dict[str, str | int]:
    if isinstance(exc, httpx.HTTPStatusError):
        code=exc.response.status_code
        reasons={
            400:('bad_request','Provider rejected the request; check model and JSON schema.'),
            401:('authentication','Gemini rejected the API key; rotate/check your Google AI Studio key.'),
            403:('access_denied','The project cannot access this model; check API restrictions and billing tier.'),
            404:('model_unavailable','This model is not available to the project; check available models.'),
            429:('quota_exceeded','Gemini quota was exhausted; check your project free-tier limits.'),
            500:('provider_error','Gemini service returned a server error.'),
            502:('provider_error','Gemini service returned a server error.'),
            503:('provider_unavailable','Gemini service is temporarily unavailable.'),
        }
        category, message = reasons.get(code,('provider_http_error','Gemini request failed.'))
        return {'model_error':category,'model_http_status':code,'model_help':message}
    if isinstance(exc, httpx.TimeoutException):
        return {'model_error':'timeout','model_help':'Gemini request timed out; retry with a smaller study.'}
    if isinstance(exc, httpx.RequestError):
        return {'model_error':'network','model_help':'Could not reach Gemini; check network access.'}
    if isinstance(exc, AgentBudgetExceeded):
        return {'model_error':'local_budget','model_help':'Local hourly or per-run inference budget was reached.'}
    if isinstance(exc, ModelUnavailable):
        return {'model_error':'invalid_response','model_help':'Gemini returned missing/invalid JSON or was not configured.'}
    if isinstance(exc, ValidationError):
        return {'model_error':'schema_validation','model_help':'Gemini response did not match the required judgment schema.'}
    return {'model_error':'model_step_error','model_help':'Model step failed; inspect local provider diagnostics.'}
