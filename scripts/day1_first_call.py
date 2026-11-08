"""Day 1, step 1: one plain, non-streaming call with no wrapper.

Run:  uv run python scripts/day1_first_call.py
Read the full response object once. Everything else in the project wraps this.
"""

import anthropic

from labor_rules_assistant import config  # importing config loads .env

client = anthropic.Anthropic()
response = client.messages.create(
    model=config.DEFAULT_MODEL,
    max_tokens=500,
    messages=[{"role": "user", "content": "Does a 6-hour shift in Oregon require a meal break?"}],
)

print("=== full response object ===")
print(response.model_dump_json(indent=2))

print("\n=== text ===")
print("".join(block.text for block in response.content if block.type == "text"))

print("\n=== the fields you'll log on every call ===")
print("model:        ", response.model)
print("stop_reason:  ", response.stop_reason)
print("input_tokens: ", response.usage.input_tokens)
print("output_tokens:", response.usage.output_tokens)
