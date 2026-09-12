---
name: audit-orchestrator
description: Entrypoint skill for the brand-ai-readiness-audit marketplace. Given a website, plans and runs the discoverability (crawl-render-audit), engagement (engagement-audit), and optionally corroboration (freshness-corroboration) sub-skills; performs the qualitative reasoning a script cannot — cross-skill correlation, root-cause clustering, severity calibration, conflict resolution, graceful degradation on sub-skill failure — then hands the result to a deterministic merge/validation script for the mechanical parts (summation, ID assignment, schema validation) before emitting the single unified audit report. Use whenever a full brand AI-discoverability-and-engagement audit is requested for any website.
license: Apache-2.0
allowed-tools: Bash
---

# Audit Orchestrator

This is the marketplace's designated entrypoint. It does not reimplement any
sub-skill's domain logic (crawl heuristics, corroboration methodology, scoring).
Its job is to plan the audit, run the sub-skills, reason across their outputs,
and hand off to a deterministic script for the parts that must be exactly
reproducible.

> **Sub-skills find and measure. The orchestrator reasons and prioritizes. The
> merge script guarantees the arithmetic and schema are always correct.**

## Inputs
- `url` (string, required): target website or domain.
- `max_pages` (integer, optional, default 15, max 50): passed through to both crawl
  sub-skills.
- `timeout` (integer, optional, default 6): passed through to both crawl sub-skills.
- `run_corroboration` (boolean, optional, default true): whether to run
  `freshness-corroboration` on load-bearing claims surfaced by
  `crawl-render-audit`.

## Procedure

### 1. Plan
Normalize the URL. Both `crawl-render-audit` and `engagement-audit` always apply
to a full audit; `freshness-corroboration` applies only if `crawl-render-audit`
surfaces specific factual claims worth checking (skip it rather than forcing a
speculative search when no such claims exist).

### 2. Execute sub-skills
Run the two crawl-based sub-skills — independent of each other, in parallel where
the environment allows:
```bash
python3 ../crawl-render-audit/scripts/crawler.py <url> --max-pages <max_pages> --timeout <timeout> --output ./discoverability_raw.json
python3 ../engagement-audit/scripts/engagement_analyzer.py <url> --max-pages <max_pages> --timeout <timeout> --output ./engagement_raw.json
```
If either command fails or the output file is missing/unreadable, do **not** abort
the whole audit — proceed with whichever sub-skill(s) succeeded, and record the
gap (the merge script surfaces this automatically as `_coverage_warnings`).

If `discoverability_raw.json` contains specific, checkable factual claims and
`run_corroboration` is true, invoke `freshness-corroboration` against up to 3 of
the most load-bearing claims, writing `corroboration_raw.json` in the same shape.

### 3. Reason across the raw outputs (this is the step a script cannot do)
Before finalizing, read all raw finding sets and:
- **Correlate.** Look for findings from different sub-skills that describe the
  same underlying weakness (e.g. missing structured data + no entity
  corroboration + a client-rendering gap may all stem from "insufficient
  machine-readable brand representation"). Where you find such a relationship
  that the sub-skills didn't already both tag as `correlatable` with a shared
  `tag`, edit the raw finding tags/`correlatable` flags accordingly before
  invoking the merge script, so the deterministic clustering step in section 4
  actually catches it. Do not silently merge findings the mechanical step won't
  also be able to reproduce — keep the tags as the source of truth.
- **Resolve conflicts**, using this precedence: direct evidence over inference;
  page-specific evidence over site-wide assumption; independent corroboration
  over unsupported claims; more recent/higher-quality evidence over stale
  evidence; multiple independent signals over a single heuristic. If a genuine
  conflict can't be resolved, keep both findings and note the tension in their
  evidence text rather than silently picking one.
- **Calibrate severity beyond the mechanical guardrail.** The merge script
  refuses to auto-escalate certain tags (e.g. `crawler_access`) to `critical`
  unless a finding is explicitly marked `override_critical: true`. Only set that
  flag yourself, with justification in the evidence text, when you've confirmed
  the block is both (a) targeting essential public content and (b) leaving no
  other discovery path — per Step: Severity calibration below.
- **Respect sampling scope.** Do not let a finding observed on 2 of 15 pages read
  as a site-wide claim in your reasoning or in any text you add — the scope
  field (`site` / `sample`) should already reflect this from the sub-skill, keep
  it that way.

### 4. Deterministic merge, dedup, and validation
Once tags/`correlatable` flags and any `override_critical` decisions are set,
hand off to the merge script for the mechanical, must-be-reproducible part:
tag-based clustering of `correlatable` findings across sub-skills, severity
guardrail enforcement, sequential ID assignment (after clustering, so counts
never drift), and schema validation.
```bash
python3 scripts/merge_report.py \
  --site <domain> \
  --discoverability ./discoverability_raw.json \
  --engagement ./engagement_raw.json \
  --corroboration ./corroboration_raw.json \
  --output ./unified_audit_report.json
```
Omit `--corroboration` if that sub-skill wasn't run. If the script exits non-zero,
it printed validation errors to stderr — fix the underlying issue (do not hand-edit
the JSON to force it to pass) and re-run.

### 5. Add proactive, beyond-defect recommendations
Beyond fixing detected problems, consider adding recommendations framed explicitly
as **opportunities** (not guaranteed outcomes), such as:
- Publishing `llms.txt` / `llms-full.txt` if not already flagged as missing.
- Adding `FAQPage` or `HowTo` structured data to capture conversational
  question-and-answer snippets.
- Adding an interactive instant-utility widget (calculator, live preview) for
  deep-linked visitors.
Add these as additional entries in the `findings` array with an explicit
`"proactive": true` field (the schema floor doesn't require this field, but it's
useful for the reader) — but only after the merge script has produced the
validated core report, so IDs stay numbered from a single final pass. If adding
findings after merge, keep IDs sequential and re-validate summary counts by hand.

### 6. Final checks before returning the report to the user
- Every material finding traces to evidence actually produced by a sub-skill or
  this orchestration step — never invent a finding.
- Proactive recommendations are clearly distinguishable from confirmed defects.
- The report is the single JSON document required by the schema — no side files.

## Failure handling
A sub-skill failing must not invalidate the whole audit:
- Record the failure, do not retry expensive crawls repeatedly (retry once only
  if the failure looks transient, e.g. a timeout).
- Continue with whichever sub-skill(s) succeeded.
- Lower confidence in / qualify any reasoning that depended on the missing
  sub-skill's evidence, and surface the gap explicitly (`_coverage_warnings`
  from the merge script, or your own note if you add findings after merge).

## Severity calibration (applies to your judgment calls in step 3)
- **Critical**: a confirmed issue creating a severe, site-wide barrier — e.g. a
  robots.txt block on essential public content with no other discovery path, or
  the site being unreachable entirely.
- **High**: materially reduces discoverability/engagement but doesn't block
  access entirely — e.g. structured data missing across most sampled pages,
  a severe rendering gap, most pages lacking any CTA.
- **Medium**: a real but non-blocking issue — e.g. partial structured-data
  coverage, missing breadcrumbs, no cross-web entity links.
- **Low**: minor optimization or a weak heuristic signal — e.g. a slightly stale
  copyright year, a handful of images missing alt text.

## Guardrails
- Recommend-only: nothing in this marketplace modifies the live site.
- Read-only, robots.txt-respecting throughout (enforced independently by each
  crawl sub-skill).
- No authenticated, destructive, or rate-abusive actions.
- Never expose internal orchestration state (raw per-skill JSON, tag/clustering
  mechanics) in the final report — only the schema's required fields plus any
  optional fields explicitly useful to the reader (e.g. `scope`, `proactive`).

## Output Schema
```json
{
  "site": "example.com",
  "audited_at": "2026-09-20T14:32:00Z",
  "summary": {
    "total_findings": 6,
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 0
  },
  "findings": [
    {
      "id": "F-001",
      "title": "No JSON-LD structured data on product pages",
      "severity": "high",
      "evidence": "Crawled 12 product pages; 0/12 contain schema.org markup.",
      "suggested_action": {
        "summary": "Add Product/Offer JSON-LD to every product page.",
        "priority": "high"
      }
    }
  ]
}
```
`id`, `title`, `severity`, `evidence`, `suggested_action` are required per finding;
`site`, `audited_at`, and `summary` (counts by severity) are required at the root.
Additional fields (e.g. `scope`, `proactive`) may be included.
