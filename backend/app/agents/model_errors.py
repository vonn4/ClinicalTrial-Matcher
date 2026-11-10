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
            503:('provider_unavailable','Gemini service is temporarily overloaded (HTTP 503). This is a Google-side failure; retry later or select another verified free-tier model in your local .env. No paid fallback is used.'),
        }
        category, message = reasons.get(code,('provider_http_error','AI provider request failed.'))
        if __import__('os').getenv('AI_PROVIDER', 'gemini').strip().lower() == 'openai':
            openai_reasons = {
                400: ('bad_request', 'OpenAI rejected model parameters or JSON request.'),
                401: ('authentication', 'OpenAI API key was rejected.'),
                403: ('access_denied', 'OpenAI project lacks permission for this model.'),
                404: ('model_unavailable', 'OpenAI model not available to this project.'),
                429: ('quota_exceeded', 'OpenAI rate limit or billing quota exceeded; no automatic fallback.'),
                500: ('provider_error', 'OpenAI returned a server error.'),
                502: ('provider_error', 'OpenAI returned a server error.'),
                503: ('provider_unavailable', 'OpenAI temporarily unavailable; retry later.'),
            }
            category, message = openai_reasons.get(code, ('provider_http_error', 'OpenAI request failed.'))
        return {'model_error':category,'model_http_status':code,'model_help':message}
    if isinstance(exc, httpx.TimeoutException):
        return {'model_error':'timeout','model_help':'AI provider request timed out; retry with a smaller study.'}
    if isinstance(exc, httpx.RequestError):
        return {'model_error':'network','model_help':'Could not reach AI provider; check network access.'}
    if isinstance(exc, AgentBudgetExceeded):
        return {'model_error':'local_budget','model_help':'Local hourly or per-run inference budget was reached.'}
    if isinstance(exc, ModelUnavailable):
        return {'model_error':'invalid_response','model_help':'AI provider returned missing/invalid JSON or was not configured.'}
    if isinstance(exc, ValidationError):
        return {'model_error':'schema_validation','model_help':'AI provider response did not match the required judgment schema.'}
    return {'model_error':'model_step_error','model_help':'Model step failed; inspect local provider diagnostics.'}
