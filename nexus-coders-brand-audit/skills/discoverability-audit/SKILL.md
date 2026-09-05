---
name: discoverability-audit
description: Dedicated skill for auditing a website's off-site AI readiness and machine discoverability. Evaluates robots.txt AI bot directives, llms.txt support, Schema.org JSON-LD structured data, JS-rendering hydration gaps, non-text locked content, and cross-web entity corroboration. Use when diagnosing why a brand is missing, ignored, or hallucinated by AI assistants (ChatGPT, Claude, Perplexity, Gemini).
license: Apache-2.0
---

# Discoverability Audit (Off-Site AI Readiness)

The `discoverability-audit` skill assesses whether automated AI search crawlers and LLM retrieval engines can reach, parse, and quote unambiguous brand facts from a website.

## When to use
Activate this skill when:
- Diagnosing why a brand does not appear in AI assistant search answers or citations.
- Checking if AI crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`) are blocked by `robots.txt`.
- Auditing Schema.org JSON-LD structured data coverage across site pages.
- Detecting client-side JavaScript rendering traps (SPAs) where content is invisible to raw HTTP scrapers.
- Identifying facts trapped inside non-text assets (images missing alt attributes, uncaptioned tables).
- Checking cross-web entity corroboration (Wikidata/Wikipedia/LinkedIn `sameAs` links).

## Inputs
- **`url`** (string, required): The target website URL or domain (e.g. `https://example.com`).
- **`max_pages`** (integer, optional): Maximum number of pages to sample (default: 15).
- **`timeout`** (integer, optional): HTTP request timeout in seconds (default: 6).

## Procedure

1. **Invoke the Quantitative Crawler**:
   Execute the bundled Python crawler script [crawler.py](./scripts/crawler.py):
   ```bash
   python3 skills/discoverability-audit/scripts/crawler.py <target-url> --max-pages 15 --output ./discoverability_findings.json
   ```

2. **Analyze Core Off-Site AI Readability Signals**:
   - **AI Crawler Gatekeeping**: Review `robots.txt` directives for `GPTBot`, `ChatGPT-User`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, and `Applebot-Extended`.
   - **Machine-Readable Standard (`llms.txt`)**: Check if the site serves `/llms.txt` or `/.well-known/llms.txt` for direct context window ingestion.
   - **Structured Data Completeness**: Verify Schema.org types (`Organization`, `Product`, `FAQPage`, `BreadcrumbList`, `WebSite`) and valid JSON-LD syntax.
   - **JS-Rendering / SSR Parity**: Check text-to-HTML ratio and flag empty root containers (`#root`, `#app`, `#__next`) that hide content from non-browser bots.
   - **Non-Text Media Locks**: Identify images, diagrams, or badges lacking descriptive `alt` tags.
   - **Entity Corroboration & Disambiguation**: Verify `sameAs` links to authoritative external entity graphs (Wikidata, Crunchbase, LinkedIn) to eliminate brand mistaken identity.
   - **Content Freshness**: Inspect HTTP `Last-Modified` headers, `dateModified` metadata, and footer copyright dates.

3. **Validate Empirical Findings**:
   Review the generated `discoverability_findings.json` to ensure:
   - Each finding contains concrete numerical evidence (e.g., `X/Y pages`, `Z% coverage`).
   - Every issue assigns an accurate severity (`critical`, `high`, `medium`, or `low`).
   - Suggested actions specify mechanism-sound remedies (e.g. specific Schema.org types, SSR pre-rendering configs) rather than generic advice.

## Output
Emits a structured findings dictionary containing:
- Discovered off-site discoverability defects with quantified evidence.
- Prioritized, mechanism-sound technical fixes.
- Proactive suggestions that strengthen AI discoverability beyond baseline defects.
