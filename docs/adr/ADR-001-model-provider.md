# ADR-001: Model provider and default model tier

- **Status:** Draft (fill in during Stage 1, Day 3)
- **Date:** YYYY-MM-DD
- **Owner:** Minhaj Shaik

## Context

The labor-rules assistant answers questions about US meal/rest break and Fair Workweek rules.
Wrong answers carry real cost for the person relying on them, so accuracy and calibrated
confidence matter more than speed. Expected volume for this project: low (dozens of calls a day
during development; eval runs of 15–50 questions).

## Options considered

| Option | Notes |
|---|---|
| Anthropic, Haiku tier | |
| Anthropic, Sonnet tier | |
| Anthropic, Opus tier | |
| Another provider (not evaluated in Stage 1) | Why it was left out: |

## Evidence

From Day 1 (questions q01, q03, q11, same prompt on each tier) and `scripts/summarize_costs.py`.
Prices copied from the official pricing page on: ____

| Model | Answer quality (1–5) | Citation looks specific? | Avg input tok | Avg output tok | TTFT p50 | Latency p50 | $ / answer |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | | | | | | | |
| claude-sonnet-5-5 | | | | | | | |
| claude-opus-5-5 | | | | | | | |

Baseline from the Day 3 run (default model, 16 seed questions, verified by hand):

| Metric | Value |
|---|---|
| Answer accuracy (correct ÷ answered) | |
| Citation accuracy (real statute, right section) | |
| Confident but wrong (high confidence, verdict wrong/outdated/fabricated) | |
| Clarify / decline behavior correct (q15, q16) | |

## Decision

Default model: ____. Reason: ____.
Other tier used for: ____ (or "none").

**Ungrounded answers are not acceptable in this domain.** The baseline above shows ____% of
citations were wrong or fabricated, ____ of them stated with high confidence. Stage 2 adds
retrieval over official sources with per-claim citations.

## Consequences

- Cost per answer at the default tier: $____.
- Every call goes through `client.py`, so switching model is a config change, not a code change.

## Revisit when

- A provider changes prices or releases a new model tier.
- The eval suite (Stage 6) shows a quality regression.
- Volume grows enough that cost per answer becomes a constraint.
