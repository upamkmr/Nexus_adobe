#!/usr/bin/env python3
"""
merge_report.py — Deterministic merge/validation layer for the audit-orchestrator skill.

IMPORTANT — what this script does and does NOT do:

  Does:
    - Load raw findings from crawl-render-audit, engagement-audit, and (optionally)
      freshness-corroboration.
    - Normalize every finding into one common shape.
    - Cluster findings that are EXPLICITLY tagged `correlatable: true` and share a tag
      into a single root-cause finding (deterministic, tag-based — not semantic NLP).
    - Apply the severity-calibration guardrails from SKILL.md (e.g. a robots.txt
      restriction is not auto-"critical" just because it exists).
    - Assign final sequential IDs AFTER clustering/dedup so counts stay internally
      consistent.
    - Validate the final report against the required output schema.

  Does NOT do:
    - Deep semantic correlation across findings that aren't already tagged as
      correlatable by the child skills, or genuine root-cause reasoning that
      requires judgment beyond matching tags (e.g. deciding whether two
      superficially different findings are secretly the same underlying problem).
      That qualitative step is the orchestrator SKILL.md's job, performed by the
      calling agent BEFORE invoking this script (by pre-annotating/adjusting the
      raw finding tags or dropping duplicates) or AFTER (by editing the emitted
      draft prior to final delivery). This script only guarantees the mechanical
      parts of the merge are correct and reproducible.

Usage:
    python3 merge_report.py \
        --site example.com \
        --discoverability discoverability_raw.json \
        --engagement engagement_raw.json \
        [--corroboration corroboration_raw.json] \
        --output unified_audit_report.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone

VALID_SEVERITIES = ("critical", "high", "medium", "low")

# Severity-calibration guardrails (see SKILL.md Step: Severity calibration).
# A tag listed here is never auto-escalated to "critical" by this script alone;
# "critical" must be set explicitly by an upstream skill/agent with evidence of a
# site-wide blocking mechanism, not inferred here.
NEVER_AUTO_CRITICAL_TAGS = {"crawler_access", "llms_txt", "structured_data", "non_text_content",
                            "entity_corroboration", "freshness", "above_fold_clarity",
                            "navigation", "scannability", "cta_clarity", "mobile_layout"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path):
    if path is None:
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def normalize(raw_doc):
    """Return list of normalized finding dicts, or [] if the child skill failed/missing."""
    if raw_doc is None:
        return []
    return raw_doc.get("findings", [])


def clamp_severity(finding):
    sev = finding.get("severity_hint", "medium")
    if sev not in VALID_SEVERITIES:
        sev = "medium"
    if sev == "critical" and set(finding.get("tags", [])) & NEVER_AUTO_CRITICAL_TAGS:
        # Guardrail: downgrade unless a human/agent step already justified critical
        # explicitly via an "override_critical": true flag on the finding.
        if not finding.get("override_critical"):
            sev = "high"
    finding["severity_hint"] = sev
    return finding


def cluster_correlatable(findings):
    """Deterministically merge findings sharing a tag AND both marked correlatable=True.

    This is intentionally conservative: it only merges when child skills have
    already flagged overlap potential via the `correlatable` + `tags` fields,
    so the mechanism is auditable and reproducible rather than inferred.
    """
    correlatable = [f for f in findings if f.get("correlatable")]
    non_correlatable = [f for f in findings if not f.get("correlatable")]

    tag_groups = {}
    for f in correlatable:
        for tag in f.get("tags", []):
            tag_groups.setdefault(tag, []).append(f)

    merged = []
    already_merged_ids = set()
    for tag, group in tag_groups.items():
        # Only cluster if the group spans more than one source skill (true cross-skill
        # reinforcement) — same-skill findings sharing a tag are left as-is.
        sources = {f["source_skill"] for f in group}
        ids = tuple(sorted(f["raw_id"] for f in group))
        if len(sources) > 1 and ids not in already_merged_ids and len(group) > 1:
            already_merged_ids.add(ids)
            severities = [f["severity_hint"] for f in group]
            worst = min(severities, key=lambda s: VALID_SEVERITIES.index(s))
            evidence_lines = [f"[{f['source_skill']}] {f['evidence']}" for f in group]
            actions = [f["suggested_action"]["summary"] for f in group]
            merged.append({
                "title": f"Root cause: {tag.replace('_', ' ')} weaknesses reinforced across discoverability and engagement",
                "severity": worst,
                "evidence": " ".join(evidence_lines),
                "suggested_action": {
                    "summary": " / ".join(dict.fromkeys(actions)),  # de-dup while preserving order
                    "priority": worst if worst in ("critical", "high") else "medium",
                },
                "scope": "site" if any(f.get("scope") == "site" for f in group) else "sample",
                "_merged_from": [f["raw_id"] for f in group],
            })

    merged_raw_ids = {rid for group_ids in already_merged_ids for rid in group_ids}
    leftover = [f for f in correlatable if f["raw_id"] not in merged_raw_ids] + non_correlatable

    final = merged + [
        {
            "title": f["title"],
            "severity": f["severity_hint"],
            "evidence": f["evidence"],
            "suggested_action": f["suggested_action"],
            "scope": f.get("scope", "site"),
            "_merged_from": [f["raw_id"]],
        }
        for f in leftover
    ]
    return final


def assign_ids_and_summarize(site, findings):
    findings_sorted = sorted(findings, key=lambda f: VALID_SEVERITIES.index(f["severity"]))
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    out_findings = []
    for i, f in enumerate(findings_sorted, start=1):
        fid = f"F-{i:03d}"
        counts[f["severity"]] += 1
        out_findings.append({
            "id": fid,
            "title": f["title"],
            "severity": f["severity"],
            "scope": f.get("scope", "site"),
            "evidence": f["evidence"],
            "suggested_action": f["suggested_action"],
        })
    report = {
        "site": site,
        "audited_at": now_iso(),
        "summary": {
            "total_findings": len(out_findings),
            "critical": counts["critical"],
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
        },
        "findings": out_findings,
    }
    return report


def validate(report):
    errors = []
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    if summary.get("total_findings") != len(findings):
        errors.append("summary.total_findings does not match len(findings)")
    by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    ids = set()
    for f in findings:
        sev = f.get("severity")
        if sev not in VALID_SEVERITIES:
            errors.append(f"finding {f.get('id')} has invalid severity {sev!r}")
        else:
            by_sev[sev] += 1
        for field in ("id", "title", "severity", "evidence", "suggested_action"):
            if field not in f:
                errors.append(f"finding {f.get('id', '?')} missing required field {field!r}")
        if f.get("id") in ids:
            errors.append(f"duplicate finding id {f.get('id')}")
        ids.add(f.get("id"))
    for sev in VALID_SEVERITIES:
        if summary.get(sev) != by_sev[sev]:
            errors.append(f"summary.{sev} ({summary.get(sev)}) does not match actual count ({by_sev[sev]})")
    try:
        datetime.strptime(report.get("audited_at", ""), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        errors.append("audited_at is not valid ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Deterministic merge/validation for the unified audit report")
    parser.add_argument("--site", required=True)
    parser.add_argument("--discoverability", required=True)
    parser.add_argument("--engagement", required=True)
    parser.add_argument("--corroboration", default=None)
    parser.add_argument("--output", default="unified_audit_report.json")
    args = parser.parse_args()

    disc = load(args.discoverability)
    eng = load(args.engagement)
    corr = load(args.corroboration)

    warnings = []
    if disc is None:
        warnings.append("discoverability-audit output missing/unreadable — proceeding with partial coverage")
    if eng is None:
        warnings.append("engagement-audit output missing/unreadable — proceeding with partial coverage")

    all_findings = normalize(disc) + normalize(eng) + normalize(corr)
    all_findings = [clamp_severity(dict(f)) for f in all_findings]
    clustered = cluster_correlatable(all_findings)
    report = assign_ids_and_summarize(args.site, clustered)

    if warnings:
        report["_coverage_warnings"] = warnings

    errors = validate(report)
    if errors:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote unified report with {report['summary']['total_findings']} findings to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
