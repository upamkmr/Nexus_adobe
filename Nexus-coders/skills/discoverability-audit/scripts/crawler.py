#!/usr/bin/env python3
"""
Nexus Coders - AI Discoverability & Crawl Analysis Engine
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Analyzes website crawlability, AI crawler access (robots.txt), JSON-LD structured data,
JS-render gaps, non-text locked facts, entity corroboration, and freshness signals.
Uses Pandas for vectorized metric aggregation and empirical evidence generation.
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


class BrandAuditCrawler:
    """Safe, read-only crawler and discoverability auditor."""

    def __init__(self, base_url: str, max_pages: int = 15, timeout: int = 6, crawl_delay: float = 0.4):
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme:
            base_url = "https://" + base_url
            parsed = urllib.parse.urlparse(base_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.netloc = parsed.netloc.lower()
        self.max_pages = max(1, min(max_pages, 50))
        self.timeout = timeout
        # Politeness delay between requests to this host (guardrail: no rate-abusing actions).
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
        self.bot_block_report: Dict[str, Any] = {"fully_blocked": [], "partially_blocked": {}}
        # Standard robots.txt compliance for the audit crawler's OWN traffic — this is
        # separate from the AI-bot-disallow *reporting* logic below, which inspects
        # whether GPTBot/ClaudeBot/etc. are blocked (that's a finding about the site,
        # not a constraint on us). This RobotFileParser enforces the guardrail that the
        # marketplace itself must never crawl paths the site disallows.
        self._robot_parser: Optional[urllib.robotparser.RobotFileParser] = None
        self._robots_delay: Optional[float] = None

    def _may_fetch(self, url: str) -> bool:
        """Returns False if robots.txt disallows OUR crawler on this path."""
        if self._robot_parser is None:
            return True
        try:
            return self._robot_parser.can_fetch(AUDIT_USER_AGENT, url) and self._robot_parser.can_fetch("*", url)
        except Exception:
            return True

    def run(self) -> Dict[str, Any]:
        """Executes the full discoverability audit pipeline."""
        self._check_robots_txt()
        self._check_llms_txt()
        self._crawl_site()
        # Bot-block detection needs real crawled URLs to sample against, so it runs
        # after the crawl (it also works fine with zero pages -- falls back to homepage-only).
        self.bot_block_report = self._check_ai_bot_blocks()
        return self._analyze_with_pandas()

    def _safe_get(self, url: str) -> requests.Response:
        """Attempts verified GET first, falling back to verify=False only upon SSLError (sandbox proxy support)."""
        try:
            return self.session.get(url, timeout=self.timeout)
        except requests.exceptions.SSLError:
            return self.session.get(url, timeout=self.timeout, verify=False)

    def _check_robots_txt(self) -> Dict[str, Any]:
        """Fetches robots.txt (raw text kept only for evidence/sitemap extraction).

        NOTE: AI-bot block/allow determination is intentionally NOT done by hand-parsing
        this raw text (a naive line-scanner cannot correctly implement robots.txt's
        user-agent group-selection rules -- e.g. it will bleed Disallow rules across
        groups that aren't separated by a blank line, or miss partial/path-level blocks).
        That determination is done in `_check_ai_bot_blocks()` using the standard-library
        `RobotFileParser` (`self._robot_parser`, set up below), which implements the
        group-selection algorithm correctly and is run once real page URLs are known.
        """
        robots_url = f"{self.base_url}/robots.txt"
        raw_text = ""
        sitemaps = []

        try:
            res = self._safe_get(robots_url)
            if res.status_code == 200:
                raw_text = res.text
                for line in raw_text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        directive, value = line.split(":", 1)
                        if directive.strip().lower() == "sitemap":
                            sitemaps.append(value.strip())
        except Exception:
            pass

        self.robots_rules = {
            "exists": bool(raw_text),
            "sitemaps": sitemaps,
            "raw_snippet": raw_text[:500]
        }
        self.sitemap_urls = sitemaps

        # Load a standard RobotFileParser so OUR OWN crawl obeys the site's rules
        # (guardrail: "Respect robots.txt"), independent of the AI-bot reporting above.
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

    def _check_ai_bot_blocks(self) -> Dict[str, Any]:
        """Determines which AI bots are fully or partially blocked, using the standard
        library's RobotFileParser (self._robot_parser) rather than a hand-rolled scanner.

        RobotFileParser correctly implements robots.txt's group-selection algorithm
        (picking the most specific matching user-agent group, falling back to '*'),
        so this avoids both failure modes of a naive line-by-line scan:
          - false positives from Disallow rules bleeding across unrelated user-agent
            groups that aren't separated by a blank line
          - false negatives from only recognizing a full-site 'Disallow: /' and missing
            common partial blocks like 'Disallow: /blog/' on an AI bot's own group.

        Checked against the homepage plus every URL actually crawled, so "partial"
        findings are backed by this site's real, meaningful paths rather than a guess.
        """
        fully_blocked: List[str] = []
        partially_blocked: Dict[str, str] = {}

        if self._robot_parser is None:
            return {"fully_blocked": fully_blocked, "partially_blocked": partially_blocked}

        sample_urls = [f"{self.base_url}/"] + [p["url"] for p in self.pages_data]
        # Dedupe while preserving order; cap so this stays cheap even on larger crawls.
        seen = set()
        deduped = []
        for u in sample_urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        sample_urls = deduped[:30]

        if not sample_urls:
            return {"fully_blocked": fully_blocked, "partially_blocked": partially_blocked}

        for bot in AI_BOTS:
            blocked_count = 0
            blocked_examples: List[str] = []
            for url in sample_urls:
                try:
                    if not self._robot_parser.can_fetch(bot, url):
                        blocked_count += 1
                        if len(blocked_examples) < 3:
                            blocked_examples.append(urllib.parse.urlparse(url).path or "/")
                except Exception:
                    continue

            if blocked_count == 0:
                continue
            elif blocked_count == len(sample_urls):
                fully_blocked.append(bot)
            else:
                partially_blocked[bot] = (
                    f"{blocked_count}/{len(sample_urls)} sampled paths, e.g. {', '.join(blocked_examples)}"
                )

        return {"fully_blocked": fully_blocked, "partially_blocked": partially_blocked}

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

    def _crawl_site(self):
        """Crawls up to max_pages within the domain to collect evidence.

        Respects robots.txt: any path disallowed to our audit User-Agent (or '*')
        is skipped entirely, never fetched, and never counted against max_pages.
        """
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
                # Disallowed by robots.txt — record as skipped, never fetched, never counted against max_pages.
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

    def _audit_page(self, url: str) -> (Optional[Dict[str, Any]], List[str]):
        """Fetches and analyzes a single page for machine readability signals."""
        try:
            res = self._safe_get(url)
        except Exception as e:
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
                # strip fragments and query params for canonical crawling
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
                    # Extract sameAs corroboration links
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

        # 3. JS-Render / Client Skeleton Check
        # If text is extremely short (< 250 chars) but has script tags, likely a SPA shell
        is_js_skeleton = False
        if text_len < 250 and ("id=\"root\"" in res.text or "id=\"app\"" in res.text or "id=\"__next\"" in res.text):
            is_js_skeleton = True

        # 4. Non-Text Locked Content (Images lacking alt)
        images = soup.find_all("img")
        total_imgs = len(images)
        missing_alt = 0
        for img in images:
            alt = img.get("alt")
            if not alt or len(alt.strip()) < 3:
                missing_alt += 1

        # 4b. Facts Locked in Canvas / PDF-Only Content (non-text render traps)
        canvas_count = len(soup.find_all("canvas"))
        is_canvas_heavy = canvas_count > 0 and text_len < 300
        pdf_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip().lower()
            if href.endswith(".pdf"):
                link_text = a.get_text(strip=True)
                pdf_links.append(link_text or href)
        # A page whose only substantive content pointer is a PDF (very little
        # surrounding readable text) traps facts in a format most AI crawlers
        # either skip or extract poorly.
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

        # Canonical tag
        canonical = ""
        canon_tag = soup.find("link", rel=re.compile(r"^canonical$", re.I))
        if canon_tag:
            canonical = canon_tag.get("href", "").strip()

        # Viewport tag
        viewport = bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}))

        # Freshness: Last-Modified header or copyright year
        last_modified_header = res.headers.get("last-modified", "")
        copyright_years = re.findall(r"(?:©|copyright|\(c\))\s*(?:20\d\d\s*-\s*)?(20\d\d)", plain_text, re.I)
        latest_copyright = int(max(copyright_years)) if copyright_years else None

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
            "copyright_year": latest_copyright
        }

        return record, new_links

    def _analyze_with_pandas(self) -> Dict[str, Any]:
        """Converts crawled metrics into a Pandas DataFrame to compute empirical evidence."""
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

        # -------------------------------------------------------------
        # 1. Robots.txt Disallow Directives for AI Bots (Critical/High)
        # -------------------------------------------------------------
        # Uses RobotFileParser-backed results (self.bot_block_report), not a hand-rolled
        # scan, so groups are scoped correctly and partial (path-level) blocks are caught.
        fully_blocked = self.bot_block_report.get("fully_blocked", [])
        partially_blocked = self.bot_block_report.get("partially_blocked", {})

        if fully_blocked:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "AI Assistant Crawlers Fully Blocked in robots.txt",
                "severity": "critical",
                "evidence": f"robots.txt fully disallows these AI retrieval crawlers on every sampled path: {', '.join(fully_blocked)}. This directly prevents ChatGPT, Claude, and Perplexity from indexing or citing brand facts.",
                "suggested_action": {
                    "summary": f"Update robots.txt to explicitly allow {', '.join(fully_blocked)} on public marketing and documentation paths.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        if partially_blocked:
            detail = "; ".join(f"{bot} blocked on {info}" for bot, info in partially_blocked.items())
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "AI Assistant Crawlers Partially Blocked in robots.txt",
                "severity": "high",
                "evidence": f"robots.txt disallows specific AI crawlers on some but not all sampled paths: {detail}. Even a partial block can hide the exact content (blog, docs, product pages) an AI assistant would otherwise cite.",
                "suggested_action": {
                    "summary": "Review the disallowed paths for each AI crawler and confirm they don't cover pages the brand wants cited (product, pricing, documentation, blog).",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 2. Missing Schema.org Structured Data (High)
        # -------------------------------------------------------------
        pages_with_schema = int(df["has_schema"].sum())
        schema_coverage_pct = round((pages_with_schema / total_pages) * 100, 1)
        if schema_coverage_pct < 50.0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Deficient Schema.org JSON-LD Structured Data",
                "severity": "high",
                "evidence": f"Crawled {total_pages} pages; only {pages_with_schema}/{total_pages} ({schema_coverage_pct}%) contain JSON-LD structured data. Key entities (Organization, Product, WebSite) are missing.",
                "suggested_action": {
                    "summary": "Inject Schema.org JSON-LD markup on every page with Organization, Product, and WebSite schemas to allow LLMs to unambiguously extract core brand facts.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 3. Client-Side Rendering Gaps (JS Skeletons) (High)
        # -------------------------------------------------------------
        js_skeletons = df[df["is_js_skeleton"] == True]
        if len(js_skeletons) > 0:
            skeleton_urls = js_skeletons["url"].head(3).tolist()
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Client-Side Rendered Skeleton Pages (Content Ingestion Gap)",
                "severity": "high",
                "evidence": f"{len(js_skeletons)}/{total_pages} pages return empty HTML shells (< 250 characters of readable text) dependent on client-side JS rendering. Examples: {', '.join(skeleton_urls)}.",
                "suggested_action": {
                    "summary": "Implement Server-Side Rendering (SSR) or dynamic pre-rendering (Static Site Generation / Edge caching) for AI crawler User-Agents.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 4. Facts Locked in Non-Text (Images Missing Alt Text) (Medium)
        # -------------------------------------------------------------
        total_images = int(df["total_images"].sum())
        missing_alt = int(df["missing_alt_images"].sum())
        if total_images > 0 and (missing_alt / total_images) > 0.35:
            missing_pct = round((missing_alt / total_images) * 100, 1)
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Key Information Locked in Non-Text Media (Missing Alt Text)",
                "severity": "medium",
                "evidence": f"Analyzed {total_images} images across crawled pages; {missing_alt} ({missing_pct}%) lack descriptive alt attributes, making product diagrams and brand badges unreadable to AI summarizers.",
                "suggested_action": {
                    "summary": "Audit image assets and provide concise, descriptive 'alt' text that captures facts, metrics, and functional descriptions for screen-readers and AI parsers.",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 4c. Facts Locked in Canvas or PDF-Only Content (Medium)
        # -------------------------------------------------------------
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
                "evidence": "; ".join(examples) + ". Canvas-rendered graphics and PDF-only documents are frequently skipped or poorly parsed by AI retrieval crawlers, unlike plain HTML text.",
                "suggested_action": {
                    "summary": "Mirror the key facts from canvas graphics and linked PDFs as plain, readable HTML text on the same page (e.g. a text summary or transcript block), reserving canvas/PDF for the visual presentation only.",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 5. Entity Ambiguity & Lack of Cross-Web Corroboration (High)
        # -------------------------------------------------------------
        all_same_as = [link for sublist in df["same_as_links"] for link in sublist]
        has_authoritative_same_as = any(
            any(auth in link.lower() for auth in AUTHORITATIVE_ENTITY_DOMAINS)
            for link in all_same_as
        )
        if not has_authoritative_same_as:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Entity Ambiguity & Missing Cross-Web Knowledge Graph Links",
                "severity": "high",
                "evidence": f"Zero pages declare 'sameAs' entity links in JSON-LD pointing to authoritative external knowledge graphs (e.g., Wikidata, Wikipedia, Crunchbase, LinkedIn). This leaves the brand vulnerable to mistaken identity in LLMs.",
                "suggested_action": {
                    "summary": "Add 'sameAs' URIs pointing to official Wikidata, Crunchbase, and LinkedIn profiles in the root Organization schema to establish unambiguous machine identity.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 6. Absence of Emerging AI Ingestion Standard: llms.txt (Proactive / Medium)
        # -------------------------------------------------------------
        if not self.llms_txt_found:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing llms.txt Standard for Context Window Ingestion",
                "severity": "medium",
                "evidence": f"Neither /llms.txt nor /.well-known/llms.txt was detected on {self.netloc}. Modern LLM agents seek this standard for concise, high-signal brand context.",
                "suggested_action": {
                    "summary": "Publish a curated /llms.txt markdown document containing core brand architecture, key offerings, and canonical documentation links formatted for LLM context windows.",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 7. Freshness & Content Staleness Signals (Low)
        # -------------------------------------------------------------
        current_year = datetime.now().year
        stale_copyright_pages = df[df["copyright_year"].apply(lambda y: y is not None and y < current_year - 1)]
        if len(stale_copyright_pages) > 0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Stale Copyright and Content Freshness Indicators",
                "severity": "low",
                "evidence": f"{len(stale_copyright_pages)}/{total_pages} pages display outdated copyright years (< {current_year - 1}), signalling abandoned content to temporal AI ranking heuristics.",
                "suggested_action": {
                    "summary": "Automate copyright year updates in global footer templates and expose HTTP 'Last-Modified' headers or 'dateModified' schema fields.",
                    "priority": "low"
                }
            })
            finding_idx += 1

        # -------------------------------------------------------------
        # 8. Proactive "Beyond-Defect" Recommendation: FAQPage Microdata
        # -------------------------------------------------------------
        has_faq_schema = any("FAQPage" in types for types in df["schema_types"])
        if not has_faq_schema:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Proactive Opportunity: Add FAQPage Schema for Conversational AI",
                "severity": "medium",
                "evidence": "No pages utilize Schema.org FAQPage structured markup. AI search engines (Perplexity, Google AI Overviews) heavily prioritize direct Question-and-Answer pairs.",
                "suggested_action": {
                    "summary": "Implement FAQPage JSON-LD on product and pricing pages, defining common user queries and canonical concise answers to dominate direct conversational citations.",
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
    parser = argparse.ArgumentParser(description="Nexus Coders Brand Audit Crawler")
    parser.add_argument("url", help="Target URL or domain to audit (e.g. https://example.com)")
    parser.add_argument("--max-pages", type=int, default=15, help="Maximum pages to crawl (default: 15)")
    parser.add_argument("--timeout", type=int, default=6, help="HTTP timeout in seconds (default: 6)")
    parser.add_argument("--output", "-o", help="Optional path to write JSON output report")
    args = parser.parse_args()

    crawler = BrandAuditCrawler(base_url=args.url, max_pages=args.max_pages, timeout=args.timeout)
    report = crawler.run()

    output_json = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Audit report saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
