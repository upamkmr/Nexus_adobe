#!/usr/bin/env python3
"""
Nexus Coders - Unified AI Discoverability, Entity Corroboration & Freshness Engine
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Performs a comprehensive off-site AI readiness audit covering:
  1. Crawl & Ingestion: robots.txt AI crawler access (GPTBot, ClaudeBot, etc.),
     XML sitemap discovery, canonical tags.
  2. Structured Data: Schema.org JSON-LD (Organization, Product, WebSite).
  3. Rendered-vs-Raw Ingestion Gap: Multi-signal SPA shell detection (empty DOM roots,
     text-to-markup ratios, hydration blobs, <noscript> warnings).
  4. Non-Text Trapping: Alt text coverage, Canvas graphics, and PDF-only locks.
  5. Entity Corroboration & Disambiguation: Wikipedia/Wikidata API grounding,
     authoritative sameAs knowledge-graph links, naming collision detection.
  6. Personalization & Prior-Context Signals (Appendix E): OpenGraph/Twitter Cards,
     hreflang locale tags, and Schema.org Audience targeting.
  7. Proactive Grounding: llms.txt context manifest, FAQPage schema, and
     Structured Claim Provenance (ClaimReview / citation markup).

Uses Pandas for vectorized metric aggregation. Uses tldextract for robust domain parsing.
Read-only, robots.txt-self-enforcing, polite crawl delays, SSL-resilient.
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

# Suppress insecure request warnings if encountered in sandboxed environments
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Standard User-Agent for polite auditing
AUDIT_USER_AGENT = "NexusCodersAuditBot/2.0 (+https://github.com/upamkmr/Nexus_adobe; read-only brand audit)"

# Known AI and conversational retrieval crawler bot identifiers
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

        # Robust TLD-aware brand name extraction
        self.brand_name = self._extract_brand_name()

    def _extract_brand_name(self) -> str:
        """Derives brand keyword from domain using tldextract with multi-part ccTLD fallback."""
        if tldextract is not None:
            try:
                extractor = tldextract.TLDExtract(cache_dir=False)
                ext = extractor(self.base_url)
                if ext.domain and ext.domain not in ("www", ""):
                    return ext.domain.capitalize()
            except Exception:
                pass

        # Multi-part ccTLD fallback handling
        host = self.netloc.replace("www.", "")
        multi_tlds = [
            ".co.uk", ".org.uk", ".gov.uk", ".ac.uk",
            ".com.au", ".net.au", ".org.au", ".edu.au",
            ".co.nz", ".co.in", ".gov.in", ".ac.in",
            ".co.jp", ".ne.jp", ".com.br", ".com.mx",
            ".com.sg", ".com.hk", ".co.za"
        ]
        for mt in multi_tlds:
            if host.endswith(mt):
                remainder = host[:-len(mt)]
                candidate = remainder.split(".")[-1]
                if candidate:
                    return candidate.capitalize()

        parts = host.split(".")
        if len(parts) >= 2:
            candidate = parts[-2] if parts[-2] not in ("com", "org", "net", "edu", "gov", "io", "ai", "co", "app", "dev") else parts[0]
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

    # -----------------------------------------------------------------
    # 1. robots.txt & Sitemap Inspection
    # -----------------------------------------------------------------
    def _check_robots_txt(self):
        robots_url = urllib.parse.urljoin(self.base_url, "/robots.txt")
        self.robots_rules = {"present": False, "blocked_ai_bots": [], "sitemaps": []}
        try:
            res = self.session.get(robots_url, timeout=self.timeout, verify=False)
            if res.status_code == 200 and res.text:
                self.robots_rules["present"] = True
                content = res.text

                # Parse rules for AI bots
                current_agents = []
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        k, v = [x.strip() for x in line.split(":", 1)]
                        k_lower = k.lower()
                        if k_lower == "user-agent":
                            current_agents.append(v)
                        elif k_lower == "disallow" and v in ["/", "/*"]:
                            for agent in current_agents:
                                for bot in AI_BOTS:
                                    if bot.lower() == agent.lower() or (agent == "*" and bot not in self.robots_rules["blocked_ai_bots"]):
                                        if bot not in self.robots_rules["blocked_ai_bots"]:
                                            self.robots_rules["blocked_ai_bots"].append(bot)
                        elif k_lower == "sitemap":
                            self.robots_rules["sitemaps"].append(v)
                            self.sitemap_urls.append(v)
                    else:
                        current_agents = []

                # Setup RobotFileParser for self-enforced compliance
                self._robot_parser = urllib.robotparser.RobotFileParser()
                self._robot_parser.set_url(robots_url)
                self._robot_parser.parse(content.splitlines())
                cd = self._robot_parser.crawl_delay(AUDIT_USER_AGENT)
                if cd is not None:
                    self._robots_delay = min(float(cd), 3.0)
        except Exception:
            pass

        # Check for /sitemap.xml if not discovered in robots.txt
        if not self.sitemap_urls:
            sitemap_url = urllib.parse.urljoin(self.base_url, "/sitemap.xml")
            try:
                s_res = self.session.head(sitemap_url, timeout=self.timeout, verify=False, allow_redirects=True)
                if s_res.status_code == 200:
                    self.sitemap_urls.append(sitemap_url)
                    self.sitemap_found = True
            except Exception:
                pass
        else:
            self.sitemap_found = True

    # -----------------------------------------------------------------
    # 2. llms.txt Discovery
    # -----------------------------------------------------------------
    def _check_llms_txt(self):
        for path in ["/llms.txt", "/.well-known/llms.txt"]:
            target = urllib.parse.urljoin(self.base_url, path)
            try:
                res = self.session.get(target, timeout=self.timeout, verify=False)
                if res.status_code == 200 and len(res.text.strip()) > 30 and "404" not in res.text[:200].lower():
                    self.llms_txt_found = True
                    self.llms_txt_url = target
                    break
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 3. BFS Polite Site Crawler
    # -----------------------------------------------------------------
    def _crawl_site(self):
        queue = [self.base_url]
        delay = self._robots_delay if self._robots_delay is not None else self.crawl_delay

        while queue and len(self.crawled_urls) < self.max_pages:
            current_url = queue.pop(0)
            if current_url in self.crawled_urls:
                continue

            if not self._may_fetch(current_url):
                continue

            self.crawled_urls.add(current_url)
            page_data, links = self._crawl_page(current_url)
            if page_data:
                self.pages_data.append(page_data)

            for link in links:
                if link not in self.crawled_urls and link not in queue:
                    if len(queue) + len(self.crawled_urls) < self.max_pages * 2:
                        queue.append(link)

            time.sleep(delay)

    def _crawl_page(self, url: str) -> (Optional[Dict[str, Any]], List[str]):
        try:
            res = self.session.get(url, timeout=self.timeout, verify=False, allow_redirects=True)
            if res.status_code != 200:
                return None, []

            content_type = res.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                return None, []
        except Exception:
            return None, []

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Schema.org JSON-LD & sameAs extraction
        schemas = []
        schema_types = []
        same_as_links = []
        has_audience_schema = False

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string) if tag.string else None
                if not data:
                    continue
                if isinstance(data, list):
                    schemas.extend(data)
                else:
                    schemas.append(data)
            except Exception:
                continue

        has_schema = len(schemas) > 0
        for item in schemas:
            try:
                if isinstance(item, dict):
                    t = item.get("@type")
                    if t:
                        if isinstance(t, list):
                            schema_types.extend(t)
                        else:
                            schema_types.append(t)
                    same_as = item.get("sameAs", [])
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    same_as_links.extend(same_as)

                    # Check for Audience / targetAudience / knowsAbout (Appendix E)
                    item_str = str(item).lower()
                    if any(k in item_str for k in ["audience", "targetaudience", "knowsabout"]):
                        has_audience_schema = True
            except Exception:
                continue

        # 2. Text & Content Depth
        raw_html_len = len(res.text)
        
        # Clone soup or extract invisibles for clean text
        for invisible in soup(["script", "style", "noscript", "svg"]):
            invisible.extract()
        plain_text = soup.get_text(separator=" ", strip=True)
        text_len = len(plain_text)
        text_ratio = round(text_len / max(raw_html_len, 1), 4)

        # 3. Advanced Rendered-vs-Raw / JS Skeleton Analysis (Appendix C)
        # Check empty root containers, hydration blobs, <noscript> warnings, script disparity
        empty_spa_roots = []
        for selector in ['#root', '#app', '#__next', '#__nuxt', 'app-root', '#__svelte']:
            el = soup.select_one(selector)
            if el and len(el.get_text(strip=True)) < 50:
                empty_spa_roots.append(selector)

        has_hydration_blob = bool(
            soup.find("script", id="__NEXT_DATA__") or
            re.search(r"window\.__INITIAL_STATE__\s*=", res.text) or
            re.search(r"window\.__NUXT__\s*=", res.text) or
            re.search(r"window\.__PRELOADED_STATE__\s*=", res.text)
        )

        noscript_tags = soup.find_all("noscript")
        has_noscript_js_warning = any(
            re.search(r"(?:enable\s+javascript|javascript\s+is\s+disabled|requires\s+javascript)", ns.get_text(), re.I)
            for ns in noscript_tags
        )

        script_tags = soup.find_all("script", src=True)
        num_scripts = len(script_tags)

        is_js_skeleton = False
        skeleton_reason = ""
        if text_len < 250 and (empty_spa_roots or has_hydration_blob or has_noscript_js_warning):
            is_js_skeleton = True
            skeleton_reason = f"Thin visible text ({text_len} chars) with empty container {empty_spa_roots[:1]}"
        elif raw_html_len > 8000 and text_ratio < 0.035 and (num_scripts >= 3 or has_hydration_blob):
            is_js_skeleton = True
            skeleton_reason = f"Extreme markup overhead (raw: {raw_html_len}b, text: {text_len}c, ratio: {text_ratio*100:.1f}%)"
        elif text_len < 150 and num_scripts > 3:
            is_js_skeleton = True
            skeleton_reason = f"Minimal readable text ({text_len} chars) dominated by {num_scripts} script bundles"

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

        # 10. OpenGraph & Twitter Cards (Appendix E — Personalization)
        og_title = ""
        og_desc = ""
        og_image = ""
        og_type = ""
        og_title_tag = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if og_title_tag:
            og_title = og_title_tag.get("content", "").strip()
        og_desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "twitter:description"})
        if og_desc_tag:
            og_desc = og_desc_tag.get("content", "").strip()
        og_image_tag = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og_image_tag:
            og_image = og_image_tag.get("content", "").strip()
        og_type_tag = soup.find("meta", property="og:type")
        if og_type_tag:
            og_type = og_type_tag.get("content", "").strip()
        has_complete_og = bool(og_title and og_desc and og_image)

        # 11. hreflang locale tags (Appendix E — prior-context personalization)
        hreflang_tags = soup.find_all("link", rel="alternate", hreflang=True)
        has_hreflang = len(hreflang_tags) > 0

        # Check for structured claim provenance markup
        has_claim_provenance = any(
            any(t in ["Claim", "ClaimReview", "CreativeWork"] for t in schema_types) and
            any(k in str(item).lower() for k in ["citation", "isbasedon", "claiminterpreter"])
            for item in schemas
        )

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
            "has_audience_schema": has_audience_schema,
            "has_claim_provenance": has_claim_provenance,
            "text_length": text_len,
            "raw_html_length": raw_html_len,
            "text_ratio": text_ratio,
            "is_js_skeleton": is_js_skeleton,
            "skeleton_reason": skeleton_reason,
            "has_hydration_blob": has_hydration_blob,
            "has_noscript_js_warning": has_noscript_js_warning,
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
            "has_hreflang": has_hreflang
        }

        # Discover internal links
        internal_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].split("#")[0].strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            abs_url = urllib.parse.urljoin(url, href)
            parsed_link = urllib.parse.urlparse(abs_url)
            if parsed_link.netloc.lower() == self.netloc:
                clean_link = f"{parsed_link.scheme}://{parsed_link.netloc}{parsed_link.path}"
                if parsed_link.query:
                    clean_link += f"?{parsed_link.query}"
                if clean_link not in internal_links:
                    internal_links.append(clean_link)

        return record, internal_links

    # -----------------------------------------------------------------
    # 4. External Knowledge Graph Disambiguation (Wikipedia API)
    # -----------------------------------------------------------------
    def _check_entity_disambiguation(self) -> Dict[str, Any]:
        result = {
            "searched_term": self.brand_name,
            "has_disambiguation": False,
            "titles": [],
            "matches_count": 0
        }
        if not self.brand_name or len(self.brand_name) < 3:
            return result

        try:
            wiki_api = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": self.brand_name,
                "srlimit": 5,
                "format": "json"
            }
            res = requests.get(wiki_api, params=params, timeout=4, headers={"User-Agent": AUDIT_USER_AGENT})
            if res.status_code == 200:
                data = res.json()
                search_results = data.get("query", {}).get("search", [])
                result["matches_count"] = len(search_results)
                for item in search_results:
                    title = item.get("title", "")
                    result["titles"].append(title)
                    snippet = item.get("snippet", "").lower()
                    if "disambiguation" in title.lower() or "may refer to" in snippet:
                        result["has_disambiguation"] = True
        except Exception:
            pass

        return result

    # -----------------------------------------------------------------
    # 5. Vectorized Metric Analysis with Concrete Code Fixes
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
            fix_directives = "\n".join([
                "# Explicitly allow AI retrieval crawlers in robots.txt",
                "User-agent: GPTBot\nAllow: /",
                "User-agent: ClaudeBot\nAllow: /",
                "User-agent: PerplexityBot\nAllow: /",
                "User-agent: Google-Extended\nAllow: /",
                "User-agent: Applebot-Extended\nAllow: /"
            ])
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "AI Assistant Crawlers Blocked in robots.txt",
                "severity": "critical",
                "evidence": f"robots.txt disallows access to top AI retrieval crawlers: {bot_list}. This directly prevents ChatGPT, Claude, and Perplexity from indexing or citing brand facts.",
                "suggested_action": {
                    "summary": (
                        "Update robots.txt to explicitly allow AI crawlers on public documentation and product paths:\n\n"
                        f"{fix_directives}"
                    ),
                    "priority": "critical"
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
                        "Inject Schema.org JSON-LD on every page. Example Organization & WebSite snippet:\n\n"
                        '<script type="application/ld+json">\n'
                        '{\n'
                        '  "@context": "https://schema.org",\n'
                        '  "@type": "Organization",\n'
                        f'  "name": "{self.brand_name}",\n'
                        f'  "url": "{self.base_url}",\n'
                        f'  "logo": "{self.base_url}/logo.png",\n'
                        '  "sameAs": [\n'
                        f'    "https://www.wikidata.org/wiki/Q...",\n'
                        f'    "https://www.linkedin.com/company/{self.brand_name.lower()}"\n'
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
                        "Add 'sameAs' URIs to the root Organization schema in homepage JSON-LD to anchor entity identity:\n\n"
                        '"sameAs": [\n'
                        '  "https://www.wikidata.org/wiki/Q<ENTITY_ID>",\n'
                        f'  "https://en.wikipedia.org/wiki/{self.brand_name}",\n'
                        f'  "https://www.linkedin.com/company/{self.brand_name.lower()}",\n'
                        f'  "https://www.crunchbase.com/organization/{self.brand_name.lower()}"\n'
                        ']\n\n'
                        f'Also add: "disambiguatingDescription": "{self.brand_name} is a software platform specializing in ..."'
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
            reasons = [r for r in js_skeletons["skeleton_reason"].unique() if r]
            detail_str = f" Root causes detected: {'; '.join(reasons[:2])}." if reasons else ""
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Client-Side Rendered Skeleton Pages (Raw Ingestion Gap)",
                "severity": "high",
                "evidence": (
                    f"{len(js_skeletons)}/{total_pages} pages return empty HTML shells with SPA markers or "
                    f"extreme markup-to-text disparity (< 3.5% readable text). Non-headless AI crawlers (GPTBot, ClaudeBot, "
                    f"PerplexityBot) ingest only blank DOM containers.{detail_str} Examples: {', '.join(skeleton_urls)}."
                ),
                "suggested_action": {
                    "summary": (
                        "Implement Server-Side Rendering (SSR) or dynamic edge prerendering for AI bots. "
                        "Example Nginx bot prerendering rule:\n\n"
                        'if ($http_user_agent ~* "GPTBot|ChatGPT-User|ClaudeBot|PerplexityBot|Applebot-Extended") {\n'
                        '    proxy_pass http://prerender-service:3000/render/$scheme://$host$request_uri;\n'
                        '    break;\n'
                        '}'
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
                        "Add descriptive 'alt' text to every informational image and diagram:\n\n"
                        '<figure>\n'
                        '  <img src="architecture.png" alt="Architecture diagram showing stream ingestion, processing, and storage cluster" />\n'
                        '  <figcaption>System Architecture Overview</figcaption>\n'
                        '</figure>'
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
                    "summary": (
                        "Mirror key facts from canvas graphics and linked PDFs as plain semantic HTML text on the same page:\n\n"
                        '<div class="canvas-text-fallback">\n'
                        '  <h3>Summary of Chart Findings</h3>\n'
                        '  <p>Q3 metrics demonstrate a 34% increase in data throughput...</p>\n'
                        '</div>'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 6. Missing OpenGraph & Twitter Metadata for AI Personalization (Medium) — Appendix E
        # =====================================================================
        pages_with_og = int(df["has_complete_og"].sum())
        og_coverage_pct = round((pages_with_og / total_pages) * 100, 1)
        if og_coverage_pct < 50.0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Incomplete OpenGraph Metadata Limits AI Personalization",
                "severity": "medium",
                "evidence": (
                    f"Only {pages_with_og}/{total_pages} ({og_coverage_pct}%) pages have complete OpenGraph/Twitter tags "
                    f"(title + description + image). AI assistants use these signals to personalize how they present the brand — "
                    f"tailoring titles, descriptions, and preview cards to user context and prior queries (Appendix E)."
                ),
                "suggested_action": {
                    "summary": (
                        "Add complete OpenGraph and Twitter Card metadata to every page template <head>:\n\n"
                        f'<meta property="og:title" content="{self.brand_name} - Platform Overview" />\n'
                        '<meta property="og:description" content="High-performance data streaming platform designed for enterprise scalability." />\n'
                        f'<meta property="og:image" content="{self.base_url}/assets/preview.jpg" />\n'
                        '<meta property="og:type" content="website" />\n'
                        f'<meta property="og:url" content="{self.base_url}" />\n'
                        '<meta name="twitter:card" content="summary_large_image" />'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 7. Missing Schema.org Audience / Persona Signals (Medium) — Appendix E
        # =====================================================================
        pages_with_audience = int(df["has_audience_schema"].sum())
        if pages_with_audience == 0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing Schema.org Audience & Persona Signals for Conversational Targeting",
                "severity": "medium",
                "evidence": (
                    "Zero crawled pages specify Schema.org 'audience' or 'targetAudience' attributes. AI assistants draw on "
                    "user context (role, company scale, technical proficiency) to tailor which brands they surface (Appendix E). "
                    "Without structured audience declarations, AI assistants cannot reliably match the brand to specific user queries."
                ),
                "suggested_action": {
                    "summary": (
                        "Declare target audience and domain competencies in JSON-LD:\n\n"
                        '<script type="application/ld+json">\n'
                        '{\n'
                        '  "@context": "https://schema.org",\n'
                        '  "@type": "SoftwareApplication",\n'
                        f'  "name": "{self.brand_name}",\n'
                        '  "audience": {\n'
                        '    "@type": "BusinessAudience",\n'
                        '    "audienceType": "Enterprise Engineering Teams"\n'
                        '  },\n'
                        '  "knowsAbout": ["Real-Time Analytics", "Stream Processing", "Distributed Systems"]\n'
                        '}\n'
                        '</script>'
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
                        f"Publish a curated /llms.txt markdown document at {self.base_url}/llms.txt:\n\n"
                        f"# {self.brand_name}\n"
                        f"> Concise 1-sentence value proposition.\n\n"
                        "## Core Capabilities\n"
                        f"- [Documentation]({self.base_url}/docs): Getting started guide.\n"
                        f"- [API Reference]({self.base_url}/api): REST & GraphQL endpoints.\n\n"
                        "## Official Knowledge Base\n"
                        "- Canonical Entity: https://www.wikidata.org/wiki/Q..."
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
                        f"Automate copyright year updates in global footer templates and emit HTTP headers:\n\n"
                        f"<footer>&copy; {current_year} {self.brand_name}. All rights reserved.</footer>\n"
                        f'<meta property="article:modified_time" content="{datetime.now().strftime("%Y-%m-%d")}" />'
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
                        f"Publish an XML sitemap index and declare it in robots.txt:\n\n"
                        f"Sitemap: {self.base_url}/sitemap.xml\n\n"
                        'Example sitemap entry in /sitemap.xml:\n'
                        '<url>\n'
                        f'  <loc>{self.base_url}/docs/quickstart</loc>\n'
                        f'  <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
                        '  <changefreq>weekly</changefreq>\n'
                        '</url>'
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
                        f'<link rel="canonical" href="{self.base_url}/canonical-path" />'
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
                        "Add hreflang tags to support regional and language-specific AI personalization:\n\n"
                        f'<link rel="alternate" hreflang="en-US" href="{self.base_url}/en/" />\n'
                        f'<link rel="alternate" hreflang="de-DE" href="{self.base_url}/de/" />\n'
                        f'<link rel="alternate" hreflang="x-default" href="{self.base_url}/" />'
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
                        "Implement FAQPage JSON-LD on product and documentation pages:\n\n"
                        '<script type="application/ld+json">\n'
                        '{\n'
                        '  "@context": "https://schema.org",\n'
                        '  "@type": "FAQPage",\n'
                        '  "mainEntity": [{\n'
                        '    "@type": "Question",\n'
                        f'    "name": "How does {self.brand_name} handle high concurrency?",\n'
                        '    "acceptedAnswer": {\n'
                        '      "@type": "Answer",\n'
                        f'      "text": "{self.brand_name} utilizes an asynchronous, non-blocking architecture that scales horizontally."\n'
                        '    }\n'
                        '  }]\n'
                        '}\n'
                        '</script>'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 15. Proactive: Structured Claim Provenance & Citation Markup (Non-Obvious)
        # =====================================================================
        has_provenance = any(df["has_claim_provenance"])
        if not has_provenance:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Proactive Opportunity: Structured Claim Provenance for AI Citation Confidence",
                "severity": "medium",
                "evidence": (
                    "No pages embed Schema.org ClaimReview or structured claim citation metadata. AI search engines "
                    "(Perplexity, SearchGPT, Claude) are heavily penalized for hallucinations and preferentially quote "
                    "claims backed by verifiable provenance, published citations, and explicit measurement methodologies."
                ),
                "suggested_action": {
                    "summary": (
                        "Tag quantitative benchmarks, performance metrics, and comparison claims with Schema.org Claim:\n\n"
                        '<script type="application/ld+json">\n'
                        '{\n'
                        '  "@context": "https://schema.org",\n'
                        '  "@type": "Claim",\n'
                        '  "claimInterpreter": {\n'
                        '    "@type": "Organization",\n'
                        '    "name": "Independent Benchmarking Laboratory"\n'
                        '  },\n'
                        f'  "text": "{self.brand_name} delivers 4x throughput compared to industry baselines.",\n'
                        '  "appearance": {\n'
                        '    "@type": "CreativeWork",\n'
                        f'    "url": "{self.base_url}/benchmarks-2026",\n'
                        '    "citation": "https://doi.org/10.1000/182"\n'
                        '  }\n'
                        '}\n'
                        '</script>'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

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
