#!/usr/bin/env python3
"""
Nexus Coders - Single Entrypoint Audit Orchestrator & Synthesizer
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Coordinates the multi-skill audit pipeline:
1. Executes discoverability-audit (crawler.py) for off-site AI discoverability & crawler readiness.
2. Executes engagement-audit (engagement_analyzer.py) for on-site visitor retention & UX friction.
3. Captures their respective outputs and mathematically merges summary counts and concatenates findings.
4. Emits a Single Unified Audit Report strictly conforming to the Adobe Hackathon Round 3 JSON schema.
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
    """Orchestrates discoverability and engagement sub-skills and synthesizes a unified audit report."""

    def __init__(
        self,
        base_url: str = "",
        max_pages: int = 15,
        timeout: int = 6,
        disc_pages: Optional[int] = None,
        eng_pages: Optional[int] = None,
        deduplicate: bool = False,
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
        
        # Look for skills directory relative to this script:
        # Expected: <marketplace_root>/skills/audit-orchestrator/scripts/orchestrator.py
        candidate_skills_dirs = [
            os.path.abspath(os.path.join(current_script_dir, "..", "..")),
            os.path.abspath(os.path.join(os.getcwd(), "nexus-coders-brand-audit", "skills")),
            os.path.abspath(os.path.join(os.getcwd(), "skills")),
        ]

        self.crawler_path = None
        self.engagement_path = None

        for s_dir in candidate_skills_dirs:
            c_candidate = os.path.join(s_dir, "discoverability-audit", "scripts", "crawler.py")
            e_candidate = os.path.join(s_dir, "engagement-audit", "scripts", "engagement_analyzer.py")
            if os.path.isfile(c_candidate) and os.path.isfile(e_candidate):
                self.crawler_path = c_candidate
                self.engagement_path = e_candidate
                break

        if not self.crawler_path or not self.engagement_path:
            # Fallback search
            for root, _, files in os.walk(os.path.abspath(os.path.join(current_script_dir, "..", "..", ".."))):
                if "crawler.py" in files and not self.crawler_path:
                    self.crawler_path = os.path.join(root, "crawler.py")
                if "engagement_analyzer.py" in files and not self.engagement_path:
                    self.engagement_path = os.path.join(root, "engagement_analyzer.py")

    def _run_sub_script(self, script_path: str, label: str, pages: int) -> Dict[str, Any]:
        """Runs a sub-skill analyzer script as a subprocess and parses its JSON output."""
        if not script_path or not os.path.isfile(script_path):
            raise FileNotFoundError(f"Sub-skill script for '{label}' not found at: {script_path}")

        cmd = [
            sys.executable,
            script_path,
            self.base_url,
            "--max-pages", str(pages),
            "--timeout", str(self.timeout)
        ]

        self._log(f"Executing {label}: {' '.join(cmd)}")
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )

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

        # Parse JSON from stdout (handles any surrounding logs)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            # Locate first '{' and last '}'
            start = stdout.find("{")
            end = stdout.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(stdout[start:end + 1])
                except json.JSONDecodeError as ex:
                    pass

            self._log(f"Failed to parse JSON output from {label}. Stdout: {stdout[:200]}")
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

    def merge(self, disc_report: Dict[str, Any], eng_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merges discoverability and engagement reports into a Single Unified Audit Report.
        Mathematically sums summary counts from both sub-skills and concatenates findings into one array.
        """
        site = disc_report.get("site") or eng_report.get("site") or self.netloc or "unknown"
        disc_summary = disc_report.get("summary", {})
        eng_summary = eng_report.get("summary", {})

        disc_findings = disc_report.get("findings", [])
        eng_findings = eng_report.get("findings", [])

        if self.deduplicate:
            # Optional deduplication if requested: merge identical titles
            seen_titles = {}
            merged_raw = []
            for f in (disc_findings + eng_findings):
                norm_title = f.get("title", "").strip().lower()
                if norm_title in seen_titles:
                    existing = seen_titles[norm_title]
                    # Append additional evidence
                    if f.get("evidence") and f.get("evidence") not in existing.get("evidence", ""):
                        existing["evidence"] = f"{existing.get('evidence', '')} | Additional context: {f.get('evidence')}"
                else:
                    new_entry = dict(f)
                    seen_titles[norm_title] = new_entry
                    merged_raw.append(new_entry)
            
            # Re-index
            merged_findings = []
            for idx, finding in enumerate(merged_raw, start=1):
                entry = dict(finding)
                entry["id"] = f"F-{idx:03d}"
                merged_findings.append(entry)

            # Re-calculate counts
            summary = {
                "total_findings": len(merged_findings),
                "critical": sum(1 for f in merged_findings if f.get("severity") == "critical"),
                "high": sum(1 for f in merged_findings if f.get("severity") == "high"),
                "medium": sum(1 for f in merged_findings if f.get("severity") == "medium"),
                "low": sum(1 for f in merged_findings if f.get("severity") == "low"),
            }
        else:
            # Standard specification behavior:
            # 1. Mathematically sum total_findings, critical, high, medium, and low counts
            summary = {
                "total_findings": int(disc_summary.get("total_findings", 0)) + int(eng_summary.get("total_findings", 0)),
                "critical": int(disc_summary.get("critical", 0)) + int(eng_summary.get("critical", 0)),
                "high": int(disc_summary.get("high", 0)) + int(eng_summary.get("high", 0)),
                "medium": int(disc_summary.get("medium", 0)) + int(eng_summary.get("medium", 0)),
                "low": int(disc_summary.get("low", 0)) + int(eng_summary.get("low", 0)),
            }

            # 2. Concatenate both findings lists into one array
            raw_concatenated = list(disc_findings) + list(eng_findings)

            # 3. Sequentially re-index findings F-001, F-002, ... for clean contiguous IDs
            merged_findings = []
            for idx, finding in enumerate(raw_concatenated, start=1):
                entry = dict(finding)
                entry["id"] = f"F-{idx:03d}"
                merged_findings.append(entry)

            # Verification check: verify mathematical consistency
            computed_total = len(merged_findings)
            if summary["total_findings"] != computed_total:
                self._log(f"Warning: Reconciling count delta ({summary['total_findings']} vs {computed_total})")
                summary["total_findings"] = computed_total

        unified_report = {
            "site": site,
            "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": summary,
            "findings": merged_findings
        }

        return unified_report

    def run(self) -> Dict[str, Any]:
        """Runs discoverability and engagement audits, captures outputs, and merges into unified report."""
        self._log(f"Starting end-to-end unified brand audit for: {self.base_url}")
        self._log(f"Crawler path: {self.crawler_path}")
        self._log(f"Engagement path: {self.engagement_path}")

        disc_report = self._run_sub_script(self.crawler_path, "discoverability-audit", self.disc_pages)
        eng_report = self._run_sub_script(self.engagement_path, "engagement-audit", self.eng_pages)

        self._log(f"Captured {len(disc_report.get('findings', []))} discoverability findings and {len(eng_report.get('findings', []))} engagement findings.")
        unified_report = self.merge(disc_report, eng_report)
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
    parser.add_argument("--save-raw-dir", help="Optional directory to save raw intermediate JSON reports")
    parser.add_argument("--from-files", nargs=2, metavar=("DISC_JSON", "ENG_JSON"), help="Directly merge two pre-existing JSON report files")
    parser.add_argument("--deduplicate", action="store_true", help="Deduplicate findings with matching titles across sub-skills")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress logging to stderr")

    args = parser.parse_args()

    orchestrator = AuditOrchestrator(
        base_url=args.url,
        max_pages=args.max_pages,
        timeout=args.timeout,
        disc_pages=args.disc_pages,
        eng_pages=args.eng_pages,
        deduplicate=args.deduplicate,
        verbose=not args.quiet
    )

    if args.from_files:
        disc_file, eng_file = args.from_files
        with open(disc_file, "r", encoding="utf-8") as f:
            disc_report = json.load(f)
        with open(eng_file, "r", encoding="utf-8") as f:
            eng_report = json.load(f)
        report = orchestrator.merge(disc_report, eng_report)
    else:
        if not args.url:
            parser.error("A target URL or domain is required unless --from-files is provided.")
        report = orchestrator.run()

    if args.save_raw_dir and hasattr(orchestrator, "_last_disc_report"):
        os.makedirs(args.save_raw_dir, exist_ok=True)
        # If needed in future extensions

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
