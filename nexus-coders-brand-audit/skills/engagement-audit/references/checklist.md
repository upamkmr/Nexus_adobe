# On-Site Engagement, Retention & AI-Summary Readiness Checklist

This reference guide details granular evaluation criteria for assessing on-site visitor retention and AI-summary readiness. When an AI assistant cites a website and a visitor clicks through, they arrive with specific expectations and short attention spans. If the landing experience fails to orient and engage them immediately, they bounce back to the AI assistant.

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

## 6. AI-Summary & Email-Digest Content Readiness (Appendix F)

AI assistants and email clients increasingly generate summaries of page content and messages. When key content isn't in readable text, the summary has little to work with and important facts disappear.

- **Text-First Content Design**:
  - Ensure the core value proposition and key facts appear as plain HTML text, not solely in images, hero graphics, or interactive widgets.
  - Lead every page with a text-based summary before visual content.
- **Image-to-Text Content Ratio**:
  - Pages with many images but very little extractable text (< 300 chars) will be poorly summarized.
  - Maintain a text-to-image ratio of at least 60:40 for content-carrying pages.
- **Email Newsletter Best Practices**:
  - Always provide a plain-text version of email content.
  - Don't rely solely on images to carry the message — include alt text and inline text equivalents.
  - Keep the "important lines" (subject, key offer, CTA) as readable text, not embedded in image files.

---

## 7. Personalization & Prior-Context Readiness (Appendix E)

AI assistants personalize responses based on user context (location, preferences, conversation history). The site's content should be structured to support this personalization.

- **Above-the-Fold Content Density**:
  - The first 500 characters of every page should contain specific, substantive content that AI assistants can match against user queries.
  - Thin above-the-fold content gives the AI little to work with when deciding which page best answers a personalized query.
- **Context-Aware Referrer Handling**:
  - Consider detecting AI-assistant referrals (via HTTP referrer) and showing context-aware messaging.
  - Example: "Looking for the pricing discussed in ChatGPT? Here's the full breakdown."
- **Structured Audience Signals**:
  - Use Schema.org `audience` properties and industry qualifiers in structured data to help AI assistants target the right user segments.

---

## 8. Proactive Engagement Enhancements (Beyond-Defect Levers)
- **Instant Value Realization (Interactive Snippet / Calculator / Preview)**:
  - Embed lightweight, interactive preview components directly on the landing page so visitors experience immediate utility.
- **Context-Aware Referrer Personalization**:
  - Welcome ribbons or tailored hero messaging for visitors referred by AI assistants.
- **Rapid Search & Instant Answer Widget**:
  - Accessible global search bar (keyboard shortcut `/` or `Cmd+K`) allowing deep-linked visitors to query site resources immediately.
