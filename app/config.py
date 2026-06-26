"""Runtime configuration, read from environment variables only.

Secrets such as GEMINI_API_KEY come from the environment at deploy time, never
from the repository. See `.env.example` for the full list.
"""
from __future__ import annotations

import os


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Service identity
    APP_NAME: str = os.getenv("APP_NAME", "queuestorm-investigator")
    VERSION: str = os.getenv("APP_VERSION", "1.0.0")

    # Main analysis endpoint path. Fixed by the problem statement.
    MAIN_ENDPOINT: str = os.getenv("MAIN_ENDPOINT", "/analyze-ticket")

    # High-value threshold (BDT). At or above this, a case is flagged for human
    # review regardless of type. Kept above the largest public sample (15,000)
    # so it never contradicts the worked cases.
    HIGH_VALUE_THRESHOLD: float = float(os.getenv("HIGH_VALUE_THRESHOLD", "50000"))

    # ---- Optional Gemini augmentation (OFF by default) ----------------------
    # The service scores fully with rules alone. Flip USE_LLM=true and provide
    # GEMINI_API_KEY to let Gemini rephrase the three free-text fields. The
    # deterministic investigator remains authoritative for every scored field.
    USE_LLM: bool = _flag("USE_LLM", False)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-3.5-flash")
    GEMINI_API_BASE_URL: str = os.getenv(
        "GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    )

    # Fallback model chain tried in order when the primary model returns a
    # quota/rate-limit error (HTTP 429/413). Smaller models sit under different
    # free-tier quotas, so this buys resilience at near-zero extra latency
    # (quota errors are returned in milliseconds). Timeout errors skip the chain
    # entirely so the total wall-clock time is still bounded by LLM_TIMEOUT_SECONDS.
    LLM_FALLBACK_MODELS: list[str] = [
        m.strip()
        for m in os.getenv(
            "LLM_FALLBACK_MODELS", "gemini-2.0-flash-lite,gemini-1.5-flash-8b"
        ).split(",")
        if m.strip()
    ]

    # Hard per-request LLM timeout shared across the entire fallback chain.
    # On timeout we stop immediately and return deterministic text.
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "4.0"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "600"))

    @property
    def llm_enabled(self) -> bool:
        return self.USE_LLM and bool(self.GEMINI_API_KEY)


settings = Settings()
