---
name: audit-orchestrator
description: Entrypoint orchestrator skill for the nexus-coders-brand-audit marketplace. Coordinates the discoverability-audit and engagement-audit skills, both of which run deterministic, robots.txt-respecting crawls and emit quantitative, evidence-backed findings; executes both analyzers, captures outputs, mathematically sums severity counts into a unified summary block, concatenates findings into a single array, and emits the final unified JSON audit report. Use whenever a full brand AI-readiness and engagement audit is requested for any website or domain.
license: Apache-2.0
allowed-tools: Bash, WebSearch
---

# Audit Orchestrator (Brand AI-Readiness & Engagement Audit)

The `audit-orchestrator` skill is the primary entrypoint for the **Nexus Coders Brand Audit Marketplace**. It receives an audit request for any target website, orchestrates specialized sub-skills to inspect both off-site AI discoverability and on-site visitor retention, and emits the final unified audit report.

## When to use
Activate this skill when:
- Conducting an end-to-end audit of a brand's presence in AI assistants (ChatGPT, Claude, Perplexity, Gemini).
- Evaluating why a website fails to get cited, gets misrepresented, or experiences high visitor bounce rates from AI referrals.
- Generating a prioritized, evidence-backed report conforming to the official Adobe Hackathon Round 3 schema.

## Inputs
- **`url`** (string, required): The target domain or URL to audit (e.g., `https://example.com` or `adobe.com`).
- **`max_pages`** (integer, optional): Maximum pages to sample during crawl (default: 15, max: 50).
- **`timeout`** (integer, optional): Network timeout per request in seconds (default: 6).

## Procedure (Numbered, Deterministic Steps)

1. **Input Ingestion & Domain Normalization**:
   - Normalize the input string into a fully qualified HTTPS URL and extract the canonical domain name (`netloc`).
   - Validate sandbox constraints: ensure strictly read-only HTTP `GET`/`HEAD` requests; no mutating or authenticated operations.

2. **Automated Single-Entrypoint Orchestration**:
   - The primary execution path is the entrypoint script `skills/audit-orchestrator/scripts/orchestrator.py`, which executes both sub-skills, captures their outputs, and performs the mathematical merge:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py <target-url> --max-pages 15 --output ./unified_audit_report.json
     ```
     **This command alone does NOT include the live cross-web corroboration spot-check**
     (step 3's `WebSearch` sub-step below) — that step needs a tool call this script
     cannot make itself. To include it, run the corroboration procedure first (see step 3),
     save its findings as JSON, and pass it in:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py <target-url> --max-pages 15 \
       --corroboration-file ./corroboration_findings.json --output ./unified_audit_report.json
     ```
     Without `--corroboration-file`, the report is still complete and valid — it just covers
     the static `sameAs` proxy check only, not the live-search verification stage. The
     orchestrator logs this explicitly (to stderr) so it's never silently missing.
   - Alternatively, when running sub-skills separately in multi-agent pipelines, merge their captured JSON outputs via:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py --from-files ./discoverability_raw.json ./engagement_raw.json \
       --corroboration-file ./corroboration_findings.json --output ./unified_audit_report.json
     ```

3. **Sub-Skill 1: Off-Site Discoverability Audit**:
   - The orchestrator dispatches the `discoverability-audit` skill (`skills/discoverability-audit/scripts/crawler.py`) to gather quantitative metrics:
     - `robots.txt` AI crawler disallows (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.) — an informational finding about the *site*.
     - `llms.txt` and `/.well-known/llms.txt` presence.
     - Schema.org JSON-LD coverage across sampled pages.
     - Client-side JS rendering gaps (empty skeleton root tags).
     - Facts locked in non-text media: images missing descriptive `alt` text, canvas-heavy pages, and PDF-only content.
     - Cross-web entity corroboration (`sameAs` links to Wikidata, LinkedIn, Crunchbase).
     - Freshness indicators (copyright year, HTTP `Last-Modified`).
   - Note: the crawler's *own* traffic separately respects the site's `robots.txt` via `RobotFileParser` — it never fetches a disallowed path, regardless of what it reports about AI bots.
   - AI-bot block detection (both the full-site and partial/path-level case) is also
     computed via `RobotFileParser.can_fetch()` against the homepage and every sampled
     page, not by hand-parsing the raw robots.txt text — this correctly scopes
     `Disallow`/`Allow` rules to their own user-agent group even when groups aren't
     separated by a blank line.
   - **Live corroboration (agent step, not part of `crawler.py`)**: after the crawl,
     follow `skills/discoverability-audit/references/corroboration-guide.md` yourself
     (using this skill's `WebSearch` access) to spot-check up to 3 load-bearing factual
     claims against independent web sources. Write the resulting findings to a JSON file
     in the shared `{"findings": [...]}` shape, continuing the `F-0xx` numbering, then
     pass that file to the orchestrator via `--corroboration-file` (step 2) so it's
     actually included in the unified report rather than only living in this reference doc.

4. **Sub-Skill 2: On-Site Engagement & Retention Audit**:
   - The orchestrator dispatches the `engagement-audit` skill (`skills/engagement-audit/scripts/engagement_analyzer.py`), which performs its own independent, robots.txt-respecting crawl:
     - Above-the-fold value proposition clarity (`<h1>` count/uniqueness and specificity — the 5-second test).
     - Navigation orientation and breadcrumb trails for deep-linked arrivals.
     - Long unbroken prose blocks and reading scannability.
     - Call-to-Action (CTA) clarity and the share of pages with zero detectable CTA (dead ends).
     - Mobile viewport tag presence and image-dimension attributes (layout-shift risk).
   - For qualitative nuance the script cannot statically measure (rendered CLS, tap-target sizing, hero-visual quality), consult `skills/engagement-audit/references/checklist.md`.

5. **Deterministic Orchestrator Merge & Mathematical Summation**:
   - The orchestrator merges both outputs into a **Single Unified Audit Report**:
     - **Mathematical Summation**: Computes the exact sum of counts across both sub-skills into one single summary block:
       - `summary.total_findings = disc_summary.total_findings + eng_summary.total_findings`
       - `summary.critical = disc_summary.critical + eng_summary.critical`
       - `summary.high = disc_summary.high + eng_summary.high`
       - `summary.medium = disc_summary.medium + eng_summary.medium`
       - `summary.low = disc_summary.low + eng_summary.low`
     - **Findings Concatenation & Re-indexing**: Concatenates both `findings` lists into a single unified array and re-indexes all findings sequentially (`F-001`, `F-002`, `F-003`, ...) to eliminate duplicate ID collisions and provide a contiguous, prioritized list.
     - **Schema Integrity**: Validates that `summary.total_findings == len(findings)` and that each category count strictly reflects the findings in the array.
   - **On determinism**: `crawler.py` and `engagement_analyzer.py` are fully deterministic
     for the same HTML (no LLM judgment in their scoring loop). The optional live
     corroboration stage is the one exception — it inherently depends on an agent's
     WebSearch results and claim selection, so re-running it can surface different
     findings if the wider web has changed. That's expected and documented, not a bug.

6. **Incorporate Proactive "Beyond-Problem" Recommendations**:
   - In addition to fixing detected defects, synthesize forward-looking enhancements that actively boost AI citation share and visitor retention:
     - Suggest publishing a comprehensive `llms.txt` and `llms-full.txt` documentation manifest.
     - Propose Schema.org `FAQPage` or `HowTo` structured data to capture direct conversational question-and-answer snippets in Perplexity and Google AI Overviews.
     - Propose interactive instant-utility widgets (e.g., live preview, ROI calculator) to engage deep-linked visitors immediately upon arrival.

7. **Validate and Emit Unified Audit Report**:
   - Emit a single JSON document strictly conforming to the required schema floor. Emitting multiple separate JSON files is prohibited.

## Output Schema

The entrypoint emits a single JSON document strictly conforming to the following structure:

```json
{
  "site": "example.com",
  "audited_at": "2026-09-05T14:30:00Z",
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
      "title": "AI Assistant Crawlers Blocked in robots.txt",
      "severity": "critical",
      "evidence": "robots.txt disallows access to top AI retrieval crawlers: GPTBot, ClaudeBot. This directly prevents AI assistants from indexing or citing brand facts.",
      "suggested_action": {
        "summary": "Update robots.txt to explicitly allow GPTBot, ClaudeBot, and PerplexityBot on public marketing and documentation paths.",
        "priority": "high"
      }
    }
  ]
}
```
