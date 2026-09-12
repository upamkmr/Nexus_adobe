# Brand AI-Readiness & Engagement Audit — Skill Marketplace

Given any website, this marketplace audits both halves of the Round-2 problem —
**why a brand isn't found/cited by AI assistants** and **why visitors who do
arrive don't stay** — and emits a single prioritized, evidence-backed report.

## Skills in this marketplace

| Skill | Role | Tools |
|---|---|---|
| **audit-orchestrator** *(entrypoint)* | Plans the audit, runs the other skills, performs cross-skill reasoning (correlation, conflict resolution, severity calibration, graceful degradation), then hands off to a deterministic script for merging/validating the final report. | Bash |
| **crawl-render-audit** | Independent, robots.txt-respecting crawl measuring off-site AI discoverability: AI-bot access in robots.txt, `llms.txt`, Schema.org/JSON-LD coverage, client-render gaps, non-text-locked facts, cross-web entity links, freshness. | Bash |
| **engagement-audit** | Independent, robots.txt-respecting crawl measuring on-site visitor retention: H1/value-prop clarity, navigation/breadcrumbs, scannability, CTA presence, mobile viewport, layout-shift risk. | Bash |
| **freshness-corroboration** | Spot-checks a small number of load-bearing factual claims (surfaced by crawl-render-audit) against independent web sources, and flags brand-name entity ambiguity. | WebSearch |

## Why this decomposition
Each concern (off-site crawlability, on-site retention, external fact-checking) has
genuinely different inputs, tools, and failure modes — the crawl skills need no
network judgment calls and run fully deterministically; corroboration inherently
requires live web search and lower-confidence classification. Splitting them lets
each skill stay narrowly scoped, testable in isolation, and independently reusable
(e.g. `engagement-audit` alone answers "why do our visitors bounce," with no
discoverability logic pulled in unnecessarily).

## How the entrypoint composes them
`audit-orchestrator` deliberately separates **judgment** from **arithmetic**:

1. It runs `crawl-render-audit` and `engagement-audit` (and, if warranted,
   `freshness-corroboration`) and treats each as authoritative for its own domain
   logic — it never reimplements crawl heuristics or corroboration methodology.
2. It performs the reasoning a script cannot: correlating findings across skills
   into root causes, resolving conflicts, calibrating severity (with an explicit
   guardrail against auto-escalating certain issue types to "critical"), and
   deciding how to degrade gracefully if a sub-skill fails.
3. It hands off to `scripts/merge_report.py` — a small, fully deterministic script
   — for the parts that must be exactly reproducible every time: tag-based
   clustering of cross-skill findings the reasoning step has flagged as related,
   sequential ID assignment *after* clustering (so `summary.total_findings` always
   equals `len(findings)`), and schema validation.

This hybrid avoids two failure modes seen in earlier drafts of this design: a
purely mechanical merge that double-counts overlapping findings and can't do
root-cause synthesis, and a purely free-form reasoning approach with no
guaranteed-reproducible arithmetic or schema conformance.

## Running a full audit
```bash
cd skills/crawl-render-audit && pip install requests beautifulsoup4 --break-system-packages
python3 scripts/crawler.py example.com --max-pages 15 --output ../../discoverability_raw.json

cd ../engagement-audit
python3 scripts/engagement_analyzer.py example.com --max-pages 15 --output ../../engagement_raw.json

# (optional) freshness-corroboration is agent-executed via WebSearch, not a script —
# see skills/freshness-corroboration/SKILL.md

cd ../audit-orchestrator
python3 scripts/merge_report.py \
  --site example.com \
  --discoverability ../../discoverability_raw.json \
  --engagement ../../engagement_raw.json \
  --output ../../unified_audit_report.json
```

## Scope & guardrails
- **Recommend-only.** Nothing in this marketplace modifies a live site.
- **Read-only, robots.txt-respecting.** Each crawl skill enforces this
  independently for its own traffic.
- No authenticated, destructive, or rate-abusive actions anywhere in the
  marketplace.
- Output conforms to the required floor schema (`site`, `audited_at`, `summary`,
  `findings[]` with `id`/`title`/`severity`/`evidence`/`suggested_action`), with a
  few additive fields (`scope`, `proactive`) for a clearer report.
