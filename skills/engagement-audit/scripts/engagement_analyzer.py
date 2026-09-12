#!/usr/bin/env python3
"""
engagement_analyzer.py — On-site visitor engagement / retention audit.

Independent, robots.txt-respecting crawl measuring whether a visitor who
lands on the site (often deep-linked from an AI assistant) can quickly
understand where they are, what the page offers, and what to do next.

Like crawl-render-audit, this script only measures and reports raw,
evidence-backed signals. Final severity/priority synthesis across both
audits happens in the orchestrator.

Usage:
    python3 engagement_analyzer.py <url> --max-pages 15 --timeout 6 --output out.json
"""
import argparse
import json
import re
import sys
import time
import urllib.robotparser as robotparser
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "NexusBrandAuditBot/1.0 (+read-only audit; respects robots.txt)"

CTA_PATTERNS = re.compile(
    r"\b(buy now|add to cart|sign up|get started|start free|contact us|book a|"
    r"request a demo|learn more|subscribe|download|try (it |for )?free|schedule a)\b",
    re.I,
)

PROSE_BLOCK_WORD_THRESHOLD = 150  # a single <p> beyond this length, with no nearby heading/list, is a "wall of text"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, timeout):
    try:
        return requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
    except requests.RequestException:
        return None


def load_robots(base_url, timeout):
    robots_url = urljoin(base_url, "/robots.txt")
    resp = fetch(robots_url, timeout)
    if resp is None or resp.status_code >= 400:
        return None
    rp = robotparser.RobotFileParser()
    rp.parse(resp.text.splitlines())
    return rp


def bfs_sample_pages(base_url, max_pages, timeout, rp):
    domain = urlparse(base_url).netloc
    seen = set()
    queue = deque([base_url])
    pages = []

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        if rp is not None:
            try:
                if not rp.can_fetch(USER_AGENT, url):
                    continue
            except Exception:
                pass

        resp = fetch(url, timeout)
        if resp is None or resp.status_code >= 400 or "text/html" not in resp.headers.get("Content-Type", ""):
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        pages.append((url, resp, soup))

        if len(pages) >= max_pages:
            break

        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"]).split("#")[0]
            if urlparse(link).netloc == domain and link not in seen:
                queue.append(link)
        time.sleep(0.1)

    return pages


def check_h1(soup):
    h1s = soup.find_all("h1")
    texts = [h.get_text(strip=True) for h in h1s]
    return len(h1s), texts


def check_nav_orientation(soup):
    has_nav = soup.find("nav") is not None
    has_breadcrumb = (
        soup.find(attrs={"aria-label": re.compile("breadcrumb", re.I)}) is not None
        or soup.find(class_=re.compile("breadcrumb", re.I)) is not None
    )
    return has_nav, has_breadcrumb


def check_prose_blocks(soup):
    offenders = 0
    for p in soup.find_all("p"):
        word_count = len(p.get_text(strip=True).split())
        if word_count >= PROSE_BLOCK_WORD_THRESHOLD:
            # look at immediate siblings for a nearby heading/list break
            prev_h = p.find_previous(re.compile("^h[1-6]$"))
            next_break = p.find_next(["h1", "h2", "h3", "h4", "ul", "ol"])
            if next_break is None:
                offenders += 1
    return offenders


def check_cta(soup):
    candidates = soup.find_all(["a", "button"])
    hits = [c for c in candidates if CTA_PATTERNS.search(c.get_text(" ", strip=True))]
    return len(hits) > 0, len(hits)


def check_mobile_viewport(soup):
    tag = soup.find("meta", attrs={"name": "viewport"})
    return tag is not None


def check_image_dimensions(soup):
    imgs = soup.find_all("img")
    total = len(imgs)
    missing_dims = sum(1 for img in imgs if not (img.get("width") and img.get("height")))
    return total, missing_dims


def build_findings(pages):
    findings = []
    ctr = 0

    def new_finding(title, severity_hint, evidence, action_summary, action_priority, tags, correlatable=False, scope="site"):
        nonlocal ctr
        ctr += 1
        return {
            "source_skill": "engagement-audit",
            "raw_id": f"eng-{ctr:03d}",
            "title": title,
            "severity_hint": severity_hint,
            "scope": scope,
            "evidence": evidence,
            "suggested_action": {"summary": action_summary, "priority": action_priority},
            "tags": tags,
            "correlatable": correlatable,
        }

    n_pages = len(pages)
    if n_pages == 0:
        findings.append(new_finding(
            "No Pages Could Be Sampled",
            "critical",
            "The crawler could not fetch any HTML page from this domain within the configured limits.",
            "Verify the site is publicly reachable and not blocking generic HTTP clients.",
            "high",
            ["crawl_failure"],
        ))
        return findings

    zero_h1_pages, multi_h1_pages = [], []
    no_nav_pages = 0
    no_breadcrumb_pages = 0
    prose_offenders_total = 0
    zero_cta_pages = []
    no_viewport_pages = []
    total_imgs = 0
    total_imgs_missing_dims = 0

    for url, resp, soup in pages:
        n_h1, h1_texts = check_h1(soup)
        if n_h1 == 0:
            zero_h1_pages.append(url)
        elif n_h1 > 1:
            multi_h1_pages.append(url)

        has_nav, has_breadcrumb = check_nav_orientation(soup)
        if not has_nav:
            no_nav_pages += 1
        if not has_breadcrumb:
            no_breadcrumb_pages += 1

        prose_offenders_total += check_prose_blocks(soup)

        has_cta, n_cta = check_cta(soup)
        if not has_cta:
            zero_cta_pages.append(url)

        if not check_mobile_viewport(soup):
            no_viewport_pages.append(url)

        n_imgs, missing_dims = check_image_dimensions(soup)
        total_imgs += n_imgs
        total_imgs_missing_dims += missing_dims

    # 1. Above-the-fold clarity (H1)
    if zero_h1_pages:
        findings.append(new_finding(
            "Pages Missing a Clear Primary Heading (H1)",
            "high" if len(zero_h1_pages) == n_pages else "medium",
            f"{len(zero_h1_pages)}/{n_pages} sampled pages have no <h1> element. Examples: {', '.join(zero_h1_pages[:3])}",
            "Add a single, specific <h1> per page stating what the page/offer actually is (the '5-second test').",
            "high",
            ["above_fold_clarity"],
        ))
    if multi_h1_pages:
        findings.append(new_finding(
            "Pages With Multiple/Ambiguous H1 Headings",
            "medium",
            f"{len(multi_h1_pages)}/{n_pages} sampled pages have more than one <h1>, diluting the primary value proposition. Examples: {', '.join(multi_h1_pages[:3])}",
            "Reduce to one <h1> per page representing the core value proposition; demote others to <h2>+.",
            "medium",
            ["above_fold_clarity"],
        ))

    # 2. Navigation orientation
    if no_nav_pages / n_pages > 0.3:
        findings.append(new_finding(
            "Missing Navigation Landmarks on Deep Pages",
            "medium",
            f"{no_nav_pages}/{n_pages} sampled pages have no <nav> landmark, which especially hurts visitors who deep-link in without visiting the homepage first.",
            "Ensure every page includes a consistent, semantic <nav> so deep-linked visitors can orient themselves.",
            "medium",
            ["navigation"],
            correlatable=True,
        ))
    if no_breadcrumb_pages / n_pages > 0.5:
        findings.append(new_finding(
            "No Breadcrumb Trails for Deep-Linked Pages",
            "low",
            f"{no_breadcrumb_pages}/{n_pages} sampled pages have no breadcrumb trail, making it harder for arriving visitors to understand where a deep page sits in the site.",
            "Add breadcrumb navigation (and matching BreadcrumbList structured data) on interior pages.",
            "low",
            ["navigation"],
        ))

    # 3. Scannability
    if prose_offenders_total > 0:
        findings.append(new_finding(
            "Long Unbroken Prose Blocks Hurt Scannability",
            "low",
            f"Found {prose_offenders_total} paragraph(s) across sampled pages exceeding {PROSE_BLOCK_WORD_THRESHOLD} words with no nearby subheading or list to break up the content.",
            "Break long paragraphs into scannable sections with subheadings, bullet lists, or short paragraphs.",
            "low",
            ["scannability"],
        ))

    # 4. CTA clarity
    if zero_cta_pages:
        findings.append(new_finding(
            "Pages With No Detectable Call-to-Action",
            "high" if len(zero_cta_pages) / n_pages > 0.5 else "medium",
            f"{len(zero_cta_pages)}/{n_pages} sampled pages have no recognizable CTA text (e.g. 'get started', 'contact us', 'sign up'). Examples: {', '.join(zero_cta_pages[:3])}",
            "Add a clear, specific CTA above the fold and at the end of content on every page — avoid dead ends.",
            "high",
            ["cta_clarity"],
            correlatable=True,
        ))

    # 5. Mobile viewport
    if no_viewport_pages:
        findings.append(new_finding(
            "Missing Mobile Viewport Meta Tag",
            "medium",
            f"{len(no_viewport_pages)}/{n_pages} sampled pages lack a <meta name=\"viewport\"> tag, risking a non-responsive mobile layout. Examples: {', '.join(no_viewport_pages[:3])}",
            "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> to all page templates.",
            "medium",
            ["mobile_layout"],
        ))

    # 6. Layout-shift risk
    if total_imgs > 0 and total_imgs_missing_dims / total_imgs > 0.3:
        findings.append(new_finding(
            "Images Missing Width/Height Attributes (Layout-Shift Risk)",
            "low",
            f"{total_imgs_missing_dims}/{total_imgs} images ({total_imgs_missing_dims / total_imgs:.0%}) sampled lack explicit width/height, risking cumulative layout shift as images load.",
            "Set explicit width/height (or aspect-ratio CSS) on images to reserve layout space before they load.",
            "low",
            ["mobile_layout"],
        ))

    return findings


def main():
    parser = argparse.ArgumentParser(description="On-site engagement/retention analyzer")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=6)
    parser.add_argument("--output", default="engagement_raw.json")
    args = parser.parse_args()

    base_url = args.url if re.match(r"^https?://", args.url) else "https://" + args.url
    domain = urlparse(base_url).netloc

    rp = load_robots(base_url, args.timeout)
    pages = bfs_sample_pages(base_url, args.max_pages, args.timeout, rp)
    findings = build_findings(pages)

    output = {
        "source_skill": "engagement-audit",
        "site": domain,
        "audited_at": now_iso(),
        "pages_sampled": len(pages),
        "sampled_urls": [p[0] for p in pages],
        "findings": findings,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(findings)} raw engagement findings to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
