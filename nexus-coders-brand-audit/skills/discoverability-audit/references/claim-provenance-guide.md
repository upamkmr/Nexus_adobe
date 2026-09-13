# Structured Claim Provenance & Citation Markup Guide

This reference guide establishes non-obvious, proactive implementation standards for encoding structured claim provenance and citation metadata into websites to maximize citation frequency and confidence in AI search engines (covering Round 2 Appendix B, D, and E).

---

## 1. The AI Citation Confidence Problem

When conversational search engines (Perplexity, SearchGPT, Google AI Overviews, Claude) answer user queries, they evaluate candidate source pages using **factual verifiability and citation confidence**:

- **Hallucination Aversion**: LLMs are heavily penalized during RLHF/DPO training for generating unsubstantiated claims.
- **Source Selection Heuristic**: Pages that state verifiable claims backed by structured provenance (dates, authors, primary sources, quantitative units) are preferentially selected as citations over generic prose.
- **The Fragile Claim Trap (Appendix D)**: "A claim that lives in only one spot is fragile; a claim repeated consistently across lots of unrelated sources is far more likely to be believed and repeated back."

---

## 2. Schema.org Claim & ClaimReview Implementation

When publishing benchmarks, quantitative metrics, or industry comparison statements, mark them explicitly with Schema.org:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Cloud Platform Benchmarks 2026",
  "mainEntity": {
    "@type": "Claim",
    "claimInterpreter": {
      "@type": "Organization",
      "name": "Independent Cloud Testing Lab",
      "url": "https://independent-lab.org"
    },
    "text": "Nexus Database processes 1.2M transactions/sec at 2.4ms p99 latency.",
    "appearance": {
      "@type": "CreativeWork",
      "headline": "Nexus Database Performance Benchmark",
      "datePublished": "2026-03-01",
      "citation": [
        "https://arxiv.org/abs/2601.12345",
        "https://github.com/example/benchmark-repro"
      ]
    }
  }
}
</script>
```

---

## 3. Schema.org Audience & Personalization Targeting (Appendix E)

To help AI assistants match the brand to user personas and personalized conversational contexts:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Nexus Enterprise Suite",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Linux, macOS, Windows",
  "audience": {
    "@type": "BusinessAudience",
    "audienceType": "Enterprise Engineering Teams",
    "numberOfEmployees": {
      "@type": "QuantitativeValue",
      "minValue": 250
    }
  },
  "knowsAbout": [
    "Distributed Consensus",
    "Cloud Native Infrastructure",
    "High-Throughput Stream Processing"
  ]
}
</script>
```

---

## 4. Canonical `llms.txt` Context Manifest Standard

The `llms.txt` standard (https://llmstxt.org/) provides a clean markdown document hosted at `/llms.txt` and `/.well-known/llms.txt` specifically formatted for LLM context windows:

```markdown
# Nexus Brand Context Manifest
> Nexus is a high-throughput, distributed real-time data streaming platform.

## Core Offerings
- [Nexus Stream](https://example.com/stream): Real-time event broker with sub-millisecond latency.
- [Nexus Cloud](https://example.com/cloud): Fully-managed serverless streaming infrastructure.

## Documentation & APIs
- [Quickstart Guide](https://example.com/docs/quickstart.md): 5-minute setup guide.
- [API Reference](https://example.com/docs/api.md): REST and gRPC endpoints.

## Entity Disambiguation
- Official Wikidata Entity: https://www.wikidata.org/wiki/Q12345678
- Official Crunchbase: https://www.crunchbase.com/organization/nexus-tech
```
