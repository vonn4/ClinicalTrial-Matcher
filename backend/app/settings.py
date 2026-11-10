import os


def setting(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def enabled(name: str) -> bool:
    return setting(name).strip().lower() in {"1", "yes", "true", "on"}


# The active provider's model IDs are resolved at backend startup.
# Legacy Gemini IDs are retained as aliases for offline tests and optional rollback.
AI_PROVIDER = setting("AI_PROVIDER", "gemini").strip().lower()
AI_ANALYSIS_MODEL = (setting("OPENAI_MODEL", "gpt-4.1-mini") if AI_PROVIDER == "openai"
                     else setting("GEMINI_MODEL", "gemini-3.5-flash"))
AI_PROFILE_MODEL = (setting("OPENAI_PROFILE_MODEL", setting("OPENAI_MODEL", "gpt-4.1-mini"))
                    if AI_PROVIDER == "openai"
                    else setting("GEMINI_PROFILE_MODEL", "gemini-3.5-flash-lite"))
GEMINI_MODEL = setting("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_PROFILE_MODEL = setting("GEMINI_PROFILE_MODEL", "gemini-3.5-flash-lite")
MAX_TRIALS = min(max(int(setting("MAX_ASSESSMENTS", "3")), 1), 5)
