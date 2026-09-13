---
name: engagement-audit
description: Dedicated skill for auditing a website's on-site visitor engagement, retention, and AI-summary/email-digest readiness. Deterministically measures above-the-fold value proposition clarity, deep-link navigation orientation, reading density, call-to-action friction, mobile viewport readiness, AI email-summary content readiness (Appendix F: text-vs-image ratios, preheader optimization, boilerplate displacement), and above-the-fold personalization signals (Appendix E). Use when diagnosing why visitors referred by AI assistants bounce or why content is dropped by AI email summarizers.
version: 2.0.0
author: Nexus Coders
license: Apache-2.0
allowed-tools:
  - bash
  - read_file
  - write_file
dependencies:
  - requests>=2.28.0
  - beautifulsoup4>=4.11.0
  - pandas>=1.4.0
---

# Engagement Audit (On-Site Visitor Retention & AI-Summary Readiness)

The `engagement-audit` skill assesses why human visitors who arrive at a website—especially those referred by AI assistant citations—stay, understand the offer, and convert, or bounce immediately. It also evaluates whether the site's content is structured to survive AI summarization in emails, inbox digests, search snippets, and chat answers (Appendix F). It is self-contained: it performs its own polite, robots.txt-respecting crawl and does not depend on `discoverability-audit` having run first.

For comprehensive guidelines and templates, see:
- [checklist.md](file:///home/iron-man/.gemini/antigravity-ide/scratch/Nexus_adobe/nexus-coders-brand-audit/skills/engagement-audit/references/checklist.md) — 8-dimension qualitative evaluation checklist for visitor retention and scannability.
- [email-readiness-guide.md](file:///home/iron-man/.gemini/antigravity-ide/scratch/Nexus_adobe/nexus-coders-brand-audit/skills/engagement-audit/references/email-readiness-guide.md) — Email template architecture, AI inbox preheader optimization, and plain-text fallback protocols.

## When to use
Activate this skill when:
- Investigating high bounce rates from search engines or AI assistant referral links.
- Evaluating whether landing pages clearly orient deep-linked visitors who bypassed the homepage.
- Auditing heading hierarchy, scannability, and information density.
- Identifying Call-to-Action (CTA) friction, ambiguous buttons, or dead-end pages.
- Checking mobile viewport readiness and layout-shift risk.
- Assessing whether content would survive AI email-digest summarization (Appendix F).
- Evaluating above-the-fold content density for AI-personalized referrals (Appendix E).

## Inputs
- **`url`** (string, required): The target website URL or domain to evaluate (e.g. `https://example.com`).
- **`max_pages`** (integer, optional): Maximum pages to sample (default: 10, max: 30).
- **`timeout`** (integer, optional): HTTP request timeout in seconds (default: 6).

## Procedure (Numbered, Deterministic Steps)

1. **Invoke the Quantitative Analyzer**:
   Execute the bundled Python analyzer [engagement_analyzer.py](./scripts/engagement_analyzer.py):
   ```bash
   python3 skills/engagement-audit/scripts/engagement_analyzer.py <target-url> --max-pages 10 --output ./engagement_findings.json
   ```

2. **Cross-Check Against the Detailed Checklist**:
   For nuances the script cannot measure statically (hero visual quality, tap-target sizing, true rendered CLS), consult [references/checklist.md](./references/checklist.md) and spot-check the rendered page.

3. **The 8 Engagement Dimensions Measured**:
   - **Value Proposition Clarity**: `<h1>` count/uniqueness, benefit alignment, and 5-second test failure detection.
   - **Orientation & Context Retention**: For non-homepage pages, presence of breadcrumb trails or persistent `<nav>`/`<header>`.
   - **Scannability & Hierarchy**: Paragraphs exceeding ~450 characters, heading progression (`H1` -> `H2` -> `H3`), and bullet list usage.
   - **CTA Friction & Conversion Pathways**: Ambiguous button text ('Click Here', 'Learn More') and pages with zero CTA (dead ends).
   - **Mobile Viewport & Layout Stability**: `<meta name="viewport">` and `<img>` explicit width/height attributes to eliminate CLS.
   - **AI Email-Digest & Inbox Summarization Readiness (Appendix F)**: Image-to-text ratios (< 60:40), opening boilerplate filler displacement, and invisible inbox preheaders.
   - **Above-the-Fold Personalization Density (Appendix E)**: Whether the first 500 characters contain substantive text answering who/what/why to match user persona and prior context.
   - **Proactive Retention Enhancement**: Instant-value interactive widget and context-aware referrer personalization.

4. **Validate Output**:
   Confirm the emitted JSON conforms to the shared schema before the `audit-orchestrator` merges it.

## Output
Emits a structured findings JSON detailing:
- Identified friction points with concrete quantitative evidence.
- AI-summary and email-digest readiness warnings.
- Prioritized design and UX actions with copy-pasteable HTML/CSS code snippets.
- Proactive engagement levers (Instant-value widget, AI referrer welcome ribbon).
