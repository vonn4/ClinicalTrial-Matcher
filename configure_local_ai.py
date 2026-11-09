#!/usr/bin/env python3
"""Secure, interactive, LOCAL configuration for the optional Gemini five-agent workflow.

Never commit .env or pass credentials as shell arguments. This script makes
no network requests. Rotate any API key previously displayed in a screenshot.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
API_KEY = re.compile(r"[A-Za-z0-9._-]{20,256}\Z")
SETTINGS = (
    "ENABLE_LIVE_AI",
    "GEMINI_API_KEY",
    "LIVE_AI_ACCESS_TOKEN",
    "GEMINI_MODEL",
    "GEMINI_PROFILE_MODEL",
    "MAX_AGENT_MODEL_CALLS_PER_HOUR",
    "MAX_LIVE_AI_REQUESTS_PER_HOUR",
)
DEFAULTS = {
    "GEMINI_MODEL": "gemini-2.5-flash",
    "GEMINI_PROFILE_MODEL": "gemini-2.5-flash-lite",
    "MAX_AGENT_MODEL_CALLS_PER_HOUR": "24",
    "MAX_LIVE_AI_REQUESTS_PER_HOUR": "12",
}


def read_settings(source: str) -> dict[str, str]:
    """Read basic dotenv assignments without evaluating code or expanding variables."""
    parsed = {}
    for line in source.splitlines():
        match = ASSIGNMENT.match(line)
        if match:
            value = line[match.end():].strip()
            parsed[match.group(1)] = value.strip("\"'")
    return parsed


def normalize_api_key(key: str) -> str:
    key = key.strip()
    if not API_KEY.fullmatch(key) or key.upper().startswith(("YOUR_", "PASTE_", "REPLACE_")):
        raise ValueError("Enter a newly generated Google AI Studio API key (no placeholders or spaces).")
    return key


def update_text(original: str, changes: dict[str, str]) -> str:
    """Patch managed variables once, preserving unrelated env settings and comments."""
    lines = []
    seen = set()
    for line in original.splitlines():
        match = ASSIGNMENT.match(line)
        name = match.group(1) if match else None
        if name in changes:
            if name not in seen:
                lines.append(name + "=" + changes[name])
                seen.add(name)
            # Remove duplicate managed settings so last-value-wins cannot override us.
        else:
            lines.append(line)
    for name in SETTINGS:
        if name in changes and name not in seen:
            lines.append(name + "=" + changes[name])
    return "\n".join(lines).rstrip("\n") + "\n"


def write_private_env(path: Path, content: str) -> None:
    """Atomic write; restrict new file on POSIX, use user's Windows file permissions."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n",
            dir=path.parent, prefix=".env-", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
        if os.name != "nt":
            temp_path.chmod(0o600)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def configure(root: Path, new_key: str, *, rotate_team_token: bool = False) -> str:
    """Create/update ignored .env; return team token for local UI entry, not the API key."""
    key = normalize_api_key(new_key)
    ignore = root / ".gitignore"
    if not ignore.exists() or ".env" not in {line.strip() for line in ignore.read_text(encoding="utf-8").splitlines()}:
        raise RuntimeError("Refusing to write a key: this project must explicitly ignore .env in .gitignore")
    env = root / ".env"
    template = root / ".env.example"
    if not env.exists() and not template.exists():
        raise FileNotFoundError("Missing .env.example; run this command from a complete repository checkout.")
    text = env.read_text(encoding="utf-8") if env.exists() else template.read_text(encoding="utf-8")
    current = read_settings(text)
    token = current.get("LIVE_AI_ACCESS_TOKEN", "")
    if rotate_team_token or len(token) < 16 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        token = secrets.token_urlsafe(32)
    changes = {
        "ENABLE_LIVE_AI": "true",
        "GEMINI_API_KEY": key,
        "LIVE_AI_ACCESS_TOKEN": token,
    }
    for name, default in DEFAULTS.items():
        candidate = current.get(name, "")
        if name.startswith("MAX_"):
            try:
                if int(candidate) < 1:
                    candidate = ""
            except ValueError:
                candidate = ""
        changes[name] = candidate or default
    write_private_env(env, update_text(text, changes))
    return token


def show_status(root: Path) -> bool:
    """Display only presence and non-secret model identifiers; no provider calls."""
    env = root / ".env"
    if not env.exists():
        print("NOT CONFIGURED: project .env does not exist. Run: python configure_local_ai.py")
        return False
    values = read_settings(env.read_text(encoding="utf-8"))
    checks = {
        "ENABLE_LIVE_AI": values.get("ENABLE_LIVE_AI", "").lower() in {"true", "1", "yes", "on"},
        "GEMINI_API_KEY": bool(API_KEY.fullmatch(values.get("GEMINI_API_KEY", ""))),
        "LIVE_AI_ACCESS_TOKEN": len(values.get("LIVE_AI_ACCESS_TOKEN", "")) >= 16,
    }
    for name, ready in checks.items():
        print(name + ": " + ("configured" if ready else "missing or disabled"))
    print("Profile model:", values.get("GEMINI_PROFILE_MODEL") or DEFAULTS["GEMINI_PROFILE_MODEL"])
    print("Analysis/skeptic model:", values.get("GEMINI_MODEL") or DEFAULTS["GEMINI_MODEL"])
    print("No model requests were sent. Check live backend with python run_local.py --check-ai.")
    return all(checks.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely configure optional local Gemini inference")
    parser.add_argument("--status", action="store_true", help="Inspect local .env without revealing credentials")
    parser.add_argument("--rotate-team-token", action="store_true", help="Also replace the local UI team token")
    args = parser.parse_args(argv)
    if args.status:
        return 0 if show_status(ROOT) else 1
    if not sys.stdin.isatty():
        print("ERROR: Run interactively in the VS Code terminal; never pass a key on the command line.", file=sys.stderr)
        return 2
    print("Use a NEW Google AI Studio key. Revoke any key previously shown in a screenshot.")
    print("Verify the associated project is on an eligible free tier with billing disabled.")
    print("Input will be hidden; no key or token is committed or sent to this script's author.")
    try:
        api_key = getpass.getpass("Paste NEW Gemini API key (hidden): ")
        token = configure(ROOT, api_key, rotate_team_token=args.rotate_team_token)
    except (ValueError, FileNotFoundError, RuntimeError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nConfiguration cancelled.", file=sys.stderr)
        return 130
    print("\nConfigured the ignored project-root .env for model-assisted analysis.")
    print("LOCAL TEAM ACCESS TOKEN (enter this in the browser; NOT the Google API key):")
    print(token)
    print("Keep that token private. Restart the app with python run_local.py.")
    print("Then, in a second terminal: python run_local.py --check-ai")
    print("That check confirms configuration only; real model invocation is verified by the agent trace.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
