"""Central configuration. Every tunable value lives here and nowhere else.

Values can be overridden with environment variables (or .env), which makes the
Day 2 failure drills a one-liner, e.g. `LRA_TIMEOUT_S=1 uv run python -m labor_rules_assistant "..."`.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# load_dotenv does NOT override variables already set in the shell, so an inline
# `ANTHROPIC_API_KEY=bad-key uv run ...` wins over .env (handy for the auth drill).
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
MODELS: dict[str, str] = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
}


def resolve_model(name: str | None) -> str:
    """Accept a short alias (haiku/sonnet/opus) or a full model ID."""
    if not name:
        return DEFAULT_MODEL
    return MODELS.get(name.lower(), name)


def _optional_float(var: str) -> float | None:
    raw = os.getenv(var)
    return float(raw) if raw not in (None, "") else None


DEFAULT_MODEL: str = os.getenv("LRA_MODEL", MODELS["sonnet"])
DEFAULT_MAX_TOKENS: int = int(os.getenv("LRA_MAX_TOKENS", "4000"))
# None = don't send temperature; the model uses its default. Day 1 compares 0 vs 1.
DEFAULT_TEMPERATURE: float | None = _optional_float("LRA_TEMPERATURE")
DEFAULT_TIMEOUT_S: float = float(os.getenv("LRA_TIMEOUT_S", "60"))
# The SDK retries 408/409/429/5xx and connection errors itself, with backoff.
# We set the count explicitly so it is a decision, not a default.
DEFAULT_MAX_RETRIES: int = int(os.getenv("LRA_MAX_RETRIES", "2"))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LOG_PATH: Path = PROJECT_ROOT / "logs" / "calls.jsonl"
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
SEED_CSV: Path = PROJECT_ROOT / "evals" / "seed_questions.csv"

# ---------------------------------------------------------------------------
# Prices (USD per 1M tokens)
# Copy these from the official pricing page — do not fill them from memory —
# and record the date you copied them. Until filled, cost is logged as null.
# ---------------------------------------------------------------------------
PRICES_AS_OF: str | None = None  # e.g. "2026-11-17"
PRICES_PER_MTOK: dict[str, dict[str, float | None]] = {
    "claude-haiku-5-5": {"input": None, "output": None},
    "claude-sonnet-5-5": {"input": None, "output": None},
    "claude-opus-5-5": {"input": None, "output": None},
}


def estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """Estimated USD cost of one call, or None if prices aren't configured."""
    price = PRICES_PER_MTOK.get(model)
    if not price or price["input"] is None or price["output"] is None:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    return round((input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000, 6)
