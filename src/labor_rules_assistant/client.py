"""The ONLY module that calls the Anthropic API.

Everything else goes through `ask()`. That gives one choke point for:
- timeouts and retry policy
- error classification (retryable vs. fatal)
- timing (time to first token, total latency)
- token usage and cost logging for every call, including failed ones
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Callable

import anthropic

from . import config
from .cost_log import log_call
from .prompts import SYSTEM_PROMPT

RETRYABLE = "retryable"  # transient: the SDK already retried; trying later may work
FATAL = "fatal"  # retrying won't help: fix config, input or account


@dataclass
class AskResult:
    call_id: str
    question_id: str | None
    model: str
    text: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    ttft_s: float | None
    latency_s: float
    cost_usd: float | None
    error_type: str | None = None
    error_class: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_type is None

    @property
    def truncated(self) -> bool:
        """True if the model hit max_tokens: the answer is incomplete."""
        return self.stop_reason == "max_tokens"


def classify_error(exc: anthropic.AnthropicError) -> tuple[str, str, str]:
    """Map an SDK exception to (error_type, error_class, user-facing message).

    Order matters: subclasses must be checked before their parents.
    """
    detail = getattr(exc, "message", None) or str(exc)

    # Timeout is a subclass of APIConnectionError, so it goes first.
    if isinstance(exc, anthropic.APITimeoutError):
        return "timeout", RETRYABLE, "The request timed out (after the SDK's retries). Try again, or raise the timeout."
    if isinstance(exc, anthropic.APIConnectionError):
        return "connection", RETRYABLE, "Couldn't reach the API. Check your network connection and try again."
    # Spend-limit errors are 429s, but retrying never helps: it's a budget decision.
    if isinstance(exc, anthropic.EnforcedSpendLimitReachedError):
        return "spend_limit", FATAL, "Your spend limit has been reached. Raise it in the Console if this is expected."
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limit", RETRYABLE, "Rate limited (after the SDK's retries). Wait a minute and try again."
    if isinstance(exc, anthropic.OverloadedError):
        return "overloaded", RETRYABLE, "The API is temporarily overloaded. Try again shortly."
    if isinstance(exc, anthropic.InternalServerError):
        return "server_error", RETRYABLE, "The API returned a server error. Try again shortly."
    if isinstance(exc, anthropic.AuthenticationError):
        return "auth", FATAL, "API key missing, invalid or revoked. Check ANTHROPIC_API_KEY in .env."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "permission", FATAL, "This key isn't allowed to do that (check its workspace and permissions)."
    if isinstance(exc, anthropic.NotFoundError):
        return "not_found", FATAL, "Not found: most likely a misspelled model name."
    if isinstance(exc, anthropic.BadRequestError):
        return "bad_request", FATAL, f"The API rejected the request: {detail}"
    if isinstance(exc, anthropic.APIStatusError):
        return f"http_{exc.status_code}", FATAL, f"Unexpected API error ({exc.status_code}): {detail}"
    # Raised before any request is sent, e.g. no API key configured at all.
    return "client_config", FATAL, f"Client configuration problem: {detail}"


def ask(
    question: str,
    *,
    system: str = SYSTEM_PROMPT,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    question_id: str | None = None,
    on_text: Callable[[str], None] | None = None,
) -> AskResult:
    """Ask one question with streaming. Never raises for API errors: check result.ok.

    `on_text` receives each text chunk as it streams (the CLI prints them).
    """
    model = config.resolve_model(model)
    max_tokens = max_tokens if max_tokens is not None else config.DEFAULT_MAX_TOKENS
    temperature = temperature if temperature is not None else config.DEFAULT_TEMPERATURE
    timeout = timeout if timeout is not None else config.DEFAULT_TIMEOUT_S
    max_retries = max_retries if max_retries is not None else config.DEFAULT_MAX_RETRIES

    params: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": question}],
    }
    if temperature is not None:
        params["temperature"] = temperature

    call_id = uuid.uuid4().hex[:12]
    chunks: list[str] = []
    ttft: float | None = None
    start = time.perf_counter()

    def _failed(error_type: str, error_class: str, message: str) -> AskResult:
        return AskResult(
            call_id=call_id,
            question_id=question_id,
            model=model,
            text="".join(chunks),  # anything streamed before the failure
            stop_reason=None,
            input_tokens=None,
            output_tokens=None,
            ttft_s=_round(ttft),
            latency_s=_round(time.perf_counter() - start),
            cost_usd=None,
            error_type=error_type,
            error_class=error_class,
            error_message=message,
        )

    # Without a key the SDK raises a bare TypeError mid-request; fail fast with a clear message instead.
    if not os.getenv("ANTHROPIC_API_KEY"):
        result = _failed("no_api_key", FATAL, "ANTHROPIC_API_KEY is not set. Add it to .env (see .env.example).")
        _log(result, question, max_tokens, temperature, timeout, max_retries)
        return result

    try:
        client = anthropic.Anthropic(timeout=timeout, max_retries=max_retries)
        with client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                if ttft is None:
                    ttft = time.perf_counter() - start
                chunks.append(text)
                if on_text:
                    on_text(text)
            final = stream.get_final_message()

        usage = final.usage
        result = AskResult(
            call_id=call_id,
            question_id=question_id,
            model=model,
            text="".join(chunks),
            stop_reason=final.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            ttft_s=_round(ttft),
            latency_s=_round(time.perf_counter() - start),
            cost_usd=config.estimate_cost(model, usage.input_tokens, usage.output_tokens),
        )
    except anthropic.AnthropicError as exc:
        result = _failed(*classify_error(exc))

    _log(result, question, max_tokens, temperature, timeout, max_retries)
    return result


def _log(result: AskResult, question: str, max_tokens: int, temperature: float | None,
         timeout: float, max_retries: int) -> None:
    record = asdict(result)
    record.pop("text")  # answers go to outputs/, not the log
    record.update(
        {
            "question": question[:200],
            "answer_chars": len(result.text),
            "truncated": result.truncated,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout_s": timeout,
            "max_retries": max_retries,
        }
    )
    log_call(record)


def _round(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None
