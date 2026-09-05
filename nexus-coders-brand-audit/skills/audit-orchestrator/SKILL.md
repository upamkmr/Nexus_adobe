---
name: audit-orchestrator
description: Entrypoint orchestrator skill for the nexus-coders-brand-audit marketplace. Coordinates the discoverability-audit and engagement-audit skills, aggregates quantitative crawl metrics and qualitative UX friction checks, synthesizes proactive beyond-defect recommendations, and emits the final unified JSON audit report. Use whenever a full brand AI-readiness and engagement audit is requested for any website or domain.
license: Apache-2.0
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

2. **Execute Off-Site Discoverability Audit**:
   - Trigger the `discoverability-audit` skill by running its bundled Pandas-powered crawler:
     ```bash
     python3 skills/discoverability-audit/scripts/crawler.py <target-url> --max-pages 15 --output ./discoverability_raw.json
     ```
   - Ingest quantitative metrics covering:
     - `robots.txt` AI crawler disallows (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.).
     - `llms.txt` and `/.well-known/llms.txt` presence.
     - Schema.org JSON-LD coverage across sampled pages.
     - Client-side JS rendering gaps (empty skeleton root tags).
     - Images missing descriptive `alt` text.
     - Cross-web entity corroboration (`sameAs` links to Wikidata, LinkedIn, Crunchbase).
     - Freshness indicators (copyright year, HTTP `Last-Modified`).

3. **Execute On-Site Engagement & Retention Audit**:
   - Trigger the `engagement-audit` skill using the criteria in `skills/engagement-audit/references/checklist.md`.
   - Evaluate sampled pages against human visitor retention signals:
     - Above-the-fold value proposition clarity (the 5-second test on `<h1>` and subheads).
     - Navigation orientation and breadcrumb trails for deep-linked arrivals.
     - Heading hierarchy progression and reading scannability.
     - Call-to-Action (CTA) clarity, visual dominance, and elimination of dead ends.
     - Mobile viewport tag presence and responsive layout stability.

4. **Correlate, Deduplicate, and Prioritize Findings**:
   - Assign sequential IDs (`F-001`, `F-002`, ...).
   - Assign calibrated severities (`critical`, `high`, `medium`, `low`) based on impact:
     - `critical`: Direct technical blocks stopping AI crawlers entirely (e.g. `robots.txt` blocking AI bots) or complete site inaccessibility.
     - `high`: Major barriers preventing fact extraction or driving bounces (missing JSON-LD on key pages, JS hydration skeletons, missing mobile viewport, entity ambiguity).
     - `medium`: Friction hurting scannability or indexing efficiency (images missing alt text, broken heading hierarchy, missing `llms.txt`).
     - `low`: Minor heuristic signals (stale copyright year).

5. **Incorporate Proactive "Beyond-Problem" Recommendations**:
   - In addition to fixing detected defects, generate forward-looking enhancements that actively boost AI citation share and visitor retention:
     - Suggest publishing a comprehensive `llms.txt` and `llms-full.txt` documentation manifest.
     - Propose Schema.org `FAQPage` or `HowTo` structured data to capture direct conversational question-and-answer snippets in Perplexity and Google AI Overviews.
     - Propose interactive instant-utility widgets (e.g., live preview, ROI calculator) to engage deep-linked visitors immediately upon arrival.

6. **Validate and Emit Unified Audit Report**:
   - Validate that the output strictly adheres to the required schema:
     - Root object has `site`, `audited_at` (ISO 8601), `summary` (`total_findings`, `critical`, `high`, `medium`), and `findings` array.
     - Each finding contains `id`, `title`, `severity`, `evidence`, and `suggested_action` (`summary`, `priority`).
     - Summary counts match the exact number of findings by severity.

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
