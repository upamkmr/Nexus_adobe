#!/usr/bin/env python3
"""
On-site engagement & retention analyser.

Crawls a target site (read-only, respects robots.txt) and measures eight
dimensions of visitor retention — from H1 clarity to email-digest readiness.
Designed for visitors arriving via AI-assistant citations (ChatGPT, Claude,
Perplexity) who land on deep pages with specific intent and short patience.

Outputs JSON matching the hackathon schema floor.
"""

import sys, os, re, json, time, argparse
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set

import requests
from bs4 import BeautifulSoup
import pandas as pd

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = (
    'NexusCodersAuditBot/2.0 '
    '(+https://github.com/upamkmr/Nexus_adobe; read-only brand audit)'
)

# headlines that sound impressive but say nothing concrete
VAGUE_H1_RX = [
    r'^welcome\b', r'^home\b', r'^empower(?:ing)?\b',
    r'^transform(?:ing)?\b', r'^the future of\b',
    r'^innovat(?:e|ion)\b', r'^unleash\b',
    r'^next-?gen(?:eration)?\b', r'^re-?defin(?:e|ing)\b',
    r'^build better\b', r'^hello\b',
]

VAGUE_CTA_WORDS = frozenset([
    'click here', 'learn more', 'more', 'read more', 'see more',
    'explore', 'continue', 'go', 'submit', 'get started',
    'view more', 'discover',
])

# opening-text patterns that signal filler — the kind AI inbox summarisers
# will happily quote instead of the actual announcement
BOILERPLATE_RX = [
    r'view\s+in\s+browser',
    r'having\s+trouble\s+viewing',
    r'click\s+here\s+to\s+unsubscribe',
    r'forward\s+to\s+a\s+friend',
    r'skip\s+to\s+(?:main\s+)?content',
    r'cookie\s+preferences',
    r'privacy\s+policy\s+\|\s+terms',
]

LONG_PARA_THRESHOLD = 450  # chars; anything longer is a "wall of text"


def _norm(url):
    p = urllib.parse.urlparse(url)
    if not p.scheme:
        url = 'https://' + url
    return url


class EngagementAnalyzer:
    """Polite read-only crawler that scores pages on retention dimensions."""

    def __init__(self, base_url, max_pages=10, timeout=6, delay=0.4):
        self.base_url = _norm(base_url)
        parsed = urllib.parse.urlparse(self.base_url)
        self.base_url = f'{parsed.scheme}://{parsed.netloc}'
        self.netloc = parsed.netloc.lower()
        self.max_pages = max(1, min(max_pages, 30))
        self.timeout = timeout
        self.delay = delay

        self.sess = requests.Session()
        self.sess.headers.update({
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        self.visited: Set[str] = set()
        self.records: List[Dict[str, Any]] = []
        self._rp: Optional[urllib.robotparser.RobotFileParser] = None
        self._cd: Optional[float] = None  # crawl-delay from robots.txt

    # ── robots compliance ──────────────────────────────────────────

    def _setup_robots(self):
        rurl = self.base_url + '/robots.txt'
        try:
            r = self.sess.get(rurl, timeout=self.timeout, verify=False)
            if r.status_code == 200 and r.text:
                self._rp = urllib.robotparser.RobotFileParser()
                self._rp.set_url(rurl)
                self._rp.parse(r.text.splitlines())
                cd = self._rp.crawl_delay(UA)
                if cd is not None:
                    self._cd = min(float(cd), 3.0)
        except Exception:
            pass

    def _ok(self, url):
        if self._rp is None:
            return True
        try:
            return self._rp.can_fetch(UA, url) and self._rp.can_fetch('*', url)
        except Exception:
            return True

    # ── BFS crawl ──────────────────────────────────────────────────

    def _crawl(self):
        q = [self.base_url]
        wait = self._cd or self.delay

        while q and len(self.visited) < self.max_pages:
            url = q.pop(0)
            if url in self.visited or not self._ok(url):
                continue
            self.visited.add(url)

            rec, links = self._inspect_page(url)
            if rec:
                self.records.append(rec)

            for lnk in links:
                if lnk not in self.visited and lnk not in q:
                    if len(q) + len(self.visited) < self.max_pages * 2:
                        q.append(lnk)
            time.sleep(wait)

    def _inspect_page(self, url):
        """Fetch a single page and measure all engagement dimensions."""
        try:
            r = self.sess.get(url, timeout=self.timeout,
                              verify=False, allow_redirects=True)
            if r.status_code != 200:
                return None, []
            if 'text/html' not in r.headers.get('content-type', '').lower():
                return None, []
        except Exception:
            return None, []

        soup = BeautifulSoup(r.text, 'html.parser')

        # gather internal links for the BFS queue
        new_links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].split('#')[0].strip()
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:')):
                continue
            full = urllib.parse.urljoin(url, href)
            pu = urllib.parse.urlparse(full)
            if pu.netloc.lower() == self.netloc:
                clean = f'{pu.scheme}://{pu.netloc}{pu.path}'
                if clean not in new_links:
                    new_links.append(clean)

        # ─── dimension 1: H1 value proposition ───
        h1s = soup.find_all('h1')
        h1_count = len(h1s)
        h1_txt = h1s[0].get_text(separator=' ', strip=True) if h1s else ''
        is_vague_h1 = False
        if h1_txt:
            for pat in VAGUE_H1_RX:
                if re.search(pat, h1_txt, re.I):
                    is_vague_h1 = True
                    break

        # ─── dimension 2: deep-link orientation ───
        path = urllib.parse.urlparse(url).path.strip('/')
        depth = len(path.split('/')) if path else 0
        is_deep = depth >= 2

        has_crumbs = bool(
            soup.find('nav', attrs={'aria-label': re.compile(r'breadcrumb', re.I)})
            or soup.find('ol', class_=re.compile(r'breadcrumb', re.I))
            or soup.find('ul', class_=re.compile(r'breadcrumb', re.I))
            or soup.find(attrs={'itemtype': re.compile(r'BreadcrumbList', re.I)})
        )
        has_nav = bool(
            soup.find('header')
            or soup.find('nav', attrs={'role': 'navigation'})
            or soup.find(class_=re.compile(r'navbar|header|nav-bar', re.I))
        )

        # ─── dimension 3: scannability ───
        h2c = len(soup.find_all('h2'))
        h3c = len(soup.find_all('h3'))
        paras = soup.find_all('p')
        long_blocks = sum(1 for p in paras
                          if len(p.get_text(strip=True)) > LONG_PARA_THRESHOLD)
        n_lists = len(soup.find_all(['ul', 'ol']))

        # ─── dimension 4: CTA clarity ───
        cta_els = (
            soup.find_all('a', class_=re.compile(r'btn|button|cta', re.I))
            + soup.find_all('button')
        )
        if not cta_els:
            cta_els = soup.find_all('a', attrs={'role': 'button'})
        n_ctas = len(cta_els)
        n_vague_ctas = 0
        for el in cta_els:
            txt = el.get_text(strip=True).lower()
            if txt in VAGUE_CTA_WORDS or (txt and len(txt) <= 4
                                           and txt not in {'buy', 'join', 'shop'}):
                n_vague_ctas += 1

        # ─── dimension 5: mobile viewport & layout ───
        has_viewport = bool(
            soup.find('meta', attrs={'name': re.compile(r'^viewport$', re.I)}))
        imgs = soup.find_all('img')
        n_imgs = len(imgs)
        imgs_no_dims = sum(1 for img in imgs
                           if not (img.get('width') and img.get('height')))

        # ─── dimension 6: AI email / inbox summary readiness (Appendix F) ───
        for junk in soup(['script', 'style', 'noscript', 'svg']):
            junk.extract()
        plain = soup.get_text(separator=' ', strip=True)
        txt_len = len(plain)

        # check if the opening chars are just "view in browser" type filler
        opener = plain[:250].strip().lower()
        has_boilerplate_opener = any(re.search(p, opener) for p in BOILERPLATE_RX)

        # look for an email preheader element
        has_preheader = bool(
            soup.find(class_=re.compile(r'preheader', re.I))
            or soup.find(id=re.compile(r'preheader', re.I))
            or soup.find('div', style=re.compile(
                r'display\s*:\s*none.*max-height\s*:\s*0', re.I))
        )

        total_heads = h1_count + h2c + h3c
        good_heading_structure = total_heads >= 2 and h2c >= 1

        # ─── dimension 7: above-fold content density (Appendix E) ───
        above_fold = plain[:500].strip()
        substantive_atf = (
            len(above_fold) > 100
            and bool(re.search(r'[a-zA-Z]{4,}\s+[a-zA-Z]{3,}\s+[a-zA-Z]{2,}',
                               above_fold))
        )

        # heuristic: is this page likely to get butchered by an AI inbox digest?
        email_risk = (
            (txt_len < 300 and n_imgs > 2)
            or (txt_len > 0 and n_imgs / max(txt_len / 200, 1) > 5)
            or (has_boilerplate_opener and txt_len < 800)
        )

        rec = {
            'url': url,
            'h1_count': h1_count,
            'h1_txt': h1_txt,
            'h1_len': len(h1_txt),
            'vague_h1': is_vague_h1,
            'is_deep': is_deep,
            'has_crumbs': has_crumbs,
            'has_nav': has_nav,
            'h2c': h2c, 'h3c': h3c,
            'long_blocks': long_blocks,
            'n_lists': n_lists,
            'n_ctas': n_ctas,
            'n_vague_ctas': n_vague_ctas,
            'has_viewport': has_viewport,
            'n_imgs': n_imgs,
            'imgs_no_dims': imgs_no_dims,
            'txt_len': txt_len,
            'boilerplate_opener': has_boilerplate_opener,
            'has_preheader': has_preheader,
            'good_headings': good_heading_structure,
            'substantive_atf': substantive_atf,
            'email_risk': email_risk,
        }
        return rec, new_links

    # ── build findings from aggregated metrics ─────────────────────

    def _build_findings(self):
        if not self.records:
            return {
                'site': self.netloc,
                'audited_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'summary': {'total_findings': 1, 'critical': 1,
                            'high': 0, 'medium': 0, 'low': 0},
                'findings': [{
                    'id': 'F-001',
                    'title': 'Site Unreachable for Engagement Audit',
                    'severity': 'critical',
                    'evidence': f'Could not fetch pages from {self.base_url}.',
                    'suggested_action': {
                        'summary': 'Verify server availability and network access.',
                        'priority': 'high',
                    },
                }],
            }

        df = pd.DataFrame(self.records)
        n = len(df)
        findings = []
        ix = [1]

        def add(title, sev, evidence, fix, prio=None):
            findings.append({
                'id': f'F-{ix[0]:03d}',
                'title': title,
                'severity': sev,
                'evidence': evidence,
                'suggested_action': {'summary': fix, 'priority': prio or sev},
            })
            ix[0] += 1

        # 1) missing H1  [high]
        no_h1 = df[df['h1_count'] == 0]
        if len(no_h1) > 0:
            add(
                'Missing H1 Heading on Landing Pages',
                'high',
                f'{len(no_h1)}/{n} pages have no <h1>. Visitors from AI '
                f'citations land with zero immediate context about the page.',
                'Add one clear, benefit-driven <h1> above the fold:\n\n'
                '<h1>Real-Time Event Streaming with Sub-ms Latency</h1>',
            )

        # 2) vague H1  [medium]
        vague = df[df['vague_h1'] == True]
        if len(vague) > 0:
            exs = [f"'{row['h1_txt'][:50]}'" for _, row in vague.head(2).iterrows()]
            add(
                'Vague Headlines Fail the 5-Second Test',
                'medium',
                f'{len(vague)}/{n} pages use buzzword H1 copy '
                f'({", ".join(exs)}) that doesn\'t say what the product does.',
                'Rewrite using: [Product] helps [Audience] do [Thing] '
                'without [Pain].\n\n'
                '❌ "Transforming the Future of Data"\n'
                '✅ "Real-Time Vector Search for K8s Workloads"',
            )

        # 3) too many H1s  [low]
        multi = df[df['h1_count'] > 1]
        if len(multi) / n > 0.3:
            add(
                'Multiple H1 Headings Dilute Topic Focus',
                'low',
                f'{len(multi)}/{n} pages have >1 <h1>, muddying the '
                f'heading hierarchy for both readers and AI parsers.',
                'Keep exactly one H1 per page; demote the rest to <h2>.',
            )

        # 4) breadcrumbs missing on deep pages  [high]
        deep = df[df['is_deep'] == True]
        if len(deep) > 0:
            no_crumbs = deep[deep['has_crumbs'] == False]
            if len(no_crumbs) / len(deep) > 0.5:
                add(
                    'Deep Pages Missing Breadcrumb Navigation',
                    'high',
                    f'{len(no_crumbs)}/{len(deep)} deep sub-pages lack breadcrumbs. '
                    f'AI-referred visitors land without knowing where they are '
                    f'in the site hierarchy.',
                    'Add semantic breadcrumbs with Schema.org:\n\n'
                    '<nav aria-label="Breadcrumb">\n'
                    '  <ol class="breadcrumb">\n'
                    '    <li><a href="/">Home</a></li>\n'
                    '    <li><a href="/docs">Docs</a></li>\n'
                    '    <li aria-current="page">API Ref</li>\n'
                    '  </ol>\n'
                    '</nav>',
                )

        # 5) wall-of-text pages  [medium]
        wordy = df[df['long_blocks'] > 0]
        if len(wordy) / n > 0.3:
            total_blk = int(df['long_blocks'].sum())
            add(
                'Dense Prose Blocks Hurt Scannability',
                'medium',
                f'{len(wordy)}/{n} pages contain paragraphs >{LONG_PARA_THRESHOLD} '
                f'chars with no sub-headings ({total_blk} blocks total).',
                'Break long paragraphs into bullets:\n\n'
                '<h3>Key Features</h3>\n'
                '<ul>\n'
                '  <li><strong>Sub-ms latency:</strong> Process events under 1ms.</li>\n'
                '  <li><strong>Zero-copy:</strong> 60% less memory overhead.</li>\n'
                '</ul>',
            )

        # 6) vague CTAs  [medium]
        pages_w_ctas = df[df['n_ctas'] > 0]
        if len(pages_w_ctas) > 0:
            tot_ctas = int(df['n_ctas'].sum())
            tot_vague = int(df['n_vague_ctas'].sum())
            vpct = round(tot_vague / tot_ctas * 100, 1) if tot_ctas else 0
            if vpct > 30:
                add(
                    'Vague CTA Copy Adds Conversion Friction',
                    'medium',
                    f'{tot_vague}/{tot_ctas} ({vpct}%) CTAs use generic '
                    f'text like "Learn More" or "Click Here".',
                    'Use explicit action text:\n\n'
                    '<a href="/signup" class="btn-primary">'
                    'Start 14-Day Free Trial (No Card Required)</a>\n'
                    '<a href="/docs/quickstart" class="btn-secondary">'
                    '5-Minute Quickstart Guide</a>',
                )

        # 7) dead-end pages  [high]
        no_cta = df[df['n_ctas'] == 0]
        if len(no_cta) / n > 0.4:
            add(
                'Dead-End Pages With No Next Step',
                'high',
                f'{len(no_cta)}/{n} pages have zero buttons or action links. '
                f'Visitors from AI citations hit a wall with nowhere to go.',
                'Add a persistent next-steps block:\n\n'
                '<div class="next-steps">\n'
                '  <h3>Ready to try it?</h3>\n'
                '  <a href="/deploy" class="btn">Deploy in 5 Min</a>\n'
                '  <a href="/community">Join the Slack</a>\n'
                '</div>',
            )

        # 8) missing viewport  [high]
        no_vp = df[df['has_viewport'] == False]
        if len(no_vp) > 0:
            add(
                'Missing Responsive Viewport Tag',
                'high',
                f'{len(no_vp)}/{n} pages lack a viewport meta tag — '
                f'mobile visitors get a desktop-scale mess.',
                'Add to every <head>:\n\n'
                '<meta name="viewport" content="width=device-width, '
                'initial-scale=1.0">',
            )

        # 9) images without dimensions → CLS risk  [low]
        tot_imgs = int(df['n_imgs'].sum())
        no_dims = int(df['imgs_no_dims'].sum())
        if tot_imgs > 0 and no_dims / tot_imgs > 0.5:
            pct = round(no_dims / tot_imgs * 100, 1)
            add(
                'Layout Shift Risk (Images Missing Width/Height)',
                'low',
                f'{no_dims}/{tot_imgs} ({pct}%) images lack explicit '
                f'dimensions, causing content jumps on load.',
                'Set width & height on all images:\n\n'
                '<img src="hero.png" width="800" height="450" '
                'alt="Overview" loading="lazy" />',
            )

        # 10) AI email/inbox summary readiness  [medium] — Appendix F
        risky = df[df['email_risk'] == True]
        if len(risky) > 0:
            ex_urls = risky['url'].head(2).tolist()
            bp_n = int(df['boilerplate_opener'].sum())
            extra = (f' {bp_n} page(s) open with low-value boilerplate that '
                     'displaces the real message in AI summaries.') if bp_n else ''
            add(
                'Content Vulnerable to AI Email Summarisation Drops',
                'medium',
                f'{len(risky)}/{n} pages have high image-to-text ratios or '
                f'filler openings. AI inbox summarisers (Apple Intelligence, '
                f'Gmail Gemini) will drop the important content.{extra} '
                f'Examples: {", ".join(ex_urls)}.',
                'Structure pages text-first and add an invisible preheader:\n\n'
                '<!-- AI Inbox Preheader -->\n'
                '<div style="display:none;font-size:1px;color:#fff;'
                'max-height:0px;overflow:hidden;">\n'
                '  v3.0 launched with native vector search and '
                'multi-region replication.\n'
                '</div>\n\n'
                'Keep at least 60:40 text-to-image ratio, and put key '
                'facts before any promotional graphics.',
            )

        # 11) thin above-fold content  [medium] — Appendix E
        weak_atf = df[df['substantive_atf'] == False]
        if len(weak_atf) / n > 0.3:
            add(
                'Thin Above-Fold Content for AI-Personalised Referrals',
                'medium',
                f'{len(weak_atf)}/{n} pages have <100 chars of substance in '
                f'the first visible section. AI assistants need dense '
                f'above-fold text to match the page to user intent (Appendix E).',
                'Front-load the first 500 chars with specific value:\n\n'
                '<p class="lead">\n'
                '  Built for enterprise data teams — real-time event '
                'streaming with automated schema registry and SOC-2 '
                'Type II compliance.\n'
                '</p>',
            )

        # 12) proactive: instant-value widget  [medium]
        add(
            'Opportunity: Instant-Value Widget for AI-Referred Visitors',
            'medium',
            'Visitors from ChatGPT/Claude/Perplexity arrive with specific '
            'intent. A static promotional wall increases bounce probability.',
            'Add a lightweight interactive element or AI-referral banner:\n\n'
            '<div class="ai-welcome" id="aiWelcome" style="display:none;">\n'
            '  <p>👋 Came from an AI assistant? '
            '<a href="#pricing-calc">Try the pricing calculator →</a></p>\n'
            '</div>\n'
            '<script>\n'
            '  if (document.referrer && '
            '/chatgpt|claude|perplexity/i.test(document.referrer)) {\n'
            '    document.getElementById("aiWelcome").style.display = "block";\n'
            '  }\n'
            '</script>',
            prio='low',
        )

        # tally severities
        counts = {'total_findings': len(findings), 'critical': 0,
                  'high': 0, 'medium': 0, 'low': 0}
        for f in findings:
            s = f.get('severity', 'medium')
            if s in counts:
                counts[s] += 1

        return {
            'site': self.netloc,
            'audited_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'summary': counts,
            'findings': findings,
        }

    # ── public entry ───────────────────────────────────────────────

    def run(self):
        self._setup_robots()
        self._crawl()
        return self._build_findings()


def main():
    ap = argparse.ArgumentParser(
        description='On-site engagement & AI-summary readiness analyser')
    ap.add_argument('url', help='Target URL or domain')
    ap.add_argument('--max-pages', type=int, default=10,
                    help='Max pages to sample (default 10)')
    ap.add_argument('--timeout', type=int, default=6)
    ap.add_argument('--output', '-o', help='Write JSON report here')
    args = ap.parse_args()

    analyser = EngagementAnalyzer(
        base_url=args.url, max_pages=args.max_pages, timeout=args.timeout)
    report = analyser.run()

    out = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(out)
        print(f'Engagement report written to {args.output}', file=sys.stderr)
    else:
        print(out)


if __name__ == '__main__':
    main()
