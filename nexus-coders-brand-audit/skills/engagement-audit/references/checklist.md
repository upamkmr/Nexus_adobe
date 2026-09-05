# On-Site Engagement & Retention Audit Checklist

This reference guide details granular evaluation criteria for assessing on-site visitor retention. When an AI assistant cites a website and a visitor clicks through, they arrive with specific expectations and short attention spans. If the landing experience fails to orient and engage them immediately, they bounce back to the AI assistant.

---

## 1. Above-The-Fold Value Proposition Clarity (The 5-Second Test)
- **Primary Heading (`<h1>`)**:
  - Exactly one `<h1>` per page.
  - Must state *what* the product/service does and *who* it is for in plain language within 60 characters.
  - Avoid vague marketing jargon (e.g., "Empowering Synergy" vs "Cloud Cost Optimization for AWS").
- **Sub-headline Context**:
  - Directly supports the `<h1>` with a concrete 1-2 sentence explanation of benefits or capabilities.
- **Hero Visual Alignment**:
  - Hero image or interactive graphic demonstrates the actual product/interface rather than generic stock photography.

---

## 2. Landing Orientation & Context Retention (Deep-Link Arrival)
- **Deep-Link Landing Friction**:
  - When visitors land directly on a documentation page, blog post, or feature sub-page from an AI citation, is the overarching brand identity immediately clear?
- **Breadcrumb Navigation**:
  - Presence of semantic breadcrumb trails (`<nav aria-label="Breadcrumb">` and Schema.org `BreadcrumbList`).
  - Allows visitors to easily navigate upward to parent categories or product suites.
- **Persistent Header & Clear Hierarchy**:
  - Sticky or readily accessible top navigation containing primary section links (Docs, Pricing, Features, Company).

---

## 3. Information Density & Scannability (Signal-to-Noise Ratio)
- **Heading Progression**:
  - Logical hierarchical structure (`H1` -> `H2` -> `H3`) without skipped levels.
  - Section headers must be descriptive and summarize the takeaway of the subsequent section.
- **Bulleted Lists & Micro-Content**:
  - Key specifications, feature benefits, and steps presented as scannable bullet points or numbered lists.
  - Avoid unbroken "walls of text" (> 5 lines of continuous prose without sub-breaks).
- **Visual Callouts & Key Takeaways**:
  - Use of highlighted callout boxes (notes, tips, warnings) to surface crucial facts for rapid skimming.

---

## 4. Call-to-Action (CTA) Clarity & Friction Points
- **Primary CTA Dominance**:
  - A single, prominent high-contrast CTA button visible above the fold (e.g., "Start Free Trial", "Read Documentation", "Request Demo").
  - Uses specific action verbs rather than ambiguous text ("Click Here", "Learn More").
- **Secondary / Low-Commitment Pathway**:
  - Provide a secondary pathway for visitors not yet ready to convert (e.g., "Explore Interactive Demo" or "Browse API Reference").
- **Dead-End Elimination**:
  - Every page (including 404s and search results) must provide clear next steps or recommended related resources rather than terminating abruptly.

---

## 5. Responsive Viewport & Layout Stability
- **Mobile Viewport Configuration**:
  - Explicit `<meta name="viewport" content="width=device-width, initial-scale=1.0">` tag in `<head>`.
  - Prevents desktop-scale zoom distortion on mobile referrals.
- **Horizontal Overflow & Touch Targets**:
  - No fixed-width elements (e.g., tables or code blocks) that break viewport bounds on mobile screens.
  - Tap targets (buttons, menu links) must have at least 44x44px clickable padding.
- **Visual Stability & Cumulative Layout Shift (CLS)**:
  - Width and height attributes on images and video embeds to prevent page jumping during asynchronous load.

---

## 6. Proactive Engagement Enhancements (Beyond-Defect Levers)
- **Instant Value Realization (Interactive Snippet / Calculator / Preview)**:
  - Embed lightweight, interactive preview components (e.g., interactive code sandbox, ROI calculator, live search preview) directly on the landing page so visitors experience immediate utility.
- **Context-Aware Referrer Personalization**:
  - Welcome ribbons or tailored hero messaging for visitors referred by AI assistants (e.g., "Looking for the pricing discussed in ChatGPT? Here is the full breakdown.").
- **Rapid Search & Instant Answer Widget**:
  - Accessible global search bar (keyboard shortcut `/` or `Cmd+K`) allowing deep-linked visitors to query site resources immediately.
