#!/usr/bin/env python3
"""
Entrypoint orchestrator — runs the discoverability and engagement sub-skills,
merges their output into a single unified audit report with an executive
summary, readiness score, and deduplicated findings.
"""

import sys, os, json, argparse, subprocess
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


class Orchestrator:
    """Runs child scripts, merges JSON reports, synthesises executive summary."""

    def __init__(self, url='', max_pages=15, timeout=6,
                 disc_pages=None, eng_pages=None,
                 dedup=True, verbose=True):
        self.raw_url = url
        self.max_pages = max_pages
        self.timeout = timeout
        self.disc_pages = disc_pages or max_pages
        self.eng_pages = eng_pages or min(10, max_pages)
        self.dedup = dedup
        self.verbose = verbose

        self.netloc = ''
        if url:
            p = urllib.parse.urlparse(url)
            if not p.scheme:
                url = 'https://' + url
                p = urllib.parse.urlparse(url)
            self.url = url
            self.netloc = p.netloc.lower()
        else:
            self.url = ''

        self._find_scripts()

    def _log(self, msg):
        if self.verbose:
            print(f'[orchestrator] {msg}', file=sys.stderr, flush=True)

    def _find_scripts(self):
        """Walk a few likely paths to locate the child analysers."""
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(here, '..', '..')),
            os.path.abspath(os.path.join(os.getcwd(), 'nexus-coders-brand-audit', 'skills')),
            os.path.abspath(os.path.join(os.getcwd(), 'skills')),
        ]

        self.crawler_path = None
        self.eng_path = None

        for d in candidates:
            # try both old and new skill directory names
            for sub in ('discoverability-audit', 'crawl-render-audit'):
                c = os.path.join(d, sub, 'scripts', 'crawler.py')
                if os.path.isfile(c) and not self.crawler_path:
                    self.crawler_path = c
            e = os.path.join(d, 'engagement-audit', 'scripts', 'engagement_analyzer.py')
            if os.path.isfile(e) and not self.eng_path:
                self.eng_path = e
            if self.crawler_path and self.eng_path:
                break

        # last resort: recursive search
        if not self.crawler_path or not self.eng_path:
            root = os.path.abspath(os.path.join(here, '..', '..', '..'))
            for dirpath, _, fnames in os.walk(root):
                if 'crawler.py' in fnames and not self.crawler_path:
                    self.crawler_path = os.path.join(dirpath, 'crawler.py')
                if 'engagement_analyzer.py' in fnames and not self.eng_path:
                    self.eng_path = os.path.join(dirpath, 'engagement_analyzer.py')

    # ── run a child script ─────────────────────────────────────────

    def _empty_report(self, label='', err_findings=None):
        """Skeleton report for when a sub-skill can't run."""
        r = {
            'site': self.netloc or 'unknown',
            'audited_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'summary': {'total_findings': 0, 'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
            'findings': [],
        }
        if err_findings:
            r['findings'] = err_findings
            r['summary']['total_findings'] = len(err_findings)
            r['summary']['critical'] = sum(1 for f in err_findings if f.get('severity') == 'critical')
        return r

    def _run_child(self, script, label, extra_args=None):
        if not script or not os.path.isfile(script):
            self._log(f'{label}: script not found at {script}, skipping')
            return self._empty_report(label)

        cmd = [sys.executable, script, self.url, '--timeout', str(self.timeout)]
        if extra_args:
            cmd.extend(extra_args)

        self._log(f'Running {label}: {" ".join(cmd)}')
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception as exc:
            self._log(f'{label} failed to launch: {exc}')
            return self._empty_report(label)

        stdout = proc.stdout.strip()
        if proc.returncode != 0 and not stdout:
            err = proc.stderr.strip() or f'exit code {proc.returncode}'
            self._log(f'{label} error: {err}')
            return self._empty_report(label, [{
                'id': 'F-ERR',
                'title': f'Sub-skill Failure ({label})',
                'severity': 'critical',
                'evidence': f'{os.path.basename(script)} failed: {err[:300]}',
                'suggested_action': {
                    'summary': 'Check network, domain, and Python deps.',
                    'priority': 'high',
                },
            }])

        # try to parse JSON, with a fallback to extract the first { ... }
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            start = stdout.find('{')
            end = stdout.rfind('}')
            if start != -1 and end > start:
                try:
                    return json.loads(stdout[start:end + 1])
                except json.JSONDecodeError:
                    pass
            self._log(f'{label}: could not parse JSON output')
            return self._empty_report(label, [{
                'id': 'F-ERR',
                'title': f'JSON Parse Error ({label})',
                'severity': 'critical',
                'evidence': f'Stdout from {os.path.basename(script)} was not valid JSON.',
                'suggested_action': {
                    'summary': 'Check analyser script stdout format.',
                    'priority': 'high',
                },
            }])

    # ── merge logic ────────────────────────────────────────────────

    def merge(self, reports: List[dict]) -> dict:
        site = self.netloc or 'unknown'
        for r in reports:
            if r.get('site') and r['site'] != 'unknown':
                site = r['site']
                break

        raw = []
        for r in reports:
            raw.extend(r.get('findings', []))

        # deduplicate by normalised title
        if self.dedup:
            seen = {}
            merged = []
            for f in raw:
                key = f.get('title', '').strip().lower()
                # collapse similar entity/sameAs findings
                if 'sameas' in key or 'knowledge graph' in key:
                    key = '_entity_sameas_'
                if 'email' in key and 'summary' in key:
                    key = '_email_summary_'

                if key in seen:
                    # merge evidence if it's different
                    existing = seen[key]
                    new_ev = f.get('evidence', '')
                    if new_ev and new_ev not in existing.get('evidence', ''):
                        existing['evidence'] += f' | Also: {new_ev}'
                else:
                    entry = dict(f)
                    seen[key] = entry
                    merged.append(entry)
            raw = merged

        # sort by severity, re-index
        sev_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        raw.sort(key=lambda x: sev_order.get(x.get('severity', 'medium'), 2))

        for i, f in enumerate(raw, 1):
            f['id'] = f'F-{i:03d}'

        # bulletproof summary: count from the actual findings list
        summary = {
            'total_findings': len(raw),
            'critical': sum(1 for f in raw if f.get('severity') == 'critical'),
            'high': sum(1 for f in raw if f.get('severity') == 'high'),
            'medium': sum(1 for f in raw if f.get('severity') == 'medium'),
            'low': sum(1 for f in raw if f.get('severity') == 'low'),
        }

        # executive summary & readiness score
        penalty = (summary['critical'] * 20 + summary['high'] * 10
                    + summary['medium'] * 5 + summary['low'] * 2)
        score = max(15, min(100, 100 - penalty))

        if score >= 90:
            grade = 'A (Excellent AI Readiness)'
        elif score >= 80:
            grade = 'B (Good — Minor Fixes Needed)'
        elif score >= 70:
            grade = 'C (Fair — Optimisation Required)'
        elif score >= 60:
            grade = 'D (At Risk of AI Invisibility)'
        else:
            grade = 'F (Critical Barriers Detected)'

        top_prios = []
        for f in raw[:3]:
            action = f.get('suggested_action', {}).get('summary', '')
            first_line = action.split('\n\n')[0].split('. ')[0].strip()
            top_prios.append(
                f"[{f.get('severity', 'high').upper()}] {f.get('title')}: {first_line}")

        def _health(subset):
            crit = sum(1 for x in subset if x.get('severity') == 'critical')
            high = sum(1 for x in subset if x.get('severity') == 'high')
            if crit:
                return {'score': 45, 'status': 'Critical Action Needed'}
            elif high:
                return {'score': 70, 'status': 'Needs Improvement'}
            elif len(subset) > 2:
                return {'score': 85, 'status': 'Good — Some Opportunities'}
            return {'score': 95, 'status': 'Optimal'}

        # bucket findings by domain — expanded keywords cover all possible titles
        disc_kw = ('crawler', 'schema', 'entity', 'skeleton', 'alt', 'sitemap',
                    'canonical', 'llms', 'opengraph', 'hreflang', 'claim', 'rendering',
                    'client-side', 'canvas', 'pdf', 'collision', 'knowledge',
                    'copyright', 'freshness', 'stale', 'json-ld', 'bot',
                    'robots', 'sameAs', 'faq')
        eng_kw = ('heading', 'h1', 'breadcrumb', 'scannability', 'call-to-action',
                   'cta', 'dead-end', 'viewport', 'layout shift', 'widget',
                   'headline', 'dense', 'prose', 'navigation', 'instant-value')
        email_kw = ('email', 'summarisation', 'summarization', 'above-the-fold',
                    'above-fold', 'preheader', 'inbox', 'digest')

        # site-unreachable findings degrade all categories
        unreachable_f = [f for f in raw if 'unreachable' in f['title'].lower()]

        disc_f = unreachable_f + [f for f in raw if any(k in f['title'].lower() for k in disc_kw)]
        eng_f = unreachable_f + [f for f in raw if any(k in f['title'].lower() for k in eng_kw)]
        email_f = unreachable_f + [f for f in raw if any(k in f['title'].lower() for k in email_kw)]

        exec_summary = {
            'overall_ai_readiness_score': score,
            'readiness_grade': grade,
            'top_priorities': top_prios,
            'category_scores': {
                'off_site_discoverability': _health(disc_f),
                'on_site_engagement': _health(eng_f),
                'email_ai_summary_readiness': _health(email_f),
            },
            'executive_brief': (
                f"Website '{site}' scored {score}/100 ({grade}). "
                f"Audited across off-site AI discoverability, on-site engagement, "
                f"and email summarisation readiness. Implementing the top "
                f"{min(3, len(raw))} prioritised action(s) will meaningfully "
                f"improve citation frequency and retention from AI assistants."
            ),
        }

        return {
            'site': site,
            'audited_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'summary': summary,
            'executive_summary': exec_summary,
            'recommendations_summary': top_prios,
            'findings': raw,
        }

    # ── end-to-end run ─────────────────────────────────────────────

    def run(self):
        self._log(f'Starting audit for {self.url}')
        reports = []

        if self.crawler_path:
            reports.append(self._run_child(
                self.crawler_path, 'discoverability-audit',
                ['--max-pages', str(self.disc_pages)]))

        if self.eng_path:
            reports.append(self._run_child(
                self.eng_path, 'engagement-audit',
                ['--max-pages', str(self.eng_pages)]))

        result = self.merge(reports)
        self._log(f'Done — {result["summary"]["total_findings"]} findings total.')
        return result


def main():
    ap = argparse.ArgumentParser(
        description='Audit orchestrator — single unified report')
    ap.add_argument('url', nargs='?', default='',
                    help='Target URL or domain')
    ap.add_argument('--max-pages', type=int, default=15)
    ap.add_argument('--disc-pages', type=int, default=None)
    ap.add_argument('--eng-pages', type=int, default=None)
    ap.add_argument('--timeout', type=int, default=6)
    ap.add_argument('--output', '-o', help='Write JSON report here')
    ap.add_argument('--from-files', nargs='+', metavar='JSON',
                    help='Merge existing reports instead of crawling')
    ap.add_argument('--no-dedup', action='store_true',
                    help='Skip cross-skill deduplication')
    ap.add_argument('--quiet', '-q', action='store_true')
    args = ap.parse_args()

    orch = Orchestrator(
        url=args.url,
        max_pages=args.max_pages,
        timeout=args.timeout,
        disc_pages=args.disc_pages,
        eng_pages=args.eng_pages,
        dedup=not args.no_dedup,
        verbose=not args.quiet,
    )

    if args.from_files:
        loaded = []
        for path in args.from_files:
            with open(path, 'r', encoding='utf-8') as fh:
                loaded.append(json.load(fh))
        report = orch.merge(loaded)
    else:
        if not args.url:
            ap.error('Provide a URL or use --from-files')
        report = orch.run()

    out = json.dumps(report, indent=2)
    if args.output:
        d = os.path.dirname(os.path.abspath(args.output))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(out)
        if not args.quiet:
            print(f'[orchestrator] Report saved to {args.output}', file=sys.stderr)
    else:
        print(out)


if __name__ == '__main__':
    main()
