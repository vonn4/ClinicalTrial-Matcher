#!/usr/bin/env python3
"""Locally activate OpenAI for ClinicalTrial Matcher without exposing credentials.

The setup command is an explicit opt-in for potentially billable API requests.
ChatGPT subscriptions do not cover OpenAI API calls.
"""
from __future__ import annotations
import argparse
import getpass
from pathlib import Path
import re
import secrets
from configure_local_ai import read_settings, update_text, write_private_env, ROOT

def configure() -> None:
    path = ROOT / ".env"
    ignore = ROOT / ".gitignore"
    if not ignore.exists() or ".env" not in {line.strip() for line in ignore.read_text(encoding="utf-8").splitlines()}:
        raise RuntimeError("Refusing to configure private keys without a .gitignore entry for .env")
    original = path.read_text(encoding="utf-8") if path.exists() else (ROOT / ".env.example").read_text(encoding="utf-8")
    old = read_settings(original)
    key = old.get("OPENAI_API_KEY", "").strip()
    if not key:
        if not __import__("sys").stdin.isatty():
            raise RuntimeError("Run interactively in a VS Code terminal to enter your OpenAI key privately")
        key = getpass.getpass("OpenAI API key (hidden, never stored in GitHub): ").strip()
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{15,256}", key):
        raise ValueError("Invalid OpenAI API key format; generate a project key in OpenAI Platform")
    token = old.get("LIVE_AI_ACCESS_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", token):
        token = secrets.token_urlsafe(32)
        print("A new local browser team token was generated.")
    updates = {
        "ENABLE_LIVE_AI": "true",
        "AI_PROVIDER": "openai",
        "OPENAI_API_KEY": key,
        "OPENAI_MODEL": old.get("OPENAI_MODEL", "gpt-4.1-mini") or "gpt-4.1-mini",
        "OPENAI_PROFILE_MODEL": old.get("OPENAI_PROFILE_MODEL", "gpt-4.1-mini") or "gpt-4.1-mini",
        "OPENAI_ALLOW_BILLABLE": "true",
        "LIVE_AI_ACCESS_TOKEN": token,
    }
    write_private_env(path, update_text(original, updates))
    print("SUCCESS: local OpenAI analysis enabled. Neither key nor browser token printed.")
    print("Provider:", updates["AI_PROVIDER"], "| analysis:", updates["OPENAI_MODEL"])
    print("IMPORTANT: OpenAI API requests may incur charges. Restart python run_local.py.")
    print("To disable billable requests later, set OPENAI_ALLOW_BILLABLE=false in .env and restart.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enable OpenAI only in your local ignored .env")
    parser.add_argument("--enable", action="store_true", help="Explicitly allow potentially billable OpenAI requests")
    args = parser.parse_args()
    if not args.enable:
        parser.error("Explicit opt-in required: python configure_openai.py --enable")
    try:
        configure()
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, "ERROR: " + str(exc) + "\n")
