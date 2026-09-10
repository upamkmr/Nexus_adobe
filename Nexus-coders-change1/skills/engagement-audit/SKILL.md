---
name: engagement-audit
description: Dedicated skill for auditing a website's on-site visitor engagement, orientation, and retention signals. Deterministically measures above-the-fold value proposition clarity, deep-link navigation orientation, reading density, call-to-action friction, and mobile viewport readiness. Use when diagnosing why visitors referred by AI assistants bounce immediately or fail to convert.
license: Apache-2.0
allowed-tools: Bash
---

# Engagement Audit (On-Site Visitor Retention)

The `engagement-audit` skill assesses why human visitors who arrive at a website—especially those referred by AI assistant citations—stay, understand the offer, and convert, or bounce immediately. It is self-contained: it performs its own polite, robots.txt-respecting crawl and does not depend on `discoverability-audit` having run first, so it stays portable as a standalone skill.

## When to use
Activate this skill when:
- Investigating high bounce rates from search engines or AI assistant referral links.
- Evaluating whether landing pages clearly orient deep-linked visitors who bypassed the homepage.
- Auditing heading hierarchy, scannability, and information density.
- Identifying Call-to-Action (CTA) friction, ambiguous buttons, or dead-end pages.
- Checking mobile viewport readiness and layout-shift risk.

## Inputs
- **`url`** (string, required): The target website URL or domain to evaluate (e.g. `https://example.com`).
- **`max_pages`** (integer, optional): Maximum pages to sample (default: 10, max: 50).
- **`timeout`** (integer, optional): HTTP request timeout in seconds (default: 6).

## Procedure (Numbered, Deterministic Steps)

1. **Invoke the Quantitative Analyzer**:
   Execute the bundled Python analyzer [engagement_analyzer.py](./scripts/engagement_analyzer.py), which crawls the site read-only (GET only, respects `robots.txt`, polite crawl delay) and scores every sampled page:
   ```bash
   python3 skills/engagement-audit/scripts/engagement_analyzer.py <target-url> --max-pages 10 --output ./engagement_findings.json
   ```

2. **Cross-Check Against the Detailed Checklist**:
   For any nuance the script cannot measure statically (hero visual quality, tap-target sizing, true rendered Cumulative Layout Shift, whether CTA copy is contextually accurate), consult [references/checklist.md](./references/checklist.md) and spot-check the rendered page. The script measures the 5 dimensions below with concrete HTML signals; the checklist covers the qualitative judgment calls that require actually looking at the rendered page.

3. **The 5 Engagement Dimensions Measured**:
   - **Value Proposition Clarity**: `<h1>` count/uniqueness and whether it reads as a concrete phrase rather than a single vague word.
   - **Orientation & Context Retention**: for every non-homepage ("deep") page sampled, presence of a breadcrumb trail (`<nav aria-label="Breadcrumb">` or Schema.org `BreadcrumbList`) or a persistent `<nav>`/`<header>`.
   - **Scannability & Hierarchy**: count of paragraphs exceeding ~800 characters (proxy for "unbroken prose > 5 lines") and presence of lists.
   - **CTA Friction & Pathways**: ratio of vague CTA copy ("Click Here", "Learn More") to total detected buttons/CTA-styled links, and the share of pages with zero detectable CTA (dead ends).
   - **Mobile Viewport & Layout Stability**: `<meta name="viewport">` presence and the share of `<img>` tags missing explicit `width`/`height` (CLS risk).

4. **Synthesize Proactive Retention Opportunities**:
   The analyzer always emits at least one proactive, beyond-defect recommendation (e.g. an above-the-fold instant-value widget for AI-referred visitors) even when no structural defect is found.

5. **Validate Output**:
   Confirm the emitted JSON conforms to the shared schema (`site`, `audited_at`, `summary`, `findings[]` with `id`/`title`/`severity`/`evidence`/`suggested_action`) before the `audit-orchestrator` merges it.

## Output
Emits a structured findings JSON (same schema as `discoverability-audit`) detailing:
- Identified friction points with concrete quantitative evidence (page counts, ratios).
- Prioritized design and UX actions to maximize visitor retention and conversion.
- Proactive engagement levers to elevate user trust.
