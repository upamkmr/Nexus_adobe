---
name: crawl-render-audit
description: Dedicated skill for auditing a website's off-site AI readiness and machine discoverability. Evaluates robots.txt AI bot directives, XML sitemap availability, canonical tags, llms.txt support, Schema.org JSON-LD structured data, JS-rendering hydration gaps, and facts locked in non-text media (images/canvas/PDF). Use when diagnosing why a brand is missing, ignored, or poorly extracted by AI assistants (ChatGPT, Claude, Perplexity, Gemini).
license: Apache-2.0
allowed-tools: Bash
---

# Crawl & Render Audit (Off-Site AI Discoverability)

The `crawl-render-audit` skill assesses whether automated AI search crawlers and LLM retrieval engines can reach, parse, and quote unambiguous brand facts from a website.

## When to use
Activate this skill when:
- Diagnosing why a brand does not appear in AI assistant search answers or citations.
- Checking if AI crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`) are blocked by `robots.txt`.
- Auditing XML sitemap declaration and `/sitemap.xml` presence for canonical page discovery.
- Auditing Schema.org JSON-LD structured data coverage across site pages.
- Detecting client-side JavaScript rendering traps (SPAs) where content is invisible to raw HTTP scrapers.
- Identifying facts trapped inside non-text assets (images missing alt attributes, canvas graphics, PDF documents).
- Checking canonical URL tag consistency across public pages.

## Inputs
- **`url`** (string, required): The target website URL or domain (e.g. `https://example.com`).
- **`max_pages`** (integer, optional): Maximum number of pages to sample (default: 15).
- **`timeout`** (integer, optional): HTTP request timeout in seconds (default: 6).

## Guardrails
The bundled crawler is strictly read-only (GET only), parses the site's own `robots.txt` with standard library `RobotFileParser`, and **never fetches a path disallowed for its User-Agent or `*`** — separate from the informational check of whether AI bots (`GPTBot`, `ClaudeBot`, etc.) are blocked, which is a *finding about the site*, not a rule for the crawler's own traffic. It also applies polite crawl delays and SSL fallback. Non-200 error pages (404/500) are safely ignored to avoid skewing metrics.

## Procedure

1. **Invoke the Quantitative Crawler**:
   Execute the bundled Python crawler script [crawler.py](./scripts/crawler.py):
   ```bash
   python3 skills/crawl-render-audit/scripts/crawler.py <target-url> --max-pages 15 --output ./discoverability_findings.json
   ```

2. **Analyze Core Off-Site AI Readability Signals**:
   - **AI Crawler Gatekeeping**: Review `robots.txt` directives for `GPTBot`, `ChatGPT-User`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, and `Applebot-Extended`.
   - **XML Sitemap Index**: Check `robots.txt` for `Sitemap:` directives and probe `/sitemap.xml`.
   - **Machine-Readable Standard (`llms.txt`)**: Check if the site serves `/llms.txt` or `/.well-known/llms.txt` for direct context window ingestion.
   - **Structured Data Completeness**: Verify Schema.org types (`Organization`, `Product`, `FAQPage`, `BreadcrumbList`, `WebSite`) and valid JSON-LD syntax.
   - **JS-Rendering / SSR Parity**: Check text-to-HTML ratio and flag empty root containers (`#root`, `#app`, `#__next`) that hide content from non-browser bots.
   - **Non-Text Media Traps**: Identify images lacking descriptive `alt` tags, canvas-rendered graphics, and PDF-only documents.
   - **Canonical Tag Coverage**: Check for self-referential canonical tags to prevent duplicate indexing.

3. **Validate Empirical Findings**:
   Review the generated `discoverability_findings.json` to ensure:
   - Each finding contains concrete numerical evidence (e.g., `X/Y pages`, `Z% coverage`).
   - Every issue assigns an accurate severity (`critical`, `high`, `medium`, or `low`).
   - Suggested actions specify mechanism-sound remedies with code/directive examples.

## Output
Emits a structured findings dictionary containing:
- Discovered off-site discoverability defects with quantified evidence.
- Prioritized, mechanism-sound technical fixes.
- Proactive suggestions (e.g., FAQPage schema, llms.txt) that strengthen AI discoverability beyond baseline defects.
