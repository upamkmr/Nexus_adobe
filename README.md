# Nexus_adobe: Brand AI-Readiness & Engagement Audit Marketplace

This repository contains the official submission for the **Adobe University Hackathon 2026 (Round 3 — Build the Agent Skill Marketplace)** by **Nexus Coders**.

## Marketplace Location
The complete Agent Skill Marketplace package is located in:
👉 **[`nexus-coders-brand-audit/`](./nexus-coders-brand-audit/)**

## Quick Links
- **Marketplace Manifest**: [`nexus-coders-brand-audit/marketplace.json`](./nexus-coders-brand-audit/marketplace.json)
- **Marketplace Documentation**: [`nexus-coders-brand-audit/README.md`](./nexus-coders-brand-audit/README.md)
- **Dependencies**: [`nexus-coders-brand-audit/requirements.txt`](./nexus-coders-brand-audit/requirements.txt)
- **License**: [`nexus-coders-brand-audit/LICENSE`](./nexus-coders-brand-audit/LICENSE)
- **Entrypoint Skill**: [`nexus-coders-brand-audit/skills/audit-orchestrator/SKILL.md`](./nexus-coders-brand-audit/skills/audit-orchestrator/SKILL.md)
  - **Orchestrator Engine**: [`nexus-coders-brand-audit/skills/audit-orchestrator/scripts/orchestrator.py`](./nexus-coders-brand-audit/skills/audit-orchestrator/scripts/orchestrator.py)
- **Off-Site Discoverability Skill**: [`nexus-coders-brand-audit/skills/crawl-render-audit/SKILL.md`](./nexus-coders-brand-audit/skills/crawl-render-audit/SKILL.md)
  - **Crawler Script**: [`nexus-coders-brand-audit/skills/crawl-render-audit/scripts/crawler.py`](./nexus-coders-brand-audit/skills/crawl-render-audit/scripts/crawler.py)
- **Entity Corroboration & Freshness Skill**: [`nexus-coders-brand-audit/skills/freshness-corroboration/SKILL.md`](./nexus-coders-brand-audit/skills/freshness-corroboration/SKILL.md)
  - **Corroboration Checker**: [`nexus-coders-brand-audit/skills/freshness-corroboration/scripts/corroboration_checker.py`](./nexus-coders-brand-audit/skills/freshness-corroboration/scripts/corroboration_checker.py)
  - **Corroboration Guide**: [`nexus-coders-brand-audit/skills/freshness-corroboration/references/corroboration-guide.md`](./nexus-coders-brand-audit/skills/freshness-corroboration/references/corroboration-guide.md)
- **On-Site Retention Skill**: [`nexus-coders-brand-audit/skills/engagement-audit/SKILL.md`](./nexus-coders-brand-audit/skills/engagement-audit/SKILL.md)
  - **Engagement Analyzer**: [`nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py`](./nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py)
  - **Retention Checklist**: [`nexus-coders-brand-audit/skills/engagement-audit/references/checklist.md`](./nexus-coders-brand-audit/skills/engagement-audit/references/checklist.md)

## Validation & Packaging
To validate all skills and generate the submission zip file (`nexus-coders-brand-audit.zip`), run:
```bash
./package_marketplace.sh
```

## Running an Audit
### Single Entrypoint Unified Audit (Recommended)
Run the master orchestrator to execute the full multi-skill audit and emit the Single Unified Audit Report:
```bash
python3 nexus-coders-brand-audit/skills/audit-orchestrator/scripts/orchestrator.py https://example.com --max-pages 15 --output unified_audit_report.json
```

### Standalone Sub-Skill CLIs
All sub-skills are self-contained CLIs that respect `robots.txt` and perform read-only GET requests:
```bash
# Off-Site AI Discoverability
python3 nexus-coders-brand-audit/skills/crawl-render-audit/scripts/crawler.py https://example.com --max-pages 15 --output discoverability_report.json

# Freshness & Knowledge Graph Corroboration
python3 nexus-coders-brand-audit/skills/freshness-corroboration/scripts/corroboration_checker.py https://example.com --output corroboration_report.json

# On-Site Visitor Retention
python3 nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py https://example.com --max-pages 10 --output engagement_report.json
```
