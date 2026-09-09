# Nexus_adobe: Brand AI-Readiness & Engagement Audit Marketplace

This repository contains the official submission for the **Adobe University Hackathon 2026 (Round 3 — Build the Agent Skill Marketplace)** by **Nexus Coders**.

## Marketplace Location
The complete Agent Skill Marketplace package is located in:
👉 **[`nexus-coders-brand-audit/`](./nexus-coders-brand-audit/)**

## Quick Links
- **Marketplace Manifest**: [`nexus-coders-brand-audit/marketplace.json`](./nexus-coders-brand-audit/marketplace.json)
- **Marketplace Documentation**: [`nexus-coders-brand-audit/README.md`](./nexus-coders-brand-audit/README.md)
- **Entrypoint Skill**: [`nexus-coders-brand-audit/skills/audit-orchestrator/SKILL.md`](./nexus-coders-brand-audit/skills/audit-orchestrator/SKILL.md)
- **Discoverability Audit Skill**: [`nexus-coders-brand-audit/skills/discoverability-audit/SKILL.md`](./nexus-coders-brand-audit/skills/discoverability-audit/SKILL.md)
- **Pandas Crawler Script**: [`nexus-coders-brand-audit/skills/discoverability-audit/scripts/crawler.py`](./nexus-coders-brand-audit/skills/discoverability-audit/scripts/crawler.py)
- **Engagement Audit Skill**: [`nexus-coders-brand-audit/skills/engagement-audit/SKILL.md`](./nexus-coders-brand-audit/skills/engagement-audit/SKILL.md)
- **Engagement Analyzer Script**: [`nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py`](./nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py)
- **Engagement Retention Checklist**: [`nexus-coders-brand-audit/skills/engagement-audit/references/checklist.md`](./nexus-coders-brand-audit/skills/engagement-audit/references/checklist.md)

## Validation & Packaging
To validate all skills and generate the submission zip file (`nexus-coders-brand-audit.zip`), run:
```bash
./package_marketplace.sh
```

## Running an Audit
Both audit skills are self-contained CLIs that respect `robots.txt` and only make read-only GET requests:
```bash
python3 nexus-coders-brand-audit/skills/discoverability-audit/scripts/crawler.py https://example.com --max-pages 15 --output discoverability_report.json
python3 nexus-coders-brand-audit/skills/engagement-audit/scripts/engagement_analyzer.py https://example.com --max-pages 10 --output engagement_report.json
```
