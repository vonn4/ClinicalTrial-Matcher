"""OpenAI activation is local-only; no key output, GitHub write or external HTTP calls."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('configure_openai', ROOT/'configure_openai.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_enable_openai_repairs_false_flag_without_exposing_secret(tmp_path, monkeypatch, capsys):
    (tmp_path/'.gitignore').write_text('.env\n', encoding='utf8')
    (tmp_path/'.env').write_text(
        'AI_PROVIDER=gemini\nENABLE_LIVE_AI=false\nOPENAI_API_KEY=sk-test-very-long-and-private-value\n'
        'LIVE_AI_ACCESS_TOKEN=existing-private-browser-token\nOPENAI_ALLOW_BILLABLE=false\n'
        'OTHER_PROJECT_SETTING=keep\n', encoding='utf8')
    monkeypatch.setattr(module,'ROOT',tmp_path)
    module.configure()
    settings=(tmp_path/'.env').read_text()
    assert 'ENABLE_LIVE_AI=true' in settings
    assert 'AI_PROVIDER=openai' in settings
    assert 'OPENAI_MODEL=gpt-4.1-mini' in settings
    assert 'OPENAI_PROFILE_MODEL=gpt-4.1-mini' in settings
    assert 'OPENAI_ALLOW_BILLABLE=true' in settings
    assert 'LIVE_AI_ACCESS_TOKEN=existing-private-browser-token' in settings
    assert 'OTHER_PROJECT_SETTING=keep' in settings
    assert settings.count('OPENAI_API_KEY=') == 1
    assert 'sk-test-very-long-and-private-value' not in capsys.readouterr().out

def test_configure_refuses_unprotected_env_file(tmp_path,monkeypatch):
    (tmp_path/'.env.example').write_text('ENABLE_LIVE_AI=false\n')
    monkeypatch.setattr(module,'ROOT',tmp_path)
    with pytest.raises(RuntimeError,match='gitignore'):
        module.configure()
    assert not (tmp_path/'.env').exists()
