"""Local Gemini setup must never publish secrets or silently overwrite unrelated settings."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "configure_local_ai.py"
SPEC = importlib.util.spec_from_file_location("local_ai_config", SCRIPT)
local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local)

KEY_A = "AQ." + "A" * 40
KEY_B = "AQ." + "B" * 40


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".gitignore").write_text(".env\n.env.*\n!.env.example\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text(
        "# private Gemini setup\n"
        "ENABLE_LIVE_AI=false\n"
        "GEMINI_API_KEY=\n"
        "LIVE_AI_ACCESS_TOKEN=\n"
        "GEMINI_MODEL=gemini-2.5-flash\n"
        "GEMINI_PROFILE_MODEL=gemini-2.5-flash-lite\n"
        "CORS_ORIGINS=http://localhost:5173\n",
        encoding="utf-8",
    )
    return tmp_path


def test_creates_ignored_env_without_losing_existing_settings(project):
    token = local.configure(project, KEY_A)
    text = (project / ".env").read_text(encoding="utf-8")
    assert "ENABLE_LIVE_AI=true" in text
    assert "GEMINI_API_KEY=" + KEY_A in text
    assert "LIVE_AI_ACCESS_TOKEN=" + token in text
    assert len(token) >= 16
    assert "CORS_ORIGINS=http://localhost:5173" in text
    assert "GEMINI_PROFILE_MODEL=gemini-2.5-flash-lite" in text
    assert text.count("GEMINI_API_KEY=") == 1


def test_rotation_replaces_key_reuses_team_token_and_removes_duplicates(project):
    token = local.configure(project, KEY_A)
    env = project / ".env"
    original = env.read_text(encoding="utf-8")
    env.write_text(
        original + "GEMINI_API_KEY=PLACEHOLDER\n"
        + "OTHER_LOCAL_FLAG=keep\n",
        encoding="utf-8",
    )
    same_token = local.configure(project, KEY_B)
    updated = env.read_text(encoding="utf-8")
    assert same_token == token
    assert KEY_A not in updated
    assert "PLACEHOLDER" not in updated
    assert "GEMINI_API_KEY=" + KEY_B in updated
    assert updated.count("GEMINI_API_KEY=") == 1
    assert "OTHER_LOCAL_FLAG=keep" in updated
    assert local.configure(project, KEY_B, rotate_team_token=True) != token


def test_status_hides_secrets_and_does_not_use_network(project, capsys):
    assert not local.show_status(project)
    capsys.readouterr()
    token = local.configure(project, KEY_A)
    assert local.show_status(project)
    output = capsys.readouterr().out
    assert KEY_A not in output
    assert token not in output
    assert "Profile model:" in output
    assert "configured" in output


def test_bad_keys_and_unsafe_checkout_are_rejected(project):
    with pytest.raises(ValueError):
        local.configure(project, "YOUR_PRIVATE_GEMINI_KEY")
    with pytest.raises(ValueError):
        local.configure(project, "this key contains spaces " + "x" * 30)
    (project / ".gitignore").unlink()
    with pytest.raises(RuntimeError, match="ignore"):
        local.configure(project, KEY_B)
    assert not (project / ".env").exists()


def test_patch_preserves_user_model_selection_and_removes_managed_duplicates(project):
    (project / ".env").write_text(
        "GEMINI_MODEL=gemini-test-model\n"
        "GEMINI_MODEL=gemini-other-test-model\n"
        "MAX_AGENT_MODEL_CALLS_PER_HOUR=4\n"
        "ENABLE_LIVE_AI=false\n"
        "# user settings\n"
        "ANOTHER_SETTING=preserve\n",
        encoding="utf-8",
    )
    local.configure(project, KEY_A)
    text = (project / ".env").read_text(encoding="utf-8")
    assert text.count("GEMINI_MODEL=") == 1
    assert "GEMINI_MODEL=gemini-other-test-model" in text
    assert "MAX_AGENT_MODEL_CALLS_PER_HOUR=4" in text
    assert "ANOTHER_SETTING=preserve" in text


def test_model_selection_preserves_private_key_and_token(project):
    token = local.configure(project, KEY_A)
    local.set_models(project, 'gemini-3.8-flash', 'gemini-3.5-flash-lite')
    values = local.read_settings((project / '.env').read_text(encoding='utf8'))
    assert values['GEMINI_MODEL'] == 'gemini-3.8-flash'
    assert values['GEMINI_PROFILE_MODEL'] == 'gemini-3.5-flash-lite'
    assert values['GEMINI_API_KEY'] == KEY_A
    assert values['LIVE_AI_ACCESS_TOKEN'] == token
    with pytest.raises(ValueError):
        local.set_models(project, 'gemini-bad\\nEXTRA=1', 'gemini-3.5-flash-lite')
    assert 'EXTRA=1' not in (project / '.env').read_text(encoding='utf8')
