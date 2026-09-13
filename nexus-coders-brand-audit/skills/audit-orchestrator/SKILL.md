---
name: audit-orchestrator
description: Designated entrypoint orchestrator skill for the nexus-coders-brand-audit marketplace. Coordinates two specialized sub-skills (discoverability-audit and engagement-audit), executes audits, captures quantitative outputs, performs cross-skill correlation and mathematical summation, and emits the Single Unified Audit Report strictly conforming to the required schema. Use whenever a full website or domain brand audit is requested.
license: Apache-2.0
allowed-tools: Bash, WebSearch
---

# Audit Orchestrator (Brand AI-Readiness & Engagement Audit)

The `audit-orchestrator` skill is the primary entrypoint for the **Nexus Coders Brand Audit Marketplace**. It receives an audit request for any target website, orchestrates two specialized sub-skills covering off-site AI discoverability (including entity corroboration and freshness) and on-site visitor retention (including AI-summary/email-digest readiness), and emits the final unified audit report.

## When to use
Activate this skill when:
- Conducting an end-to-end audit of a brand's visibility and reputation across AI assistants (ChatGPT, Claude, Perplexity, Gemini).
- Evaluating why a website fails to get cited, suffers from entity confusion, experiences high bounce rates from AI referrals, or has content dropped by AI email summarizers.
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
   - Alternatively, merge pre-existing JSON reports:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py --from-files ./disc_report.json ./eng_report.json --output ./unified_audit_report.json
     ```

3. **Sub-Skill 1: Off-Site AI Discoverability & Entity Corroboration (`discoverability-audit`)**:
   - Executes `skills/discoverability-audit/scripts/crawler.py` to evaluate:
     - `robots.txt` AI retrieval crawler access (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.).
     - XML Sitemap discovery in `robots.txt` and at `/sitemap.xml`.
     - `llms.txt` and `/.well-known/llms.txt` presence for LLM context windows.
     - Schema.org JSON-LD structured data coverage across sampled pages.
     - Client-side JS rendering gaps (SPA shells with framework markers).
     - Facts locked in non-text media: images missing `alt`, canvas graphics, PDF-only.
     - Canonical URL tag coverage.
     - Cross-web entity disambiguation via Wikipedia/Wikidata API (brand naming collisions).
     - Authoritative `sameAs` knowledge graph links (Wikidata, LinkedIn, Crunchbase).
     - Content freshness signals (copyright staleness, `Last-Modified` headers).
     - OpenGraph metadata completeness for AI personalization (Appendix E).
     - hreflang locale tags for geographically personalized AI responses (Appendix E).
     - AI-summary content ratios — pages with high image-to-text ratios poorly suited for email digests (Appendix F).

4. **Sub-Skill 2: On-Site Engagement & AI-Summary Readiness (`engagement-audit`)**:
   - Executes `skills/engagement-audit/scripts/engagement_analyzer.py` to evaluate:
     - Above-the-fold value proposition clarity (`<h1>` count, uniqueness, specificity).
     - Landing orientation and breadcrumb trails for deep-linked arrivals.
     - Long unbroken prose blocks and reading density.
     - Call-to-Action (CTA) friction and pages with zero detectable CTA (dead ends).
     - Mobile viewport tag presence and layout-shift risk (images missing dimensions).
     - AI email-digest content readiness — pages where visual content dominates with minimal extractable text (Appendix F).
     - Above-the-fold personalization density — whether first-visible content gives AI assistants enough to match user context (Appendix E).

5. **Cross-Skill Synthesis & Mathematical Resummation**:
   - The orchestrator merges all outputs into a **Single Unified Audit Report**:
     - **Mathematical Summation**: `summary.total_findings = sum(severities) == len(findings)`.
     - **Findings Concatenation & Re-indexing**: Sequential `F-001`, `F-002`… to eliminate ID collisions.
     - **Deduplication & Cross-Skill Correlation**: Merges overlapping findings (e.g., entity + email-summary) while preserving evidence.

6. **Proactive "Beyond-Problem" Opportunities**:
   - Synthesizes non-obvious proactive enhancements:
     - Schema.org `FAQPage` for conversational AI citations.
     - `llms.txt` context manifest for LLM token ingestion.
     - Instant-value widgets and context-aware referrer personalization for AI-referred visitors.

7. **Emit Final JSON Audit Report**:
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
      "evidence": "robots.txt disallows GPTBot, ClaudeBot...",
      "suggested_action": {
        "summary": "Update robots.txt to allow AI crawlers:\n\nUser-agent: GPTBot\nAllow: /",
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
