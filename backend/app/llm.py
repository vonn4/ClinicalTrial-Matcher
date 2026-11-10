"""Opt-in Gemini REST adapter. No API calls in replay or CI mode."""
import json
import os
import re
import httpx

class ModelUnavailable(RuntimeError):pass

# Keep the Analyst/Skeptic schema deliberately small: short, bounded criterion
# chunks are easier for Gemini to satisfy than entire multi-page study protocols.
# Only this validated role receives structured-output restrictions.
JUDGMENT_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'assessments': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'criterion_id': {'type': 'string'},
                    'status': {'type': 'string', 'enum': ['met', 'not_met', 'unknown', 'clinical_review']},
                    'exclusion_triggered': {'type': ['boolean', 'null']},
                    'explanation': {'type': 'string'},
                    'patient_evidence': {'type': 'array', 'items': {'type': 'string'}},
                    'question_for_doctor': {'type': ['string', 'null']},
                },
                'required': ['criterion_id', 'status', 'exclusion_triggered',
                             'explanation', 'patient_evidence', 'question_for_doctor'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['assessments'],
    'additionalProperties': False,
}


async def generate_json(*,model: str,system: str,payload: dict) -> dict:
    provider = os.getenv('AI_PROVIDER', 'gemini').strip().lower()
    if provider == 'openai':
        return await generate_openai_json(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
                                          system=system, payload=payload)
    if provider != 'gemini':
        raise ModelUnavailable('AI_PROVIDER must be gemini or openai')
    if os.getenv('ENABLE_LIVE_AI','').strip().lower() not in {'1','true','yes','on'}:
        raise ModelUnavailable('Live model inference is disabled by default; set ENABLE_LIVE_AI=true on a trusted backend')
    key=os.getenv('GEMINI_API_KEY','')
    if not key:
        raise ModelUnavailable('GEMINI_API_KEY is not configured; add it to the project .env file')
    if not re.fullmatch(r'[a-zA-Z0-9._-]+',model):
        raise ValueError('Invalid model name')
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    body={
        'systemInstruction':{'parts':[{'text':system}]},
        'contents':[{'role':'user','parts':[{'text':json.dumps(payload,ensure_ascii=False)}]}],
        'generationConfig':{'responseMimeType':'application/json','temperature':0.0,'maxOutputTokens':8192},
    }
    if payload.get('role') in {'primary_analyst', 'independent_skeptic'}:
        # Google's v1beta generateContent supports responseJsonSchema with JSON MIME.
        # Schema constrains format; source/patient evidence is still verified downstream.
        body['generationConfig']['responseJsonSchema'] = JUDGMENT_RESPONSE_SCHEMA
    async with httpx.AsyncClient(timeout=55,follow_redirects=False) as client:
        response=await client.post(url,headers={'x-goog-api-key':key,'Content-Type':'application/json'},json=body)
        response.raise_for_status()
        data=response.json()
    try:
        parts=data['candidates'][0]['content']['parts']
        output=''.join(p.get('text','') for p in parts)
        return json.loads(output)
    except (KeyError,IndexError,TypeError,json.JSONDecodeError) as exc:
        raise ModelUnavailable('Model returned missing or invalid JSON') from exc


async def generate_openai_json(*, model: str, system: str, payload: dict) -> dict:
    """Explicitly opted-in OpenAI JSON adapter; no key ever goes to browser/GitHub."""
    if os.getenv('ENABLE_LIVE_AI', '').strip().lower() not in {'1','true','yes','on'}:
        raise ModelUnavailable('Live AI disabled')
    if os.getenv('OPENAI_ALLOW_BILLABLE', '').strip().lower() not in {'1','true','yes','on'}:
        raise ModelUnavailable('OpenAI API calls require OPENAI_ALLOW_BILLABLE=true; API use may incur charges')
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise ModelUnavailable('OPENAI_API_KEY is not configured')
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', model):
        raise ValueError('Invalid OpenAI model name')
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
        ],
        'response_format': {'type': 'json_object'},
        'temperature': 0,
        'max_completion_tokens': 4096,
    }
    async with httpx.AsyncClient(timeout=65, follow_redirects=False) as client:
        response = await client.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
            json=body,
        )
        response.raise_for_status()
        data = response.json()
    try:
        output = data['choices'][0]['message']['content']
        result = json.loads(output)
        if not isinstance(result, dict):
            raise ValueError('Expected JSON object')
        return result
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ModelUnavailable('OpenAI returned missing or invalid JSON') from exc
