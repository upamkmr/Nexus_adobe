# Nexus_adobe: Brand AI-Readiness & Engagement Audit Marketplace

This repository contains the official submission for the **Adobe University Hackathon 2026 (Round 3 — Build the Agent Skill Marketplace)** by **Nexus Coders**.

## Marketplace Location
The complete Agent Skill Marketplace package is located in:
👉 **[`nexus-coders-brand-audit/`](./nexus-coders-brand-audit/)**

## Quick Links
- **Marketplace Manifest**: [`marketplace.json`](./nexus-coders-brand-audit/marketplace.json) (3 skills, 1 entrypoint)
- **Marketplace Documentation**: [`README.md`](./nexus-coders-brand-audit/README.md)
- **Dependencies**: [`requirements.txt`](./nexus-coders-brand-audit/requirements.txt)
- **Entrypoint Skill**: [`audit-orchestrator/SKILL.md`](./nexus-coders-brand-audit/skills/audit-orchestrator/SKILL.md)
  - **Orchestrator Engine**: [`orchestrator.py`](./nexus-coders-brand-audit/skills/audit-orchestrator/scripts/orchestrator.py)
- **Off-Site Discoverability + Entity Corroboration Skill**: [`discoverability-audit/SKILL.md`](./nexus-coders-brand-audit/skills/discoverability-audit/SKILL.md)
  - **Crawler Script**: [`crawler.py`](./nexus-coders-brand-audit/skills/discoverability-audit/scripts/crawler.py)
  - **Corroboration Guide**: [`corroboration-guide.md`](./nexus-coders-brand-audit/skills/discoverability-audit/references/corroboration-guide.md)
- **On-Site Retention + AI-Summary Readiness Skill**: [`engagement-audit/SKILL.md`](./nexus-coders-brand-audit/skills/engagement-audit/SKILL.md)
  - **Engagement Analyzer**: [`engagement_analyzer.py`](./nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py)
  - **Retention Checklist (7 dimensions + Appendix E/F)**: [`checklist.md`](./nexus-coders-brand-audit/skills/engagement-audit/references/checklist.md)

## Validation & Packaging
```bash
./package_marketplace.sh
```

## Running an Audit
### Single Entrypoint (Recommended)
```bash
python3 nexus-coders-brand-audit/skills/audit-orchestrator/scripts/orchestrator.py https://example.com --max-pages 15 --output unified_audit_report.json
```

### Standalone Sub-Skill CLIs
```bash
# Off-Site AI Discoverability + Entity Corroboration
python3 nexus-coders-brand-audit/skills/discoverability-audit/scripts/crawler.py https://example.com --max-pages 15 --output discoverability_report.json

# On-Site Visitor Retention + AI-Summary Readiness
python3 nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py https://example.com --max-pages 10 --output engagement_report.json
```
