#!/usr/bin/env python3
"""
Nexus Coders - Single Entrypoint Audit Orchestrator & Synthesizer
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Coordinates the multi-skill audit pipeline:
1. Executes discoverability-audit (crawler.py) for off-site AI discoverability, technical crawlability,
   Schema.org JSON-LD, entity disambiguation, knowledge-graph links, and Appendix E signals.
2. Executes engagement-audit (engagement_analyzer.py) for on-site visitor retention, orientation,
   UX friction, and Appendix F AI email-summary readiness.
3. Synthesizes cross-skill correlations, deduplicates overlapping signals, and mathematically sums summary counts.
4. Synthesizes an Executive Summary (readiness score 0–100, grade, category health, top 3 priorities).
5. Emits a Single Unified Audit Report strictly satisfying the required JSON schema floor.
"""

import sys
import os
import json
import argparse
import subprocess
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple


class AuditOrchestrator:
    """Orchestrates specialized sub-skills and synthesizes a single unified audit report."""

    def __init__(
        self,
        base_url: str = "",
        max_pages: int = 15,
        timeout: int = 6,
        disc_pages: Optional[int] = None,
        eng_pages: Optional[int] = None,
        deduplicate: bool = True,
        verbose: bool = True
    ):
        self.raw_url = base_url
        self.max_pages = max_pages
        self.timeout = timeout
        self.disc_pages = disc_pages if disc_pages is not None else max_pages
        self.eng_pages = eng_pages if eng_pages is not None else min(10, max_pages)
        self.deduplicate = deduplicate
        self.verbose = verbose

        self.netloc = ""
        if base_url:
            parsed = urllib.parse.urlparse(base_url)
            if not parsed.scheme:
                self.base_url = "https://" + base_url
                parsed = urllib.parse.urlparse(self.base_url)
            else:
                self.base_url = base_url
            self.netloc = parsed.netloc.lower()
        else:
            self.base_url = ""

        self._resolve_script_paths()

    def _log(self, message: str):
        if self.verbose:
            sys.stderr.write(f"[orchestrator] {message}\n")
            sys.stderr.flush()

    def _resolve_script_paths(self):
        """Locates the child scripts within the skills marketplace hierarchy."""
        current_script_dir = os.path.dirname(os.path.abspath(__file__))

        candidate_skills_dirs = [
            os.path.abspath(os.path.join(current_script_dir, "..", "..")),
            os.path.abspath(os.path.join(os.getcwd(), "nexus-coders-brand-audit", "skills")),
            os.path.abspath(os.path.join(os.getcwd(), "skills")),
        ]

        self.crawler_path = None
        self.engagement_path = None

        for s_dir in candidate_skills_dirs:
            c_candidate = os.path.join(s_dir, "discoverability-audit", "scripts", "crawler.py")
            if not os.path.isfile(c_candidate):
                c_candidate = os.path.join(s_dir, "crawl-render-audit", "scripts", "crawler.py")

            e_candidate = os.path.join(s_dir, "engagement-audit", "scripts", "engagement_analyzer.py")

            if os.path.isfile(c_candidate) and not self.crawler_path:
                self.crawler_path = c_candidate
            if os.path.isfile(e_candidate) and not self.engagement_path:
                self.engagement_path = e_candidate

            if self.crawler_path and self.engagement_path:
                break

        # Fallback recursive search if still not found
        if not self.crawler_path or not self.engagement_path:
            for root, _, files in os.walk(os.path.abspath(os.path.join(current_script_dir, "..", "..", ".."))):
                if "crawler.py" in files and not self.crawler_path:
                    self.crawler_path = os.path.join(root, "crawler.py")
                if "engagement_analyzer.py" in files and not self.engagement_path:
                    self.engagement_path = os.path.join(root, "engagement_analyzer.py")

    def _run_sub_script(self, script_path: str, label: str, extra_args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Runs a sub-skill analyzer script as a subprocess and parses its JSON output."""
        if not script_path or not os.path.isfile(script_path):
            self._log(f"Warning: Script for '{label}' not found at: {script_path}. Skipping gracefully.")
            return {
                "site": self.netloc or "unknown",
                "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": {"total_findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
                "findings": []
            }

        cmd = [sys.executable, script_path, self.base_url, "--timeout", str(self.timeout)]
        if extra_args:
            cmd.extend(extra_args)

        self._log(f"Executing {label}: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
        except Exception as exc:
            self._log(f"Failed to launch {label}: {exc}")
            return {
                "site": self.netloc or "unknown",
                "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": {"total_findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
                "findings": []
            }

        stdout = proc.stdout.strip()
        if proc.returncode != 0 and not stdout:
            err_msg = proc.stderr.strip() or f"Process exited with returncode {proc.returncode}"
            self._log(f"Error executing {label}: {err_msg}")
            return {
                "site": self.netloc or "unknown",
                "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": {"total_findings": 1, "critical": 1, "high": 0, "medium": 0, "low": 0},
                "findings": [{
                    "id": "F-ERR",
                    "title": f"Sub-skill Execution Failure ({label})",
                    "severity": "critical",
                    "evidence": f"Failed to execute {os.path.basename(script_path)}: {err_msg[:300]}",
                    "suggested_action": {
                        "summary": "Check network connectivity, domain availability, and Python dependencies.",
                        "priority": "high"
                    }
                }]
            }

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            start = stdout.find("{")
            end = stdout.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(stdout[start:end + 1])
                except json.JSONDecodeError:
                    pass

            self._log(f"Failed to parse JSON output from {label}. Stdout snippet: {stdout[:200]}")
            return {
                "site": self.netloc or "unknown",
                "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": {"total_findings": 1, "critical": 1, "high": 0, "medium": 0, "low": 0},
                "findings": [{
                    "id": "F-ERR",
                    "title": f"JSON Parse Error ({label})",
                    "severity": "critical",
                    "evidence": f"Output from {os.path.basename(script_path)} was not valid JSON.",
                    "suggested_action": {
                        "summary": "Verify analyzer script stdout format conforms strictly to JSON.",
                        "priority": "high"
                    }
                }]
            }

    def merge(self, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merges sub-skill reports into a Single Unified Audit Report.
        Mathematically sums summary counts and concatenates findings into one array.
        Eliminates duplicate collisions and synthesizes an executive summary.
        """
        site = self.netloc or "unknown"
        for r in reports:
            if r.get("site") and r.get("site") != "unknown":
                site = r.get("site")
                break

        raw_findings: List[Dict[str, Any]] = []
        for r in reports:
            raw_findings.extend(r.get("findings", []))

        # Deduplicate findings with matching titles or identical root causes
        if self.deduplicate:
            seen_titles: Dict[str, Dict[str, Any]] = {}
            merged_raw: List[Dict[str, Any]] = []
            for f in raw_findings:
                norm_title = f.get("title", "").strip().lower()
                if "sameas" in norm_title or "knowledge graph" in norm_title:
                    norm_title = "entity_ambiguity_sameas_key"
                if "email" in norm_title and "summary" in norm_title:
                    norm_title = "ai_email_summary_readiness_key"

                if norm_title in seen_titles:
                    existing = seen_titles[norm_title]
                    if f.get("evidence") and f.get("evidence") not in existing.get("evidence", ""):
                        existing["evidence"] = f"{existing.get('evidence', '')} | Additional corroboration: {f.get('evidence')}"
                else:
                    new_entry = dict(f)
                    seen_titles[norm_title] = new_entry
                    merged_raw.append(new_entry)
            raw_concatenated = merged_raw
        else:
            raw_concatenated = list(raw_findings)

        # Sort findings: critical first, then high, medium, low
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_findings = sorted(
            raw_concatenated,
            key=lambda item: severity_order.get(item.get("severity", "medium").lower(), 2)
        )

        # Re-index findings F-001, F-002, ... for clean contiguous IDs
        merged_findings = []
        for idx, finding in enumerate(sorted_findings, start=1):
            entry = dict(finding)
            entry["id"] = f"F-{idx:03d}"
            merged_findings.append(entry)

        # Bulletproof mathematical re-summation: summary.total_findings == sum(severities) == len(findings)
        summary = {
            "total_findings": len(merged_findings),
            "critical": sum(1 for f in merged_findings if f.get("severity") == "critical"),
            "high": sum(1 for f in merged_findings if f.get("severity") == "high"),
            "medium": sum(1 for f in merged_findings if f.get("severity") == "medium"),
            "low": sum(1 for f in merged_findings if f.get("severity") == "low"),
        }

        # Synthesize Executive Summary for non-expert business stakeholders and evaluators
        crit_count = summary["critical"]
        hi_count = summary["high"]
        med_count = summary["medium"]
        lo_count = summary["low"]

        penalty = (crit_count * 20) + (hi_count * 10) + (med_count * 5) + (lo_count * 2)
        readiness_score = max(15, min(100, 100 - penalty))

        if readiness_score >= 90:
            readiness_grade = "A (Optimal AI Readiness)"
        elif readiness_score >= 80:
            readiness_grade = "B (Good with Minor Fixes)"
        elif readiness_score >= 70:
            readiness_grade = "C (Fair - Optimization Required)"
        elif readiness_score >= 60:
            readiness_grade = "D (High Risk of AI Invisibility)"
        else:
            readiness_grade = "F (Critical AI Barriers Detected)"

        top_priorities = []
        for f in merged_findings[:3]:
            action_summary = f.get("suggested_action", {}).get("summary", "")
            first_sentence = action_summary.split("\n\n")[0].split(". ")[0].strip()
            top_priorities.append(f"[{f.get('severity', 'high').upper()}] {f.get('title')}: {first_sentence}")

        disc_findings = [f for f in merged_findings if any(k in f["title"].lower() for k in ["crawler", "schema", "entity", "skeleton", "alt", "sitemap", "canonical", "llms", "opengraph", "hreflang", "claim"])]
        eng_findings = [f for f in merged_findings if any(k in f["title"].lower() for k in ["heading", "h1", "breadcrumb", "scannability", "call-to-action", "cta", "dead-end", "viewport", "layout shift", "widget"])]
        email_findings = [f for f in merged_findings if any(k in f["title"].lower() for k in ["email", "summarization", "above-the-fold"])]

        def calc_health(f_list):
            crit = sum(1 for x in f_list if x.get("severity") == "critical")
            hi = sum(1 for x in f_list if x.get("severity") == "high")
            if crit > 0:
                return {"score": 45, "status": "Critical Action Needed"}
            elif hi > 0:
                return {"score": 70, "status": "Needs Improvement"}
            elif len(f_list) > 2:
                return {"score": 85, "status": "Good with Opportunities"}
            else:
                return {"score": 95, "status": "Optimal"}

        executive_summary = {
            "overall_ai_readiness_score": readiness_score,
            "readiness_grade": readiness_grade,
            "top_priorities": top_priorities,
            "category_scores": {
                "off_site_discoverability": calc_health(disc_findings),
                "on_site_engagement": calc_health(eng_findings),
                "email_ai_summary_readiness": calc_health(email_findings)
            },
            "executive_brief": (
                f"Website '{site}' scored {readiness_score}/100 ({readiness_grade}). "
                f"Audited across off-site AI discoverability, on-site engagement, and email summarization readiness. "
                f"Implementing the top {min(3, len(merged_findings))} prioritized action(s) will substantially enhance "
                f"citation frequency and retention from conversational AI assistants."
            )
        }

        unified_report = {
            "site": site,
            "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": summary,
            "executive_summary": executive_summary,
            "recommendations_summary": top_priorities,
            "findings": merged_findings
        }

        return unified_report

    def run(self) -> Dict[str, Any]:
        """Runs discoverability and engagement audits, merging into a unified report."""
        self._log(f"Starting end-to-end unified brand audit for: {self.base_url}")
        self._log(f"Discoverability path: {self.crawler_path}")
        self._log(f"Engagement path: {self.engagement_path}")

        reports = []

        # 1. Discoverability Audit (off-site AI readiness + entity corroboration + Appendix E)
        if self.crawler_path:
            disc_report = self._run_sub_script(
                self.crawler_path,
                "discoverability-audit",
                ["--max-pages", str(self.disc_pages)]
            )
            reports.append(disc_report)

        # 2. Engagement Audit (on-site retention + Appendix F email-digest readiness)
        if self.engagement_path:
            eng_report = self._run_sub_script(
                self.engagement_path,
                "engagement-audit",
                ["--max-pages", str(self.eng_pages)]
            )
            reports.append(eng_report)

        unified_report = self.merge(reports)
        self._log(f"Synthesized Single Unified Audit Report: {unified_report['summary']['total_findings']} total findings.")

        return unified_report


def main():
    parser = argparse.ArgumentParser(
        description="Nexus Coders Audit Orchestrator - Emits a Single Unified Audit Report"
    )
    parser.add_argument("url", nargs="?", default="", help="Target URL or domain to audit (e.g. https://example.com)")
    parser.add_argument("--max-pages", type=int, default=15, help="Max pages to crawl for discoverability (default: 15)")
    parser.add_argument("--disc-pages", type=int, default=None, help="Explicit max pages for discoverability audit")
    parser.add_argument("--eng-pages", type=int, default=None, help="Explicit max pages for engagement audit")
    parser.add_argument("--timeout", type=int, default=6, help="HTTP timeout in seconds (default: 6)")
    parser.add_argument("--output", "-o", help="Path to write the Single Unified Audit Report (JSON)")
    parser.add_argument("--from-files", nargs="+", metavar="REPORT_JSON", help="Directly merge pre-existing JSON report files")
    parser.add_argument("--no-dedup", action="store_true", help="Disable deduplication across sub-skill findings")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress logging to stderr")

    args = parser.parse_args()

    orchestrator = AuditOrchestrator(
        base_url=args.url,
        max_pages=args.max_pages,
        timeout=args.timeout,
        disc_pages=args.disc_pages,
        eng_pages=args.eng_pages,
        deduplicate=not args.no_dedup,
        verbose=not args.quiet
    )

    if args.from_files:
        loaded_reports = []
        for fpath in args.from_files:
            with open(fpath, "r", encoding="utf-8") as f:
                loaded_reports.append(json.load(f))
        report = orchestrator.merge(loaded_reports)
    else:
        if not args.url:
            parser.error("A target URL or domain is required unless --from-files is provided.")
        report = orchestrator.run()

    output_json = json.dumps(report, indent=2)
    if args.output:
        output_dir = os.path.dirname(os.path.abspath(args.output))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        if not args.quiet:
            sys.stderr.write(f"[orchestrator] Unified audit report successfully saved to {args.output}\n")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
