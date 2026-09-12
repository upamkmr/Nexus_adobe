---
name: freshness-corroboration
description: Spot-checks a small number of load-bearing factual claims found on a target website against independent web sources, to assess whether the brand's self-reported facts are corroborated, contradicted, or unsupported elsewhere on the web — a key factor in whether AI assistants trust and repeat a claim, since fragile single-source facts are weighed less than facts repeated consistently across independent sources. Also flags entity-ambiguity risk (multiple distinct entities sharing a brand name) when corroboration searches surface a naming collision. Use as a sub-skill of a full brand audit when discoverability findings include factual claims worth corroborating, or standalone to check a specific list of claims.
license: Apache-2.0
allowed-tools: WebSearch
---

# Freshness & Corroboration Check

## When to use
Use after (or alongside) `crawl-render-audit` when it has surfaced load-bearing
factual claims about the brand — founding date, leadership, headline product
claims, certifications, awards — that are worth checking against independent
sources. This skill requires live web search and is judgment-based (unlike the
deterministic crawlers), so keep its scope narrow: a handful of claims, not an
exhaustive fact-check of the whole site.

## Inputs
- `claims` (array of strings, required): specific factual claims to check, ideally
  supplied by `crawl-render-audit`'s output or extracted directly from the site
  (e.g. "Founded in 2014", "Used by over 10,000 companies", "ISO 27001 certified").
- `site` (string, required): the domain the claims are attributed to, used to
  disambiguate entities during search.
- `max_claims` (integer, optional, default 3): do not exceed this without a
  specific reason — corroboration should strengthen or weaken existing findings,
  not manufacture a large parallel investigation.

## Procedure
1. Select up to `max_claims` claims, prioritizing ones that are (a) specific and
   checkable, and (b) consequential if wrong (e.g. a compliance certification
   claim outranks a marketing adjective).
2. For each claim, search independent sources (not the target site itself, not
   its own press releases where avoidable) for corroboration.
3. Classify each claim as one of:
   - `corroborated` — multiple independent sources agree.
   - `contradicted` — independent sources conflict with the claim.
   - `uncorroborated` — no independent source addresses it (fragile, not
     necessarily false).
   - `insufficient_evidence` — search did not return enough to judge.
4. While searching, note if results reveal **entity ambiguity** — i.e. another
   distinct organization shares the same or a very similar name. If so, emit this
   as its own finding: ambiguity makes it harder for AI assistants to attribute
   facts to the correct entity, independent of whether any single claim was true.
5. Do not manufacture new unrelated findings from this process — corroboration
   results must attach to an existing claim/finding, strengthening or weakening it.

## Output
Emit a JSON object:
```json
{
  "source_skill": "freshness-corroboration",
  "site": "example.com",
  "audited_at": "2026-09-20T14:32:00Z",
  "findings": [
    {
      "source_skill": "freshness-corroboration",
      "raw_id": "corr-001",
      "title": "Claim 'Founded in 2014' is uncorroborated outside site's own pages",
      "severity_hint": "low",
      "scope": "site",
      "evidence": "Searched for independent mentions of the founding year; only the company's own About page states 2014. No independent directory, press coverage, or registry listing corroborates or contradicts it.",
      "suggested_action": {"summary": "Where possible, link to an independent, authoritative corroborating source (e.g. a registry filing or press mention) for load-bearing factual claims.", "priority": "low"},
      "tags": ["entity_corroboration"],
      "correlatable": true
    }
  ]
}
```
This follows the same raw-finding shape used by `crawl-render-audit` and
`engagement-audit` so `audit-orchestrator`'s merge step can normalize all three
uniformly.

## Guardrails
- Read-only web search only — no site mutation, no authentication.
- Never uses corroboration results to invent findings unrelated to a specific,
  identified claim.
- Distinguishes "uncorroborated" (weak evidence) from "contradicted" (conflicting
  evidence) from "insufficient_evidence" (search didn't surface enough) —
  these are not interchangeable and must not be flattened into a single "bad" label.
- Keeps scope to a small number of claims (`max_claims`); this is a spot-check,
  not an exhaustive audit.

See `references/corroboration-guide.md` for the detailed methodology and
worked examples.
