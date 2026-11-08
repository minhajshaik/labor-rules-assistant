# Labor Rules Assistant

Ask a question about US workplace break and scheduling rules and get a structured answer:
the rule, which jurisdiction controls, the conditions that change it, and a confidence level.

> **Not legal advice.** General information only. Verify with the official source or a qualified professional.

```
$ uv run python -m labor_rules_assistant "Does a 6-hour shift in Oregon require a meal break?"
Answer: ...
Jurisdictions applied: ...
Rule the model believes applies: ...
Conditions and exceptions: ...
Confidence: ...
What to verify: ...
Disclaimer: General information, not legal advice. ...

[claude-sonnet-5-5 · 812 in / 341 out tokens · TTFT 0.9s · total 6.2s · $0.00xxx · stop=end_turn]
```

## Why this project

Labor rules stack across federal, state and city law, change over time, and carry real cost when
they're misread. That makes them a good test of whether an AI assistant can be trusted: every claim
needs a source, and "I'm not sure" has to be an acceptable answer.

The project is built in stages, each one measured against the last:

| Stage | Adds | Status |
|---|---|---|
| 1 | Raw SDK, streaming, error handling, per-call cost log, **ungrounded baseline** | 🚧 in progress |
| 2 | Retrieval over official sources (pgvector), answers with URL + date citations | planned |
| 6 | Eval suite and tracing: grounding accuracy, cost per answer, latency | planned |

Stage 1 deliberately answers from the model's own knowledge only. The point is to measure how often
that goes wrong, so later stages have a baseline to beat.

## Scope

FLSA; meal and rest break rules for CA, OR, WA, NY and TX; Fair Workweek / predictive scheduling for
NYC, Seattle, Chicago and Oregon. Details and official sources: [docs/scope.md](docs/scope.md).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and an Anthropic API key.

```bash
uv sync
cp .env.example .env    # then paste your API key into .env
uv run python -m labor_rules_assistant --help
```

## Usage

```bash
# Ask one question (streams the answer)
uv run python -m labor_rules_assistant "Are rest breaks in Washington paid?"

# Pick a model tier and tag the call in the log
uv run python -m labor_rules_assistant --model haiku --id q07 "Are rest breaks in Washington paid?"

# Run the seed questions and write a verification sheet to outputs/
uv run python scripts/run_seed.py --model sonnet

# Cost per answer, latency percentiles and errors, per model
uv run python scripts/summarize_costs.py
```

Exit codes: `0` ok · `1` fatal error (fix config) · `3` transient error (retry later) · `4` answer truncated.

## Project layout

```
src/labor_rules_assistant/
  config.py       models, limits, timeouts, price table — every tunable value
  client.py       the only module that calls the API: streaming, error classification, logging
  prompts.py      system prompt, answer format, section parser
  cost_log.py     one JSONL row per call (logs/calls.jsonl, not committed)
  cli.py          command line
scripts/
  day1_first_call.py   a single raw API call, for learning the response shape
  run_seed.py          runs evals/seed_questions.csv → outputs/run_*.csv
  summarize_costs.py   cost and latency report from the call log
evals/seed_questions.csv   16 seed questions (becomes the Stage 6 eval set)
docs/
  scope.md                    in/out of scope, official sources
  failure-drills.md           Day 2 forced-failure log
  adr/ADR-001-model-provider.md
```

## Stage 1 results

_Filled in at the end of Stage 1._

| Metric | Value |
|---|---|
| Answer accuracy (ungrounded) | |
| Citation accuracy | |
| Confident but wrong | |
| Cost per answer (default model) | |
| Latency p50 / p95 | |

**Next:** Stage 2 grounds every answer in official sources, with source URLs and effective dates.
