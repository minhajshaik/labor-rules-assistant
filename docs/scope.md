# Scope

**This assistant gives general information about US labor rules. It is not legal advice.**
Answers must be verified against the official source before anyone relies on them.

## In scope

| Layer | Jurisdictions | Topics |
|---|---|---|
| Federal | United States | FLSA and 29 CFR as they relate to breaks and hours worked |
| State | California, Oregon, Washington, New York, Texas | Meal periods and rest breaks, including rules for minors and industry carve-outs |
| City / state scheduling | New York City, Seattle, Chicago, Oregon (statewide) | Fair Workweek and predictive-scheduling rules: advance notice, predictability pay, rest between shifts, coverage thresholds |

Texas is included on purpose as a contrast case with few state-level requirements.

## Out of scope

- Any other state or city (the assistant should say "Outside my scope").
- Wage rates, overtime calculation, leave, tips, classification (exempt / non-exempt) beyond what a break question needs.
- Collective bargaining agreements and individual employer policies.
- Anything asking whether a specific employer is compliant.

## Behavior rules

1. **Missing jurisdiction → ask.** If the answer depends on the state or city and the question doesn't say, ask a clarifying question instead of guessing.
2. **Out-of-scope jurisdiction → decline**, and list what is in scope.
3. **Most protective rule usually controls** when federal, state and city rules overlap. Say which layer controls.
4. **No invented citations.** "Not certain of the section" beats a fabricated one.

## Official sources for verification

| Jurisdiction | Where to check |
|---|---|
| Federal | eCFR (ecfr.gov), title 29; US DOL Wage and Hour Division (dol.gov/agencies/whd) |
| California | California Department of Industrial Relations (dir.ca.gov); Labor Code; IWC wage orders |
| Oregon | Oregon Bureau of Labor and Industries (oregon.gov/boli); OAR chapter 839 |
| Washington | Washington Department of Labor & Industries (lni.wa.gov); WAC chapter 296 |
| New York | New York State Department of Labor (dol.ny.gov); NY Labor Law |
| Texas | Texas Workforce Commission (twc.texas.gov) |
| New York City | NYC Department of Consumer and Worker Protection (nyc.gov) |
| Seattle | Seattle Office of Labor Standards (seattle.gov) |
| Chicago | Chicago Office of Labor Standards (chicago.gov) |

Record the exact page URL and the date you checked it in `evals/seed_questions.csv`.
