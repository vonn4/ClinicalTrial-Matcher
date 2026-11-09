"""PowerShell-friendly launcher diagnosis; no actual Gemini calls or credentials."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("local_launcher", ROOT/"run_local.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


@pytest.fixture
def fake_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    (tmp_path/".env").write_text(
        "ENABLE_LIVE_AI=true\n"
        "GEMINI_API_KEY=" + "A" * 35 + "\n"
        "LIVE_AI_ACCESS_TOKEN=" + "T" * 25 + "\n",
        encoding="utf-8")
    return tmp_path


def test_check_ai_detects_stale_backend_after_env_changes(fake_configuration, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "request_json", lambda *a, **k:{
        "agent_roles":["profile","discovery","analyst","skeptic","clarification"],
        "model_provider":"Google Gemini",
        "model_ready":False,
        "model_readiness_message":"ENABLE_LIVE_AI is false in the backend environment"
    })
    with pytest.raises(RuntimeError, match="STALE BACKEND CONFIGURATION") as exc:
        launcher.verify_model_readiness("http://127.0.0.1:8000")
    assert "Ctrl+C" in str(exc.value)
    assert "Local AI enabled: True" in capsys.readouterr().out
    assert "GEMINI_API_KEY=" not in str(exc.value)


def test_check_ai_reports_local_and_running_backend_ready(fake_configuration, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "request_json", lambda *a, **k:{
        "agent_roles":["profile","discovery","analyst","skeptic","clarification"],
        "model_provider":"Google Gemini",
        "model_ready":True,
        "profile_model":"gemini-2.5-flash-lite",
        "analysis_model":"gemini-2.5-flash",
    })
    launcher.verify_model_readiness("http://127.0.0.1:8000")
    output=capsys.readouterr().out
    assert "READY: local .env and running backend" in output
    assert "GEMINI_API_KEY=" not in output
    assert "TTTTTTTT" not in output


def test_check_ai_refuses_old_backend_when_local_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher, "request_json", lambda *a, **k:{
        "agent_roles":["profile"], "model_provider":"Google Gemini",
        "model_ready":False,
    })
    with pytest.raises(RuntimeError, match="LOCAL CONFIGURATION INCOMPLETE"):
        launcher.verify_model_readiness("http://127.0.0.1:8000")


def test_check_ai_missing_running_backend_has_actionable_instructions(fake_configuration, monkeypatch):
    from urllib.error import URLError
    def unavailable(*a, **k):
        raise URLError("network not available")
    monkeypatch.setattr(launcher, "request_json", unavailable)
    with pytest.raises(RuntimeError, match="No matching backend was reachable"):
        launcher.verify_model_readiness("http://127.0.0.1:8000")
