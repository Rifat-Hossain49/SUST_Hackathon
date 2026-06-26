"""Runtime configuration, read from environment variables only.

Secrets (e.g. ANTHROPIC_API_KEY) come from the environment at deploy time, never
from the repository. See `.env.example` for the full list.
"""
from __future__ import annotations

import os


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Service identity
    APP_NAME: str = os.getenv("APP_NAME", "codex-prelim-api")
    VERSION: str = os.getenv("APP_VERSION", "0.1.0")

    # The main analysis endpoint path. The Problem Statement will specify the
    # exact route (e.g. /analyze-ticket, /investigate). Change ONLY this value.
    MAIN_ENDPOINT: str = os.getenv("MAIN_ENDPOINT", "/analyze")

    # Reasoning thresholds (rule engine). Tune per the official judge policy.
    ESCALATE_CONFIDENCE_BELOW: float = float(os.getenv("ESCALATE_CONFIDENCE_BELOW", "0.55"))

    # ---- Optional LLM augmentation (OFF by default) -------------------------
    # The service is fully functional with rules alone (no paid API needed).
    # Flip USE_LLM=true + provide ANTHROPIC_API_KEY to let an LLM polish the
    # human-readable text. The deterministic decision/safety logic stays
    # authoritative even when the LLM is on.
    USE_LLM: bool = _flag("USE_LLM", False)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # claude-haiku-4-5: fast + cheap ($1/$5 per 1M tok), 200K ctx — the right
    # tier for a p95<=5s judge. Switch to claude-opus-4-8 for higher quality.
    MODEL_NAME: str = os.getenv("MODEL_NAME", "claude-haiku-4-5")
    # Hard per-request LLM timeout (seconds). On timeout we fall back to the
    # rule-engine text so the API never blows the 30s judge limit.
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "4.0"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "512"))

    @property
    def llm_enabled(self) -> bool:
        return self.USE_LLM and bool(self.ANTHROPIC_API_KEY)


settings = Settings()
