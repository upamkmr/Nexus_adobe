---
name: discoverability-audit
description: Unified skill for auditing a website's off-site AI discoverability, entity corroboration, and machine-readable data infrastructure. Evaluates robots.txt AI bot access, XML sitemaps, llms.txt, Schema.org JSON-LD, multi-signal raw-vs-rendered JS gaps, non-text media traps, Wikipedia/Wikidata entity disambiguation, authoritative sameAs knowledge-graph links, OpenGraph/hreflang personalization, Schema.org Audience targeting, and Structured Claim Provenance. Use when diagnosing why a brand is missing or misrepresented in conversational AI.
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
  - tldextract>=3.0.0
---

# Discoverability Audit (Off-Site AI Readiness & Entity Corroboration)

The `discoverability-audit` skill assesses whether automated AI search crawlers and LLM retrieval engines can reach, parse, corroborate, and quote unambiguous brand facts from a website. It unifies crawl/render analysis with entity corroboration, freshness verification, and machine-readable personalization into a single cohesive skill: **"Can an AI assistant find, trust, and correctly cite this brand?"**

For detailed technical specifications and implementation guides, see:
- [ai-crawler-spec.md](file:///home/iron-man/.gemini/antigravity-ide/scratch/Nexus_adobe/nexus-coders-brand-audit/skills/discoverability-audit/references/ai-crawler-spec.md) — AI crawler user-agents, robots.txt directives, and SSR prerendering rules.
- [claim-provenance-guide.md](file:///home/iron-man/.gemini/antigravity-ide/scratch/Nexus_adobe/nexus-coders-brand-audit/skills/discoverability-audit/references/claim-provenance-guide.md) — Structured Claim Provenance and Schema.org Audience markup.
- [corroboration-guide.md](file:///home/iron-man/.gemini/antigravity-ide/scratch/Nexus_adobe/nexus-coders-brand-audit/skills/discoverability-audit/references/corroboration-guide.md) — Cross-web claim corroboration and disambiguation procedures.

## When to use
Activate this skill when:
- Diagnosing why a brand does not appear in AI assistant search answers or citations.
- Checking if AI crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`) are blocked by `robots.txt`.
- Auditing XML sitemap declaration and `/sitemap.xml` presence for canonical page discovery.
- Auditing Schema.org JSON-LD structured data coverage across site pages.
- Detecting client-side JavaScript rendering traps (SPAs) where content is invisible to HTTP scrapers.
- Identifying facts trapped inside non-text assets (images without alt, canvas graphics, PDF documents).
- Checking whether the brand's entity identity is grounded in external knowledge graphs (Wikidata, Wikipedia) and testing for naming collisions with other organizations.
- Evaluating content freshness signals (stale copyrights, missing `Last-Modified` headers).
- Checking OpenGraph, Twitter Cards, and hreflang personalization signals (Appendix E).
- Evaluating Schema.org Audience and persona targeting declarations.

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
   - **JS-Rendering / SSR Parity (Appendix C)**: Multi-signal SPA detection: empty DOM containers (`#root`, `#app`, `#__next`), low text-to-markup ratios, client hydration JSON blobs (`__NEXT_DATA__`), and `<noscript>` JS warnings.
   - **Non-Text Media Traps**: Images lacking `alt`, canvas-rendered graphics, PDF-only documents.
   - **Canonical Tag Coverage**: Self-referential canonical tags to prevent duplicate indexing.

3. **Entity Corroboration & Disambiguation (Appendix D)**:
   - **Wikipedia/Wikidata Disambiguation**: Queries Wikipedia OpenSearch API using the TLD-extracted brand name to detect naming collisions with other notable entities.
   - **sameAs Knowledge Graph Links**: Inspects JSON-LD for authoritative `sameAs` links (Wikidata, Wikipedia, LinkedIn, Crunchbase).
   - **Temporal Freshness**: Copyright year staleness and HTTP `Last-Modified` header analysis.

4. **Personalization & Prior-Context Signals (Appendix E)**:
   - **OpenGraph & Twitter Cards Metadata**: Checks `og:title`, `og:description`, `og:image` completeness — used by AI assistants to personalize how the brand is presented.
   - **hreflang Locale Tags**: Checks for language/region alternate tags that help AI assistants serve geographically relevant content.
   - **Schema.org Audience Declarations**: Inspects structured data for `audience`, `targetAudience`, and `knowsAbout` declarations to enable AI persona matching.

5. **Proactive "Beyond-Problem" Opportunities**:
   - **Structured Claim Provenance**: Emits concrete recommendations and JSON-LD snippets for Schema.org `Claim` / `ClaimReview` to give AI search engines verified citation confidence.
   - **FAQPage Schema**: Emits structured Q&A snippets targeting conversational AI engines.
   - **Canonical `llms.txt`**: Emits ready-to-publish context window markdown manifests.

## Output
Emits a structured findings dictionary containing:
- Discovered off-site discoverability defects with quantified evidence.
- Entity disambiguation warnings with Wikipedia search results.
- Personalization and structured data signals.
- Prioritized, mechanism-sound technical fixes with concrete code/directive examples.
- Non-obvious proactive suggestions (Claim provenance, FAQPage schema, llms.txt).
