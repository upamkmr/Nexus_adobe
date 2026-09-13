# Multi-Skill Orchestration Protocol & Synthesis Architecture

This reference guide specifies the Inter-Process Communication (IPC), JSON schema validation, mathematical reconciliation, and synthesis algorithms implemented by the `audit-orchestrator` entrypoint skill.

---

## 1. Composition Architecture

The marketplace consists of exactly one entrypoint skill (`audit-orchestrator`) coordinating specialized sub-skills (`discoverability-audit` and `engagement-audit`) with clear separation of concerns:

```
[Agent / CLI Invocation]
        │
        ▼
skills/audit-orchestrator/scripts/orchestrator.py
        │
        ├── Subprocess execution (polite crawl, independent isolation)
        │     ├── skills/discoverability-audit/scripts/crawler.py
        │     └── skills/engagement-audit/scripts/engagement_analyzer.py
        │
        ├── Cross-Skill Deduplication & Sequential Normalization (F-001, F-002...)
        ├── Mathematical Count Reconciliation: total_findings == sum(severities) == len(findings)
        └── Executive Summary Synthesis (Readiness Score 0–100, Grade, Top Priorities)
        │
        ▼
[Single Unified Audit Report (JSON)]
```

---

## 2. Schema Floor Guarantee

Per the hackathon rubric (`ps_adobe.pdf`), the entrypoint report strictly satisfies the required JSON schema floor:
- Top-level properties:
  - `site` (string): The normalized hostname/domain audited.
  - `audited_at` (string, ISO 8601 UTC timestamp).
  - `summary` (object): Strict counts of `total_findings`, `critical`, `high`, `medium`, `low`.
  - `findings` (array of objects): Contiguous sequential array of findings.
- Finding properties:
  - `id` (string, e.g. `F-001`, `F-002`).
  - `title` (string).
  - `severity` (enum: `critical`, `high`, `medium`, `low`).
  - `evidence` (string, quantitative and mechanism-specific).
  - `suggested_action` (object with `summary` and `priority`).

### Executive Enhancement
To satisfy both non-expert business stakeholders and technical evaluators, the orchestrator includes an `executive_summary` object containing:
- `overall_ai_readiness_score`: 0–100 weighted index.
- `readiness_grade`: A (90–100), B (80–89), C (70–79), D (60–69), F (<60).
- `top_priorities`: Top 3 actionable, highest-impact items.
- `category_scores`: Granular health across Discoverability, Corroboration, Engagement, and Email/AI Summary.
- `executive_brief`: Plain-English narrative summary.

---

## 3. Mathematical Re-Summation Algorithm

To prevent count mismatch bugs:
```python
summary = {
    "total_findings": len(merged_findings),
    "critical": sum(1 for f in merged_findings if f.get("severity") == "critical"),
    "high": sum(1 for f in merged_findings if f.get("severity") == "high"),
    "medium": sum(1 for f in merged_findings if f.get("severity") == "medium"),
    "low": sum(1 for f in merged_findings if f.get("severity") == "low"),
}
assert summary["total_findings"] == (
    summary["critical"] + summary["high"] + summary["medium"] + summary["low"]
)
```
