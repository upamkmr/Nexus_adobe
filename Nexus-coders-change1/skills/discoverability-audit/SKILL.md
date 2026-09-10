---
name: discoverability-audit
description: Dedicated skill for auditing a website's off-site AI readiness and machine discoverability. Evaluates robots.txt AI bot directives, llms.txt support, Schema.org JSON-LD structured data, JS-rendering hydration gaps, facts locked in non-text media (images/canvas/PDF), freshness, and cross-web entity corroboration (including a live spot-check for contradicted or mistaken-identity claims). Use when diagnosing why a brand is missing, ignored, or hallucinated by AI assistants (ChatGPT, Claude, Perplexity, Gemini).
license: Apache-2.0
allowed-tools: Bash, WebSearch
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

## Guardrails
The bundled crawler is strictly read-only (GET only), parses the site's own `robots.txt` with the standard library `RobotFileParser`, and **never fetches a path disallowed for its User-Agent or `*`** — separate from the informational check of whether AI bots (`GPTBot`, `ClaudeBot`, etc.) are blocked, which is a *finding about the site*, not a rule for the crawler's own traffic. It also applies a polite crawl delay (honoring `Crawl-delay` when declared) between requests.

The AI-bot-blocked finding is also computed via `RobotFileParser.can_fetch()` (against
the homepage and every sampled page) rather than a hand-rolled robots.txt line scanner —
this avoids mis-scoping `Disallow`/`Allow` rules across unrelated user-agent groups, and
catches partial/path-level blocks (e.g. `Disallow: /blog/` for `GPTBot`), not just a
full-site `Disallow: /`. Full and partial blocks are reported as separate findings
(`critical` and `high` respectively) since a partial block on high-value content is a
real but different problem from being blocked entirely.

**The live web-search half of entity corroboration is not run by `crawler.py`.** It's a
separate agent-performed step — see `references/corroboration-guide.md` — because it
needs a `WebSearch` tool call the sandboxed script can't make. Its findings only reach the
final report if written to JSON and passed to the orchestrator via `--corroboration-file`;
running `crawler.py` alone only produces the static `sameAs` proxy finding.

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
   - **Non-Text Media Locks**: Identify images, diagrams, or badges lacking descriptive `alt` tags, plus pages that render key content inside `<canvas>` or point to a PDF as the primary content with little surrounding page text.
   - **Entity Corroboration & Disambiguation**: Verify `sameAs` links to authoritative external entity graphs (Wikidata, Crunchbase, LinkedIn) to eliminate brand mistaken identity.
   - **Content Freshness**: Inspect HTTP `Last-Modified` headers, `dateModified` metadata, and footer copyright dates.

3. **Validate Empirical Findings**:
   Review the generated `discoverability_findings.json` to ensure:
   - Each finding contains concrete numerical evidence (e.g., `X/Y pages`, `Z% coverage`).
   - Every issue assigns an accurate severity (`critical`, `high`, `medium`, or `low`).
   - Suggested actions specify mechanism-sound remedies (e.g. specific Schema.org types, SSR pre-rendering configs) rather than generic advice.

4. **Cross-Web Corroboration Spot-Check (requires a web search tool)**:
   `crawler.py` only sees the target site itself, so its `sameAs`-presence check is a
   proxy for corroboration, not a verification of it. Follow the deterministic
   procedure in [references/corroboration-guide.md](./references/corroboration-guide.md)
   to spot-check up to 3 load-bearing factual claims against independent sources via
   web search, and append any `contradicted` (mistaken-identity risk, `high` severity)
   or `uncorroborated` (`low` severity) results to the findings list using the same
   `F-0xx` schema. Skip this step gracefully (note it as not performed) if no web
   search tool is available in the current environment — it is additive evidence, not
   a blocker for emitting the rest of the report.

## Output
Emits a structured findings dictionary containing:
- Discovered off-site discoverability defects with quantified evidence.
- Prioritized, mechanism-sound technical fixes.
- Proactive suggestions that strengthen AI discoverability beyond baseline defects.
