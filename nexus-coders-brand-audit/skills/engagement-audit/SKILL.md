---
name: engagement-audit
description: Dedicated skill for auditing a website's on-site visitor engagement, retention, and AI-summary/email-digest readiness. Deterministically measures above-the-fold value proposition clarity, deep-link navigation orientation, reading density, call-to-action friction, mobile viewport readiness, AI email-summary content readiness (Appendix F), and above-the-fold personalization signals (Appendix E). Use when diagnosing why visitors referred by AI assistants bounce or why content is dropped by AI email summarizers.
license: Apache-2.0
allowed-tools: Bash
---

# Engagement Audit (On-Site Visitor Retention & AI-Summary Readiness)

The `engagement-audit` skill assesses why human visitors who arrive at a website—especially those referred by AI assistant citations—stay, understand the offer, and convert, or bounce immediately. It also evaluates whether the site's content is structured to survive AI summarization in emails, search snippets, and chat answers (Appendix F). It is self-contained: it performs its own polite, robots.txt-respecting crawl and does not depend on `discoverability-audit` having run first.

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
- **`max_pages`** (integer, optional): Maximum pages to sample (default: 10, max: 50).
- **`timeout`** (integer, optional): HTTP request timeout in seconds (default: 6).

## Procedure (Numbered, Deterministic Steps)

1. **Invoke the Quantitative Analyzer**:
   Execute the bundled Python analyzer [engagement_analyzer.py](./scripts/engagement_analyzer.py):
   ```bash
   python3 skills/engagement-audit/scripts/engagement_analyzer.py <target-url> --max-pages 10 --output ./engagement_findings.json
   ```

2. **Cross-Check Against the Detailed Checklist**:
   For nuances the script cannot measure statically (hero visual quality, tap-target sizing, true rendered CLS), consult [references/checklist.md](./references/checklist.md) and spot-check the rendered page.

3. **The 7 Engagement Dimensions Measured**:
   - **Value Proposition Clarity**: `<h1>` count/uniqueness and whether it reads as a concrete phrase.
   - **Orientation & Context Retention**: For non-homepage pages, presence of breadcrumb trails or persistent `<nav>`/`<header>`.
   - **Scannability & Hierarchy**: Paragraphs exceeding ~800 characters, heading structure, and list usage.
   - **CTA Friction & Pathways**: Ratio of vague CTA copy to total, and share of pages with zero CTA.
   - **Mobile Viewport & Layout Stability**: `<meta name="viewport">` and `<img>` width/height attributes.
   - **AI-Summary & Email-Digest Readiness (Appendix F)**: Image-to-text ratio flagging pages that would be poorly summarized by AI assistants in emails or chat.
   - **Above-the-Fold Personalization Density (Appendix E)**: Whether the first 500 characters contain enough substantive text for AI assistants to match against user context.

4. **Synthesize Proactive Retention Opportunities**:
   The analyzer always emits at least one proactive, beyond-defect recommendation (e.g. instant-value widget, context-aware referrer personalization).

5. **Validate Output**:
   Confirm the emitted JSON conforms to the shared schema before the `audit-orchestrator` merges it.

## Output
Emits a structured findings JSON detailing:
- Identified friction points with concrete quantitative evidence.
- AI-summary readiness warnings.
- Prioritized design and UX actions with code/directive examples.
- Proactive engagement levers.
