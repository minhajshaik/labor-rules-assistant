"""Day 1, step 4: compare model tiers side by side.

First run the same questions on each tier:
  uv run python scripts/run_seed.py --model haiku  --ids q01,q03,q11
  uv run python scripts/run_seed.py --model sonnet --ids q01,q03,q11
  uv run python scripts/run_seed.py --model opus   --ids q01,q03,q11
Then:
  uv run python scripts/compare_tiers.py

It takes the LATEST run_*.csv for each model in outputs/, and:
  - prints each question across the three models (format, confidence, citation, tokens, latency)
  - prints a per-model summary in the same shape as the ADR-001 evidence table
  - writes outputs/tier_comparison_<timestamp>.csv with blank `quality_1to5` and
    `notes` columns for your judgment

"Citation looks specific" is automatic: yes if the cited rule names a statute AND a
section number (e.g. OAR 839-020-0050). It says nothing about whether it's CORRECT;
that is Day 3's job.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from labor_rules_assistant import config

# Same pattern as day1_step2_params.py: a statute/regulation name followed by a section number.
CITE_RE = re.compile(
    r"(?:\b\d+\s+)?\b(?:OAR|ORS|C\.?F\.?R\.?|U\.?S\.?C\.?|RCW|WAC|SMC|MCC|NYLL|Labor Code|Lab\. Code|Labor Law|"
    r"Admin(?:istrative|\.)? Code|Municipal Code(?: of Chicago)?)"
    r"\s*(?:§+\s*)?\d[\d.\-]*(?:\([a-z0-9]+\))*",
    re.IGNORECASE,
)

TIER_ORDER = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
OUT_COLUMNS = [
    "id", "question", "model", "observed_behavior", "confidence", "citation_specific", "citations_found",
    "cited_rule", "input_tokens", "output_tokens", "thinking_tokens", "ttft_s", "latency_s", "cost_usd",
    "stop_reason", "error", "quality_1to5", "notes", "model_answer",
]


def latest_run_per_model(outputs: Path) -> dict[str, Path]:
    """Map model ID -> newest run_*.csv that contains it."""
    latest: dict[str, tuple[float, Path]] = {}
    for path in outputs.glob("run_*.csv"):
        with path.open(encoding="utf-8") as f:
            first = next(csv.DictReader(f), None)
        if not first or not first.get("model"):
            continue
        model = first["model"]
        mtime = path.stat().st_mtime
        if model not in latest or mtime > latest[model][0]:
            latest[model] = (mtime, path)
    return {m: p for m, (_, p) in latest.items()}


def num(v: str) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def avg(values: list[float | None], digits: int = 0):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), digits) if digits else round(sum(vals) / len(vals))


def show(v, unit: str = "") -> str:
    return "—" if v is None or v == "" else f"{v}{unit}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ids", default="q01,q03,q11", help="question IDs to compare (default: %(default)s)")
    args = p.parse_args()
    wanted = [i.strip() for i in args.ids.split(",")]

    runs = latest_run_per_model(config.OUTPUTS_DIR)
    models = [m for m in TIER_ORDER if m in runs] + sorted(m for m in runs if m not in TIER_ORDER)
    if not models:
        print("No run_*.csv files in outputs/. Run scripts/run_seed.py for each model first.")
        return 1
    missing = [m for m in TIER_ORDER if m not in runs]
    print("Using:")
    for m in models:
        print(f"  {m:<20} {runs[m].relative_to(config.PROJECT_ROOT)}")
    if missing:
        print(f"  (no run yet for: {', '.join(missing)})")

    rows: list[dict] = []
    for m in models:
        with runs[m].open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["id"] not in wanted:
                    continue
                cites = sorted({c.group(0).strip(" .,;") for c in CITE_RE.finditer(r.get("cited_rule", ""))})
                rows.append({
                    **{k: r.get(k, "") for k in OUT_COLUMNS if k in r},
                    "citation_specific": "yes" if cites else "no",
                    "citations_found": " | ".join(cites),
                    "quality_1to5": "",
                    "notes": "",
                })

    # ---- per question ----------------------------------------------------------------
    for qid in wanted:
        q_rows = [r for r in rows if r["id"] == qid]
        if not q_rows:
            continue
        print(f"\n{qid}: {q_rows[0]['question']}")
        print(f"  {'model':<20}{'reply':<13}{'conf':<8}{'specific':<10}{'think':>7}{'out':>7}{'TTFT':>8}{'total':>8}  citation")
        for r in q_rows:
            reply = r["observed_behavior"] if not r.get("error") else "ERROR"
            print(f"  {r['model']:<20}{reply:<13}{show(r['confidence']):<8}{r['citation_specific']:<10}"
                  f"{show(r['thinking_tokens']):>7}{show(r['output_tokens']):>7}{show(r['ttft_s'], 's'):>8}"
                  f"{show(r['latency_s'], 's'):>8}  {r['citations_found'][:60] or '—'}")

    # ---- per model summary (ADR-001 shape) ----------------------------------------------
    print("\nSummary for ADR-001 (quality is yours to score; open the CSV):\n")
    print("| Model | Answers formatted | Citation looks specific | Confidence | Avg input tok | Avg output tok "
          "| Avg thinking tok | TTFT avg | Latency avg | $ / answer |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for m in models:
        mr = [r for r in rows if r["model"] == m and not r.get("error")]
        if not mr:
            print(f"| {m} | all calls failed | | | | | | | | |")
            continue
        formatted = sum(r["observed_behavior"] == "answered" for r in mr)
        specific = sum(r["citation_specific"] == "yes" for r in mr)
        conf = Counter(r["confidence"] or "—" for r in mr)
        costs = [num(r.get("cost_usd", "")) for r in mr]
        cost = avg(costs, 5)
        print(f"| {m} | {formatted}/{len(mr)} | {specific}/{len(mr)} | "
              f"{', '.join(f'{k} {v}' for k, v in conf.most_common())} | "
              f"{show(avg([num(r['input_tokens']) for r in mr]))} | {show(avg([num(r['output_tokens']) for r in mr]))} | "
              f"{show(avg([num(r['thinking_tokens']) for r in mr]))} | {show(avg([num(r['ttft_s']) for r in mr], 1), 's')} | "
              f"{show(avg([num(r['latency_s']) for r in mr], 1), 's')} | "
              f"{'$' + format(cost, '.5f') if cost is not None else 'n/a (set prices in config.py)'} |")

    errors = [r for r in rows if r.get("error")]
    if errors:
        print("\nErrors:")
        for r in errors:
            print(f"  {r['model']} {r['id']}: {r['error'][:100]}")

    out = config.OUTPUTS_DIR / f"tier_comparison_{datetime.now():%Y%m%d-%H%M}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["id"], TIER_ORDER.index(r["model"]) if r["model"] in TIER_ORDER else 9)))
    print(f"\nWrote {out.relative_to(config.PROJECT_ROOT)}: fill in quality_1to5 and notes for each row.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
