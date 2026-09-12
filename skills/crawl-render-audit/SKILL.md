---
name: crawl-render-audit
description: Off-site AI discoverability audit for a website. Runs a deterministic, robots.txt-respecting crawl to measure whether AI assistant crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, etc.) can reach, render, and extract facts from the site — AI-bot access in robots.txt, llms.txt presence, Schema.org/JSON-LD coverage, client-side-rendering gaps, facts locked in non-text media (missing alt text, PDF-only content), cross-web entity corroboration links (sameAs to Wikidata/LinkedIn/Crunchbase), and freshness signals. Emits raw, evidence-backed findings for the audit-orchestrator to consume. Use as a sub-skill of a full brand audit, or standalone when only off-site discoverability (not on-site engagement) needs checking.
license: Apache-2.0
allowed-tools: Bash
---

# Crawl & Render Audit (Off-Site AI Discoverability)

## When to use
Use this skill whenever a site needs to be checked for whether AI assistants and
their crawlers can find, read, and cite it. Use standalone for a discoverability-only
question ("why doesn't ChatGPT know about us?"); use as a sub-skill under
`audit-orchestrator` when a full brand audit (discoverability + engagement) is
requested.

## Inputs
- `url` (string, required): target domain or URL.
- `max_pages` (integer, optional, default 15, max 50): pages to sample via same-domain
  breadth-first crawl from the homepage.
- `timeout` (integer, optional, default 6): per-request timeout in seconds.

## What this skill measures (and why)
Each check maps to a specific mechanism by which AI assistants find and use content
(see the reasoning primer in `references/why-these-checks.md` if present, or the
background supplied by the calling task):

1. **AI crawler access** — checks robots.txt against known AI bot user agents
   (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot, Applebot-Extended,
   Bytespider). A block here means the site is invisible to that system regardless
   of content quality.
2. **llms.txt / llms-full.txt** — presence of an LLM-oriented content manifest.
3. **Schema.org / JSON-LD coverage** — whether facts are stated in a
   machine-parsable structured format, not just prose.
4. **Client-side rendering gaps** — pages whose initial HTML is near-empty relative
   to visible content, signaling that a simple fetch-based crawler would see little
   or nothing.
5. **Non-text-locked facts** — missing alt text on informational images, and
   PDF-only content that a fetch-based reader may not process the same way as HTML.
6. **Cross-web entity corroboration** — `sameAs` links to Wikidata, Wikipedia,
   LinkedIn, or Crunchbase, which help disambiguate the brand from unrelated
   same-named entities and let independent sources corroborate facts.
7. **Freshness signals** — copyright year / staleness indicators in visible text.

## Procedure
1. Normalize the input to an HTTPS URL; extract the registrable domain.
2. Load `/robots.txt`. If present, parse it and check `can_fetch()` for each known
   AI bot UA against the homepage path. Never fetch a path this skill's own crawl UA
   is disallowed from.
3. Check `/llms.txt`, `/.well-known/llms.txt`, `/llms-full.txt`.
4. BFS-sample up to `max_pages` same-domain HTML pages from the homepage, skipping
   any path disallowed to this skill's own user agent.
5. For each sampled page, extract and evaluate JSON-LD, visible-text-vs-script-tag
   ratio (render-gap heuristic), image alt-text coverage, PDF links, `sameAs`
   entities, and copyright-year freshness.
6. Aggregate per-check findings across the sample (do not report a per-page glitch
   as a site-wide fact — state it as "`X`/`N` sampled pages").
7. Emit each finding with: title, an evidence-hint severity (`severity_hint` — a
   suggestion, not final), the specific evidence string, a suggested action, and
   `tags` (topic) plus a `correlatable` flag (true when this finding is the kind
   that plausibly reinforces a similar finding from `engagement-audit`, e.g.
   `structured_data`, `entity_corroboration`).

## Running it
```bash
python3 scripts/crawler.py <target-url> --max-pages 15 --timeout 6 --output ./discoverability_raw.json
```
Requires `requests` and `beautifulsoup4` (`pip install requests beautifulsoup4 --break-system-packages`
if not already available in the environment).

## Output
Writes a JSON file (see `scripts/crawler.py` for the exact shape) containing
`site`, `audited_at`, crawl metadata (`pages_sampled`, `sampled_urls`,
`robots_txt_found`, `ai_bot_access`, `llms_txt`), and a `findings` array of raw,
unmerged findings. This is **not** the final report schema — `audit-orchestrator`
normalizes, correlates, and re-indexes this output alongside `engagement-audit`'s
output into the single unified report.

## Guardrails
- Read-only: GET/HEAD only, no authentication, no form submission, no mutation.
- Always respects the target's robots.txt for this skill's own crawl traffic,
  independent of what it *reports* about other bots' access.
- Never claims a per-sample observation is site-wide; always states sample size.
- Does not assign final severity — only a `severity_hint` — because severity
  calibration (e.g. not auto-classifying every robots.txt restriction as
  "critical") depends on cross-skill context that belongs to the orchestrator.
