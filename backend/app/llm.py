"""Opt-in Gemini REST adapter. No API calls in replay or CI mode."""
import json
import os
import re
import httpx
from pydantic import ValidationError

class ModelUnavailable(RuntimeError):pass

async def generate_json(*,model: str,system: str,payload: dict) -> dict:
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
