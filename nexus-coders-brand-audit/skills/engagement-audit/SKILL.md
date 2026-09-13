---
name: engagement-audit
description: Audits on-site visitor engagement, retention friction, and AI-summary / email-digest readiness. Evaluates above-the-fold value proposition clarity, navigation orientation, reading density, CTA friction, mobile viewport stability, and email-digest content readiness.
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
---

# Engagement Audit (On-Site Visitor Retention & AI-Summary Readiness)

The `engagement-audit` skill assesses why visitors who arrive at a website—especially those referred by AI assistant citations—stay and explore or bounce immediately. It also checks whether page content survives automated summarization in AI email digests, search snippets, and conversational answers (Appendix F). The skill is self-contained: it runs its own polite crawl and does not require `discoverability-audit` to run first.

For comprehensive guidelines and templates, see:
- [references/checklist.md](references/checklist.md) — 8-dimension qualitative evaluation checklist for visitor retention and scannability.
- [references/email-readiness-guide.md](references/email-readiness-guide.md) — Email template architecture, AI inbox preheader optimization, and plain-text protocols.

## When to use
Activate this skill when:
- Diagnosing high bounce rates from search engines or AI assistant referral links.
- Evaluating whether landing pages orient visitors who land directly on deep links rather than the homepage.
- Auditing heading hierarchy, scannability, and information density.
- Spotting Call-to-Action (CTA) friction, vague buttons, or dead-end pages.
- Checking mobile viewport tags and layout shift risks.
- Checking whether content will survive AI email-digest summarization (Appendix F).
- Evaluating above-the-fold content density for AI-personalized referrals (Appendix E).

## Inputs
- `url` (string, required): Target website URL or domain (e.g., `https://example.com`).
- `max_pages` (integer, optional): Maximum pages to sample (default: 10, max: 30).
- `timeout` (integer, optional): HTTP request timeout in seconds (default: 6).

## Procedure

1. **Run the Engagement Analyzer**:
   Execute the bundled Python analyzer [engagement_analyzer.py](./scripts/engagement_analyzer.py):
   ```bash
   python3 skills/engagement-audit/scripts/engagement_analyzer.py <target-url> --max-pages 10 --output ./engagement_findings.json
   ```

2. **Cross-Check with the Reference Checklist**:
   For aspects that cannot be measured statically (such as hero visual context or live tap target geometry), consult [references/checklist.md](references/checklist.md) and spot-check the page visually.

3. **The 8 Dimensions Evaluated**:
   - **Value Proposition Clarity**: `<h1>` count/uniqueness, benefit alignment, and 5-second test failures.
   - **Orientation & Context Retention**: Presence of breadcrumbs or clear navigation on deep-linked landing pages.
   - **Scannability & Hierarchy**: Paragraphs exceeding ~450 characters, heading progression (`H1` -> `H2` -> `H3`), and bullet list usage.
   - **CTA Friction & Conversion Pathways**: Ambiguous button text ('Click Here', 'Learn More') and pages with zero CTA (dead ends).
   - **Mobile Viewport & Layout Stability**: `<meta name="viewport">` and image dimension attributes to minimize CLS.
   - **AI Email-Digest & Inbox Readiness (Appendix F)**: Image-to-text ratios (< 60:40), opening boilerplate filler displacement, and invisible inbox preheaders.
   - **Above-the-Fold Personalization Density (Appendix E)**: Whether first-visible text gives AI assistants enough substance to match user persona and prior context.
   - **Proactive Retention Enhancements**: Instant-value interactive widgets and context-aware referrer personalization.

4. **Output Verification**:
   Verify the emitted JSON report conforms to the shared schema before handing off to `audit-orchestrator`.

## Output
Emits a structured findings JSON detailing:
- Identified friction points with quantitative evidence.
- AI-summary and email-digest readiness warnings.
- Prioritized design and UX recommendations with copy-pasteable HTML/CSS code snippets.
- Proactive engagement levers (Instant-value widget, AI referrer welcome ribbon).
