"""Ollama launcher diagnostics use loopback API without requiring cloud keys."""
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ollama_launcher',ROOT/'run_local.py')
launcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

def test_ollama_check_and_model_listing_are_offline(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    (tmp_path/'.env').write_text(
        'AI_PROVIDER=ollama\nENABLE_LIVE_AI=true\n'
        'OLLAMA_MODEL=qwen3:4b\n'
        'LIVE_AI_ACCESS_TOKEN=synthetic-team-token-for-tests\n'
        'OPENAI_ALLOW_BILLABLE=false\n',encoding='utf8')
    calls=[]
    def respond(url,**kwargs):
        calls.append(url)
        if url.endswith('/api/tags'):
            return {'models':[{'name':'qwen3:4b'},{'name':'qwen3:1.7b'}]}
        return {
            'model_provider':'Ollama (local)','analysis_model':'qwen3:4b',
            'profile_model':'qwen3:4b','model_ready':True,
        }
    monkeypatch.setattr(launcher,'request_json',respond)
    launcher.verify_model_readiness('http://127.0.0.1:8000')
    launcher.list_available_models()
    output=capsys.readouterr().out
    assert 'Ollama server and installed model' in output
    assert 'qwen3:4b' in output
    assert 'not required (Ollama)' in output
    assert all(url.startswith('http://127.0.0.1:') for url in calls)
    assert 'OPENAI_API_KEY' not in output

def test_ollama_check_detects_missing_installed_model(monkeypatch,tmp_path):
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    (tmp_path/'.env').write_text(
        'AI_PROVIDER=ollama\nENABLE_LIVE_AI=true\n'
        'OLLAMA_MODEL=qwen3:4b\nLIVE_AI_ACCESS_TOKEN=synthetic-team-token-for-tests\n',
        encoding='utf8')
    def respond(url,**kwargs):
        if url.endswith('/api/tags'):
            return {'models':[]}
        return {'model_provider':'Ollama (local)','analysis_model':'qwen3:4b',
                'model_ready':True}
    monkeypatch.setattr(launcher,'request_json',respond)
    import pytest
    with pytest.raises(RuntimeError,match='ollama pull qwen3:4b'):
        launcher.verify_model_readiness('http://127.0.0.1:8000')
