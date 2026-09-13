---
name: discoverability-audit
description: Unified skill for auditing a website's off-site AI discoverability, entity corroboration, and content readiness for AI summarization. Evaluates robots.txt AI bot directives, XML sitemap, llms.txt, Schema.org JSON-LD, JS-render gaps, non-text media traps, cross-web entity disambiguation (Wikipedia/Wikidata), sameAs knowledge-graph links, OpenGraph/hreflang personalization signals, AI-summary content ratios, and temporal freshness. Use when diagnosing why a brand is missing, ignored, or poorly cited by AI assistants.
license: Apache-2.0
allowed-tools: Bash, WebSearch
---

# Discoverability Audit (Off-Site AI Readiness & Entity Corroboration)

The `discoverability-audit` skill assesses whether automated AI search crawlers and LLM retrieval engines can reach, parse, corroborate, and quote unambiguous brand facts from a website. It unifies crawl/render analysis with entity corroboration and freshness checking into a single cohesive skill — both are aspects of the same question: **"Can an AI assistant find, trust, and correctly cite this brand?"**

## When to use
Activate this skill when:
- Diagnosing why a brand does not appear in AI assistant search answers or citations.
- Checking if AI crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`) are blocked by `robots.txt`.
- Auditing XML sitemap declaration and `/sitemap.xml` presence for canonical page discovery.
- Auditing Schema.org JSON-LD structured data coverage across site pages.
- Detecting client-side JavaScript rendering traps (SPAs) where content is invisible to HTTP scrapers.
- Identifying facts trapped inside non-text assets (images without alt, canvas, PDF documents).
- Checking whether the brand's entity identity is grounded in external knowledge graphs (Wikidata, Wikipedia) and testing for naming collisions with other organizations.
- Evaluating content freshness signals (stale copyrights, missing `Last-Modified` headers).
- Assessing AI-summary readiness (pages where key content is locked in images, not text — Appendix F).
- Checking OpenGraph/hreflang personalization signals (Appendix E).

## Inputs
- **`url`** (string, required): The target website URL or domain (e.g. `https://example.com`).
- **`max_pages`** (integer, optional): Maximum number of pages to sample (default: 15).
- **`timeout`** (integer, optional): HTTP request timeout in seconds (default: 6).

## Guardrails
The bundled crawler is strictly read-only (GET only), parses the site's own `robots.txt` with standard library `RobotFileParser`, and **never fetches a path disallowed for its User-Agent or `*`**. It applies polite crawl delays, SSL fallback, and discards non-200 error pages (404/500) to avoid skewing metrics. Entity disambiguation uses only the public Wikipedia OpenSearch API.

## Procedure

1. **Invoke the Unified Discoverability Auditor**:
   Execute the bundled Python script [crawler.py](./scripts/crawler.py):
   ```bash
   python3 skills/discoverability-audit/scripts/crawler.py <target-url> --max-pages 15 --output ./discoverability_findings.json
   ```

2. **Analyze Core Off-Site AI Readability Signals**:
   - **AI Crawler Gatekeeping**: Review `robots.txt` directives for `GPTBot`, `ChatGPT-User`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, and `Applebot-Extended`.
   - **XML Sitemap Index**: Check `robots.txt` for `Sitemap:` directives and probe `/sitemap.xml`.
   - **Machine-Readable Standard (`llms.txt`)**: Check if the site serves `/llms.txt` or `/.well-known/llms.txt`.
   - **Structured Data Completeness**: Verify Schema.org types (`Organization`, `Product`, `FAQPage`, `BreadcrumbList`, `WebSite`) and valid JSON-LD.
   - **JS-Rendering / SSR Parity**: Detect SPA shells with framework markers (`data-reactroot`, `ng-app`, `#root`, `#__next`) and low text output.
   - **Non-Text Media Traps**: Images lacking `alt`, canvas-rendered graphics, PDF-only documents.
   - **Canonical Tag Coverage**: Self-referential canonical tags to prevent duplicate indexing.

3. **Entity Corroboration & Disambiguation**:
   - **Wikipedia/Wikidata Disambiguation**: Queries Wikipedia OpenSearch API using the TLD-extracted brand name to detect naming collisions with other notable entities.
   - **sameAs Knowledge Graph Links**: Inspects JSON-LD for authoritative `sameAs` links (Wikidata, Wikipedia, LinkedIn, Crunchbase).
   - **Temporal Freshness**: Copyright year staleness and HTTP `Last-Modified` header analysis.

4. **AI-Summary & Personalization Readiness (Appendices E & F)**:
   - **AI-Summary Content Ratio**: Flags pages with very high image-to-text ratios that would be poorly summarized by AI assistants in email digests, search snippets, or chat answers.
   - **OpenGraph Metadata**: Checks `og:title`, `og:description`, `og:image` completeness — used by AI assistants to personalize how the brand is presented to each user.
   - **hreflang Locale Tags**: Checks for language/region alternate tags that help AI assistants serve geographically relevant content.

5. **Agent WebSearch Spot-Checking (Optional Multi-Agent Mode)**:
   For environments with live web search capabilities, consult [references/corroboration-guide.md](./references/corroboration-guide.md) to spot-check up to 3 load-bearing claims against independent third-party sources.

## Output
Emits a structured findings dictionary containing:
- Discovered off-site discoverability defects with quantified evidence.
- Entity disambiguation warnings with Wikipedia search results.
- AI-summary readiness and personalization signal findings.
- Prioritized, mechanism-sound technical fixes with concrete code/directive examples.
- Proactive suggestions (e.g., FAQPage schema, llms.txt, disambiguatingDescription).
