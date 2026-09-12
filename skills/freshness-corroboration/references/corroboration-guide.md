# Corroboration Methodology & Worked Examples

## Why this matters
AI assistants weigh a claim more heavily when it is repeated consistently across
independent sources, and less when it lives in only one place (the brand's own
site). A single-source claim is not necessarily false — it is *fragile*: one
correction, outage, or redesign away from disappearing entirely from what an
assistant can find.

## Claim selection
Prioritize claims that are:
- **Specific and checkable** — a date, a number, a certification, a named
  partnership — not vague marketing language ("industry-leading").
- **Consequential** — a compliance/certification claim or a headline statistic
  matters more than an adjective.
- **Plausibly searchable** — claims about internal-only facts (e.g. "our support
  team responds fast") cannot be meaningfully corroborated externally; skip them.

## Search strategy
1. Start with the specific claim plus the brand/entity name.
2. Prefer authoritative independent sources: government/registry filings, established
   press, industry directories, Wikidata/Wikipedia, standards bodies (for
   certification claims).
3. Deliberately search for *disconfirming* evidence, not just confirming evidence —
   look for conflicting dates, numbers, or entity names, not only agreement.
4. If multiple entities share the brand's name, note this explicitly regardless of
   whether it affects the specific claim being checked.

## Classification definitions
| Label | Meaning | Example |
|---|---|---|
| `corroborated` | 2+ independent sources agree with the claim | Founding year matches both a press article and a business registry |
| `contradicted` | An independent source conflicts with the claim | Site claims "ISO 27001 certified" but no certification body lists it |
| `uncorroborated` | No independent source addresses it either way | A specific customer-count claim appears only on the brand's own page |
| `insufficient_evidence` | Search didn't surface enough to judge either way | Claim is too vague or too new to have independent coverage yet |

## Entity ambiguity
If search results reveal a distinct organization with the same or a
confusingly similar name (different industry, different location, different legal
entity), record this as its own finding — tag `entity_corroboration` — separately
from the specific claim being checked. Ambiguity is a discoverability risk on its
own: an AI assistant may attribute the wrong entity's facts to the brand being
audited, or vice versa, regardless of whether any individual claim is accurate.

## What NOT to do
- Do not treat "uncorroborated" as equivalent to "false." Say what the evidence
  actually shows.
- Do not spot-check more than the configured `max_claims` without a specific
  reason — this is a targeted check, not an exhaustive fact-check of the site.
- Do not use this process to generate findings about topics unrelated to the
  claims actually being checked.
