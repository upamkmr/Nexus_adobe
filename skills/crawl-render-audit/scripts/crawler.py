#!/usr/bin/env python3
"""
crawler.py — Off-site AI discoverability crawler.

Read-only, robots.txt-respecting crawl of a single site that produces
quantitative, evidence-backed raw findings about whether AI crawlers /
assistants can reach, read, and extract facts from the site.

This script owns NO judgment about final severity or whether a finding is
"the" root cause — it only measures and reports facts. The orchestrator
(a separate skill) is responsible for correlating this output with the
engagement-audit output and calibrating final severity/confidence.

Usage:
    python3 crawler.py <url> --max-pages 15 --timeout 6 --output out.json
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

AI_BOTS = [
    "GPTBot", "ChatGPT-User", "OAI-SearchBot",       # OpenAI
    "ClaudeBot", "Claude-Web", "anthropic-ai",       # Anthropic
    "PerplexityBot", "Perplexity-User",              # Perplexity
    "Google-Extended",                               # Google Gemini / AI Overviews training+grounding
    "CCBot",                                         # Common Crawl (feeds many LLMs)
    "Applebot-Extended",                             # Apple Intelligence
    "Bytespider",                                    # ByteDance / Doubao
]

ENTITY_HOSTS = ("wikidata.org", "linkedin.com", "crunchbase.com", "wikipedia.org")

USER_AGENT = "NexusBrandAuditBot/1.0 (+read-only audit; respects robots.txt)"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, timeout):
    try:
        resp = requests.get(
            url, timeout=timeout, headers={"User-Agent": USER_AGENT}, allow_redirects=True
        )
        return resp
    except requests.RequestException as exc:
        return None


def load_robots(base_url, timeout):
    """Return (RobotFileParser or None, raw_text or None, fetch_ok bool)."""
    robots_url = urljoin(base_url, "/robots.txt")
    resp = fetch(robots_url, timeout)
    if resp is None or resp.status_code >= 400:
        return None, None, False
    rp = robotparser.RobotFileParser()
    rp.parse(resp.text.splitlines())
    return rp, resp.text, True


def check_ai_bot_access(rp, base_url):
    """For each known AI bot UA, check whether root/homepage-equivalent path is disallowed."""
    results = {}
    if rp is None:
        return results
    for bot in AI_BOTS:
        try:
            allowed = rp.can_fetch(bot, base_url)
        except Exception:
            allowed = True
        results[bot] = allowed
    return results


def check_llms_txt(base_url, timeout):
    found = {}
    for path in ("/llms.txt", "/.well-known/llms.txt", "/llms-full.txt"):
        resp = fetch(urljoin(base_url, path), timeout)
        found[path] = bool(resp is not None and resp.status_code == 200 and len(resp.text.strip()) > 0)
    return found


def extract_jsonld(soup):
    blocks = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
            blocks.append(data)
        except (json.JSONDecodeError, TypeError):
            blocks.append({"_parse_error": True})
    return blocks


def flatten_types(jsonld_blocks):
    types = set()
    same_as = []

    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                types.add(t)
            elif isinstance(t, list):
                types.update(str(x) for x in t)
            sa = node.get("sameAs")
            if isinstance(sa, str):
                same_as.append(sa)
            elif isinstance(sa, list):
                same_as.extend(str(x) for x in sa)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for block in jsonld_blocks:
        walk(block)
    return types, same_as


def is_render_gap(soup, html_text):
    """Heuristic: near-empty visible text but a client-rendering framework is present."""
    body = soup.find("body")
    visible_text = body.get_text(strip=True) if body else ""
    script_count = len(soup.find_all("script"))
    # A common SPA fingerprint: a near-empty root/app div plus a bundle-heavy page.
    root_like = soup.find(attrs={"id": re.compile(r"^(root|app|__next)$", re.I)})
    root_text_len = len(root_like.get_text(strip=True)) if root_like else None
    suspicious = (
        len(visible_text) < 200
        and script_count >= 3
        and (root_text_len is None or root_text_len < 50)
    )
    return suspicious, len(visible_text), script_count


def check_alt_text(soup):
    imgs = soup.find_all("img")
    total = len(imgs)
    missing = sum(1 for img in imgs if not (img.get("alt") or "").strip())
    return total, missing


def check_pdf_only_content(soup, base_url):
    pdf_links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].lower().endswith(".pdf")]
    return len(pdf_links)


def check_freshness(resp, soup):
    last_modified = resp.headers.get("Last-Modified") if resp is not None else None
    text = soup.get_text(" ", strip=True)
    year_matches = re.findall(r"(?:©|copyright)\s*(\d{4})", text, flags=re.I)
    copyright_year = max((int(y) for y in year_matches), default=None)
    return last_modified, copyright_year


def bfs_sample_pages(base_url, max_pages, timeout, rp):
    """Same-domain BFS from homepage, skipping paths robots.txt disallows for our own UA."""
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

        time.sleep(0.1)  # polite delay

    return pages


def build_findings(base_url, robots_text, ai_bot_access, llms_txt, pages):
    findings = []
    tag_ctr = 0

    def new_finding(title, severity_hint, evidence, action_summary, action_priority, tags, correlatable=False, scope="site"):
        nonlocal tag_ctr
        tag_ctr += 1
        return {
            "source_skill": "crawl-render-audit",
            "raw_id": f"disc-{tag_ctr:03d}",
            "title": title,
            "severity_hint": severity_hint,
            "scope": scope,
            "evidence": evidence,
            "suggested_action": {"summary": action_summary, "priority": action_priority},
            "tags": tags,
            "correlatable": correlatable,
        }

    # 1. AI crawler access
    blocked_bots = [b for b, allowed in ai_bot_access.items() if not allowed]
    if ai_bot_access and blocked_bots:
        findings.append(new_finding(
            "AI Assistant Crawler Access Restricted in robots.txt",
            severity_hint="high" if len(blocked_bots) < len(ai_bot_access) else "critical",
            evidence=(
                f"robots.txt disallows the following AI retrieval crawlers from the homepage path: "
                f"{', '.join(blocked_bots)}. {len(ai_bot_access) - len(blocked_bots)} of "
                f"{len(ai_bot_access)} known AI bots remain allowed."
            ),
            action_summary="Review robots.txt and explicitly allow AI retrieval crawlers on public marketing/docs paths, unless the block is intentional.",
            action_priority="high",
            tags=["crawler_access"],
        ))
    elif not robots_text:
        findings.append(new_finding(
            "robots.txt Not Found or Unreachable",
            severity_hint="low",
            evidence="No robots.txt was found at /robots.txt (or it could not be fetched). Absence is not itself a defect, but it means crawl policy is entirely implicit.",
            action_summary="Publish an explicit robots.txt so crawl intent for AI bots is unambiguous rather than default-permissive.",
            action_priority="low",
            tags=["crawler_access"],
        ))

    # 2. llms.txt
    if not any(llms_txt.values()):
        findings.append(new_finding(
            "No llms.txt / llms-full.txt Manifest",
            severity_hint="medium",
            evidence="Checked /llms.txt, /.well-known/llms.txt, and /llms-full.txt — none were found.",
            action_summary="Publish an llms.txt (and optionally llms-full.txt) summarizing key pages/facts for LLM consumption.",
            action_priority="medium",
            tags=["llms_txt"],
        ))

    # Per-page aggregate signals
    n_pages = len(pages)
    if n_pages == 0:
        findings.append(new_finding(
            "No Pages Could Be Sampled",
            severity_hint="critical",
            evidence="The crawler could not successfully fetch any HTML page from this domain within the configured limits.",
            action_summary="Verify the site is publicly reachable over HTTPS and not blocking generic HTTP clients.",
            action_priority="high",
            tags=["crawl_failure"],
            scope="site",
        ))
        return findings

    pages_missing_jsonld = 0
    pages_render_gap = 0
    total_imgs = 0
    total_imgs_missing_alt = 0
    pdf_only_hits = 0
    sameas_hosts_seen = set()
    freshness_years = []
    sample_urls_missing_jsonld = []
    sample_urls_render_gap = []

    for url, resp, soup in pages:
        jsonld_blocks = extract_jsonld(soup)
        types, same_as = flatten_types(jsonld_blocks)
        if not types:
            pages_missing_jsonld += 1
            if len(sample_urls_missing_jsonld) < 3:
                sample_urls_missing_jsonld.append(url)
        for sa in same_as:
            host = urlparse(sa).netloc
            for eh in ENTITY_HOSTS:
                if eh in host:
                    sameas_hosts_seen.add(eh)

        gap, text_len, script_count = is_render_gap(soup, resp.text)
        if gap:
            pages_render_gap += 1
            if len(sample_urls_render_gap) < 3:
                sample_urls_render_gap.append(url)

        n_imgs, missing_alt = check_alt_text(soup)
        total_imgs += n_imgs
        total_imgs_missing_alt += missing_alt

        pdf_only_hits += check_pdf_only_content(soup, url)

        last_modified, copyright_year = check_freshness(resp, soup)
        if copyright_year:
            freshness_years.append(copyright_year)

    # 3. Schema.org / JSON-LD coverage
    if pages_missing_jsonld > 0:
        findings.append(new_finding(
            "Missing or Incomplete Schema.org Structured Data",
            severity_hint="high" if pages_missing_jsonld == n_pages else "medium",
            evidence=(
                f"{pages_missing_jsonld}/{n_pages} sampled pages contain no parsable JSON-LD structured data. "
                f"Examples: {', '.join(sample_urls_missing_jsonld)}"
            ),
            action_summary="Add JSON-LD structured data (Organization, Product, Article, FAQPage as applicable) to pages that lack it.",
            action_priority="high",
            tags=["structured_data"],
            correlatable=True,
            scope="sample",
        ))

    # 4. JS-render gaps
    if pages_render_gap > 0:
        findings.append(new_finding(
            "Client-Side Rendering Gap (Near-Empty Server-Rendered HTML)",
            severity_hint="high",
            evidence=(
                f"{pages_render_gap}/{n_pages} sampled pages returned near-empty visible text in the initial "
                f"HTML response alongside multiple script tags — a signature of content assembled client-side "
                f"after load. Examples: {', '.join(sample_urls_render_gap)}"
            ),
            action_summary="Server-side render (or statically pre-render) essential content so it is present in the initial HTML response.",
            action_priority="high",
            tags=["render_gap", "structured_data"],
            correlatable=True,
            scope="sample",
        ))

    # 5. Alt text / non-text facts
    if total_imgs > 0 and total_imgs_missing_alt / total_imgs > 0.3:
        findings.append(new_finding(
            "Facts Likely Locked in Non-Text Media (Missing Alt Text)",
            severity_hint="medium",
            evidence=(
                f"{total_imgs_missing_alt}/{total_imgs} sampled images "
                f"({total_imgs_missing_alt / total_imgs:.0%}) have no descriptive alt attribute, "
                f"suggesting facts conveyed visually are not machine-extractable."
            ),
            action_summary="Add descriptive alt text to informational images (not purely decorative ones).",
            action_priority="medium",
            tags=["non_text_content"],
        ))

    if pdf_only_hits > n_pages:  # heuristic: more PDF links than pages sampled implies heavy PDF reliance
        findings.append(new_finding(
            "Notable Reliance on PDF-Only Content",
            severity_hint="low",
            evidence=f"Sampled pages link to {pdf_only_hits} PDF documents; key facts may live only inside PDFs rather than crawlable HTML.",
            action_summary="Mirror essential PDF content (specs, pricing, docs) as readable HTML in addition to the PDF.",
            action_priority="low",
            tags=["non_text_content"],
        ))

    # 6. Cross-web entity corroboration
    if not sameas_hosts_seen:
        findings.append(new_finding(
            "No Cross-Web Entity Corroboration Links Detected",
            severity_hint="medium",
            evidence=(
                "No sameAs links to Wikidata, Wikipedia, LinkedIn, or Crunchbase were found in structured data "
                "across sampled pages, making entity disambiguation harder for external systems."
            ),
            action_summary="Add sameAs entries in Organization/Person JSON-LD linking to authoritative external profiles (Wikidata, LinkedIn, Crunchbase).",
            action_priority="medium",
            tags=["entity_corroboration"],
            correlatable=True,
        ))

    # 7. Freshness
    current_year = datetime.now().year
    if freshness_years:
        newest = max(freshness_years)
        if current_year - newest >= 2:
            findings.append(new_finding(
                "Stale Freshness Signals (Copyright Year)",
                severity_hint="low",
                evidence=f"The most recent copyright year found across sampled pages is {newest}, {current_year - newest} years behind the current year.",
                action_summary="Update copyright/footer freshness signals and ensure page metadata reflects real last-modified dates.",
                action_priority="low",
                tags=["freshness"],
            ))
    else:
        findings.append(new_finding(
            "No Freshness Signals Detected",
            severity_hint="low",
            evidence="No copyright year or other freshness indicator was found in sampled page text.",
            action_summary="Expose a visible last-updated date or copyright year so freshness can be assessed by both humans and machines.",
            action_priority="low",
            tags=["freshness"],
        ))

    return findings


def main():
    parser = argparse.ArgumentParser(description="Off-site AI discoverability crawler")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=6)
    parser.add_argument("--output", default="discoverability_raw.json")
    args = parser.parse_args()

    if not re.match(r"^https?://", args.url):
        base_url = "https://" + args.url
    else:
        base_url = args.url
    parsed = urlparse(base_url)
    domain = parsed.netloc

    rp, robots_text, robots_ok = load_robots(base_url, args.timeout)
    ai_bot_access = check_ai_bot_access(rp, base_url) if robots_ok else {}
    llms_txt = check_llms_txt(base_url, args.timeout)
    pages = bfs_sample_pages(base_url, args.max_pages, args.timeout, rp)

    findings = build_findings(base_url, robots_text, ai_bot_access, llms_txt, pages)

    output = {
        "source_skill": "crawl-render-audit",
        "site": domain,
        "audited_at": now_iso(),
        "pages_sampled": len(pages),
        "sampled_urls": [p[0] for p in pages],
        "robots_txt_found": robots_ok,
        "ai_bot_access": ai_bot_access,
        "llms_txt": llms_txt,
        "findings": findings,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(findings)} raw discoverability findings to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
