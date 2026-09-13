#!/usr/bin/env python3
"""
Off-site AI discoverability + entity corroboration auditor.

Crawls a target website (politely, read-only, robots.txt-respecting) and checks
whether AI retrieval bots can actually find, parse, trust, and cite the brand.
Covers crawl access, structured data, JS rendering gaps, entity disambiguation,
personalisation signals, and freshness — basically everything from Appendix A–F
that lives on the "can machines even see you?" side of the fence.

Outputs a JSON report matching the hackathon schema floor.
"""

import sys, os, re, json, time, argparse
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set

import requests
from bs4 import BeautifulSoup
import pandas as pd

try:
    import tldextract
except ImportError:
    tldextract = None  # graceful fallback to manual parsing

# shut up the SSL warnings in sandboxed envs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ── constants ───────────────────────────────────────────────────────

UA_STRING = (
    'NexusCodersAuditBot/2.0 '
    '(+https://github.com/upamkmr/Nexus_adobe; read-only brand audit)'
)

# bots we check in robots.txt — these are the ones that matter for AI citations
AI_BOT_TOKENS = [
    'GPTBot', 'ChatGPT-User', 'ClaudeBot', 'PerplexityBot',
    'Google-Extended', 'Applebot-Extended', 'CCBot', 'cohere-ai',
]

# domains we consider "authoritative" for sameAs entity grounding
KNOWN_ENTITY_DOMAINS = [
    'wikidata.org', 'wikipedia.org', 'linkedin.com',
    'crunchbase.com', 'github.com', 'twitter.com', 'x.com',
]

# SPA container IDs that signal client-side-only rendering
SPA_ROOT_SELECTORS = ['#root', '#app', '#__next', '#__nuxt', 'app-root', '#__svelte']


# ── small helpers ───────────────────────────────────────────────────

def _norm_url(raw: str) -> str:
    """Slap https:// on if the user forgot it."""
    p = urllib.parse.urlparse(raw)
    if not p.scheme:
        raw = 'https://' + raw
    return raw


def _brand_from_domain(url: str) -> str:
    """
    Best-effort brand keyword extraction from the domain.
    Uses tldextract when available, falls back to manual ccTLD stripping.
    """
    if tldextract is not None:
        try:
            ext = tldextract.TLDExtract(cache_dir=False)(url)
            if ext.domain and ext.domain not in ('www', ''):
                return ext.domain.capitalize()
        except Exception:
            pass

    host = urllib.parse.urlparse(_norm_url(url)).netloc.lower().replace('www.', '')

    # handle multi-part ccTLDs like .co.uk, .com.au etc.
    multi_tlds = [
        '.co.uk', '.org.uk', '.gov.uk', '.ac.uk',
        '.com.au', '.net.au', '.org.au', '.edu.au',
        '.co.nz', '.co.in', '.gov.in', '.ac.in',
        '.co.jp', '.ne.jp', '.com.br', '.com.mx',
        '.com.sg', '.com.hk', '.co.za',
    ]
    for suffix in multi_tlds:
        if host.endswith(suffix):
            chunk = host[:-len(suffix)].split('.')[-1]
            if chunk:
                return chunk.capitalize()

    parts = host.split('.')
    generic_tlds = {'com', 'org', 'net', 'edu', 'gov', 'io', 'ai', 'co', 'app', 'dev'}
    if len(parts) >= 2:
        pick = parts[-2] if parts[-2] not in generic_tlds else parts[0]
    else:
        pick = parts[0]
    return pick.capitalize()


def _severity_counts(findings: list) -> dict:
    """Tally severity buckets for the summary block."""
    c = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for f in findings:
        sev = f.get('severity', 'medium')
        if sev in c:
            c[sev] += 1
    c['total_findings'] = len(findings)
    return c


# ── main auditor class ─────────────────────────────────────────────

class DiscoverabilityAuditor:
    """
    Crawls a site, gathers signals, then uses pandas to crunch page-level
    metrics into actionable findings with concrete fix snippets.
    """

    def __init__(self, base_url: str, max_pages: int = 15,
                 timeout: int = 6, delay: float = 0.4):
        self.base_url = _norm_url(base_url)
        parsed = urllib.parse.urlparse(self.base_url)
        self.base_url = f'{parsed.scheme}://{parsed.netloc}'
        self.netloc = parsed.netloc.lower()
        self.netloc_bare = self.netloc.replace('www.', '')
        self.max_pages = max(1, min(max_pages, 50))
        self.timeout = timeout
        self.delay = delay

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': UA_STRING,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        self.visited: Set[str] = set()
        self.page_records: List[Dict[str, Any]] = []

        # robots / sitemap / llms state
        self.robots_info: Dict[str, Any] = {}
        self.has_llms_txt = False
        self.llms_txt_url: Optional[str] = None
        self.sitemap_urls: List[str] = []
        self._rp: Optional[urllib.robotparser.RobotFileParser] = None
        self._crawl_delay_override: Optional[float] = None

        self.brand = _brand_from_domain(self.base_url)

    # ── robots.txt & our own compliance ────────────────────────────

    def _allowed(self, url: str) -> bool:
        if self._rp is None:
            return True
        try:
            return (self._rp.can_fetch(UA_STRING, url)
                    and self._rp.can_fetch('*', url))
        except Exception:
            return True

    def _parse_robots(self):
        """Fetch robots.txt: (a) set up our own compliance parser,
        (b) check which AI bots are blocked — that's a *finding*, not a rule
        for us."""
        robots_url = self.base_url + '/robots.txt'
        self.robots_info = {'present': False, 'blocked_bots': [], 'sitemaps': []}
        try:
            r = self.session.get(robots_url, timeout=self.timeout, verify=False)
            if r.status_code != 200 or not r.text:
                return
        except Exception:
            return

        self.robots_info['present'] = True
        txt = r.text

        # extract sitemaps from robots.txt
        for line in txt.splitlines():
            line = line.strip()
            if not line or line.startswith('#') or ':' not in line:
                continue
            key, val = [s.strip() for s in line.split(':', 1)]
            if key.lower() == 'sitemap' and val:
                self.robots_info['sitemaps'].append(val)
                self.sitemap_urls.append(val)

        # Use the standard-library RobotFileParser to accurately check
        # which AI bots are blocked (handles wildcard precedence correctly)
        rp_check = urllib.robotparser.RobotFileParser()
        rp_check.parse(txt.splitlines())
        for bot in AI_BOT_TOKENS:
            try:
                if not rp_check.can_fetch(bot, self.base_url + '/'):
                    self.robots_info['blocked_bots'].append(bot)
            except Exception:
                pass

        # set up compliance parser for our own crawler
        self._rp = urllib.robotparser.RobotFileParser()
        self._rp.set_url(robots_url)
        self._rp.parse(txt.splitlines())
        cd = self._rp.crawl_delay(UA_STRING)
        if cd is not None:
            self._crawl_delay_override = min(float(cd), 3.0)

    def _probe_sitemap(self):
        """If robots.txt didn't declare a sitemap, try /sitemap.xml directly."""
        if self.sitemap_urls:
            return
        url = self.base_url + '/sitemap.xml'
        try:
            r = self.session.head(url, timeout=self.timeout,
                                  verify=False, allow_redirects=True)
            if r.status_code == 200:
                self.sitemap_urls.append(url)
        except Exception:
            pass

    def _probe_llms_txt(self):
        for path in ['/llms.txt', '/.well-known/llms.txt']:
            target = self.base_url + path
            try:
                r = self.session.get(target, timeout=self.timeout, verify=False)
                # make sure it's real content, not a soft-404 or SPA fallback
                ct = r.headers.get('content-type', '').lower()
                body = r.text.strip()
                is_html = (
                    'text/html' in ct
                    or body.lower().startswith(('<!doctype', '<html', '<head'))
                )
                if (r.status_code == 200
                        and len(body) > 30
                        and '404' not in body[:200].lower()
                        and not is_html):
                    self.has_llms_txt = True
                    self.llms_txt_url = target
                    return
            except Exception:
                pass

    # ── BFS crawl ──────────────────────────────────────────────────

    def _crawl(self):
        queue = [self.base_url]
        wait = self._crawl_delay_override or self.delay

        while queue and len(self.visited) < self.max_pages:
            url = queue.pop(0)
            if url in self.visited:
                continue
            if not self._allowed(url):
                continue

            self.visited.add(url)
            rec, links = self._fetch_and_extract(url)
            if rec:
                self.page_records.append(rec)

            for lnk in links:
                if lnk not in self.visited and lnk not in queue:
                    if len(queue) + len(self.visited) < self.max_pages * 2:
                        queue.append(lnk)

            time.sleep(wait)

    def _fetch_and_extract(self, url: str):
        """Fetch one page, pull out everything we need for analysis.
        Returns (record_dict, list_of_internal_links) or (None, [])."""
        try:
            resp = self.session.get(url, timeout=self.timeout,
                                    verify=False, allow_redirects=True)
            if resp.status_code != 200:
                return None, []
            if 'text/html' not in resp.headers.get('content-type', '').lower():
                return None, []
        except Exception:
            return None, []

        soup = BeautifulSoup(resp.text, 'html.parser')
        raw_len = len(resp.text)

        # -- structured data (JSON-LD) --
        schemas, types_found, sameas_links = [], [], []
        has_audience = False

        for tag in soup.find_all('script', type='application/ld+json'):
            try:
                raw_text = tag.string
                if not raw_text:
                    continue
                blob = json.loads(raw_text)
                if not blob:
                    continue
                # Handle @graph wrapper used by WordPress/Yoast, Shopify, etc.
                if isinstance(blob, dict) and '@graph' in blob:
                    graph_items = blob['@graph']
                    items = graph_items if isinstance(graph_items, list) else [graph_items]
                else:
                    items = blob if isinstance(blob, list) else [blob]
                schemas.extend(items)
            except (json.JSONDecodeError, TypeError):
                continue

        for item in schemas:
            if not isinstance(item, dict):
                continue
            t = item.get('@type')
            if t:
                types_found.extend(t if isinstance(t, list) else [t])
            sa = item.get('sameAs', [])
            sa_list = sa if isinstance(sa, list) else [sa]
            # Filter out None/non-string values to prevent AttributeError
            sameas_links.extend([s for s in sa_list if isinstance(s, str)])
            # Appendix E: audience / persona signals
            item_lower = str(item).lower()
            if any(kw in item_lower for kw in ('audience', 'targetaudience', 'knowsabout')):
                has_audience = True

        got_schema = len(schemas) > 0

        # -- JS rendering gap detection (Appendix C) --
        # IMPORTANT: inspect script/noscript BEFORE stripping them from the tree
        empty_roots = []
        for sel in SPA_ROOT_SELECTORS:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) < 50:
                empty_roots.append(sel)

        has_hydration = bool(
            soup.find('script', id='__NEXT_DATA__')
            or re.search(r'window\.__INITIAL_STATE__\s*=', resp.text)
            or re.search(r'window\.__NUXT__\s*=', resp.text)
            or re.search(r'window\.__PRELOADED_STATE__\s*=', resp.text)
        )

        noscript_warn = any(
            re.search(r'(?:enable\s+javascript|javascript\s+is\s+disabled|requires\s+javascript)',
                       ns.get_text(), re.I)
            for ns in soup.find_all('noscript')
        )

        n_scripts = len(soup.find_all('script', src=True))

        # -- visible text extraction (strip junk AFTER script/noscript checks) --
        for junk in soup(['script', 'style', 'noscript', 'svg']):
            junk.extract()
        text = soup.get_text(separator=' ', strip=True)
        text_len = len(text)
        text_ratio = round(text_len / max(raw_len, 1), 4)

        # combine signals to decide if this is a JS skeleton
        is_skeleton = False
        skeleton_why = ''
        if text_len < 250 and (empty_roots or has_hydration or noscript_warn):
            is_skeleton = True
            skeleton_why = f'thin text ({text_len}ch) + empty container {empty_roots[:1]}'
        elif raw_len > 8000 and text_ratio < 0.035 and (n_scripts >= 3 or has_hydration):
            is_skeleton = True
            skeleton_why = (f'markup bloat (raw={raw_len}b, text={text_len}ch, '
                            f'ratio={text_ratio*100:.1f}%)')
        elif text_len < 150 and n_scripts > 3:
            is_skeleton = True
            skeleton_why = f'barely any text ({text_len}ch) drowned by {n_scripts} script bundles'

        # -- images & alt text --
        imgs = soup.find_all('img')
        n_imgs = len(imgs)
        n_missing_alt = sum(1 for img in imgs
                            if not img.get('alt') or len(img.get('alt', '').strip()) < 3)

        # canvas & PDF-only traps
        n_canvas = len(soup.find_all('canvas'))
        canvas_heavy = n_canvas > 0 and text_len < 300
        pdf_links = []
        for a in soup.find_all('a', href=True):
            if a['href'].strip().lower().endswith('.pdf'):
                pdf_links.append(a.get_text(strip=True) or a['href'])
        pdf_only = bool(pdf_links) and text_len < 400

        # -- headings --
        n_h1 = len(soup.find_all('h1'))

        # -- metadata --
        title_tag = soup.title
        title = title_tag.string.strip() if (title_tag and title_tag.string) else ''
        meta_d = soup.find('meta', attrs={'name': re.compile(r'^description$', re.I)})
        meta_desc = meta_d.get('content', '').strip() if meta_d else ''

        # canonical
        canon = soup.find('link', rel=re.compile(r'^canonical$', re.I))
        canonical = canon.get('href', '').strip() if canon else ''

        # viewport
        has_vp = bool(soup.find('meta', attrs={'name': re.compile(r'^viewport$', re.I)}))

        # -- freshness signals --
        last_mod = resp.headers.get('last-modified', '')
        cr_years = re.findall(
            r'(?:©|copyright|\(c\))\s*(?:20\d\d\s*-\s*)?(20\d\d)', text, re.I
        )
        latest_cr = int(max(cr_years)) if cr_years else None

        # also look for dateModified in structured data
        date_mod_schema = None
        for item in schemas:
            if isinstance(item, dict):
                dm = item.get('dateModified') or item.get('datePublished')
                if dm and isinstance(dm, str):
                    date_mod_schema = dm
                    break

        # -- OpenGraph / Twitter Cards (Appendix E) --
        def _og(prop, fallback_name=None):
            tag = soup.find('meta', property=prop)
            if not tag and fallback_name:
                tag = soup.find('meta', attrs={'name': fallback_name})
            return tag.get('content', '').strip() if tag else ''

        og_title = _og('og:title', 'twitter:title')
        og_desc = _og('og:description', 'twitter:description')
        og_img = _og('og:image', 'twitter:image')
        complete_og = bool(og_title and og_desc and og_img)

        # -- hreflang (Appendix E) --
        hreflang_tags = soup.find_all('link', rel='alternate', hreflang=True)

        # -- claim provenance markup --
        has_provenance = any(
            any(t in ('Claim', 'ClaimReview', 'CreativeWork') for t in types_found)
            and any(k in str(item).lower()
                    for k in ('citation', 'isbasedon', 'claiminterpreter'))
            for item in schemas
        )

        # -- collect internal links for BFS --
        int_links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].split('#')[0].strip()
            if not href or href.startswith(('mailto:', 'tel:', 'javascript:')):
                continue
            full = urllib.parse.urljoin(url, href)
            purl = urllib.parse.urlparse(full)
            if purl.netloc.lower().replace('www.', '') == self.netloc_bare:
                clean = f'{purl.scheme}://{purl.netloc}{purl.path}'
                if purl.query:
                    clean += f'?{purl.query}'
                if clean not in int_links:
                    int_links.append(clean)

        record = {
            'url': url,
            'title': title,
            'meta_desc': meta_desc,
            'has_canonical': bool(canonical),
            'has_viewport': has_vp,
            'has_schema': got_schema,
            'schema_types': types_found,
            'sameas_links': sameas_links,
            'has_audience_schema': has_audience,
            'has_claim_provenance': has_provenance,
            'text_len': text_len,
            'raw_html_len': raw_len,
            'text_ratio': text_ratio,
            'is_skeleton': is_skeleton,
            'skeleton_why': skeleton_why,
            'has_hydration': has_hydration,
            'noscript_warn': noscript_warn,
            'n_imgs': n_imgs,
            'n_missing_alt': n_missing_alt,
            'n_canvas': n_canvas,
            'canvas_heavy': canvas_heavy,
            'pdf_links': pdf_links,
            'pdf_only': pdf_only,
            'n_h1': n_h1,
            'last_modified': last_mod,
            'copyright_yr': latest_cr,
            'date_modified_schema': date_mod_schema,
            'complete_og': complete_og,
            'has_hreflang': len(hreflang_tags) > 0,
        }
        return record, int_links

    # ── wikipedia entity lookup ────────────────────────────────────

    def _check_entity(self) -> dict:
        """Hit the Wikipedia search API to see if the brand name is ambiguous."""
        result = {
            'term': self.brand,
            'has_disambiguation': False,
            'titles': [],
            'n_matches': 0,
        }
        if not self.brand or len(self.brand) < 3:
            return result

        try:
            r = requests.get(
                'https://en.wikipedia.org/w/api.php',
                params={
                    'action': 'query', 'list': 'search',
                    'srsearch': self.brand, 'srlimit': 5, 'format': 'json',
                },
                timeout=4,
                headers={'User-Agent': UA_STRING},
            )
            if r.status_code != 200:
                return result
            hits = r.json().get('query', {}).get('search', [])
            result['n_matches'] = len(hits)
            for h in hits:
                result['titles'].append(h.get('title', ''))
                snip = h.get('snippet', '').lower()
                if 'disambiguation' in h.get('title', '').lower() or 'may refer to' in snip:
                    result['has_disambiguation'] = True
        except Exception:
            pass
        return result

    # ── analysis: turn raw page data into findings ─────────────────

    def _build_findings(self, entity_info: dict) -> dict:
        """
        Crunch all the page-level data through pandas and emit
        prioritised findings with copy-pasteable fix snippets.
        """
        if not self.page_records:
            return {
                'site': self.netloc,
                'audited_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'summary': {'total_findings': 1, 'critical': 1, 'high': 0, 'medium': 0, 'low': 0},
                'findings': [{
                    'id': 'F-001',
                    'title': 'Site Unreachable — No Pages Crawled',
                    'severity': 'critical',
                    'evidence': f'Could not fetch any HTML from {self.base_url}.',
                    'suggested_action': {
                        'summary': 'Check DNS, SSL certs, and server availability.',
                        'priority': 'high',
                    },
                }],
            }

        df = pd.DataFrame(self.page_records)
        n = len(df)
        findings = []
        idx = [1]  # mutable counter so helpers can bump it

        def _add(title, severity, evidence, fix, priority=None):
            findings.append({
                'id': f'F-{idx[0]:03d}',
                'title': title,
                'severity': severity,
                'evidence': evidence,
                'suggested_action': {
                    'summary': fix,
                    'priority': priority or severity,
                },
            })
            idx[0] += 1

        # 1) AI bots blocked in robots.txt  [critical]
        blocked = self.robots_info.get('blocked_bots', [])
        if blocked:
            bots_str = ', '.join(blocked)
            directives = '\n'.join([
                '# Allow AI retrieval crawlers on public paths',
                'User-agent: GPTBot\nAllow: /',
                'User-agent: ClaudeBot\nAllow: /',
                'User-agent: PerplexityBot\nAllow: /',
                'User-agent: Google-Extended\nAllow: /',
                'User-agent: Applebot-Extended\nAllow: /',
            ])
            _add(
                'AI Crawlers Blocked in robots.txt',
                'critical',
                (f'robots.txt blocks these AI retrieval bots: {bots_str}. '
                 'ChatGPT, Claude, and Perplexity literally cannot index the site.'),
                f'Add explicit Allow rules for each AI crawler:\n\n{directives}',
            )

        # 2) low Schema.org JSON-LD coverage  [high]
        with_schema = int(df['has_schema'].sum())
        schema_pct = round(with_schema / n * 100, 1)
        if schema_pct < 50:
            snippet = (
                '<script type="application/ld+json">\n'
                '{\n'
                '  "@context": "https://schema.org",\n'
                '  "@type": "Organization",\n'
                f'  "name": "{self.brand}",\n'
                f'  "url": "{self.base_url}",\n'
                f'  "logo": "{self.base_url}/logo.png",\n'
                '  "sameAs": [\n'
                '    "https://www.wikidata.org/wiki/Q...",\n'
                f'    "https://www.linkedin.com/company/{self.brand.lower()}"\n'
                '  ]\n'
                '}\n'
                '</script>'
            )
            _add(
                'Low Schema.org JSON-LD Coverage',
                'high',
                (f'{with_schema}/{n} pages ({schema_pct}%) have JSON-LD. '
                 'Missing Organization, Product, and WebSite types means AI '
                 'assistants can\'t reliably extract structured brand facts.'),
                f'Add JSON-LD to every page template:\n\n{snippet}',
            )

        # 3) missing sameAs + entity ambiguity  [high]
        all_sa = [lnk for row_links in df['sameas_links'] for lnk in row_links]
        has_good_sameas = any(
            any(d in lnk.lower() for d in KNOWN_ENTITY_DOMAINS)
            for lnk in all_sa
        )
        if not has_good_sameas:
            bits = [
                'No pages link to authoritative knowledge graphs (Wikidata, '
                'Wikipedia, Crunchbase, LinkedIn) via sameAs in JSON-LD.'
            ]
            if entity_info.get('has_disambiguation') or entity_info.get('n_matches', 0) > 1:
                matched = ', '.join(f"'{t}'" for t in entity_info.get('titles', []))
                bits.append(
                    f"Wikipedia search for '{entity_info['term']}' returned "
                    f"multiple entities ({matched}) — high naming-collision risk."
                )
            else:
                bits.append(
                    'Without external entity anchors, LLMs risk hallucinating '
                    'or conflating the brand with something else entirely.'
                )
            _add(
                'Missing Knowledge-Graph Entity Links (sameAs)',
                'high',
                ' '.join(bits),
                (
                    'Add sameAs URIs to the homepage Organization schema:\n\n'
                    '"sameAs": [\n'
                    '  "https://www.wikidata.org/wiki/Q<ENTITY_ID>",\n'
                    f'  "https://en.wikipedia.org/wiki/{self.brand}",\n'
                    f'  "https://www.linkedin.com/company/{self.brand.lower()}",\n'
                    f'  "https://www.crunchbase.com/organization/{self.brand.lower()}"\n'
                    ']\n\n'
                    f'Also add: "disambiguatingDescription": '
                    f'"{self.brand} is a ... (fill in what makes it unique)"'
                ),
            )

        # 4) JS skeleton / SPA rendering gap  [high]
        skeletons = df[df['is_skeleton'] == True]
        if len(skeletons) > 0:
            example_urls = skeletons['url'].head(3).tolist()
            reasons = [r for r in skeletons['skeleton_why'].unique() if r]
            detail = f' Signals: {"; ".join(reasons[:2])}.' if reasons else ''
            _add(
                'Client-Side Rendered Pages (AI Ingestion Gap)',
                'high',
                (f'{len(skeletons)}/{n} pages are JS-only shells that return '
                 f'near-empty HTML to non-headless crawlers like GPTBot and '
                 f'ClaudeBot.{detail} Examples: {", ".join(example_urls)}.'),
                (
                    'Use SSR or set up bot-specific prerendering. '
                    'Nginx example:\n\n'
                    'if ($http_user_agent ~* "GPTBot|ChatGPT-User|ClaudeBot|'
                    'PerplexityBot|Applebot-Extended") {\n'
                    '    proxy_pass http://prerender-service:3000/render/'
                    '$scheme://$host$request_uri;\n'
                    '    break;\n'
                    '}'
                ),
            )

        # 5) images missing alt text  [medium]
        total_imgs = int(df['n_imgs'].sum())
        missing_alt = int(df['n_missing_alt'].sum())
        if total_imgs > 0 and missing_alt / total_imgs > 0.35:
            pct = round(missing_alt / total_imgs * 100, 1)
            _add(
                'Images Missing Descriptive Alt Text',
                'medium',
                f'{missing_alt}/{total_imgs} ({pct}%) images lack meaningful alt '
                f'attributes — AI summarisers treat them as invisible.',
                (
                    'Write descriptive alt for every informational image:\n\n'
                    '<figure>\n'
                    '  <img src="arch.png" alt="Architecture: stream ingestion '
                    '→ processing → storage cluster" />\n'
                    '  <figcaption>System Architecture</figcaption>\n'
                    '</figure>'
                ),
            )

        # 5b) canvas / PDF-only traps  [medium]
        canvas_pages = df[df['canvas_heavy'] == True]
        pdf_pages = df[df['pdf_only'] == True]
        if len(canvas_pages) > 0 or len(pdf_pages) > 0:
            parts = []
            if len(canvas_pages):
                parts.append(f'{len(canvas_pages)} page(s) render content in '
                             '<canvas> with barely any surrounding text')
            if len(pdf_pages):
                parts.append(f'{len(pdf_pages)} page(s) rely on PDF links '
                             'as primary content with <400 chars of HTML text')
            _add(
                'Content Trapped in Canvas / PDF-Only Pages',
                'medium',
                '; '.join(parts) + '. AI crawlers skip or poorly parse these formats.',
                (
                    'Mirror key facts as semantic HTML next to the visual:\n\n'
                    '<div class="canvas-text-fallback">\n'
                    '  <h3>Chart Summary</h3>\n'
                    '  <p>Q3 throughput increased 34% over baseline...</p>\n'
                    '</div>'
                ),
            )

        # 6) incomplete OpenGraph / Twitter Cards  [medium] — Appendix E
        og_count = int(df['complete_og'].sum())
        og_pct = round(og_count / n * 100, 1)
        if og_pct < 50:
            _add(
                'Incomplete OpenGraph Metadata Limits AI Personalisation',
                'medium',
                (f'Only {og_count}/{n} ({og_pct}%) pages have full OG tags '
                 '(title+desc+image). AI assistants use these to tailor how '
                 'they present the brand in conversational answers (Appendix E).'),
                (
                    'Add OG + Twitter Card tags to every page <head>:\n\n'
                    f'<meta property="og:title" content="{self.brand} — '
                    f'Platform Overview" />\n'
                    '<meta property="og:description" content="High-performance '
                    'data streaming for enterprise scale." />\n'
                    f'<meta property="og:image" content="{self.base_url}'
                    '/assets/preview.jpg" />\n'
                    '<meta property="og:type" content="website" />\n'
                    f'<meta property="og:url" content="{self.base_url}" />\n'
                    '<meta name="twitter:card" content="summary_large_image" />'
                ),
            )

        # 7) no Schema.org audience / persona  [medium] — Appendix E
        if int(df['has_audience_schema'].sum()) == 0:
            _add(
                'No Schema.org Audience Signals for Persona Matching',
                'medium',
                ('Zero pages declare audience or targetAudience in JSON-LD. '
                 'AI assistants use these to decide which brand to surface '
                 'for a given user profile (Appendix E).'),
                (
                    'Declare target audience in structured data:\n\n'
                    '<script type="application/ld+json">\n'
                    '{\n'
                    '  "@context": "https://schema.org",\n'
                    '  "@type": "SoftwareApplication",\n'
                    f'  "name": "{self.brand}",\n'
                    '  "audience": {\n'
                    '    "@type": "BusinessAudience",\n'
                    '    "audienceType": "Enterprise Engineering Teams"\n'
                    '  },\n'
                    '  "knowsAbout": ["Real-Time Analytics", '
                    '"Stream Processing", "Distributed Systems"]\n'
                    '}\n'
                    '</script>'
                ),
            )

        # 8) missing llms.txt  [medium]
        if not self.has_llms_txt:
            _add(
                'No llms.txt for LLM Context-Window Ingestion',
                'medium',
                f'Neither /llms.txt nor /.well-known/llms.txt exists on '
                f'{self.netloc}. LLM agents look for this standard when '
                f'building brand context.',
                (
                    f'Create {self.base_url}/llms.txt:\n\n'
                    f'# {self.brand}\n'
                    '> One-sentence value prop.\n\n'
                    '## Core Docs\n'
                    f'- [Getting Started]({self.base_url}/docs): Setup guide.\n'
                    f'- [API Ref]({self.base_url}/api): REST & GraphQL.\n\n'
                    '## Entity\n'
                    '- Wikidata: https://www.wikidata.org/wiki/Q...'
                ),
            )

        # 9) entity name collision warning  [medium]
        ei = entity_info
        if ei.get('has_disambiguation') or ei.get('n_matches', 0) > 2:
            titles_str = ', '.join(f"'{t}'" for t in ei.get('titles', []))
            _add(
                'Brand-Name Collision in External Knowledge Bases',
                'medium',
                (f"Wikipedia search for '{ei['term']}' returned "
                 f"{ei['n_matches']} entities: {titles_str}. "
                 f"{'Disambiguation page exists — ' if ei.get('has_disambiguation') else ''}"
                 f"LLMs may confuse this brand with unrelated entities."),
                (f"Use the full qualified name everywhere (e.g. "
                 f"'{self.brand} (software company)' not just '{self.brand}'). "
                 f"Add disambiguatingDescription and official Wikidata URIs."),
            )

        # 10) stale copyright / freshness  [low]
        this_year = datetime.now().year
        stale = df[df['copyright_yr'].apply(lambda y: y is not None and y < this_year - 1)]
        if len(stale) > 0:
            _add(
                'Stale Copyright / Freshness Signals',
                'low',
                (f'{len(stale)}/{n} pages show copyright years older than '
                 f'{this_year - 1}, signalling abandoned content to '
                 f'temporal AI ranking heuristics.'),
                (
                    f'Auto-update copyright in footer templates:\n\n'
                    f'<footer>&copy; {this_year} {self.brand}. All rights reserved.</footer>\n'
                    f'<meta property="article:modified_time" '
                    f'content="{datetime.now().strftime("%Y-%m-%d")}" />'
                ),
            )

        # 11) no XML sitemap  [low]
        if not self.sitemap_urls:
            _add(
                'No XML Sitemap Declared or Found at /sitemap.xml',
                'low',
                ('Neither robots.txt nor /sitemap.xml provides a sitemap. '
                 'AI crawlers must rely on link-following alone, likely '
                 'missing deep pages.'),
                (
                    f'Publish a sitemap and declare it:\n\n'
                    f'Sitemap: {self.base_url}/sitemap.xml\n\n'
                    '<url>\n'
                    f'  <loc>{self.base_url}/docs/quickstart</loc>\n'
                    f'  <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
                    '  <changefreq>weekly</changefreq>\n'
                    '</url>'
                ),
            )

        # 12) missing canonical tags  [low]
        no_canon = df[df['has_canonical'] == False]
        if len(no_canon) / n > 0.4:
            _add(
                'Canonical Tags Missing on Many Pages',
                'low',
                f'{len(no_canon)}/{n} pages lack <link rel="canonical">. '
                f'Search engines and AI scrapers risk indexing duplicates.',
                (
                    'Add self-referential canonical to every page:\n\n'
                    f'<link rel="canonical" href="{self.base_url}/your-page" />'
                ),
            )

        # 13) no hreflang  [low] — Appendix E
        hreflang_count = int(df['has_hreflang'].sum())
        if hreflang_count == 0 and n >= 3:
            _add(
                'No hreflang Tags for Locale-Aware AI Responses',
                'low',
                ('Zero pages declare hreflang alternates. AI assistants use '
                 'locale signals to serve geographically relevant content '
                 '(Appendix E).'),
                (
                    'Add hreflang for each supported locale:\n\n'
                    f'<link rel="alternate" hreflang="en-US" '
                    f'href="{self.base_url}/en/" />\n'
                    f'<link rel="alternate" hreflang="de-DE" '
                    f'href="{self.base_url}/de/" />\n'
                    f'<link rel="alternate" hreflang="x-default" '
                    f'href="{self.base_url}/" />'
                ),
            )

        # 14) proactive: FAQPage schema  [medium]
        has_faq = any('FAQPage' in ts for ts in df['schema_types'])
        if not has_faq:
            _add(
                'Opportunity: FAQPage Schema for Conversational Citations',
                'medium',
                ('No FAQPage JSON-LD found. Perplexity and Google AI Overviews '
                 'heavily prioritise Q&A pairs for direct conversational answers.'),
                (
                    'Add FAQPage structured data on docs/product pages:\n\n'
                    '<script type="application/ld+json">\n'
                    '{\n'
                    '  "@context": "https://schema.org",\n'
                    '  "@type": "FAQPage",\n'
                    '  "mainEntity": [{\n'
                    '    "@type": "Question",\n'
                    f'    "name": "What does {self.brand} do?",\n'
                    '    "acceptedAnswer": {\n'
                    '      "@type": "Answer",\n'
                    f'      "text": "{self.brand} provides ..."\n'
                    '    }\n'
                    '  }]\n'
                    '}\n'
                    '</script>'
                ),
            )

        # 15) proactive: claim provenance  [medium]
        if not any(df['has_claim_provenance']):
            _add(
                'Opportunity: Structured Claim Provenance for Citation Confidence',
                'medium',
                ('No ClaimReview or citation provenance markup detected. '
                 'AI search engines increasingly prefer sources with verifiable, '
                 'structured evidence backing their claims.'),
                (
                    'Tag benchmarks and metrics with Schema.org Claim:\n\n'
                    '<script type="application/ld+json">\n'
                    '{\n'
                    '  "@context": "https://schema.org",\n'
                    '  "@type": "Claim",\n'
                    '  "claimInterpreter": {\n'
                    '    "@type": "Organization",\n'
                    '    "name": "Independent Testing Lab"\n'
                    '  },\n'
                    f'  "text": "{self.brand} delivers 4x throughput '
                    f'vs industry baselines.",\n'
                    '  "appearance": {\n'
                    '    "@type": "CreativeWork",\n'
                    f'    "url": "{self.base_url}/benchmarks",\n'
                    '    "citation": "https://doi.org/10.1000/182"\n'
                    '  }\n'
                    '}\n'
                    '</script>'
                ),
            )

        return {
            'site': self.netloc,
            'audited_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'summary': _severity_counts(findings),
            'findings': findings,
        }

    # ── public entry point ─────────────────────────────────────────

    def run(self) -> dict:
        self._parse_robots()
        self._probe_sitemap()
        self._probe_llms_txt()
        self._crawl()
        entity = self._check_entity()
        return self._build_findings(entity)


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Discoverability & entity corroboration auditor')
    ap.add_argument('url', help='Target URL or domain')
    ap.add_argument('--max-pages', type=int, default=15,
                    help='Max pages to crawl (default 15)')
    ap.add_argument('--timeout', type=int, default=6,
                    help='HTTP timeout in seconds (default 6)')
    ap.add_argument('--output', '-o', help='Write JSON report to this path')
    args = ap.parse_args()

    auditor = DiscoverabilityAuditor(
        base_url=args.url, max_pages=args.max_pages, timeout=args.timeout)
    report = auditor.run()

    out = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(out)
        print(f'Report saved to {args.output}', file=sys.stderr)
    else:
        print(out)


if __name__ == '__main__':
    main()
