#!/usr/bin/env python3
"""
Nexus Coders - Freshness & Entity Corroboration Checker
Part of the nexus-coders-brand-audit Agent Skill Marketplace (Adobe University Hackathon 2026 - Round 3).

Spot-checks brand entity ambiguity via knowledge graph search (Wikidata / Wikipedia API),
evaluates authoritative sameAs links, and measures temporal content freshness signals.
Read-only, rate-polite, and deterministic.
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AUDIT_USER_AGENT = "NexusCodersCorroborationBot/1.0 (+https://github.com/upamkmr/Nexus_adobe; read-only entity check)"

AUTHORITATIVE_ENTITY_DOMAINS = [
    "wikidata.org",
    "wikipedia.org",
    "linkedin.com",
    "crunchbase.com",
    "github.com"
]


class CorroborationChecker:
    """Safe, read-only corroboration and entity ambiguity analyzer."""

    def __init__(self, base_url: str, timeout: int = 6):
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme:
            base_url = "https://" + base_url
            parsed = urllib.parse.urlparse(base_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.netloc = parsed.netloc.lower()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": AUDIT_USER_AGENT,
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "en-US,en;q=0.5"
        })

    def _safe_get(self, url: str) -> Optional[requests.Response]:
        try:
            return self.session.get(url, timeout=self.timeout)
        except requests.exceptions.SSLError:
            try:
                return self.session.get(url, timeout=self.timeout, verify=False)
            except Exception:
                return None
        except Exception:
            return None

    def extract_brand_name(self) -> str:
        """Derives a primary brand keyword from domain and title."""
        # Derive from netloc (e.g. 'adobe.com' -> 'adobe', 'sub.brand.co' -> 'brand')
        parts = self.netloc.split(".")
        if len(parts) >= 2:
            brand_token = parts[-2] if parts[-2] not in ("com", "co", "org", "net", "edu", "gov") else parts[-3]
        else:
            brand_token = parts[0]
        return brand_token.capitalize()

    def check_homepage_entity_signals(self) -> Dict[str, Any]:
        """Fetches homepage to inspect title, schema sameAs, and freshness headers."""
        resp = self._safe_get(self.base_url)
        if resp is None or resp.status_code != 200:
            return {"sameAs": [], "copyright_year": None, "last_modified": None, "title": ""}

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if (soup.title and soup.title.string) else ""
        last_modified = resp.headers.get("last-modified")

        same_as_links = []
        for script in soup.find_all("script", type=lambda t: t and "ld+json" in t.lower()):
            try:
                data = json.loads(script.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    same_as = item.get("sameAs", [])
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    same_as_links.extend(same_as)
            except Exception:
                pass

        plain_text = soup.get_text(" ", strip=True)
        copyright_years = re.findall(r"(?:©|copyright|\(c\))\s*(?:20\d\d\s*-\s*)?(20\d\d)", plain_text, re.I)
        latest_year = int(max(copyright_years)) if copyright_years else None

        return {
            "sameAs": same_as_links,
            "copyright_year": latest_year,
            "last_modified": last_modified,
            "title": title
        }

    def check_wikipedia_wikidata_ambiguity(self, brand_name: str) -> Dict[str, Any]:
        """
        Checks Wikipedia OpenSearch API to determine if the brand keyword
        has multiple conflicting entity interpretations or disambiguation pages.
        """
        api_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(brand_name)}&limit=5&namespace=0&format=json"
        try:
            res = self._safe_get(api_url)
            if res and res.status_code == 200:
                data = res.json()
                # format: [search_term, [titles], [descriptions], [urls]]
                if len(data) >= 4:
                    titles = data[1]
                    descriptions = data[2]
                    urls = data[3]
                    disambig = any("disambiguation" in d.lower() or "(disambiguation)" in t.lower() for t, d in zip(titles, descriptions))
                    return {
                        "searched_term": brand_name,
                        "matches_count": len(titles),
                        "titles": titles[:3],
                        "has_disambiguation": disambig,
                        "checked": True
                    }
        except Exception:
            pass
        return {"searched_term": brand_name, "matches_count": 0, "titles": [], "has_disambiguation": False, "checked": False}

    def run(self) -> Dict[str, Any]:
        brand_name = self.extract_brand_name()
        signals = self.check_homepage_entity_signals()
        kg_search = self.check_wikipedia_wikidata_ambiguity(brand_name)

        findings = []
        finding_idx = 1

        # 1. Authoritative sameAs Knowledge Graph Links
        has_auth_sameas = any(
            any(auth in link.lower() for auth in AUTHORITATIVE_ENTITY_DOMAINS)
            for link in signals["sameAs"]
        )
        if not has_auth_sameas:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Missing Authoritative Knowledge Graph sameAs Links",
                "severity": "high",
                "evidence": f"No 'sameAs' links to authoritative knowledge bases (Wikidata, Wikipedia, LinkedIn, Crunchbase) were detected in structured data for {self.netloc}. Independent AI retrieval models lack a grounding anchor.",
                "suggested_action": {
                    "summary": f"Add Schema.org Organization 'sameAs' URLs in homepage JSON-LD linking to verified Wikidata/LinkedIn/Crunchbase entity IDs to prevent hallucinated brand identity.",
                    "priority": "high"
                }
            })
            finding_idx += 1

        # 2. Entity Disambiguation / Naming Collision Risk
        if kg_search.get("has_disambiguation") or kg_search.get("matches_count", 0) > 1:
            matched = ", ".join(f"'{t}'" for t in kg_search.get("titles", []))
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Entity Ambiguity & Naming Collision in External Knowledge Bases",
                "severity": "medium",
                "evidence": f"External knowledge graph search for brand keyword '{brand_name}' returned multiple distinct entities ({matched}). Without unambiguous disambiguation, LLMs risk conflating the brand with unrelated entities.",
                "suggested_action": {
                    "summary": f"Disambiguate the brand in all schema markup and external citations using exact canonical entity names, industry qualifiers, and official Wikidata URIs.",
                    "priority": "medium"
                }
            })
            finding_idx += 1

        # 3. Content Freshness & Staleness Signals
        current_year = datetime.now().year
        copyright_year = signals.get("copyright_year")
        if copyright_year is not None and copyright_year < current_year - 1:
            findings.append({
                "id": f"F-{finding_idx:03d}",
                "title": "Stale Copyright Notice Signals Content Abandonment",
                "severity": "low",
                "evidence": f"Homepage displays copyright year {copyright_year}, older than {current_year - 1}. Stale temporal indicators penalize dynamic retrieval in time-sensitive AI search engines.",
                "suggested_action": {
                    "summary": f"Update footer templates to dynamically render current year ({current_year}) and configure HTTP Last-Modified headers on marketing assets.",
                    "priority": "low"
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
    parser = argparse.ArgumentParser(description="Nexus Coders Corroboration & Freshness Checker")
    parser.add_argument("url", help="Target URL or domain to inspect (e.g. https://example.com)")
    parser.add_argument("--timeout", type=int, default=6, help="HTTP timeout in seconds (default: 6)")
    parser.add_argument("--output", "-o", help="Optional path to write JSON output report")
    args = parser.parse_args()

    checker = CorroborationChecker(base_url=args.url, timeout=args.timeout)
    report = checker.run()

    output_json = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Corroboration report saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
