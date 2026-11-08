"""Command line: `uv run python -m labor_rules_assistant "Does a 6-hour shift in Oregon require a meal break?"`"""

from __future__ import annotations

import argparse
import sys

from . import config
from .client import RETRYABLE, ask


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="labor_rules_assistant",
        description="Labor-rules explainer (Stage 1: ungrounded baseline). General information, not legal advice.",
    )
    p.add_argument("question", nargs="?", help="Your question. If omitted, you'll be prompted.")
    p.add_argument("--model", help="haiku | sonnet | opus, or a full model ID (default: %(default)s)",
                   default=config.DEFAULT_MODEL)
    p.add_argument("--max-tokens", type=int, default=None, help=f"default {config.DEFAULT_MAX_TOKENS}")
    p.add_argument("--temperature", type=float, default=None, help="omit to use the model default")
    p.add_argument("--timeout", type=float, default=None, help=f"seconds, default {config.DEFAULT_TIMEOUT_S}")
    p.add_argument("--retries", type=int, default=None, help=f"SDK retries, default {config.DEFAULT_MAX_RETRIES}")
    p.add_argument("--id", dest="question_id", help="question ID to tag in the log, e.g. q01")
    p.add_argument("--quiet", action="store_true", help="don't print the stats line")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    question = args.question or input("Question: ").strip()
    if not question:
        print("No question given.", file=sys.stderr)
        return 2

    result = ask(
        question,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        timeout=args.timeout,
        max_retries=args.retries,
        question_id=args.question_id,
        on_text=lambda t: print(t, end="", flush=True),
    )
    if result.text:
        print()

    if not result.ok:
        print(f"\nERROR [{result.error_type}, {result.error_class}]: {result.error_message}", file=sys.stderr)
        if result.text:
            print("The answer above is PARTIAL: the stream failed midway.", file=sys.stderr)
        return 3 if result.error_class == RETRYABLE else 1

    if result.truncated:
        print("\nINCOMPLETE ANSWER: hit max_tokens. Don't rely on it; rerun with a higher --max-tokens.",
              file=sys.stderr)

    if not args.quiet:
        cost = f"${result.cost_usd:.5f}" if result.cost_usd is not None else "cost n/a (set prices in config.py)"
        print(
            f"\n[{result.model} · {result.input_tokens} in / {result.output_tokens} out tokens · "
            f"TTFT {result.ttft_s}s · total {result.latency_s}s · {cost} · stop={result.stop_reason}]",
            file=sys.stderr,
        )
    return 4 if result.truncated else 0
