"""Summarize logs/calls.jsonl: cost per answer, latency, errors — per model.

Run:  uv run python scripts/summarize_costs.py
      uv run python scripts/summarize_costs.py --since 2026-11-17
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from labor_rules_assistant import config
from labor_rules_assistant.cost_log import read_log


def pct(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile; fine for a few hundred rows."""
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(q / 100 * len(s) + 0.5) - 1))
    return s[k]


def fmt(v, unit: str = "", digits: int = 2) -> str:
    return "—" if v is None else f"{v:.{digits}f}{unit}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--since", help="only rows on/after this date (YYYY-MM-DD, UTC)")
    args = p.parse_args()

    rows = read_log()
    if args.since:
        rows = [r for r in rows if r["ts"][:10] >= args.since]
    if not rows:
        print(f"No calls logged yet in {config.LOG_PATH.relative_to(config.PROJECT_ROOT)}.")
        return 0

    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)

    print(f"{len(rows)} calls · {rows[0]['ts'][:10]} → {rows[-1]['ts'][:10]}"
          f" · prices as of {config.PRICES_AS_OF or 'NOT SET (edit config.py)'}\n")

    header = f"{'model':<20}{'calls':>6}{'ok':>5}{'err':>5}{'trunc':>6}{'in tok':>9}{'out tok':>9}" \
             f"{'$/answer':>10}{'$ total':>9}{'TTFT p50':>10}{'lat p50':>9}{'lat p95':>9}{'lat max':>9}"
    print(header)
    print("-" * len(header))
    errors: Counter = Counter()
    for model, rs in sorted(by_model.items()):
        ok = [r for r in rs if not r.get("error_type")]
        for r in rs:
            if r.get("error_type"):
                errors[(model, r["error_type"])] += 1
        trunc = sum(1 for r in ok if r.get("truncated"))
        costs = [r["cost_usd"] for r in ok if r.get("cost_usd") is not None]
        lat = [r["latency_s"] for r in ok]
        ttft = [r["ttft_s"] for r in ok if r.get("ttft_s") is not None]
        print(
            f"{model:<20}{len(rs):>6}{len(ok):>5}{len(rs) - len(ok):>5}{trunc:>6}"
            f"{sum(r.get('input_tokens') or 0 for r in ok):>9}{sum(r.get('output_tokens') or 0 for r in ok):>9}"
            f"{fmt(sum(costs) / len(costs) if costs else None, '', 5):>10}{fmt(sum(costs) if costs else None, '', 4):>9}"
            f"{fmt(pct(ttft, 50), 's'):>10}{fmt(pct(lat, 50), 's'):>9}{fmt(pct(lat, 95), 's'):>9}"
            f"{fmt(max(lat) if lat else None, 's'):>9}"
        )

    if errors:
        print("\nErrors by type:")
        for (model, etype), n in errors.most_common():
            print(f"  {model:<20} {etype:<15} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
