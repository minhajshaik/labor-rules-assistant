# Stage 1, Day 2: failure drills

Break the system on purpose and record what happened. These notes become the
"failure I engineered around" interview story.

Tip: prefix any command with `ANTHROPIC_LOG=info` to see the SDK's own retries.

| # | Drill | Command | Expected | Observed | Handled cleanly? |
|---|---|---|---|---|---|
| 1 | Timeout | `LRA_TIMEOUT_S=1 LRA_MAX_RETRIES=0 uv run python -m labor_rules_assistant "Does a 6-hour shift in Oregon require a meal break?"` (if it succeeds, try `0.2`) | `timeout`, retryable, exit 3 | | |
| 2 | Truncation | `uv run python -m labor_rules_assistant --max-tokens 50 "In California, when is a second meal period required?"` | "INCOMPLETE ANSWER", stop=max_tokens, exit 4 | | |
| 3 | Bad model name | `uv run python -m labor_rules_assistant --model claude-sonet-5-5 "test"` | `not_found`, fatal, exit 1 | | |
| 4 | Bad / revoked key | `ANTHROPIC_API_KEY=sk-ant-invalid uv run python -m labor_rules_assistant "test"` (or revoke a throwaway key in the Console) | `auth`, fatal, exit 1, no stack trace | | |

After the drills, run `uv run python scripts/summarize_costs.py` and confirm every
failed call appears in the error breakdown.

## What I learned

- Which errors does the SDK retry on its own, and how long did that take?
- What does a user see in each case? Would they know what to do next?
- Which of these would page someone in production, and which wouldn't?
