---
name: engagement-audit
description: On-site visitor engagement and retention audit for a website. Runs a deterministic, robots.txt-respecting crawl to measure whether visitors who land on the site — especially deep-linked arrivals from AI assistants — can quickly understand the page and take a next step. Checks above-the-fold value-proposition clarity (H1 count/specificity), navigation and breadcrumb orientation, scannability (long unbroken prose blocks), call-to-action presence (dead-end pages), mobile viewport configuration, and layout-shift risk from images missing dimensions. Emits raw, evidence-backed findings for the audit-orchestrator to consume. Use as a sub-skill of a full brand audit, or standalone when only on-site engagement (not off-site discoverability) needs checking.
license: Apache-2.0
allowed-tools: Bash
---

# Engagement Audit (On-Site Retention)

## When to use
Use this skill whenever a site needs to be checked for why visitors bounce after
arriving — including visitors deep-linked in by an AI assistant who never see the
homepage. Use standalone for an engagement-only question; use as a sub-skill under
`audit-orchestrator` when a full brand audit is requested.

## Inputs
- `url` (string, required): target domain or URL.
- `max_pages` (integer, optional, default 15, max 50): pages to sample via
  same-domain breadth-first crawl from the homepage.
- `timeout` (integer, optional, default 6): per-request timeout in seconds.

## What this skill measures (and why)
1. **Above-the-fold clarity** — zero or multiple `<h1>` elements per page dilute or
   remove a clear, specific statement of what the page offers (the "5-second test").
2. **Navigation orientation** — missing `<nav>` landmarks or breadcrumb trails hurt
   visitors who land deep in the site with no context for where they are.
3. **Scannability** — long unbroken paragraphs with no nearby heading or list make
   content hard to scan, especially for an already-impatient deep-linked visitor.
4. **CTA clarity** — pages with no recognizable call-to-action are dead ends: the
   visitor has nowhere obvious to go next.
5. **Mobile viewport** — missing `<meta name="viewport">` risks a broken mobile
   layout for the large share of AI-assistant-referred traffic that is mobile.
6. **Layout-shift risk** — images without width/height attributes can cause content
   to jump as the page loads, a common source of frustrated exits.

## Procedure
1. Normalize input to HTTPS URL; extract domain.
2. Load `/robots.txt` if present and respect it for this skill's own crawl traffic.
3. BFS-sample up to `max_pages` same-domain HTML pages from the homepage.
4. For each page: count `<h1>`s, check for `<nav>`/breadcrumb markers, scan `<p>`
   tags for word count vs. proximity to the next heading/list, search link/button
   text against a CTA phrase list, check for a viewport meta tag, and check image
   width/height attribute coverage.
5. Aggregate per-check findings across the sample as "`X`/`N` sampled pages" —
   never generalize a single-page issue to the whole site without qualifying scope.
6. Emit each finding with title, `severity_hint`, evidence, suggested action,
   `tags`, and `correlatable` (true for findings that could reinforce a
   discoverability finding, e.g. `structured_data`-adjacent navigation gaps).

## Running it
```bash
python3 scripts/engagement_analyzer.py <target-url> --max-pages 15 --timeout 6 --output ./engagement_raw.json
```
Requires `requests` and `beautifulsoup4`.

## Output
Writes a JSON file with `site`, `audited_at`, crawl metadata, and a `findings`
array of raw, unmerged findings — not the final unified schema. `audit-orchestrator`
combines this with `crawl-render-audit`'s output.

## Guardrails
- Read-only: GET/HEAD only, no forms, no authentication, no mutation.
- Independently respects the target's robots.txt.
- Reports sample-scoped findings, not site-wide claims, unless the issue was
  observed on every sampled page.
- Only emits a `severity_hint`, not final severity.
