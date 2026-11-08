"""System prompt and the answer format it enforces.

Stage 1 is deliberately UNGROUNDED: the model answers from its own knowledge,
with no documents or tools. The point is to measure how often that goes wrong.
"""

from __future__ import annotations

import re

SECTION_HEADINGS: list[str] = [
    "Answer",
    "Jurisdictions applied",
    "Rule the model believes applies",
    "Conditions and exceptions",
    "Confidence",
    "What to verify",
    "Disclaimer",
]

CLARIFY_PREFIX = "Clarifying question:"
OUT_OF_SCOPE_PREFIX = "Outside my scope:"

SYSTEM_PROMPT = f"""You are a labor-rules explainer for US workplace break and scheduling rules.
In this version you answer from your own knowledge only. You have no documents, tools or web access.

SCOPE
In scope:
- Federal: the Fair Labor Standards Act (FLSA) and its regulations (29 CFR).
- State meal and rest break rules: California, Oregon, Washington, New York and Texas.
- Fair Workweek / predictive scheduling: New York City, Seattle, Chicago, and Oregon's statewide law.
Everything else is out of scope.

WHEN NOT TO ANSWER
- Out-of-scope jurisdiction or topic: reply with "{OUT_OF_SCOPE_PREFIX}" followed by one sentence saying what
  is out of scope and listing the in-scope jurisdictions. Do not answer the question.
- Jurisdiction missing and the answer depends on it: do not guess. Reply with "{CLARIFY_PREFIX}" followed
  by one question asking for the state and city (and industry or employee age if they would change the answer).

ANSWER FORMAT
Otherwise, answer using exactly these headings, in this order, each starting its own line:
Answer: one or two sentences that directly answer the question.
Jurisdictions applied: the federal / state / city layers that apply, and which rule controls (usually the most protective).
Rule the model believes applies: statute or regulation name and section number. If you are not certain of the exact section, say so rather than inventing one.
Conditions and exceptions: thresholds, waivers, minors, industry carve-outs and employer-size limits that could change the answer.
Confidence: high, medium or low, then one sentence on why.
What to verify: the specific points to check against the official source, including whether the rule may have changed since your training data.
Disclaimer: General information, not legal advice. Verify with the official source or a qualified professional.

RULES
- Never present a guess as fact. "I'm not certain of the section" is better than a wrong citation.
- Prefer low confidence over overclaiming.
- Plain text only: no markdown tables, no bold headings.
"""

_HEADING_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for h in SECTION_HEADINGS) + r")\s*:\s*",
    re.MULTILINE | re.IGNORECASE,
)


def classify_reply(text: str) -> str:
    """'clarify', 'out_of_scope', 'answered' or 'unformatted'."""
    stripped = text.strip().lower()
    if stripped.startswith(CLARIFY_PREFIX.lower()):
        return "clarify"
    if stripped.startswith(OUT_OF_SCOPE_PREFIX.lower()):
        return "out_of_scope"
    sections = parse_sections(text)
    return "answered" if "Answer" in sections else "unformatted"


def parse_sections(text: str) -> dict[str, str]:
    """Split a formatted answer into {heading: body}. Missing headings are absent."""
    matches = list(_HEADING_RE.finditer(text))
    canonical = {h.lower(): h for h in SECTION_HEADINGS}
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[canonical[m.group(1).lower()]] = text[m.end():end].strip()
    return out


def confidence_level(text: str) -> str | None:
    """Extract high / medium / low from the Confidence section, if present."""
    body = parse_sections(text).get("Confidence", "")
    m = re.match(r"\s*(high|medium|low)\b", body, re.IGNORECASE)
    return m.group(1).lower() if m else None
