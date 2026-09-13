#!/usr/bin/env python3
"""
Nexus Coders - Unified AI Discoverability, Entity Corroboration & Freshness Engine
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Performs a comprehensive off-site AI readiness audit by merging:
  1. Crawl & Render analysis: robots.txt AI crawler access, XML sitemap, llms.txt,
     JSON-LD structured data, JS-render gaps, non-text media trapping, canonical tags.
  2. Entity Corroboration & Freshness: Wikipedia/Wikidata disambiguation, sameAs
     knowledge-graph links, temporal freshness signals.
  3. AI-Summary & Personalization Readiness: OpenGraph metadata, hreflang locale
     targeting, image-to-text content ratios (Appendix E & F coverage).

Uses Pandas for vectorized metric aggregation. Uses tldextract for robust domain
parsing. Read-only, robots.txt-self-enforcing, polite crawl delays.
"""

import sys
import os
import re
import json
import time
import argparse
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
    tldextract = None

# Suppress insecure request warnings if encountered in sandbox
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Standard User-Agent for polite auditing
AUDIT_USER_AGENT = "NexusCodersAuditBot/1.0 (+https://github.com/upamkmr/Nexus_adobe; read-only brand audit)"

# Known AI and search assistant crawler bot identifiers
AI_BOTS = [
    "GPTBot",
    "ChatGPT-User",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "Applebot-Extended",
    "CCBot",
    "cohere-ai"
]

AUTHORITATIVE_ENTITY_DOMAINS = [
    "wikidata.org",
    "wikipedia.org",
    "linkedin.com",
    "crunchbase.com",
    "github.com",
    "twitter.com",
    "x.com"
]


class DiscoverabilityAuditor:
    """Safe, read-only crawler, entity corroborator, and AI discoverability auditor."""

    def __init__(self, base_url: str, max_pages: int = 15, timeout: int = 6, crawl_delay: float = 0.4):
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme:
            base_url = "https://" + base_url
            parsed = urllib.parse.urlparse(base_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.netloc = parsed.netloc.lower()
        self.max_pages = max(1, min(max_pages, 50))
        self.timeout = timeout
        # Politeness delay between requests (guardrail: no rate-abusing actions).
        self.crawl_delay = crawl_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": AUDIT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        })

        self.crawled_urls: Set[str] = set()
        self.pages_data: List[Dict[str, Any]] = []
        self.robots_rules: Dict[str, Any] = {}
        self.llms_txt_found: bool = False
        self.llms_txt_url: Optional[str] = None
        self.sitemap_found: bool = False
        self.sitemap_urls: List[str] = []
        self._robot_parser: Optional[urllib.robotparser.RobotFileParser] = None
        self._robots_delay: Optional[float] = None

        # Brand name via tldextract (robust) with manual fallback
        self.brand_name = self._extract_brand_name()

    def _extract_brand_name(self) -> str:
        """Derives brand keyword from domain using tldextract for TLD-aware parsing."""
        if tldextract is not None:
            ext = tldextract.extract(self.base_url)
            if ext.domain and ext.domain not in ("www", ""):
                return ext.domain.capitalize()
        # Fallback: manual domain parsing
        parts = self.netloc.replace("www.", "").split(".")
        if len(parts) >= 2:
            candidate = parts[-2] if parts[-2] not in ("com", "co", "org", "net", "edu", "gov") else parts[0]
        else:
            candidate = parts[0]
        return candidate.capitalize()

    def _may_fetch(self, url: str) -> bool:
        """Returns False if robots.txt disallows OUR crawler on this path."""
        if self._robot_parser is None:
            return True
        try:
            return self._robot_parser.can_fetch(AUDIT_USER_AGENT, url) and self._robot_parser.can_fetch("*", url)
        except Exception:
            return True

    def run(self) -> Dict[str, Any]:
        """Executes the full discoverability + corroboration audit pipeline."""
        self._check_robots_txt()
        self._check_llms_txt()
        self._crawl_site()
        entity_data = self._check_entity_disambiguation()
        return self._analyze_with_pandas(entity_data)

    def _safe_get(self, url: str) -> requests.Response:
        """Attempts verified GET first, falling back to verify=False only upon SSLError."""
        try:
            return self.session.get(url, timeout=self.timeout)
        except requests.exceptions.SSLError:
            return self.session.get(url, timeout=self.timeout, verify=False)

    # -----------------------------------------------------------------
    # Robots.txt, Sitemap, llms.txt
    # -----------------------------------------------------------------
    def _check_robots_txt(self) -> Dict[str, Any]:
        """Fetches and parses robots.txt for AI bot directives."""
        robots_url = f"{self.base_url}/robots.txt"
        blocked_bots = []
        allowed_bots = []
        raw_text = ""
        sitemaps = []

        try:
            res = self._safe_get(robots_url)
            if res.status_code == 200:
                raw_text = res.text
                current_agents: List[str] = []
                for line in raw_text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        directive, value = line.split(":", 1)
                        directive = directive.strip().lower()
                        value = value.strip()

                        if directive == "user-agent":
                            current_agents = [value]
                        elif directive == "disallow":
                            for agent in current_agents:
                                for bot in AI_BOTS:
                                    if agent == "*" or bot.lower() in agent.lower():
                                        if value in ["/", "/*"] and bot not in blocked_bots:
                                            blocked_bots.append(bot)
                        elif directive == "allow":
                            for agent in current_agents:
                                for bot in AI_BOTS:
                                    if bot.lower() in agent.lower():
                                        allowed_bots.append(bot)
                        elif directive == "sitemap":
                            sitemaps.append(value)
                    else:
                        current_agents = []
        except Exception:
            pass

        # Probe default /sitemap.xml if not explicitly declared in robots.txt
        if not sitemaps:
            try:
                sitemap_resp = self._safe_get(f"{self.base_url}/sitemap.xml")
                if sitemap_resp.status_code == 200 and (
                    "xml" in sitemap_resp.headers.get("content-type", "").lower()
                    or "<urlset" in sitemap_resp.text.lower()
                    or "<sitemapindex" in sitemap_resp.text.lower()
                ):
                    sitemaps.append(f"{self.base_url}/sitemap.xml")
            except Exception:
                pass

        self.robots_rules = {
            "exists": bool(raw_text),
            "blocked_ai_bots": blocked_bots,
            "sitemaps": sitemaps,
            "raw_snippet": raw_text[:500]
        }
        self.sitemap_urls = sitemaps

        # Load RobotFileParser so OUR OWN crawl obeys the site's rules
        try:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            if raw_text:
                rp.parse(raw_text.splitlines())
            else:
                rp.parse([])
            self._robot_parser = rp
            try:
                delay = rp.crawl_delay(AUDIT_USER_AGENT) or rp.crawl_delay("*")
                if delay:
                    self._robots_delay = float(delay)
            except Exception:
                pass
        except Exception:
            self._robot_parser = None

    def _check_llms_txt(self):
        """Checks for the presence of modern /llms.txt or /.well-known/llms.txt."""
        candidates = [
            f"{self.base_url}/llms.txt",
            f"{self.base_url}/.well-known/llms.txt"
        ]
        for url in candidates:
            try:
                res = self._safe_get(url)
                if res.status_code == 200 and len(res.text.strip()) > 20:
                    self.llms_txt_found = True
                    self.llms_txt_url = url
                    break
            except Exception:
                continue

    # -----------------------------------------------------------------
    # Entity Disambiguation (merged from freshness-corroboration)
    # -----------------------------------------------------------------
    def _check_entity_disambiguation(self) -> Dict[str, Any]:
        """
        Checks Wikipedia OpenSearch API to determine if the brand keyword
        has multiple conflicting entity interpretations or disambiguation pages.
        """
        brand = self.brand_name
        api_url = (
            f"https://en.wikipedia.org/w/api.php?action=opensearch"
            f"&search={urllib.parse.quote(brand)}&limit=5&namespace=0&format=json"
        )
        try:
            res = self._safe_get(api_url)
            if res and res.status_code == 200:
                data = res.json()
                if len(data) >= 4:
                    titles = data[1]
                    descriptions = data[2]
                    disambig = any(
                        "disambiguation" in d.lower() or "(disambiguation)" in t.lower()
                        for t, d in zip(titles, descriptions)
                    )
                    return {
                        "searched_term": brand,
                        "matches_count": len(titles),
                        "titles": titles[:5],
                        "has_disambiguation": disambig,
                        "checked": True
                    }
        except Exception:
            pass
        return {
            "searched_term": brand,
            "matches_count": 0,
            "titles": [],
            "has_disambiguation": False,
            "checked": False
        }

    # -----------------------------------------------------------------
    # Multi-page crawl
    # -----------------------------------------------------------------
    def _crawl_site(self):
        """Crawls up to max_pages within the domain. Respects robots.txt."""
        queue = [self.base_url]
        visited_urls: Set[str] = set()
        delay = self._robots_delay if self._robots_delay is not None else self.crawl_delay
        first_request = True

        while queue and len(self.pages_data) < self.max_pages:
            current_url = queue.pop(0)
            if current_url in visited_urls:
                continue
            visited_urls.add(current_url)

            if not self._may_fetch(current_url):
                continue

            if not first_request and delay > 0:
                time.sleep(delay)
            first_request = False

            page_metrics, internal_links = self._audit_page(current_url)
            self.crawled_urls.add(current_url)
            if page_metrics:
                self.pages_data.append(page_metrics)

            for link in internal_links:
                if link not in visited_urls and link not in queue and len(queue) < 100 and self._may_fetch(link):
                    queue.append(link)

    # -----------------------------------------------------------------
    # Per-page analysis (enhanced with OG, hreflang, AI-summary signals)
    # -----------------------------------------------------------------
    def _audit_page(self, url: str):
        """Fetches and analyzes a single page for machine readability & AI discoverability."""
        try:
            res = self._safe_get(url)
        except Exception:
            return None, []

        if res.status_code != 200:
            return None, []

        content_type = res.headers.get("content-type", "").lower()
        if "text/html" not in content_type:
            return None, []

        soup = BeautifulSoup(res.text, "html.parser")
        new_links: List[str] = []

        # Find internal links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            joined = urllib.parse.urljoin(url, href)
            p = urllib.parse.urlparse(joined)
            if p.netloc.lower() == self.netloc and p.scheme in ["http", "https"]:
                clean_url = urllib.parse.urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
                if not any(clean_url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".pdf", ".zip", ".svg", ".css", ".js"]):
                    new_links.append(clean_url)

        # 1. Structured Data (JSON-LD)
        json_ld_scripts = soup.find_all("script", type=lambda t: t and "ld+json" in t.lower())
        schema_types = []
        has_schema = False
        same_as_links = []

        for script in json_ld_scripts:
            try:
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    t = item.get("@type")
                    if t:
                        has_schema = True
                        if isinstance(t, list):
                            schema_types.extend(t)
                        else:
                            schema_types.append(t)
                    same_as = item.get("sameAs", [])
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    same_as_links.extend(same_as)
            except Exception:
                continue

        # 2. Text & Content Depth
        for invisible in soup(["script", "style", "noscript", "svg"]):
            invisible.extract()
        plain_text = soup.get_text(separator=" ", strip=True)
        raw_html_len = len(res.text)
        text_len = len(plain_text)
        text_ratio = round(text_len / max(raw_html_len, 1), 3)

        # 3. JS-Render / Client Skeleton Check (improved heuristic)
        # Detect SPA shells: very little text but heavy script presence and
        # characteristic root containers or framework attributes.
        is_js_skeleton = False
        spa_markers = [
            'id="root"', 'id="app"', 'id="__next"',
            'data-reactroot', 'ng-app', 'ng-version', 'data-server-rendered'
        ]
        has_spa_marker = any(marker in res.text for marker in spa_markers)
        script_tags = soup.find_all("script", src=True)
        # Criterion: very low text, SPA marker present, or very low text-to-script ratio
        if text_len < 250 and has_spa_marker:
            is_js_skeleton = True
        elif text_len < 150 and len(script_tags) > 3:
            # Even without SPA markers, extremely low text + many scripts = likely SPA
            is_js_skeleton = True

        # 4. Non-Text Locked Content (Images lacking alt)
        images = soup.find_all("img")
        total_imgs = len(images)
        missing_alt = 0
        for img in images:
            alt = img.get("alt")
            if not alt or len(alt.strip()) < 3:
                missing_alt += 1

        # 4b. Canvas / PDF-only content
        canvas_count = len(soup.find_all("canvas"))
        is_canvas_heavy = canvas_count > 0 and text_len < 300
        pdf_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip().lower()
            if href.endswith(".pdf"):
                link_text = a.get_text(strip=True)
                pdf_links.append(link_text or href)
        pdf_only_risk = bool(pdf_links) and text_len < 400

        # 5. Headings & Hierarchy
        h1_count = len(soup.find_all("h1"))
        h2_count = len(soup.find_all("h2"))
        h3_count = len(soup.find_all("h3"))

        # 6. Metadata
        title = soup.title.string.strip() if (soup.title and soup.title.string) else ""
        meta_desc = ""
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if meta_desc_tag:
            meta_desc = meta_desc_tag.get("content", "").strip()

        # 7. Canonical tag
        canonical = ""
        canon_tag = soup.find("link", rel=re.compile(r"^canonical$", re.I))
        if canon_tag:
            canonical = canon_tag.get("href", "").strip()

        # 8. Viewport tag
        viewport = bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}))

        # 9. Freshness: Last-Modified header or copyright year
        last_modified_header = res.headers.get("last-modified", "")
        copyright_years = re.findall(r"(?:©|copyright|\(c\))\s*(?:20\d\d\s*-\s*)?(20\d\d)", plain_text, re.I)
        latest_copyright = int(max(copyright_years)) if copyright_years else None

        # 10. OpenGraph Metadata (Appendix E — Personalization)
        og_title = ""
        og_desc = ""
        og_image = ""
        og_title_tag = soup.find("meta", property="og:title")
        if og_title_tag:
            og_title = og_title_tag.get("content", "").strip()
        og_desc_tag = soup.find("meta", property="og:description")
        if og_desc_tag:
            og_desc = og_desc_tag.get("content", "").strip()
        og_image_tag = soup.find("meta", property="og:image")
        if og_image_tag:
            og_image = og_image_tag.get("content", "").strip()
        has_complete_og = bool(og_title and og_desc and og_image)

        # 11. hreflang locale tags (Appendix E — prior-context personalization)
        hreflang_tags = soup.find_all("link", rel="alternate", hreflang=True)
        has_hreflang = len(hreflang_tags) > 0

        # 12. AI-Summary Content Ratio (Appendix F)
        # Pages with very high image count but low extractable text would be
        # poorly summarized by AI assistants in emails, search, or chat.
        # Ratio: images per 500 chars of text. High ratio = image-heavy content.
        ai_summary_ratio = total_imgs / max(text_len / 500, 1) if text_len > 0 else (total_imgs if total_imgs > 0 else 0)
        is_summary_unfriendly = (ai_summary_ratio > 3.0 and text_len < 1000) or (text_len < 200 and total_imgs > 3)

        record = {
            "url": url,
            "status_code": res.status_code,
            "title": title,
            "meta_description": meta_desc,
            "has_canonical": bool(canonical),
            "canonical_url": canonical,
            "has_viewport": viewport,
            "has_schema": has_schema,
            "schema_types": schema_types,
            "same_as_links": same_as_links,
            "text_length": text_len,
            "raw_html_length": raw_html_len,
            "text_ratio": text_ratio,
            "is_js_skeleton": is_js_skeleton,
            "total_images": total_imgs,
            "missing_alt_images": missing_alt,
            "canvas_count": canvas_count,
            "is_canvas_heavy": is_canvas_heavy,
            "pdf_links": pdf_links,
            "pdf_only_risk": pdf_only_risk,
            "h1_count": h1_count,
            "h2_count": h2_count,
            "h3_count": h3_count,
            "last_modified": last_modified_header,
            "copyright_year": latest_copyright,
            "has_complete_og": has_complete_og,
            "has_hreflang": has_hreflang,
            "is_summary_unfriendly": is_summary_unfriendly,
        }

        return record, new_links

    # -----------------------------------------------------------------
    # Pandas-based analysis → structured findings with code snippets
    # -----------------------------------------------------------------
    def _analyze_with_pandas(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Converts crawled metrics into a Pandas DataFrame and emits findings with concrete fix snippets."""
        if not self.pages_data:
            return {
                "site": self.netloc,
                "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": {"total_findings": 1, "critical": 1, "high": 0, "medium": 0, "low": 0},
                "findings": [{
                    "id": "F-001",
                    "title": "Site Inaccessible or Refused Connection",
                    "severity": "critical",
                    "evidence": f"Failed to crawl any valid HTML pages from {self.base_url}.",
                    "suggested_action": {
                        "summary": "Verify domain DNS records, SSL certificates, and server availability.",
                        "priority": "high"
                    }
                }]
            }

        df = pd.DataFrame(self.pages_data)
        total_pages = len(df)
        findings = []
        finding_idx = 1

        # =====================================================================
        # 1. AI Crawler Blocking (Critical)
        # =====================================================================
        blocked_ai = self.robots_rules.get("blocked_ai_bots", [])
        if blocked_ai:
            bot_list = ", ".join(blocked_ai)
            fix_lines = "\n".join(
                f"User-agent: {bot}\nAllow: /"
                for bot in ["GPTBot", "ChatGPT-User", "ClaudeBot", "PerplexityBot", "Google-Extended"]
            )
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "AI Assistant Crawlers Blocked in robots.txt",
                "severity": "critical",
                "evidence": f"robots.txt disallows access to top AI retrieval crawlers: {bot_list}. This directly prevents ChatGPT, Claude, and Perplexity from indexing or citing brand facts.",
                "suggested_action": {
                    "summary": f"Update robots.txt to explicitly allow AI crawlers on public paths. Add these directives:\n\n{fix_lines}",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 2. Deficient Schema.org JSON-LD (High)
        # =====================================================================
        pages_with_schema = int(df["has_schema"].sum())
        schema_coverage_pct = round((pages_with_schema / total_pages) * 100, 1)
        if schema_coverage_pct < 50.0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Deficient Schema.org JSON-LD Structured Data",
                "severity": "high",
                "evidence": f"Crawled {total_pages} pages; only {pages_with_schema}/{total_pages} ({schema_coverage_pct}%) contain JSON-LD structured data. Key entity types (Organization, Product, WebSite) are missing.",
                "suggested_action": {
                    "summary": (
                        "Inject Schema.org JSON-LD on every page. Minimum homepage example:\n\n"
                        '<script type="application/ld+json">\n'
                        '{\n'
                        '  "@context": "https://schema.org",\n'
                        '  "@type": "Organization",\n'
                        f'  "name": "{self.brand_name}",\n'
                        f'  "url": "{self.base_url}",\n'
                        '  "sameAs": [\n'
                        '    "https://www.wikidata.org/wiki/Q...",\n'
                        '    "https://www.linkedin.com/company/..."\n'
                        '  ]\n'
                        '}\n'
                        '</script>'
                    ),
                    "priority": "high"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 3. Entity Ambiguity & Missing sameAs Links (High)
        # =====================================================================
        all_same_as = [link for sublist in df["same_as_links"] for link in sublist]
        has_authoritative_same_as = any(
            any(auth in link.lower() for auth in AUTHORITATIVE_ENTITY_DOMAINS)
            for link in all_same_as
        )
        if not has_authoritative_same_as:
            evidence_parts = [
                f"Zero pages declare 'sameAs' entity links in JSON-LD pointing to authoritative knowledge graphs "
                f"(Wikidata, Wikipedia, Crunchbase, LinkedIn)."
            ]
            # Augment with disambiguation data
            if entity_data.get("has_disambiguation") or entity_data.get("matches_count", 0) > 1:
                matched = ", ".join(f"'{t}'" for t in entity_data.get("titles", []))
                evidence_parts.append(
                    f"External knowledge graph search for '{entity_data['searched_term']}' returned "
                    f"multiple distinct entities ({matched}), confirming high naming-collision risk."
                )
            else:
                evidence_parts.append(
                    "Without unambiguous entity anchors, LLMs risk hallucinating or conflating the brand with unrelated entities."
                )
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Entity Ambiguity & Missing Cross-Web Knowledge Graph Links",
                "severity": "high",
                "evidence": " ".join(evidence_parts),
                "suggested_action": {
                    "summary": (
                        "Add 'sameAs' URIs to the root Organization schema in homepage JSON-LD:\n\n"
                        '"sameAs": [\n'
                        '  "https://www.wikidata.org/wiki/Q<ENTITY_ID>",\n'
                        '  "https://en.wikipedia.org/wiki/<Brand_Name>",\n'
                        '  "https://www.linkedin.com/company/<slug>",\n'
                        '  "https://www.crunchbase.com/organization/<slug>"\n'
                        ']\n\n'
                        "Also add a Schema.org 'disambiguatingDescription' field to prevent AI entity confusion."
                    ),
                    "priority": "high"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 4. Client-Side Rendering Gaps / SPA Shells (High)
        # =====================================================================
        js_skeletons = df[df["is_js_skeleton"] == True]
        if len(js_skeletons) > 0:
            skeleton_urls = js_skeletons["url"].head(3).tolist()
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Client-Side Rendered Skeleton Pages (Content Ingestion Gap)",
                "severity": "high",
                "evidence": (
                    f"{len(js_skeletons)}/{total_pages} pages return empty HTML shells "
                    f"(< 250 characters of readable text) with SPA framework markers, dependent on "
                    f"client-side JS rendering. Examples: {', '.join(skeleton_urls)}."
                ),
                "suggested_action": {
                    "summary": (
                        "Implement Server-Side Rendering (SSR) or pre-rendering for AI crawler User-Agents. "
                        "For Next.js: use `getServerSideProps()` or `generateStaticParams()`. "
                        "For React SPAs: add a prerender service (e.g., Prerender.io) that returns "
                        "fully-hydrated HTML to bot User-Agents."
                    ),
                    "priority": "high"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 5. Non-Text Media Lock: Images Missing Alt (Medium)
        # =====================================================================
        total_images = int(df["total_images"].sum())
        missing_alt = int(df["missing_alt_images"].sum())
        if total_images > 0 and (missing_alt / total_images) > 0.35:
            missing_pct = round((missing_alt / total_images) * 100, 1)
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Key Information Locked in Non-Text Media (Missing Alt Text)",
                "severity": "medium",
                "evidence": f"Analyzed {total_images} images across crawled pages; {missing_alt} ({missing_pct}%) lack descriptive alt attributes, making visuals unreadable to AI summarizers.",
                "suggested_action": {
                    "summary": (
                        "Add descriptive 'alt' text to every informational image:\n\n"
                        '<img src="product-diagram.png" alt="Architecture diagram showing '
                        'three-tier cloud deployment with load balancer, app servers, and database cluster">'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 5b. Canvas / PDF-Only Content (Medium)
        # =====================================================================
        canvas_heavy_pages = df[df["is_canvas_heavy"] == True]
        pdf_risk_pages = df[df["pdf_only_risk"] == True]
        if len(canvas_heavy_pages) > 0 or len(pdf_risk_pages) > 0:
            examples = []
            if len(canvas_heavy_pages) > 0:
                examples.append(f"{len(canvas_heavy_pages)} page(s) render key content inside <canvas> with under 300 chars of surrounding text")
            if len(pdf_risk_pages) > 0:
                examples.append(f"{len(pdf_risk_pages)} page(s) point to PDF documents as the primary content with under 400 chars of on-page text")
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Facts Locked in Canvas or PDF-Only Content",
                "severity": "medium",
                "evidence": "; ".join(examples) + ". Canvas-rendered graphics and PDF-only documents are frequently skipped or poorly parsed by AI retrieval crawlers.",
                "suggested_action": {
                    "summary": "Mirror key facts from canvas graphics and linked PDFs as plain, readable HTML text on the same page (e.g., a text summary or transcript block), reserving canvas/PDF for visual presentation only.",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 6. AI-Summary & Email-Digest Readiness (Medium) — Appendix F
        # =====================================================================
        summary_unfriendly_pages = df[df["is_summary_unfriendly"] == True]
        if len(summary_unfriendly_pages) > 0:
            example_urls = summary_unfriendly_pages["url"].head(3).tolist()
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Pages Poorly Suited for AI Summarization & Email Digests",
                "severity": "medium",
                "evidence": (
                    f"{len(summary_unfriendly_pages)}/{total_pages} pages have very high image-to-text content "
                    f"ratios (many images, under 1000 chars of extractable text). When AI assistants generate "
                    f"email digests, search summaries, or chat answers citing these pages, the summary will have "
                    f"little readable text to work with — key information effectively disappears. "
                    f"Examples: {', '.join(example_urls[:2])}."
                ),
                "suggested_action": {
                    "summary": (
                        "Ensure every page carries its key facts as plain HTML text, not solely in images or graphics. "
                        "Add descriptive text summaries alongside visual content. For email newsletters, "
                        "always provide a plain-text version and keep the text-to-image ratio above 60:40."
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 7. Missing OpenGraph Metadata for AI Personalization (Medium) — Appendix E
        # =====================================================================
        pages_with_og = int(df["has_complete_og"].sum())
        og_coverage_pct = round((pages_with_og / total_pages) * 100, 1)
        if og_coverage_pct < 50.0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Incomplete OpenGraph Metadata Limits AI Personalization",
                "severity": "medium",
                "evidence": (
                    f"Only {pages_with_og}/{total_pages} ({og_coverage_pct}%) pages have complete OpenGraph tags "
                    f"(og:title + og:description + og:image). AI assistants use these signals to personalize "
                    f"how they present the brand — tailoring titles, descriptions, and preview images to the user's "
                    f"context and prior queries (see Appendix E: Personalization and prior context)."
                ),
                "suggested_action": {
                    "summary": (
                        "Add complete OpenGraph metadata to every public page:\n\n"
                        '<meta property="og:title" content="Your Page Title">\n'
                        '<meta property="og:description" content="Concise 1-2 sentence description">\n'
                        '<meta property="og:image" content="https://example.com/og-image.jpg">\n'
                        '<meta property="og:type" content="website">\n'
                        '<meta property="og:url" content="https://example.com/page">'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 8. Missing llms.txt (Medium — Proactive)
        # =====================================================================
        if not self.llms_txt_found:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing llms.txt Standard for Context Window Ingestion",
                "severity": "medium",
                "evidence": f"Neither /llms.txt nor /.well-known/llms.txt was detected on {self.netloc}. Modern LLM agents seek this standard for concise, high-signal brand context.",
                "suggested_action": {
                    "summary": (
                        "Publish a curated /llms.txt markdown document containing core brand architecture, "
                        "key offerings, and canonical documentation links formatted for LLM context windows. "
                        "See https://llmstxt.org/ for the specification."
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 9. Entity Disambiguation Warning (Medium)
        # =====================================================================
        if entity_data.get("has_disambiguation") or entity_data.get("matches_count", 0) > 2:
            matched = ", ".join(f"'{t}'" for t in entity_data.get("titles", []))
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Brand-Name Collision Detected in External Knowledge Bases",
                "severity": "medium",
                "evidence": (
                    f"Wikipedia search for brand keyword '{entity_data['searched_term']}' returned "
                    f"{entity_data['matches_count']} distinct entities: {matched}. "
                    f"{'A disambiguation page exists, confirming' if entity_data.get('has_disambiguation') else 'Multiple matches suggest'} "
                    f"that LLMs may conflate this brand with unrelated entities sharing the same name."
                ),
                "suggested_action": {
                    "summary": (
                        f"Disambiguate the brand in all schema markup using the exact canonical entity name "
                        f"with industry qualifiers (e.g., '{self.brand_name} (software company)' not just "
                        f"'{self.brand_name}'). Add Schema.org 'disambiguatingDescription' and official "
                        f"Wikidata entity URIs to anchor identity unambiguously."
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 10. Content Staleness (Low)
        # =====================================================================
        current_year = datetime.now().year
        stale_copyright_pages = df[df["copyright_year"].apply(lambda y: y is not None and y < current_year - 1)]
        if len(stale_copyright_pages) > 0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Stale Copyright and Content Freshness Indicators",
                "severity": "low",
                "evidence": f"{len(stale_copyright_pages)}/{total_pages} pages display outdated copyright years (< {current_year - 1}), signalling abandoned content to temporal AI ranking heuristics.",
                "suggested_action": {
                    "summary": (
                        f"Automate copyright year updates in global footer templates (e.g., "
                        f"'© {current_year} {self.brand_name}') and expose HTTP 'Last-Modified' headers "
                        f"and Schema.org 'dateModified' fields on all content pages."
                    ),
                    "priority": "low"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 11. Missing XML Sitemap (Low)
        # =====================================================================
        if not self.sitemap_urls:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "No XML Sitemap Declared in robots.txt or at /sitemap.xml",
                "severity": "low",
                "evidence": "Neither robots.txt nor /sitemap.xml declares an XML sitemap index. AI retrieval crawlers must discover content purely through hyperlink traversal, leaving deep pages unindexed.",
                "suggested_action": {
                    "summary": (
                        f"Publish an XML sitemap and declare it in robots.txt:\n\n"
                        f"Sitemap: {self.base_url}/sitemap.xml\n\n"
                        f"Include all canonical public URLs with <lastmod> dates for freshness signals."
                    ),
                    "priority": "low"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 12. Missing Canonical URL Tags (Low)
        # =====================================================================
        missing_canonical_pages = df[df["has_canonical"] == False]
        if len(missing_canonical_pages) / total_pages > 0.4:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing Canonical URL Tags Across Sampled Pages",
                "severity": "low",
                "evidence": f"{len(missing_canonical_pages)}/{total_pages} sampled pages lack a <link rel='canonical'> tag. Search engines and AI scrapers risk indexing duplicate URL variations.",
                "suggested_action": {
                    "summary": (
                        "Inject self-referential canonical tags into every page <head>:\n\n"
                        '<link rel="canonical" href="https://example.com/your-page">'
                    ),
                    "priority": "low"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 13. Missing hreflang for Locale Targeting (Low) — Appendix E
        # =====================================================================
        pages_with_hreflang = int(df["has_hreflang"].sum())
        if pages_with_hreflang == 0 and total_pages >= 3:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "No hreflang Locale Tags for Geographically Personalized AI Responses",
                "severity": "low",
                "evidence": (
                    "Zero sampled pages declare hreflang alternate-language tags. AI assistants use locale "
                    "signals (including hreflang) to personalize which version of content to surface based "
                    "on the user's location and language preferences (Appendix E)."
                ),
                "suggested_action": {
                    "summary": (
                        "If the site serves content in multiple languages or regions, add hreflang tags:\n\n"
                        '<link rel="alternate" hreflang="en-US" href="https://example.com/en/">\n'
                        '<link rel="alternate" hreflang="fr-FR" href="https://example.com/fr/">\n'
                        '<link rel="alternate" hreflang="x-default" href="https://example.com/">'
                    ),
                    "priority": "low"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 14. Proactive: FAQPage Schema for Conversational AI
        # =====================================================================
        has_faq_schema = any("FAQPage" in types for types in df["schema_types"])
        if not has_faq_schema:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Proactive Opportunity: Add FAQPage Schema for Conversational AI Citations",
                "severity": "medium",
                "evidence": "No pages utilize Schema.org FAQPage structured markup. AI search engines (Perplexity, Google AI Overviews) heavily prioritize direct Question-and-Answer pairs for conversational citations.",
                "suggested_action": {
                    "summary": (
                        "Implement FAQPage JSON-LD on product and pricing pages:\n\n"
                        '<script type="application/ld+json">\n'
                        '{\n'
                        '  "@context": "https://schema.org",\n'
                        '  "@type": "FAQPage",\n'
                        '  "mainEntity": [{\n'
                        '    "@type": "Question",\n'
                        '    "name": "What does YourProduct do?",\n'
                        '    "acceptedAnswer": {\n'
                        '      "@type": "Answer",\n'
                        '      "text": "YourProduct is a ... that helps ... by ..."\n'
                        '    }\n'
                        '  }]\n'
                        '}\n'
                        '</script>'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # Calculate counts
        counts = {
            "total_findings": len(findings),
            "critical": sum(1 for f in findings if f["severity"] == "critical"),
            "high": sum(1 for f in findings if f["severity"] == "high"),
            "medium": sum(1 for f in findings if f["severity"] == "medium"),
            "low": sum(1 for f in findings if f["severity"] == "low")
        }

        return {
            "site": self.netloc,
            "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": counts,
            "findings": findings
        }


def main():
    parser = argparse.ArgumentParser(description="Nexus Coders Unified Discoverability & Corroboration Auditor")
    parser.add_argument("url", help="Target URL or domain to audit (e.g. https://example.com)")
    parser.add_argument("--max-pages", type=int, default=15, help="Maximum pages to crawl (default: 15)")
    parser.add_argument("--timeout", type=int, default=6, help="HTTP timeout in seconds (default: 6)")
    parser.add_argument("--output", "-o", help="Optional path to write JSON output report")
    args = parser.parse_args()

    auditor = DiscoverabilityAuditor(base_url=args.url, max_pages=args.max_pages, timeout=args.timeout)
    report = auditor.run()

    output_json = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Discoverability audit report saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
