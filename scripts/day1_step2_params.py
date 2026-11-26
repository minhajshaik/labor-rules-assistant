"""Day 1, step 2: which parameters actually control consistency?

On current Claude models, `temperature` can't be changed (any non-default value
returns 400), so the levers left are the system prompt, effort, and max_tokens.

This script runs four experiments on ONE question and prints a comparison table:
  A. temperature=0        -> expect a 400; records that the lever doesn't exist
  B. no system prompt     -> N identical runs: does the cited rule drift?
  C. with system prompt   -> N identical runs: does the format + rule stabilize?
  D. effort low vs high   -> N runs each (with system prompt): cost vs. drift

Run:
  uv run python scripts/day1_step2_params.py                  # q01, 3 runs each (~15 calls)
  uv run python scripts/day1_step2_params.py --runs 5
  uv run python scripts/day1_step2_params.py --question "Does Chicago's Fair Workweek ordinance cover an employer with 50 employees?"

Output: a table on screen plus outputs/step2_<timestamp>.json with every answer.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime

import anthropic

from labor_rules_assistant import config
from labor_rules_assistant.prompts import SYSTEM_PROMPT, confidence_level, parse_sections

DEFAULT_Q = "Does a 6-hour shift in Oregon require a meal break?"
# Statute-like references: OAR 839-020-0050, ORS 653.261, 29 CFR 785.18, Cal. Labor Code § 512(a), WAC 296-126-092
CITE_RE = re.compile(
    r"(?:\b\d+\s+)?\b(?:OAR|ORS|C\.?F\.?R\.?|U\.?S\.?C\.?|RCW|WAC|SMC|NYLL|Labor Code|Lab\. Code|Labor Law)"
    r"\s*(?:§+\s*)?\d[\d.\-]*(?:\([a-z0-9]+\))*",
    re.IGNORECASE,
)


def one_call(client, question, *, system=None, effort=None, temperature=None, max_tokens=4000):
    params = {
        "model": config.DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": question}],
    }
    if system:
        params["system"] = system
    if effort:
        params["output_config"] = {"effort": effort}
    if temperature is not None:
        # Recent SDKs removed `temperature` from create() entirely, so passing it as a normal
        # argument fails in Python before any request is sent. extra_body sends it raw so you
        # see what the API itself says.
        params["extra_body"] = {"temperature": temperature}

    start = time.perf_counter()
    try:
        r = client.messages.create(**params)
    except anthropic.BadRequestError as e:
        return {"error": f"400 {getattr(e, 'message', e)}", "latency_s": round(time.perf_counter() - start, 2)}

    text = "".join(b.text for b in r.content if b.type == "text")
    details = getattr(r.usage, "output_tokens_details", None)
    sections = parse_sections(text)
    rule_line = sections.get("Rule the model believes applies", "")
    return {
        "stop_reason": r.stop_reason,
        "output_tokens": r.usage.output_tokens,
        "thinking_tokens": getattr(details, "thinking_tokens", None),
        "latency_s": round(time.perf_counter() - start, 2),
        "has_format": "Answer" in sections and "Confidence" in sections,
        "confidence": confidence_level(text),
        "citations": sorted({normalize(m.group(0)) for m in CITE_RE.finditer(rule_line or text)}),
        "answer_first_line": (sections.get("Answer") or text.strip().split("\n")[0])[:120],
        "text": text,
    }


def normalize(cite: str) -> str:
    return re.sub(r"\s+", " ", cite).strip(" .,;:()")


def summarize(label, runs):
    ok = [r for r in runs if "error" not in r]
    if not ok:
        return {"label": label, "runs": len(runs), "error": runs[0]["error"]}
    cite_sets = Counter(" | ".join(r["citations"]) or "(none)" for r in ok)
    return {
        "label": label,
        "runs": len(runs),
        "distinct_citation_sets": len(cite_sets),
        "most_common_citation": cite_sets.most_common(1)[0][0],
        "formatted": f"{sum(r['has_format'] for r in ok)}/{len(ok)}",
        "confidence": dict(Counter(r["confidence"] or "-" for r in ok)),
        "avg_thinking_tok": _avg([r["thinking_tokens"] for r in ok]),
        "avg_output_tok": _avg([r["output_tokens"] for r in ok]),
        "avg_latency_s": _avg([r["latency_s"] for r in ok], 1),
        "truncated": sum(r["stop_reason"] == "max_tokens" for r in ok),
    }


def _avg(values, digits=0):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), digits) if vals else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--question", default=DEFAULT_Q)
    p.add_argument("--runs", type=int, default=3, help="identical runs per experiment (default 3)")
    args = p.parse_args()

    client = anthropic.Anthropic(timeout=config.DEFAULT_TIMEOUT_S, max_retries=config.DEFAULT_MAX_RETRIES)
    experiments = [
        ("A  temperature=0", dict(temperature=0), 1),
        ("B  no system prompt", dict(), args.runs),
        ("C  system prompt", dict(system=SYSTEM_PROMPT), args.runs),
        ("D1 system + effort=low", dict(system=SYSTEM_PROMPT, effort="low"), args.runs),
        ("D2 system + effort=high", dict(system=SYSTEM_PROMPT, effort="high"), args.runs),
    ]

    print(f"Model: {config.DEFAULT_MODEL}\nQuestion: {args.question}\n")
    all_runs, summaries = {}, []
    for label, kwargs, n in experiments:
        runs = []
        for i in range(n):
            print(f"  {label}  run {i + 1}/{n} ...", flush=True)
            runs.append(one_call(client, args.question, **kwargs))
        all_runs[label] = runs
        summaries.append(summarize(label, runs))

    print("\n" + "=" * 100)
    for s in summaries:
        if "error" in s:
            print(f"{s['label']:<26} REJECTED: {s['error'][:90]}")
            continue
        print(f"{s['label']:<26} formatted {s['formatted']:<5} distinct citation sets: {s['distinct_citation_sets']}"
              f"   thinking≈{s['avg_thinking_tok']}  output≈{s['avg_output_tok']}  latency≈{s['avg_latency_s']}s"
              f"   confidence {s['confidence']}  truncated {s['truncated']}")
        print(f"{'':<26} most common citation: {s['most_common_citation'][:80]}")
    print("=" * 100)
    print("distinct citation sets = 1 means the cited rule was identical on every run (no drift).")

    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.OUTPUTS_DIR / f"step2_{datetime.now():%Y%m%d-%H%M}.json"
    out.write_text(json.dumps({"model": config.DEFAULT_MODEL, "question": args.question,
                               "summaries": summaries, "runs": all_runs}, indent=2), encoding="utf-8")
    print(f"\nEvery answer saved to {out.relative_to(config.PROJECT_ROOT)} — read the citations side by side.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
