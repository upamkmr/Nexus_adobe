---
name: freshness-corroboration
description: Dedicated skill for spot-checking load-bearing brand facts against independent web sources, identifying brand-name entity ambiguity (naming collisions with other organizations), and assessing content freshness signals. Use when diagnosing why AI assistants confuse or uncorroborate brand identity.
license: Apache-2.0
allowed-tools: Bash, WebSearch
---

# Freshness & Corroboration Audit

The `freshness-corroboration` skill investigates whether a brand's claims are corroborated across independent web sources, whether another organization shares the brand name (entity ambiguity), and whether temporal freshness signals indicate content abandonment.

## When to use
Activate this skill when:
- Diagnosing why an AI assistant misattributes facts, confuses one brand with another, or treats self-reported facts with low confidence.
- Verifying whether external knowledge bases (Wikidata, Wikipedia, LinkedIn) corroborate the organization's existence and credentials.
- Checking for stale copyright dates and HTTP headers that penalize search freshness heuristics.

## Inputs
- **`url`** (string, required): The target brand URL or domain (e.g., `https://example.com` or `adobe.com`).
- **`timeout`** (integer, optional): HTTP timeout in seconds (default: 6).

## Guardrails
The bundled script performs strictly read-only public API queries (Wikipedia OpenSearch) and HTTP GET requests. No credentials or mutating operations are performed.

## Procedure

1. **Deterministic Corroboration & Freshness Analysis**:
   Run the bundled Python script [corroboration_checker.py](./scripts/corroboration_checker.py):
   ```bash
   python3 skills/freshness-corroboration/scripts/corroboration_checker.py <target-url> --output ./corroboration_findings.json
   ```

2. **Cross-Web Entity Disambiguation**:
   - The script queries Wikipedia / Wikidata APIs to detect if the brand keyword collides with other notable entities (e.g., companies, cities, concepts sharing the same name).
   - Confirms presence of Schema.org `sameAs` links pointing to authoritative knowledge graphs (Wikidata, Wikipedia, LinkedIn, Crunchbase).

3. **Temporal Freshness Evaluation**:
   - Inspects homepage copyright declarations and HTTP `Last-Modified` headers to detect outdated information.

4. **Agent WebSearch Spot-Checking (Optional Multi-Agent Mode)**:
   For environments with live web search capabilities, consult [references/corroboration-guide.md](./references/corroboration-guide.md) to spot-check up to 3 load-bearing claims (e.g. founding year, customer count, certifications) against independent third-party sources.

## Output
Emits a structured findings dictionary containing:
- Discovered entity collisions and naming ambiguity risks.
- Missing authoritative knowledge graph links.
- Outdated temporal signals with specific remediation steps.
