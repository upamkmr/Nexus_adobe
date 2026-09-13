---
name: audit-orchestrator
description: Designated entrypoint orchestrator skill for the nexus-coders-brand-audit marketplace. Coordinates specialized sub-skills (crawl-render-audit, freshness-corroboration, engagement-audit), executes audits, captures quantitative outputs, performs cross-skill correlation and mathematical summation, and emits the Single Unified Audit Report strictly conforming to the required schema. Use whenever a full website or domain brand audit is requested.
license: Apache-2.0
allowed-tools: Bash, WebSearch
---

# Audit Orchestrator (Brand AI-Readiness & Engagement Audit)

The `audit-orchestrator` skill is the primary entrypoint for the **Nexus Coders Brand Audit Marketplace**. It receives an audit request for any target website, orchestrates specialized sub-skills across off-site AI discoverability, cross-web corroboration/freshness, and on-site visitor retention, and emits the final unified audit report.

## When to use
Activate this skill when:
- Conducting an end-to-end audit of a brand's visibility and reputation across AI assistants (ChatGPT, Claude, Perplexity, Gemini).
- Evaluating why a website fails to get cited, suffers from entity confusion, or experiences high bounce rates from AI referrals.
- Generating a prioritized, evidence-backed audit report conforming strictly to the official Adobe Hackathon Round 3 schema floor.

## Inputs
- **`url`** (string, required): The target domain or URL to audit (e.g., `https://example.com` or `adobe.com`).
- **`max_pages`** (integer, optional): Maximum pages to sample during crawl (default: 15, max: 50).
- **`timeout`** (integer, optional): Network timeout per request in seconds (default: 6).

## Procedure (Numbered, Deterministic Steps)

1. **Target Normalization & Sandbox Guardrail Verification**:
   - Normalize the input string into a canonical HTTPS URL and extract the registrable domain.
   - Enforce read-only GET/HEAD requests; verify that no modifying, authenticated, or rate-abusive actions are performed.

2. **Automated Single-Entrypoint Orchestration**:
   - The primary execution path is the entrypoint master script `skills/audit-orchestrator/scripts/orchestrator.py`, which composes all sub-skills and produces the final unified report:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py <target-url> --max-pages 15 --output ./unified_audit_report.json
     ```
   - Alternatively, when running sub-skills separately in distributed multi-agent workflows, merge pre-existing JSON reports via:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py --from-files ./crawl_report.json ./corr_report.json ./eng_report.json --output ./unified_audit_report.json
     ```

3. **Sub-Skill 1: Off-Site AI Discoverability & Crawl Readiness (`crawl-render-audit`)**:
   - Executes `skills/crawl-render-audit/scripts/crawler.py` to evaluate:
     - `robots.txt` AI retrieval crawler access (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.).
     - XML Sitemap discovery in `robots.txt` and at `/sitemap.xml`.
     - `llms.txt` and `/.well-known/llms.txt` presence for LLM context windows.
     - Schema.org JSON-LD structured data coverage across sampled pages.
     - Client-side JS rendering gaps (empty skeleton root tags `#root`, `#app`, `#__next`).
     - Facts locked in non-text media: images missing `alt` text, canvas-rendered graphics, and PDF-only documents.
     - Canonical URL tag coverage.
   - Note: The crawler self-enforces robots.txt compliance via `urllib.robotparser.RobotFileParser` for its own traffic, ignoring non-200 error pages.

4. **Sub-Skill 2: Cross-Web Corroboration & Freshness (`freshness-corroboration`)**:
   - Executes `skills/freshness-corroboration/scripts/corroboration_checker.py` to evaluate:
     - External knowledge base search (Wikipedia OpenSearch API) to identify brand-name entity ambiguity and naming collisions with other organizations.
     - Presence of authoritative `sameAs` entity links (Wikidata, Wikipedia, LinkedIn, Crunchbase) in root schema.
     - Temporal content staleness indicators (outdated copyright years, missing `Last-Modified` headers).
   - For environments with interactive agent web search tools, consult `skills/freshness-corroboration/references/corroboration-guide.md` to spot-check load-bearing facts.

5. **Sub-Skill 3: On-Site Engagement & Visitor Retention (`engagement-audit`)**:
   - Executes `skills/engagement-audit/scripts/engagement_analyzer.py` to evaluate:
     - Above-the-fold value proposition clarity (`<h1>` count, uniqueness, and specificity).
     - Landing orientation and breadcrumb trails for deep-linked arrivals.
     - Long unbroken prose blocks and reading density.
     - Call-to-Action (CTA) friction and pages with zero detectable CTA (dead ends).
     - Mobile viewport tag presence and layout-shift risk (images missing dimensions).

6. **Cross-Skill Synthesis & Mathematical Resummation**:
   - The orchestrator merges all outputs into a **Single Unified Audit Report**:
     - **Mathematical Summation**: Computes the exact sum of counts across all sub-skills:
       - `summary.total_findings = sum(severities) == len(findings)`
       - Validates that `critical`, `high`, `medium`, and `low` counts match the findings array.
     - **Findings Concatenation & Re-indexing**: Concatenates and re-indexes all findings sequentially (`F-001`, `F-002`, `F-003`, ...) to eliminate duplicate ID collisions.
     - **Deduplication & Cross-Skill Correlation**: Intelligently correlates overlapping findings (e.g. structured data + entity links) and merges duplicate titles while preserving evidence context.

7. **Proactive "Beyond-Problem" Opportunities**:
   - Synthesizes non-obvious proactive enhancements that strengthen AI discovery and retention even where no defect was found:
     - Schema.org `FAQPage` or `HowTo` structured data to capture direct conversational citations in Perplexity and Google AI Overviews.
     - `llms.txt` context manifest formatted for LLM token ingestion.
     - Above-the-fold instant-utility widgets (e.g., live preview, ROI calculator) to retain deep-linked AI visitors.

8. **Emit Final JSON Audit Report**:
   - Emits a single JSON document strictly conforming to the required schema floor.

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

## Guardrails
- **Recommend-only**: Audits and reports only; never modifies the live target website.
- **Read-only & Safe**: Uses polite delays, respects `robots.txt`, and operates in a standard sandbox.
- **Self-contained**: Portable and deterministic; no external subscription or proprietary model weights required.
