#!/usr/bin/env python3
"""Activate local Ollama without modifying or printing existing secrets."""
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parent
path = ROOT / ".env"
if ".env" not in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
    raise SystemExit("ERROR: .env must be gitignored")
original = path.read_text(encoding="utf-8") if path.exists() else ""
updates = {
    "ENABLE_LIVE_AI": "true",
    "AI_PROVIDER": "ollama",
    "OLLAMA_MODEL": "qwen3:4b",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "OPENAI_ALLOW_BILLABLE": "false",
}
token = re.search(r"^LIVE_AI_ACCESS_TOKEN=(.+)$", original, re.M)
if not token or len(token.group(1).strip()) < 16:
    updates["LIVE_AI_ACCESS_TOKEN"] = secrets.token_urlsafe(32)
lines = []
seen = set()
for line in original.splitlines():
    match = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
    key = match.group(1) if match else None
    if key in updates:
        if key not in seen:
            lines.append(key + "=" + updates[key])
            seen.add(key)
    else:
        lines.append(line)
for key, value in updates.items():
    if key not in seen:
        lines.append(key + "=" + value)
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Ollama configured in local .env; cloud billing disabled. Restart python run_local.py.")
