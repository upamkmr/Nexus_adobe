#!/usr/bin/env python3
"""
Nexus Coders - On-Site Engagement & Retention Analysis Engine
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Deterministically samples pages on a target site and scores them against the
five on-site retention dimensions in ../references/checklist.md: above-the-fold
value proposition clarity, deep-link orientation, scannability/information
density, CTA clarity, and mobile viewport readiness. Self-contained (does not
require discoverability-audit to have run first) so this skill stays portable.

Read-only: GET requests only, respects robots.txt, polite crawl delay.
"""

import re
import sys
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

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AUDIT_USER_AGENT = "NexusCodersAuditBot/1.0 (+https://github.com/upamkmr/Nexus_adobe; read-only brand audit)"

# Vague CTA phrases that give a visitor no sense of what happens next.
VAGUE_CTA_PHRASES = {"click here", "here", "learn more", "read more", "more", "go", "submit", "link"}
# Long, unbroken prose block threshold (~ >5 lines of continuous text).
LONG_PROSE_CHAR_THRESHOLD = 800


class EngagementAnalyzer:
    """Safe, read-only analyzer for on-site visitor retention signals."""

    def __init__(self, base_url: str, max_pages: int = 10, timeout: int = 6, crawl_delay: float = 0.4):
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
        self._robot_parser: Optional[urllib.robotparser.RobotFileParser] = None
        self._robots_delay: Optional[float] = None

    def _load_robots(self):
        try:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{self.base_url}/robots.txt"
            rp.set_url(robots_url)
            res = self.session.get(robots_url, timeout=self.timeout, verify=False)
            rp.parse(res.text.splitlines() if res.status_code == 200 else [])
            self._robot_parser = rp
            try:
                delay = rp.crawl_delay(AUDIT_USER_AGENT) or rp.crawl_delay("*")
                if delay:
                    self._robots_delay = float(delay)
            except Exception:
                pass
        except Exception:
            self._robot_parser = None

    def _may_fetch(self, url: str) -> bool:
        if self._robot_parser is None:
            return True
        try:
            return self._robot_parser.can_fetch(AUDIT_USER_AGENT, url) and self._robot_parser.can_fetch("*", url)
        except Exception:
            return True

    def run(self) -> Dict[str, Any]:
        self._load_robots()
        self._crawl_site()
        return self._analyze_with_pandas()

    def _crawl_site(self):
        queue = [self.base_url]
        delay = self._robots_delay if self._robots_delay is not None else self.crawl_delay
        first_request = True

        while queue and len(self.crawled_urls) < self.max_pages:
            current_url = queue.pop(0)
            if current_url in self.crawled_urls:
                continue
            if not self._may_fetch(current_url):
                self.crawled_urls.add(current_url)
                continue
            if not first_request and delay > 0:
                time.sleep(delay)
            first_request = False

            page_metrics, internal_links = self._analyze_page(current_url)
            self.crawled_urls.add(current_url)
            if page_metrics:
                self.pages_data.append(page_metrics)

            for link in internal_links:
                if link not in self.crawled_urls and link not in queue and len(queue) < 100 and self._may_fetch(link):
                    queue.append(link)

    def _analyze_page(self, url: str):
        try:
            res = self.session.get(url, timeout=self.timeout, verify=False)
        except Exception:
            return None, []

        content_type = res.headers.get("content-type", "").lower()
        if "text/html" not in content_type:
            return None, []

        soup = BeautifulSoup(res.text, "html.parser")
        new_links: List[str] = []
        for a in soup.find_all("a", href=True):
            joined = urllib.parse.urljoin(url, a["href"].strip())
            p = urllib.parse.urlparse(joined)
            if p.netloc.lower() == self.netloc and p.scheme in ["http", "https"]:
                clean_url = urllib.parse.urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
                if not any(clean_url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".pdf", ".zip", ".svg", ".css", ".js"]):
                    new_links.append(clean_url)

        # --- 1. Above-the-fold value proposition clarity ---
        h1_tags = soup.find_all("h1")
        h1_count = len(h1_tags)
        h1_text = h1_tags[0].get_text(strip=True) if h1_tags else ""
        h1_len = len(h1_text)
        vague_h1 = bool(h1_text) and not re.search(r"[a-zA-Z]{4,}\s+[a-zA-Z]{2,}", h1_text)

        # --- 2. Landing orientation & context retention (deep-link arrival) ---
        has_breadcrumb_nav = soup.find("nav", attrs={"aria-label": re.compile(r"breadcrumb", re.I)}) is not None
        has_breadcrumb_schema = False
        for script in soup.find_all("script", type=lambda t: t and "ld+json" in t.lower()):
            try:
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    t = item.get("@type", "")
                    if isinstance(t, list):
                        if "BreadcrumbList" in t:
                            has_breadcrumb_schema = True
                    elif t == "BreadcrumbList":
                        has_breadcrumb_schema = True
            except Exception:
                continue
        has_breadcrumb = has_breadcrumb_nav or has_breadcrumb_schema
        has_persistent_nav = soup.find("nav") is not None or soup.find("header") is not None
        is_deep_page = urllib.parse.urlparse(url).path not in ("", "/")

        # --- 3. Information density & scannability ---
        h1c, h2c, h3c = len(soup.find_all("h1")), len(soup.find_all("h2")), len(soup.find_all("h3"))
        paragraphs = soup.find_all("p")
        long_prose_blocks = sum(1 for p in paragraphs if len(p.get_text(strip=True)) > LONG_PROSE_CHAR_THRESHOLD)
        list_count = len(soup.find_all(["ul", "ol"]))

        # --- 4. CTA clarity & friction ---
        cta_candidates = soup.find_all("a", class_=re.compile(r"btn|button|cta", re.I)) + soup.find_all("button")
        # Fall back to any anchor with button-like role if no class-based CTAs found
        if not cta_candidates:
            cta_candidates = soup.find_all("a", attrs={"role": "button"})
        total_ctas = len(cta_candidates)
        vague_ctas = 0
        for el in cta_candidates:
            text = el.get_text(strip=True).lower()
            if text in VAGUE_CTA_PHRASES or (text and len(text) <= 4 and text not in {"buy", "join", "shop"}):
                vague_ctas += 1

        # --- 5. Mobile viewport & layout stability ---
        has_viewport = bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}))
        images = soup.find_all("img")
        total_images = len(images)
        images_missing_dims = sum(1 for img in images if not (img.get("width") and img.get("height")))

        record = {
            "url": url,
            "h1_count": h1_count,
            "h1_text": h1_text,
            "h1_len": h1_len,
            "vague_h1": vague_h1,
            "is_deep_page": is_deep_page,
            "has_breadcrumb": has_breadcrumb,
            "has_persistent_nav": has_persistent_nav,
            "h2_count": h2c,
            "h3_count": h3c,
            "long_prose_blocks": long_prose_blocks,
            "list_count": list_count,
            "total_ctas": total_ctas,
            "vague_ctas": vague_ctas,
            "has_viewport": has_viewport,
            "total_images": total_images,
            "images_missing_dims": images_missing_dims,
        }
        return record, new_links

    def _analyze_with_pandas(self) -> Dict[str, Any]:
        if not self.pages_data:
            return {
                "site": self.netloc,
                "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": {"total_findings": 1, "critical": 1, "high": 0, "medium": 0, "low": 0},
                "findings": [{
                    "id": "F-001",
                    "title": "Site Inaccessible for Engagement Analysis",
                    "severity": "critical",
                    "evidence": f"Failed to crawl any valid HTML pages from {self.base_url} (blocked by robots.txt, network error, or non-HTML responses).",
                    "suggested_action": {
                        "summary": "Verify domain availability and confirm robots.txt permits standard crawler access to public marketing pages.",
                        "priority": "high"
                    }
                }]
            }

        df = pd.DataFrame(self.pages_data)
        total_pages = len(df)
        findings = []
        finding_idx = 1

        # 1. Missing / duplicate H1 (value proposition clarity)
        no_h1 = df[df["h1_count"] == 0]
        multi_h1 = df[df["h1_count"] > 1]
        if len(no_h1) > 0 or len(multi_h1) > 0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Unclear Above-the-Fold Value Proposition (Missing or Duplicate H1)",
                "severity": "high",
                "evidence": f"{len(no_h1)}/{total_pages} pages have no <h1> and {len(multi_h1)}/{total_pages} have more than one, so a visitor cannot identify the page's core value proposition within the 5-second test.",
                "suggested_action": {
                    "summary": "Give every page exactly one <h1> stating what the product/service does and who it's for in plain language, under ~60 characters.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # 2. Vague/short H1 headlines
        vague_h1_pages = df[(df["vague_h1"] == True) & (df["h1_count"] > 0)]
        if len(vague_h1_pages) / total_pages > 0.3:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Vague or Jargon-Heavy Headlines",
                "severity": "medium",
                "evidence": f"{len(vague_h1_pages)}/{total_pages} sampled pages have an <h1> that reads as a single vague word/phrase rather than a concrete statement of what the offering is.",
                "suggested_action": {
                    "summary": "Rewrite headlines to state a concrete capability and audience (e.g. 'Cloud Cost Optimization for AWS' instead of generic branding phrases).",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # 3. Deep pages lacking orientation (breadcrumbs / persistent nav)
        deep_pages = df[df["is_deep_page"] == True]
        if len(deep_pages) > 0:
            unoriented = deep_pages[(deep_pages["has_breadcrumb"] == False) & (deep_pages["has_persistent_nav"] == False)]
            if len(unoriented) > 0:
                findings.append({
                    "id": f"F-{finding_idx:03d}",
                    "title": "Deep-Linked Pages Lack Orientation for AI-Referred Visitors",
                    "severity": "high",
                    "evidence": f"{len(unoriented)}/{len(deep_pages)} non-homepage pages sampled have neither a breadcrumb trail nor a persistent nav/header, leaving visitors who click through from an AI citation with no way to identify the brand or navigate to related content.",
                    "suggested_action": {
                        "summary": "Add a persistent site header (logo + primary nav) and semantic breadcrumbs (<nav aria-label='Breadcrumb'> plus Schema.org BreadcrumbList) to every template.",
                        "priority": "high"
                    }
                })
                finding_idx += 1

        # 4. Long unbroken prose blocks (scannability)
        prose_heavy = df[df["long_prose_blocks"] > 0]
        if len(prose_heavy) / total_pages > 0.25:
            total_blocks = int(df["long_prose_blocks"].sum())
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Unbroken Prose Blocks Hurt Scannability",
                "severity": "medium",
                "evidence": f"{len(prose_heavy)}/{total_pages} pages contain at least one paragraph exceeding ~{LONG_PROSE_CHAR_THRESHOLD} characters (roughly 5+ unbroken lines) with no sub-headings or bullets; {total_blocks} such blocks found in total.",
                "suggested_action": {
                    "summary": "Break long paragraphs into scannable bullet lists, short paragraphs (2-3 sentences), and labeled sub-sections; surface key facts in bolded callouts.",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # 5. CTA clarity & friction
        pages_with_ctas = df[df["total_ctas"] > 0]
        if len(pages_with_ctas) > 0:
            total_ctas = int(df["total_ctas"].sum())
            total_vague = int(df["vague_ctas"].sum())
            vague_pct = round((total_vague / total_ctas) * 100, 1) if total_ctas else 0
            if vague_pct > 30:
                findings.append({
                    "id": f"F-{finding_idx:03d}",
                    "title": "Ambiguous Call-to-Action Copy",
                    "severity": "medium",
                    "evidence": f"{total_vague}/{total_ctas} ({vague_pct}%) of detected CTA buttons/links across sampled pages use vague copy (e.g. 'Click Here', 'Learn More') that doesn't tell the visitor what happens next.",
                    "suggested_action": {
                        "summary": "Replace vague CTA copy with specific action verbs describing the outcome (e.g. 'Start Free Trial', 'Read the API Docs', 'Book a Demo').",
                        "priority": "medium"
                    }
                })
                finding_idx += 1
        no_cta_pages = df[df["total_ctas"] == 0]
        if len(no_cta_pages) / total_pages > 0.4:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Pages With No Detectable Call-to-Action",
                "severity": "high",
                "evidence": f"{len(no_cta_pages)}/{total_pages} sampled pages have no identifiable button- or CTA-styled element, risking dead ends for visitors who arrive without a clear next step.",
                "suggested_action": {
                    "summary": "Add at least one clear primary CTA (and a low-commitment secondary option) to every page template, especially deep content and documentation pages.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # 6. Mobile viewport configuration
        missing_viewport = df[df["has_viewport"] == False]
        if len(missing_viewport) > 0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing Mobile Viewport Configuration",
                "severity": "high",
                "evidence": f"{len(missing_viewport)}/{total_pages} pages lack a responsive viewport meta tag, causing distorted layouts and elevated bounce rates for the large share of AI-assistant referrals that arrive on mobile.",
                "suggested_action": {
                    "summary": "Add <meta name='viewport' content='width=device-width, initial-scale=1.0'> to the <head> of every page template.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # 7. Layout shift risk (images missing explicit dimensions)
        total_images = int(df["total_images"].sum())
        missing_dims = int(df["images_missing_dims"].sum())
        if total_images > 0 and (missing_dims / total_images) > 0.5:
            pct = round((missing_dims / total_images) * 100, 1)
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Cumulative Layout Shift Risk (Images Missing Width/Height)",
                "severity": "low",
                "evidence": f"{missing_dims}/{total_images} ({pct}%) images lack explicit width/height attributes, so the browser cannot reserve space before they load, causing the page to jump and disorienting visitors mid-read.",
                "suggested_action": {
                    "summary": "Set explicit width/height (or aspect-ratio CSS) on every <img> and embedded video so layout is stable before assets finish loading.",
                    "priority": "low"
                }
            })
            finding_idx += 1

        # 8. Proactive beyond-defect: instant value / referral personalization
        findings.append({
            "id": f"F-{finding_idx:03d}",
            "title": "Proactive Opportunity: Instant-Value Widget for AI-Referred Visitors",
            "severity": "medium",
            "evidence": "No structural defect required — this is a proactive retention lever. Visitors who click through from an AI assistant's answer have a specific question in mind and a short attention span before bouncing back to the assistant.",
            "suggested_action": {
                "summary": "Add a lightweight interactive element above the fold (ROI/pricing calculator, live search, or an interactive product preview) so referred visitors get value within seconds instead of having to explore the whole site.",
                "priority": "low"
            }
        })
        finding_idx += 1

        counts = {
            "total_findings": len(findings),
            "critical": sum(1 for f in findings if f["severity"] == "critical"),
            "high": sum(1 for f in findings if f["severity"] == "high"),
            "medium": sum(1 for f in findings if f["severity"] == "medium"),
            "low": sum(1 for f in findings if f["severity"] == "low"),
        }

        return {
            "site": self.netloc,
            "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": counts,
            "findings": findings,
        }


def main():
    parser = argparse.ArgumentParser(description="Nexus Coders On-Site Engagement Analyzer")
    parser.add_argument("url", help="Target URL or domain to audit (e.g. https://example.com)")
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum pages to sample (default: 10)")
    parser.add_argument("--timeout", type=int, default=6, help="HTTP timeout in seconds (default: 6)")
    parser.add_argument("--output", "-o", help="Optional path to write JSON output report")
    args = parser.parse_args()

    analyzer = EngagementAnalyzer(base_url=args.url, max_pages=args.max_pages, timeout=args.timeout)
    report = analyzer.run()

    output_json = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Engagement report saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
