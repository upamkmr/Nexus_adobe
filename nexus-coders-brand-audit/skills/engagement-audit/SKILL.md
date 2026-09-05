---
name: engagement-audit
description: Dedicated skill for auditing a website's on-site visitor engagement, orientation, and retention signals. Evaluates above-the-fold value proposition clarity, deep-link navigation orientation, reading density, call-to-action friction, and mobile viewport readiness. Use when diagnosing why visitors referred by AI assistants bounce immediately or fail to convert.
license: Apache-2.0
---

# Engagement Audit (On-Site Visitor Retention)

The `engagement-audit` skill assesses why human visitors who arrive at a website—especially those referred by AI assistant citations—stay, understand the offer, and convert, or bounce immediately.

## When to use
Activate this skill when:
- Investigating high bounce rates from search engines or AI assistant referral links.
- Evaluating whether landing pages clearly orient deep-linked visitors who bypassed the homepage.
- Auditing heading hierarchy, scannability, and information density.
- Identifying Call-to-Action (CTA) friction, ambiguous buttons, or dead-end pages.
- Checking mobile viewport readiness and layout stability.

## Inputs
- **`url`** (string, required): The target website URL or landing page to evaluate.
- **`html_content`** (string, optional): Raw or pre-rendered HTML content of the target page(s).
- **`crawler_metrics`** (object, optional): Quantitative metrics emitted by `discoverability-audit` (heading counts, viewport flags, text ratio).

## Procedure

1. **Review Detailed Guidelines**:
   Read the comprehensive checklist in [references/checklist.md](./references/checklist.md) for granular inspection criteria.

2. **Evaluate the 5 Engagement Dimensions**:
   - **Value Proposition Clarity**: Test whether a visitor can comprehend the product/service within 5 seconds based on the `<h1>` headline and supporting subhead.
   - **Orientation & Context Retention**: Ensure visitors arriving on deep subpages (docs, blogs, product specs) have clear breadcrumb trails and persistent branding to orient themselves.
   - **Scannability & Hierarchy**: Check for a clean `H1` -> `H2` -> `H3` sequence, concise bullet points, and the absence of unbroken prose blocks (> 5 lines).
   - **CTA Friction & Pathways**: Verify a prominent primary CTA with unambiguous action verbs, supplemented by a low-friction secondary exploration pathway. Ensure no dead ends.
   - **Mobile Viewport & Responsiveness**: Confirm `<meta name="viewport">` is properly configured and no fixed-width containers force horizontal scrolling.

3. **Synthesize Proactive Retention Opportunities**:
   Formulate at least one proactive enhancement (e.g. interactive product sandbox, contextual AI-referral banner, or `Cmd+K` instant search) that boosts visitor retention even if no structural defect exists.

4. **Format Findings**:
   Ensure all identified engagement issues provide concrete observational evidence and mechanism-sound remediation steps prioritized by impact.

## Output
Emits structured on-site retention findings detailing:
- Identified friction points with qualitative and quantitative evidence.
- Prioritized design and UX actions to maximize visitor retention and conversion.
- Proactive engagement levers to elevate user trust.
