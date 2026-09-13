---
name: audit-orchestrator
description: Entrypoint orchestrator for the brand audit marketplace. Runs discoverability and engagement audits across a target site, reconciles findings, deduplicates issues, calculates AI readiness scores, and outputs a single unified JSON report.
license: Apache-2.0
allowed-tools:
  - bash
  - read_file
  - write_file
metadata:
  version: 2.0.0
  author: Nexus Coders
  dependencies:
    - requests>=2.28.0
    - beautifulsoup4>=4.11.0
    - pandas>=1.4.0
    - tldextract>=3.0.0
---

# Audit Orchestrator (Brand AI-Readiness & Engagement Audit)

The `audit-orchestrator` skill is the primary entrypoint for the brand audit marketplace. When given a website URL, it delegates work to two specialized sub-skills—`discoverability-audit` (for crawler accessibility, structured data, and entity disambiguation) and `engagement-audit` (for on-site visitor retention and AI summary readiness)—then synthesizes their output into one clean, unified JSON audit report.

For IPC protocols and schema details, see [references/orchestration-protocol.md](references/orchestration-protocol.md).

## When to use
Activate this skill when:
- Running a full brand audit across AI search assistants (ChatGPT, Claude, Perplexity, Gemini).
- Diagnosing why a site isn't cited, suffers from entity confusion, has high referral bounce rates, or loses key info in AI email digests.
- Emitting an evidence-backed audit report conforming to the hackathon schema floor.

## Inputs
- `url` (string, required): Target URL or domain (e.g., `https://example.com` or `adobe.com`).
- `max_pages` (integer, optional): Page sample budget (default: 15, max: 50).
- `timeout` (integer, optional): Request timeout in seconds (default: 6).

## Procedure

1. **URL Normalization & Safety Checks**:
   - Normalize user input into a canonical HTTPS URL and pull the registrable domain via TLD-aware parsing.
   - Enforce read-only GET/HEAD requests; verify no state-mutating requests occur.

2. **Automated Orchestration Run**:
   - Primary path: run the master runner `skills/audit-orchestrator/scripts/orchestrator.py`:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py <target-url> --max-pages 15 --output ./unified_audit_report.json
     ```
   - Alternatively, merge existing JSON reports from disk:
     ```bash
     python3 skills/audit-orchestrator/scripts/orchestrator.py --from-files ./disc_report.json ./eng_report.json --output ./unified_audit_report.json
     ```

3. **Sub-Skill 1: Off-Site Discoverability & Entity Corroboration (`discoverability-audit`)**:
   - Executes `skills/discoverability-audit/scripts/crawler.py` to audit:
     - `robots.txt` AI crawler rules (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.).
     - XML sitemap presence in `robots.txt` and `/sitemap.xml`.
     - `llms.txt` and `/.well-known/llms.txt` context manifests.
     - Schema.org JSON-LD coverage across sampled URLs.
     - Raw vs. rendered JS gaps (empty SPA mount points, low text-to-code ratios, hydration blobs, noscript tags).
     - Text locked inside canvas, PDFs, or images missing alt attributes.
     - Canonical tag consistency.
     - Wikipedia/Wikidata entity disambiguation (catches name collisions with unrelated organizations).
     - `sameAs` links to authoritative profiles (Wikidata, LinkedIn, Crunchbase).
     - Freshness indicators: copyright years, `Last-Modified` headers, schema date fields.
     - OpenGraph, Twitter Cards, and hreflang locale declarations (Appendix E).

4. **Sub-Skill 2: On-Site Engagement & AI-Summary Readiness (`engagement-audit`)**:
   - Executes `skills/engagement-audit/scripts/engagement_analyzer.py` to check:
     - Above-the-fold value prop clarity (`<h1>` count, specificity, 5-second test).
     - Orientation cues and breadcrumb trails for visitors arriving directly on deep links.
     - Reading density and wall-of-text paragraphs.
     - CTA friction and dead-end pages.
     - Mobile viewport tag and image aspect ratios to prevent CLS.
     - AI email-digest readiness (Appendix F): image-to-text ratios, opening boilerplate displacement, and invisible preheaders.
     - Above-the-fold personalization density (Appendix E).

5. **Cross-Skill Synthesis & Deduplication**:
   - Merges findings into the unified report:
     - **Re-indexing**: Sequential IDs (`F-001`, `F-002`, ...) to eliminate collisions.
     - **Math Reconciliation**: Ensures `total_findings == sum(severities) == len(findings)`.
     - **Deduplication**: Collapses duplicate issues between skills while combining evidence.
     - **Executive Summary**: Computes 0–100 AI readiness score, health grade, and top priority recommendations.

6. **Proactive Opportunities**:
   - Recommends proactive enhancements where applicable:
     - Structured Claim Provenance (`ClaimReview` / `citation`) for verifiable AI citations.
     - `FAQPage` schema for conversational search snippets.
     - `llms.txt` manifests.

7. **Report Output**:
   - Writes the final JSON report to disk and prints a concise summary.

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
  "executive_summary": {
    "overall_ai_readiness_score": 75,
    "readiness_grade": "C (Fair - Optimization Required)",
    "top_priorities": [
      "[CRITICAL] AI Assistant Crawlers Blocked in robots.txt: Update robots.txt to explicitly allow AI crawlers...",
      "[HIGH] Deficient Schema.org JSON-LD Structured Data: Inject Schema.org JSON-LD on every page..."
    ],
    "category_scores": {
      "off_site_discoverability": {"score": 70, "status": "Needs Improvement"},
      "on_site_engagement": {"score": 85, "status": "Good with Opportunities"},
      "email_ai_summary_readiness": {"score": 70, "status": "Needs Improvement"}
    },
    "executive_brief": "Website 'example.com' scored 75/100..."
  },
  "findings": [
    {
      "id": "F-001",
      "title": "AI Assistant Crawlers Blocked in robots.txt",
      "severity": "critical",
      "evidence": "robots.txt disallows GPTBot, ClaudeBot...",
      "suggested_action": {
        "summary": "Update robots.txt to explicitly allow AI crawlers on public documentation:\n\nUser-agent: GPTBot\nAllow: /",
        "priority": "critical"
      }
    }
  ]
}
```

## Guardrails
- **Read-only**: Sends GET/HEAD requests only; never mutates the target site.
- **Polite Crawling**: Respects `robots.txt`, includes sensible crawl delays, and handles network timeouts gracefully.
- **Deterministic**: No non-deterministic dependencies or paid APIs required.
