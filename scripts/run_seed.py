"""Day 3: run the seed questions and write a verification sheet.

Run:  uv run python scripts/run_seed.py --model sonnet
      uv run python scripts/run_seed.py --model haiku --ids q01,q03,q11   (Day 1 tier comparison)

Writes outputs/run_<model>_<timestamp>.csv with the model's answers filled in and
the verification columns (verdict, official_source_url, date_checked, notes) left
blank for you. Copy your verdicts back into evals/seed_questions.csv when done.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime

from labor_rules_assistant import config
from labor_rules_assistant.client import ask
from labor_rules_assistant.prompts import classify_reply, confidence_level, parse_sections

VERDICTS = "correct | partially correct | wrong | outdated | fabricated citation | correctly refused | wrongly refused"

OUT_COLUMNS = [
    "id", "question", "category", "expected_behavior", "observed_behavior", "behavior_match",
    "model", "model_answer", "cited_rule", "confidence",
    "stop_reason", "input_tokens", "output_tokens", "ttft_s", "latency_s", "cost_usd", "error",
    "verdict", "official_source_url", "date_checked", "notes",
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=config.DEFAULT_MODEL, help="haiku | sonnet | opus, or a full model ID")
    p.add_argument("--ids", help="comma-separated question IDs to run (default: all)")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    args = p.parse_args()

    model = config.resolve_model(args.model)
    with config.SEED_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        rows = [r for r in rows if r["id"] in wanted]
    if not rows:
        print("No matching questions.", file=sys.stderr)
        return 2

    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    short = next((k for k, v in config.MODELS.items() if v == model), model)
    out_path = config.OUTPUTS_DIR / f"run_{short}_{datetime.now():%Y%m%d-%H%M}.csv"

    out_rows, errors = [], 0
    for n, row in enumerate(rows, 1):
        print(f"[{n}/{len(rows)}] {row['id']}: {row['question'][:70]}", file=sys.stderr)
        r = ask(row["question"], model=model, question_id=row["id"],
                temperature=args.temperature, max_tokens=args.max_tokens)
        observed = "error" if not r.ok else classify_reply(r.text)
        if r.truncated:
            observed = "truncated"
        errors += 0 if r.ok else 1
        expected = row.get("expected_behavior", "")
        out_rows.append({
            "id": row["id"],
            "question": row["question"],
            "category": row.get("category", ""),
            "expected_behavior": expected,
            "observed_behavior": observed,
            "behavior_match": _behavior_match(expected, observed),
            "model": model,
            "model_answer": r.text.strip(),
            "cited_rule": parse_sections(r.text).get("Rule the model believes applies", ""),
            "confidence": confidence_level(r.text) or "",
            "stop_reason": r.stop_reason or "",
            "input_tokens": r.input_tokens if r.input_tokens is not None else "",
            "output_tokens": r.output_tokens if r.output_tokens is not None else "",
            "ttft_s": r.ttft_s if r.ttft_s is not None else "",
            "latency_s": r.latency_s,
            "cost_usd": r.cost_usd if r.cost_usd is not None else "",
            "error": f"{r.error_type}: {r.error_message}" if not r.ok else "",
            "verdict": "", "official_source_url": "", "date_checked": "", "notes": "",
        })

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    matched = sum(1 for r in out_rows if r["behavior_match"] == "yes")
    print(f"\nWrote {out_path.relative_to(config.PROJECT_ROOT)}", file=sys.stderr)
    print(f"{len(out_rows)} questions · {errors} errors · behavior matched expected on {matched}/{len(out_rows)}",
          file=sys.stderr)
    print(f"Next: verify each answer against the official source. Verdicts: {VERDICTS}", file=sys.stderr)
    return 0


def _behavior_match(expected: str, observed: str) -> str:
    """Did the model answer / clarify / refuse as intended? (Correctness is your call, not this script's.)"""
    mapping = {"answer": "answered", "clarify": "clarify", "refuse": "out_of_scope"}
    if expected not in mapping:
        return ""
    return "yes" if mapping[expected] == observed else "no"


if __name__ == "__main__":
    raise SystemExit(main())
