---
name: discoverability-audit
description: Audits off-site AI discoverability, entity corroboration, and structured data infrastructure. Evaluates robots.txt AI bot access, XML sitemaps, llms.txt, Schema.org JSON-LD, JS hydration gaps, non-text media traps, Wikipedia entity disambiguation, sameAs links, OpenGraph metadata, and temporal freshness.
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
    - tldextract>=3.0.0
---

# Discoverability Audit (Off-Site AI Readiness & Entity Corroboration)

The `discoverability-audit` skill checks whether AI search engines and retrieval bots (ChatGPT Search, Claude, Perplexity, Gemini) can fetch, parse, corroborate, and quote facts from a website without stumbling into crawler blocks, blank SPA shells, or entity naming confusion.

For technical deep-dives and implementation references, see:
- [references/ai-crawler-spec.md](references/ai-crawler-spec.md) — AI user-agent tokens, `robots.txt` rules, and SSR prerendering rules.
- [references/claim-provenance-guide.md](references/claim-provenance-guide.md) — Structured Claim Provenance and Schema.org Audience markup.
- [references/corroboration-guide.md](references/corroboration-guide.md) — Cross-web entity disambiguation procedures.

## When to use
Activate this skill when:
- Diagnosing why a brand isn't cited by AI search assistants.
- Checking if AI crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`) are blocked by `robots.txt`.
- Auditing XML sitemap declaration and `/sitemap.xml` presence for canonical page discovery.
- Checking Schema.org JSON-LD structured data coverage across site pages.
- Detecting client-side JavaScript rendering traps (SPAs) where content is invisible to simple HTTP scrapers.
- Finding facts trapped inside non-text assets (images without alt, canvas graphics, PDF documents).
- Checking whether the brand's entity identity is grounded in external knowledge graphs (Wikidata, Wikipedia) and testing for naming collisions.
- Checking freshness signals (stale copyright notices, missing `Last-Modified` headers, schema date fields).
- Checking OpenGraph, Twitter Cards, and hreflang localization signals (Appendix E).

## Inputs
- `url` (string, required): Target URL or domain (e.g., `https://example.com`).
- `max_pages` (integer, optional): Maximum pages to sample (default: 15).
- `timeout` (integer, optional): HTTP request timeout in seconds (default: 6).

## Guardrails
The bundled crawler is strictly read-only (GET only). It parses `robots.txt` with standard library `RobotFileParser` and **never fetches a disallowed path**. It applies polite delays, handles SSL fallback, and filters out non-200 responses (404/500) to keep metrics clean. Entity disambiguation queries the public Wikipedia OpenSearch API directly.

## Procedure

1. **Run the Discoverability Crawler**:
   Execute the bundled script [crawler.py](./scripts/crawler.py):
   ```bash
   python3 skills/discoverability-audit/scripts/crawler.py <target-url> --max-pages 15 --output ./discoverability_findings.json
   ```

2. **Inspect Off-Site Retrieval & Crawlability Signals**:
   - **AI Crawler Gatekeeping**: Review `robots.txt` for `GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, and `Applebot-Extended`.
   - **XML Sitemap Discovery**: Check for `Sitemap:` declarations in `robots.txt` and verify `/sitemap.xml` response.
   - **Machine-Readable Standard (`llms.txt`)**: Probe for `/llms.txt` and `/.well-known/llms.txt`.
   - **Structured Data Completeness**: Verify Schema.org types (`Organization`, `Product`, `FAQPage`, `BreadcrumbList`, `WebSite`) and valid JSON-LD.
   - **JS-Rendering / SSR Parity (Appendix C)**: Multi-signal SPA detection: empty DOM containers (`#root`, `#app`, `#__next`), low text-to-markup ratios, client hydration JSON blobs (`__NEXT_DATA__`), and `<noscript>` warnings.
   - **Non-Text Media Traps**: Images lacking `alt`, canvas-rendered graphics, PDF-only documents.
   - **Canonical Tag Coverage**: Self-referential canonical tags to avoid duplicate indexing.

3. **Entity Corroboration & Disambiguation (Appendix D)**:
   - **Wikipedia/Wikidata Disambiguation**: Queries Wikipedia OpenSearch API using the TLD-extracted brand name to detect naming collisions with other notable entities.
   - **sameAs Knowledge Graph Links**: Inspects JSON-LD for authoritative `sameAs` links (Wikidata, Wikipedia, LinkedIn, Crunchbase).
   - **Temporal Freshness**: Copyright year staleness, `Last-Modified` HTTP headers, and structured schema date fields (`dateModified`, `datePublished`).

4. **Personalization & Prior-Context Signals (Appendix E)**:
   - **OpenGraph & Twitter Cards Metadata**: Checks `og:title`, `og:description`, `og:image` completeness.
   - **hreflang Locale Tags**: Checks for language/region alternate tags for geographic relevance.
   - **Schema.org Audience Declarations**: Inspects structured data for `audience`, `targetAudience`, and `knowsAbout` declarations.

5. **Proactive Opportunities**:
   - **Structured Claim Provenance**: Concrete JSON-LD snippets for Schema.org `Claim` / `ClaimReview`.
   - **FAQPage Schema**: Structured Q&A snippets targeting conversational AI engines.
   - **Canonical `llms.txt`**: Ready-to-publish context window markdown manifests.

## Output
Emits a structured findings dictionary containing:
- Discovered discoverability defects with quantified evidence.
- Entity disambiguation warnings with Wikipedia search results.
- Personalization and structured data signals.
- Prioritized technical fixes with copy-pasteable configuration and code snippets.
- Proactive suggestions (Claim provenance, FAQPage schema, llms.txt).
