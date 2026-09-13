# Cross-Web Corroboration & Entity Disambiguation Spot-Check

`crawler.py` can only see the target site itself, so it checks a *proxy* signal for
corroboration: whether the site declares `sameAs` links to authoritative external
profiles (Wikidata, Wikipedia, Crunchbase, LinkedIn). That proxy catches sites with
zero external identity signals, but it cannot tell you whether the wider web actually
**agrees** with what the site claims, or whether the brand name collides with an
unrelated entity elsewhere. That verification needs a live web search, which only the
orchestrating agent (not the sandboxed script) can perform. This reference defines a
deterministic *procedure* for that step — the judgment stays bounded, only the lookup
is delegated to a tool.

## Why this matters (see Appendix D)
A fact repeated consistently across independent, unrelated sources is far more likely
to be trusted and repeated by an AI assistant than a fact that lives in only one place.
Mistaken identity — several different things sharing a name — causes assistants to mix
up brands unless something clearly disambiguates them.

## Procedure (run once per audit, after the crawl completes)

1. **Select up to 3 load-bearing factual claims** from the crawled pages — prefer
   claims an AI assistant is likely to be asked about and that are falsifiable:
   - Founding year / headquarters location / legal entity name
   - A specific product claim (e.g. "the only X that does Y")
   - A named executive or founder
   Skip vague marketing claims ("industry-leading") — they aren't independently
   verifiable and shouldn't be treated as corroboration failures.

2. **For each selected claim, run 1–2 targeted web searches** using terms that would
   surface independent sources (news coverage, Wikipedia/Wikidata, industry
   directories, regulatory filings) — not just the brand's own domain or its official
   social accounts (those aren't independent).

3. **Classify each claim:**
   - **Corroborated**: ≥2 independent, unrelated sources state the same fact.
   - **Uncorroborated**: no independent source mentions it (fine for very new/small
     brands — note as `low` severity, not a defect, since brand-new entities can't
     yet have accumulated cross-web mentions).
   - **Contradicted**: an independent source states something materially different
     (e.g. a different founding year, a different company at a similar name). This is
     the important case — it signals the entity-disambiguation risk described in
     Appendix D, and should be raised as a `high` severity finding regardless of brand
     size.

4. **For a `contradicted` result**, check whether the name collision looks like genuine
   mistaken identity (a different, unrelated company/product with a similar or
   identical name) versus a simple factual error on the site. Report which one it looks
   like — the fix is different: disambiguating page copy and `sameAs`/`disambiguatingDescription`
   markup for the former, a correction for the latter.

5. **Add findings to the shared JSON report** in the same shape as the crawler's
   findings (`id`, `title`, `severity`, `evidence`, `suggested_action`), continuing the
   `F-0xx` numbering the orchestrator is already tracking. `evidence` should name the
   specific claim and what the independent sources actually say (not just "unverified").

## What NOT to do
- Don't flag every unsourced marketing claim — only factual, checkable claims.
- Don't treat a brand-new/small company's lack of web mentions as equivalent to a
  contradiction — severity differs materially between the two.
- Don't search the brand's own subdomains, official social accounts, or PR wire
  reposts of the brand's own press release as "independent" sources.
