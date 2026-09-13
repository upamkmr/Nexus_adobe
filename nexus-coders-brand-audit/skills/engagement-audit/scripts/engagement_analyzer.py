#!/usr/bin/env python3
"""
Nexus Coders - On-Site Visitor Engagement & Retention Analyzer
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Evaluates on-site visitor retention, reading experience, and content readiness:
  1. Above-The-Fold Value Proposition (H1 clarity, "5-second test", vague headlines)
  2. Deep-Link Navigation & Orientation (Breadcrumbs, persistent header nav for AI referrals)
  3. Reading Scannability & Information Density (Heading progression, wall-of-text paragraphs)
  4. Call-to-Action (CTA) Friction (Vague copy, dead-end pages lacking conversion pathways)
  5. Mobile Viewport & Cumulative Layout Shift (Responsive viewport, explicit image dimensions)
  6. Email-Digest & AI-Summary Content Readiness (Appendix F: text-vs-image ratio,
     preheader optimization, opening boilerplate displacement detection)
  7. Above-The-Fold Personalization Density (Appendix E: substantive first-visible text)
  8. Proactive Instant-Value Retention Widget (Context retention for AI-referred visitors)

Uses Pandas for vectorized metric aggregation.
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

# Suppress insecure request warnings in sandboxed environments
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AUDIT_USER_AGENT = "NexusCodersAuditBot/2.0 (+https://github.com/upamkmr/Nexus_adobe; read-only brand audit)"

VAGUE_H1_PATTERNS = [
    r"^welcome\b",
    r"^home\b",
    r"^empower(?:ing)?\b",
    r"^transform(?:ing)?\b",
    r"^the future of\b",
    r"^innovat(?:e|ion)\b",
    r"^unleash\b",
    r"^next-?gen(?:eration)?\b",
    r"^re-?defin(?:e|ing)\b",
    r"^build better\b",
    r"^hello\b",
]

VAGUE_CTA_PHRASES = {
    "click here", "learn more", "more", "read more", "see more", "explore",
    "continue", "go", "submit", "get started", "view more", "discover"
}

BOILERPLATE_FILLER_PATTERNS = [
    r"view\s+in\s+browser",
    r"having\s+trouble\s+viewing",
    r"click\s+here\s+to\s+unsubscribe",
    r"forward\s+to\s+a\s+friend",
    r"skip\s+to\s+(?:main\s+)?content",
    r"cookie\s+preferences",
    r"privacy\s+policy\s+\|\s+terms"
]

LONG_PROSE_CHAR_THRESHOLD = 450


class EngagementAnalyzer:
    """Safe, read-only analyzer for on-site visitor retention, reading experience, and email readiness."""

    def __init__(self, base_url: str, max_pages: int = 10, timeout: int = 6, crawl_delay: float = 0.4):
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme:
            base_url = "https://" + base_url
            parsed = urllib.parse.urlparse(base_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.netloc = parsed.netloc.lower()
        self.max_pages = max(1, min(max_pages, 30))
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

    def _init_robots(self):
        robots_url = urllib.parse.urljoin(self.base_url, "/robots.txt")
        try:
            res = self.session.get(robots_url, timeout=self.timeout, verify=False)
            if res.status_code == 200 and res.text:
                self._robot_parser = urllib.robotparser.RobotFileParser()
                self._robot_parser.set_url(robots_url)
                self._robot_parser.parse(res.text.splitlines())
                cd = self._robot_parser.crawl_delay(AUDIT_USER_AGENT)
                if cd is not None:
                    self._robots_delay = min(float(cd), 3.0)
        except Exception:
            pass

    def _may_fetch(self, url: str) -> bool:
        if self._robot_parser is None:
            return True
        try:
            return self._robot_parser.can_fetch(AUDIT_USER_AGENT, url) and self._robot_parser.can_fetch("*", url)
        except Exception:
            return True

    def run(self) -> Dict[str, Any]:
        """Executes the polite engagement analysis crawl and generates findings."""
        self._init_robots()
        self._crawl_site()
        return self._analyze_with_pandas()

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
            page_data, links = self._analyze_page(current_url)
            if page_data:
                self.pages_data.append(page_data)

            for link in links:
                if link not in self.crawled_urls and link not in queue:
                    if len(queue) + len(self.crawled_urls) < self.max_pages * 2:
                        queue.append(link)

            time.sleep(delay)

    def _analyze_page(self, url: str) -> (Optional[Dict[str, Any]], List[str]):
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

        # Discover internal links for crawling
        new_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].split("#")[0].strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            abs_url = urllib.parse.urljoin(url, href)
            p = urllib.parse.urlparse(abs_url)
            if p.netloc.lower() == self.netloc:
                clean = f"{p.scheme}://{p.netloc}{p.path}"
                if clean not in new_links:
                    new_links.append(clean)

        # --- 1. Above-The-Fold H1 value proposition ---
        h1_tags = soup.find_all("h1")
        h1_count = len(h1_tags)
        h1_text = h1_tags[0].get_text(separator=" ", strip=True) if h1_tags else ""
        h1_len = len(h1_text)
        vague_h1 = False
        if h1_text:
            for pat in VAGUE_H1_PATTERNS:
                if re.search(pat, h1_text, re.I):
                    vague_h1 = True
                    break

        # --- 2. Deep-link orientation & breadcrumbs ---
        path = urllib.parse.urlparse(url).path.strip("/")
        depth = len(path.split("/")) if path else 0
        is_deep_page = depth >= 2

        has_breadcrumb = bool(
            soup.find("nav", attrs={"aria-label": re.compile(r"breadcrumb", re.I)}) or
            soup.find("ol", class_=re.compile(r"breadcrumb", re.I)) or
            soup.find("ul", class_=re.compile(r"breadcrumb", re.I)) or
            soup.find(attrs={"itemtype": re.compile(r"BreadcrumbList", re.I)})
        )
        has_persistent_nav = bool(
            soup.find("header") or
            soup.find("nav", attrs={"role": "navigation"}) or
            soup.find(class_=re.compile(r"navbar|header|nav-bar", re.I))
        )

        # --- 3. Information density & scannability ---
        h1c, h2c, h3c = len(soup.find_all("h1")), len(soup.find_all("h2")), len(soup.find_all("h3"))
        paragraphs = soup.find_all("p")
        long_prose_blocks = sum(1 for p in paragraphs if len(p.get_text(strip=True)) > LONG_PROSE_CHAR_THRESHOLD)
        list_count = len(soup.find_all(["ul", "ol"]))

        # --- 4. CTA clarity & friction ---
        cta_candidates = soup.find_all("a", class_=re.compile(r"btn|button|cta", re.I)) + soup.find_all("button")
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

        # --- 6. AI-Summary & Email-Digest Content Readiness (Appendix F) ---
        # Strip invisible elements for text extraction
        for invisible in soup(["script", "style", "noscript", "svg"]):
            invisible.extract()
        plain_text = soup.get_text(separator=" ", strip=True)
        text_length = len(plain_text)

        # Opening 250 characters: check for boilerplate filler displacement
        opening_text = plain_text[:250].strip().lower()
        has_opening_boilerplate = any(re.search(pat, opening_text) for pat in BOILERPLATE_FILLER_PATTERNS)

        # Check for email preheader
        has_email_preheader = bool(
            soup.find(class_=re.compile(r"preheader", re.I)) or
            soup.find(id=re.compile(r"preheader", re.I)) or
            soup.find("div", style=re.compile(r"display\s*:\s*none.*max-height\s*:\s*0", re.I))
        )

        # Heading-to-text progression
        total_headings = h1c + h2c + h3c
        has_good_heading_structure = total_headings >= 2 and h2c >= 1

        # Above-the-fold content density (first 500 chars) — Appendix E
        above_fold_text = plain_text[:500].strip()
        has_substantive_above_fold = len(above_fold_text) > 100 and bool(re.search(r"[a-zA-Z]{4,}\s+[a-zA-Z]{3,}\s+[a-zA-Z]{2,}", above_fold_text))

        # Email-digest readiness: high image count with low text or high boilerplate
        is_email_summary_poor = (
            (text_length < 300 and total_images > 2) or
            (text_length > 0 and total_images / max(text_length / 200, 1) > 5) or
            (has_opening_boilerplate and text_length < 800)
        )

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
            "text_length": text_length,
            "has_opening_boilerplate": has_opening_boilerplate,
            "has_email_preheader": has_email_preheader,
            "has_good_heading_structure": has_good_heading_structure,
            "has_substantive_above_fold": has_substantive_above_fold,
            "is_email_summary_poor": is_email_summary_poor,
        }
        return record, new_links

    def _analyze_with_pandas(self) -> Dict[str, Any]:
        """Converts engagement telemetry into a Pandas DataFrame and emits prioritized findings with code snippets."""
        if not self.pages_data:
            return {
                "site": self.netloc,
                "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary": {"total_findings": 1, "critical": 1, "high": 0, "medium": 0, "low": 0},
                "findings": [{
                    "id": "F-001",
                    "title": "Site Unreachable for Engagement Audit",
                    "severity": "critical",
                    "evidence": f"Could not sample HTML pages from {self.base_url} within timeout limit.",
                    "suggested_action": {
                        "summary": "Check server availability and ensure network requests are permitted.",
                        "priority": "high"
                    }
                }]
            }

        df = pd.DataFrame(self.pages_data)
        total_pages = len(df)
        findings = []
        finding_idx = 1

        # =====================================================================
        # 1. Above-The-Fold Value Proposition (H1 Clarity)
        # =====================================================================
        no_h1 = df[df["h1_count"] == 0]
        multi_h1 = df[df["h1_count"] > 1]
        vague_h1 = df[df["vague_h1"] == True]

        if len(no_h1) > 0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing Primary Heading (H1) on Key Landing Pages",
                "severity": "high",
                "evidence": f"{len(no_h1)}/{total_pages} sampled pages have no <h1> heading. Visitors referred by AI assistants arrive without an immediate anchor explaining what page they landed on.",
                "suggested_action": {
                    "summary": (
                        "Add exactly one clear, benefit-driven <h1> heading above the fold on every page template:\n\n"
                        '<h1>Nexus Stream: Real-Time Event Broker with Sub-Millisecond Latency</h1>'
                    ),
                    "priority": "high"
                }
            })
            finding_idx += 1

        if len(vague_h1) > 0:
            examples = [f"'{row['h1_text'][:50]}'" for _, row in vague_h1.head(2).iterrows()]
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Vague or Buzzword-Heavy Primary Headline (Fails 5-Second Test)",
                "severity": "medium",
                "evidence": (
                    f"{len(vague_h1)}/{total_pages} pages use generic or buzzword-heavy <h1> copy "
                    f"(e.g. {', '.join(examples)}) that fails to state what the product does within 5 seconds."
                ),
                "suggested_action": {
                    "summary": (
                        "Rewrite the <h1> using the concrete clarity formula: [Product] helps [Audience] achieve [Benefit] without [Pain]:\n\n"
                        "❌ 'Transforming the Future of Data'\n"
                        "✅ 'Real-Time Vector Search for Kubernetes Workloads'"
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        if len(multi_h1) / total_pages > 0.3:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Multiple Competing H1 Headings Dilute Topic Focus",
                "severity": "low",
                "evidence": f"{len(multi_h1)}/{total_pages} pages have more than one <h1>, confusing both reading hierarchy and AI citation parsers.",
                "suggested_action": {
                    "summary": "Enforce a strict single-H1 rule per page; demote secondary section titles to <h2>.",
                    "priority": "low"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 2. Deep-Link Navigation & Orientation
        # =====================================================================
        deep_pages = df[df["is_deep_page"] == True]
        if len(deep_pages) > 0:
            missing_crumbs = deep_pages[deep_pages["has_breadcrumb"] == False]
            if len(missing_crumbs) / len(deep_pages) > 0.5:
                findings.append({
                    "id": f"F-{finding_idx:03d}",
                    "title": "Missing Breadcrumbs on Deep-Link Landing Pages",
                    "severity": "high",
                    "evidence": (
                        f"{len(missing_crumbs)}/{len(deep_pages)} deep sub-pages lack breadcrumb navigation. "
                        f"When an AI assistant cites a specific technical doc or article, referred visitors land deep "
                        f"without context of where they are in the site hierarchy, increasing bounce rates."
                    ),
                    "suggested_action": {
                        "summary": (
                            "Implement semantic breadcrumb navigation with Schema.org markup on all deep pages:\n\n"
                            '<nav aria-label="Breadcrumb">\n'
                            '  <ol class="breadcrumb">\n'
                            '    <li><a href="/">Home</a></li>\n'
                            '    <li><a href="/docs">Documentation</a></li>\n'
                            '    <li aria-current="page">API Reference</li>\n'
                            '  </ol>\n'
                            '</nav>'
                        ),
                        "priority": "high"
                    }
                })
                finding_idx += 1

        # =====================================================================
        # 3. Reading Scannability & Information Density
        # =====================================================================
        prose_heavy = df[df["long_prose_blocks"] > 0]
        if len(prose_heavy) / total_pages > 0.3:
            total_blocks = int(df["long_prose_blocks"].sum())
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Unbroken Prose Blocks Hurt Scannability",
                "severity": "medium",
                "evidence": f"{len(prose_heavy)}/{total_pages} pages contain paragraphs exceeding ~{LONG_PROSE_CHAR_THRESHOLD} characters with no sub-headings or bullets ({total_blocks} such blocks detected).",
                "suggested_action": {
                    "summary": (
                        "Break dense paragraphs into scannable subsections with bolded takeaways and bullet lists:\n\n"
                        '<h3>Key Capabilities</h3>\n'
                        '<ul>\n'
                        '  <li><strong>Sub-millisecond latency:</strong> Process events under 1ms.</li>\n'
                        '  <li><strong>Zero-copy architecture:</strong> Reduce memory overhead by 60%.</li>\n'
                        '</ul>'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 4. CTA Clarity & Conversion Friction
        # =====================================================================
        pages_with_ctas = df[df["total_ctas"] > 0]
        if len(pages_with_ctas) > 0:
            total_ctas = int(df["total_ctas"].sum())
            total_vague = int(df["vague_ctas"].sum())
            vague_pct = round((total_vague / total_ctas) * 100, 1) if total_ctas else 0
            if vague_pct > 30:
                findings.append({
                    "id": f"F-{finding_idx:03d}",
                    "title": "Ambiguous Call-to-Action Copy Increases Friction",
                    "severity": "medium",
                    "evidence": f"{total_vague}/{total_ctas} ({vague_pct}%) of detected CTAs use ambiguous copy (e.g. 'Click Here', 'Learn More') that does not communicate the destination value.",
                    "suggested_action": {
                        "summary": (
                            "Replace ambiguous CTA text with explicit, action-oriented button copy:\n\n"
                            '<a href="/signup" class="btn-primary">Start 14-Day Free Trial (No Credit Card)</a>\n'
                            '<a href="/docs/quickstart" class="btn-secondary">Explore 5-Minute Quickstart</a>'
                        ),
                        "priority": "medium"
                    }
                })
                finding_idx += 1

        no_cta_pages = df[df["total_ctas"] == 0]
        if len(no_cta_pages) / total_pages > 0.4:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Dead-End Pages Lacking Next-Step Conversion Pathways",
                "severity": "high",
                "evidence": f"{len(no_cta_pages)}/{total_pages} sampled pages have no button or action link, stranding visitors who arrive from AI citations without a recommended next step.",
                "suggested_action": {
                    "summary": (
                        "Add a persistent next-steps block to every content and documentation template:\n\n"
                        '<div class="next-steps-banner">\n'
                        '  <h3>Ready to implement?</h3>\n'
                        '  <a href="/deploy" class="btn-cta">Deploy in 5 Minutes</a>\n'
                        '  <a href="/community" class="link-secondary">Join Developer Slack</a>\n'
                        '</div>'
                    ),
                    "priority": "high"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 5. Mobile Viewport Configuration
        # =====================================================================
        missing_viewport = df[df["has_viewport"] == False]
        if len(missing_viewport) > 0:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing Mobile Viewport Configuration",
                "severity": "high",
                "evidence": f"{len(missing_viewport)}/{total_pages} pages lack a responsive viewport meta tag, causing unreadable desktop-scaled layouts on mobile AI referrals.",
                "suggested_action": {
                    "summary": (
                        "Add the responsive viewport meta tag to every page template <head>:\n\n"
                        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
                    ),
                    "priority": "high"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 6. Cumulative Layout Shift Risk (Images Missing Dimensions)
        # =====================================================================
        total_images = int(df["total_images"].sum())
        missing_dims = int(df["images_missing_dims"].sum())
        if total_images > 0 and (missing_dims / total_images) > 0.5:
            pct = round((missing_dims / total_images) * 100, 1)
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Cumulative Layout Shift Risk (Images Missing Width/Height)",
                "severity": "low",
                "evidence": f"{missing_dims}/{total_images} ({pct}%) images lack explicit width/height attributes, causing sudden content jumps during asynchronous load.",
                "suggested_action": {
                    "summary": (
                        "Include explicit width and height attributes on all image elements to reserve layout space:\n\n"
                        '<img src="hero-graphic.png" width="800" height="450" alt="Platform Overview" loading="lazy" />'
                    ),
                    "priority": "low"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 7. AI Email-Digest & Inbox Summarization Readiness (Appendix F)
        # =====================================================================
        email_poor_pages = df[df["is_email_summary_poor"] == True]
        if len(email_poor_pages) > 0:
            example_urls = email_poor_pages["url"].head(2).tolist()
            boilerplate_count = int(df["has_opening_boilerplate"].sum())
            extra_context = f" {boilerplate_count} page(s) begin with low-value boilerplate filler that displaces core messaging in AI summaries." if boilerplate_count else ""
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Content Structure Vulnerable to AI Email Summarization Drops",
                "severity": "medium",
                "evidence": (
                    f"{len(email_poor_pages)}/{total_pages} pages have high image-to-text ratios or low-value opening filler. "
                    f"When AI assistants generate inbox summaries or email digests citing these pages, the important message "
                    f"disappears because the summarizer has no readable text or parses only boilerplate (Appendix F).{extra_context} "
                    f"Examples: {', '.join(example_urls)}."
                ),
                "suggested_action": {
                    "summary": (
                        "Structure email-linked landing pages and newsletters with text-first hierarchy and an invisible preheader:\n\n"
                        '<!-- AI Summarizer Inbox Preheader -->\n'
                        '<div style="display:none;font-size:1px;color:#fff;max-height:0px;overflow:hidden;">\n'
                        '  Nexus v3.0 launched with native sub-millisecond vector indexing and multi-region replication.\n'
                        '</div>\n\n'
                        "Maintain at least a 60:40 text-to-image ratio and ensure key value propositions precede any promotional imagery."
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 8. Weak Above-the-Fold Personalization Density (Appendix E)
        # =====================================================================
        weak_above_fold = df[df["has_substantive_above_fold"] == False]
        if len(weak_above_fold) / total_pages > 0.3:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Insufficient Above-the-Fold Content for AI-Personalized Referrals",
                "severity": "medium",
                "evidence": (
                    f"{len(weak_above_fold)}/{total_pages} pages contain less than 100 characters of substantive "
                    f"text in the first visible section. AI assistants personalize which content to surface based on "
                    f"user context (Appendix E); pages with thin above-the-fold text provide little context for the "
                    f"assistant to match against user intent."
                ),
                "suggested_action": {
                    "summary": (
                        "Front-load the first 500 characters of every page with specific value statements and target audience qualifiers:\n\n"
                        '<p class="lead-summary">\n'
                        '  Built for enterprise data engineering teams, Nexus delivers real-time event streaming\n'
                        '  with automated schema registry and SOC-2 Type II compliance.\n'
                        '</p>'
                    ),
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # =====================================================================
        # 9. Proactive: Instant-Value Widget for AI-Referred Visitors
        # =====================================================================
        findings.append({
            "id": f"F-{finding_idx:03d}",
            "title": "Proactive Opportunity: Instant-Value Retention Widget for AI-Referred Visitors",
            "severity": "medium",
            "evidence": (
                "Proactive retention enhancement: Visitors arriving via deep links from conversational AI assistants "
                "(ChatGPT, Claude, Perplexity) arrive with specific intent and short attention spans. If they encounter "
                "a static promotional wall, bounce probability increases substantially."
            ),
            "suggested_action": {
                "summary": (
                    "Embed a lightweight interactive element above the fold (interactive calculator, code snippet tester, "
                    "or AI-referral welcome banner) to deliver instant utility:\n\n"
                    '<div class="ai-referrer-banner" id="aiWelcome" style="display:none;">\n'
                    '  <p>👋 Arrived from an AI assistant looking for pricing? <a href="#pricing-calculator">View Interactive Calculator &rarr;</a></p>\n'
                    '</div>\n'
                    '<script>\n'
                    '  if (document.referrer && /chatgpt|claude|perplexity/i.test(document.referrer)) {\n'
                    '    document.getElementById("aiWelcome").style.display = "block";\n'
                    '  }\n'
                    '</script>'
                ),
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
    parser = argparse.ArgumentParser(description="Nexus Coders On-Site Engagement & AI-Summary Readiness Analyzer")
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
