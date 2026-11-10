import os


def setting(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def enabled(name: str) -> bool:
    return setting(name).strip().lower() in {"1", "yes", "true", "on"}


GEMINI_MODEL = setting("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_PROFILE_MODEL = setting("GEMINI_PROFILE_MODEL", "gemini-3.5-flash-lite")
MAX_TRIALS = min(max(int(setting("MAX_ASSESSMENTS", "3")), 1), 5)
