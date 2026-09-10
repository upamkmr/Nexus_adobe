---

name: audit-orchestrator
description: Intelligent entrypoint orchestrator for the nexus-coders-brand-audit marketplace. Validates and normalizes audit targets, builds a dynamic audit plan, delegates domain-specific analysis to specialized skills, manages dependencies and evidence requirements, performs cross-skill correlation and conflict resolution, calibrates confidence, prioritizes root-cause fixes, and emits a unified evidence-backed brand AI-readiness and engagement assessment. Use whenever a complete website or domain audit is requested.
license: Apache-2.0
allowed-tools: Bash, WebSearch
------------------------------

# Audit Orchestrator

The `audit-orchestrator` is the **decision and synthesis layer** of the Nexus Coders Brand Audit Marketplace.

Its job is not to repeat the logic already implemented in the individual audit skills.

Instead, it brings their results together and handles the parts that sit between the skills:

1. **What should be audited?**
2. **What evidence do we actually need?**
3. **Do we have enough evidence to trust a finding?**
4. **How are findings from different skills connected or related?**
5. **Which fixes are actually worth doing first?**

Each specialized skill stays responsible for its own analysis and evidence gathering.

The orchestrator takes those independent results and turns them into one consistent assessment.

> **Skills find the problems. The orchestrator connects the dots, checks the evidence, and decides what matters most.**

---

# When to use

Use this skill when:

* A complete website or domain audit is requested.
* The audit needs to cover AI discoverability, AI citation readiness, visitor engagement, or a combination of these.
* Results from multiple specialized audit skills need to be combined into one report.
* Findings from different areas need to be compared or related to each other.
* The final result needs to be prioritized and backed by evidence.

Do not use this skill when only one specialized audit is needed and there is no need to combine or interpret results across skills.

---

# Core Design Principles

## 1. Orchestrate, don't duplicate

The orchestrator should not reimplement logic that already belongs to a specialized skill.

That includes things like:

* discoverability analysis
* engagement analysis
* freshness detection
* corroboration methodology
* structured-data analysis
* crawl heuristics
* individual scoring algorithms

Those stay inside their respective skills.

The orchestrator works with their outputs, compares them, finds relationships, and can ask for more evidence when needed.

---

## 2. Evidence before conclusions

Every important finding should be backed by evidence from a skill or from an explicit corroboration check.

An uncertain signal should not automatically become a confirmed defect.

Depending on the evidence, findings can be treated as:

* `confirmed`
* `likely`
* `possible`
* `insufficient evidence`

The wording should match the actual strength of the evidence.

---

## 3. Confidence is separate from severity

Severity and confidence answer different questions.

For every finding, think of them separately:

```text
Severity   = How damaging is the issue?
Confidence = How certain are we that the issue is actually present?
Impact     = How much could fixing it help?
Effort     = How difficult is the fix?
```

A severe issue with weak evidence should not be treated the same way as a severe issue supported by several strong signals.

Do not use confidence as a replacement for severity.

---

## 4. Root causes over duplicate symptoms

Different skills can sometimes report different symptoms that are actually related to the same underlying issue.

For example:

```text
Missing structured data
        +
Weak entity corroboration
        +
Poor AI fact extraction
        ↓
Possible underlying issue:
Insufficient machine-readable entity representation
```

Where the evidence supports that relationship, the orchestrator should connect the findings instead of turning them into several disconnected recommendations.

---

## 5. Adaptive auditing

The first pass should not automatically run every possible analysis.

Build the **minimum sufficient audit plan** based on:

* the target
* the evidence already available
* the skills that apply
* dependencies between those skills
* detected uncertainty
* the requested scope

When an important conclusion does not have enough evidence, perform a targeted follow-up instead of simply repeating the entire audit.

---

# Inputs

* **`url`** (string, required): Target website, domain, or URL.
* **`max_pages`** (integer, optional): Maximum pages available to each crawl-based skill. Default: `15`. Maximum: `50`.
* **`timeout`** (integer, optional): Network timeout per request in seconds. Default: `6`.
* **`scope`** (string, optional): Audit scope. Defaults to `full`.
* **`focus`** (array, optional): Optional areas of interest such as `discoverability`, `engagement`, `freshness`, or `corroboration`.

Unknown input parameters should not silently change how the audit behaves.

---

# Execution Model

The orchestrator follows this overall flow:

```text
INPUT
  ↓
VALIDATE
  ↓
NORMALIZE
  ↓
UNDERSTAND TARGET
  ↓
BUILD AUDIT PLAN
  ↓
EXECUTE INDEPENDENT AUDITS
  ↓
COLLECT EVIDENCE
  ↓
CHECK EVIDENCE SUFFICIENCY
  ↓
TARGETED FOLLOW-UP AUDITS (if necessary)
  ↓
CORRELATE FINDINGS
  ↓
RESOLVE CONFLICTS
  ↓
IDENTIFY ROOT CAUSES
  ↓
GENERATE RECOMMENDATIONS
  ↓
PRIORITIZE ACTIONS
  ↓
VALIDATE REPORT
  ↓
UNIFIED REPORT
```

Independent audits can be run in parallel when the execution environment allows it.

Any audit that depends on another audit's output should wait until that evidence is available.

---

# Procedure

## Step 1 — Input validation and normalization

1. Accept the supplied URL or domain.
2. Normalize it to a canonical HTTPS target where appropriate.
3. Extract the registrable domain / canonical site identity.
4. Reject malformed or unsupported targets.
5. Make sure the crawl stays within the requested domain.
6. Keep the audit read-only:

   * `GET` and `HEAD` only
   * no authentication
   * no form submission
   * no mutations
   * no credential handling
7. Apply the requested crawl and timeout limits.

If normalization materially changes the supplied target, keep the normalized target in the internal audit context.

---

# Step 2 — Establish audit context

Create an internal audit context:

```json
{
  "target": {
    "input": "...",
    "normalized_url": "...",
    "domain": "..."
  },
  "constraints": {
    "max_pages": 15,
    "timeout": 6
  },
  "requested_scope": "full",
  "skills_requested": [],
  "skills_executed": [],
  "evidence": [],
  "findings": [],
  "warnings": []
}
```

This is internal orchestration state and does not need to appear in the final report.

---

# Step 3 — Build the audit plan

Decide which specialized skills apply to this audit.

For the current marketplace:

```text
                    AUDIT ORCHESTRATOR
                           │
             ┌─────────────┴─────────────┐
             ↓                           ↓
   discoverability-audit          engagement-audit
             │                           │
             └─────────────┬─────────────┘
                           ↓
                    CROSS-SKILL SYNTHESIS
```

The orchestrator should not assume that every future skill belongs in every audit.

As the marketplace grows, each skill should ideally expose a simple contract describing:

```text
skill
capabilities
inputs
outputs
evidence_types
dependencies
failure_behavior
```

The orchestrator can then use that information to build the execution plan without knowing how the skill works internally.

---

# Step 4 — Execute Discoverability Audit

Hand discoverability-specific analysis to:

`discoverability-audit`

For the current implementation, this may be invoked through:

```bash
python3 skills/discoverability-audit/scripts/crawler.py \
  <target-url> \
  --max-pages <max_pages> \
  --output ./discoverability_raw.json
```

The orchestrator should treat the child skill as the authority on how its discoverability metrics are calculated.

Expected evidence may include:

* AI crawler robots directives
* `llms.txt` / related files
* Schema.org / JSON-LD coverage
* server-rendered versus client-rendered content
* media-only or difficult-to-extract information
* entity relationships
* freshness signals
* other discoverability findings returned by the skill

Keep the evidence and confidence returned by the skill instead of reducing everything to a simple pass/fail result.

---

# Step 5 — Execute Engagement Audit

Hand engagement-specific analysis to:

`engagement-audit`

For the current implementation, this may be invoked through:

```bash
python3 skills/engagement-audit/scripts/engagement_analyzer.py \
  <target-url> \
  --max-pages <max_pages> \
  --output ./engagement_raw.json
```

The orchestrator should not duplicate the engagement skill's analysis.

Expected evidence may include:

* value proposition clarity
* heading quality
* navigation orientation
* breadcrumb availability
* content scannability
* CTA availability
* mobile viewport configuration
* layout-shift risk indicators
* other engagement findings returned by the skill

For qualitative checks, follow the engagement skill's own reference material.

---

# Step 6 — Evidence normalization

Bring outputs from the child skills into a common internal format.

Each finding should conceptually contain:

```json
{
  "source_skill": "discoverability-audit",
  "finding": "...",
  "evidence": [],
  "severity": "high",
  "confidence": 0.91,
  "scope": "site",
  "affected_pages": [],
  "recommendation": "...",
  "relationships": []
}
```

Do not throw away useful evidence simply because the final external schema is smaller.

Keep the richer representation internally until the final report is generated.

---

# Step 7 — Evidence sufficiency check

For every important finding, ask:

1. Do we have direct evidence?
2. Is the evidence specific enough to support the claim?
3. Is the finding page-specific or site-wide?
4. Could something else explain the same signal?
5. Does another skill support or contradict it?
6. Do we need more evidence before calling this a real issue?

When a high-impact finding is not well supported, run a targeted follow-up where possible.

Examples:

```text
Low confidence freshness finding
        ↓
Check metadata / source dates / page signals
```

```text
Possible AI extraction problem
        ↓
Inspect rendered content / structured data evidence
```

```text
Potential entity ambiguity
        ↓
Run targeted corroboration
```

The goal is to collect the missing evidence, not to repeatedly crawl the entire site.

---

# Step 8 — Corroboration

When a finding depends on factual claims about the brand or how it is represented externally, use the discoverability skill's existing corroboration methodology.

For the current implementation:

* follow `skills/discoverability-audit/references/corroboration-guide.md`
* spot-check up to 3 load-bearing claims when appropriate
* use independent web sources
* distinguish between:

  * corroborated
  * contradicted
  * uncorroborated
  * insufficient evidence

Corroboration should strengthen, weaken, or qualify an existing finding. It should not be used to create unrelated findings.

---

# Step 9 — Cross-skill correlation

Once the individual skills have finished, compare their findings.

Look for four things.

### Reinforcement

Two independent skills support the same conclusion.

Example:

```text
Weak machine-readable content
        +
Poor above-the-fold clarity
        ↓
Visitors and AI systems may both struggle
to quickly understand the site's core offering
```

### Dependency

One issue may cause or make another issue worse.

Example:

```text
Client-side rendering gap
        ↓
Reduced extractable content
        ↓
Weak AI discoverability
```

### Contradiction

Two findings appear to disagree.

Do not immediately choose one and discard the other.

First check whether they describe different dimensions.

Example:

```text
Page updated recently
        ≠
Referenced sources are current
```

### Duplication

Different findings recommend essentially the same fix.

Where appropriate, merge them rather than presenting the same action multiple times.

---

# Step 10 — Conflict resolution

When findings conflict, use the following order:

1. Direct evidence over inference.
2. Page-specific evidence over broad assumptions.
3. Independent corroboration over unsupported claims.
4. Stronger or more recent evidence over stale evidence.
5. Multiple independent signals over a single heuristic.

If the conflict cannot be resolved, keep the uncertainty instead of hiding it.

Example:

```text
Finding A:
Page appears recently updated.

Finding B:
Supporting references contain older information.

Resolution:
The page itself is fresh, but supporting evidence may be stale.
These findings are complementary rather than contradictory.
```

Do not force a single conclusion just to make the report look cleaner.

---

# Step 11 — Severity calibration

Severity describes the potential technical or business impact of an issue.

### Critical

Use `critical` when a confirmed issue creates a severe barrier to the audit objective or causes broad site inaccessibility.

Examples:

* complete site inaccessibility
* a confirmed technical mechanism preventing relevant systems from accessing essential public content

Do not automatically mark every robots.txt restriction as critical.

Consider:

* which bots are blocked
* which paths are blocked
* whether essential content is affected
* whether other discovery paths remain available

### High

Use `high` for major issues that materially reduce discoverability, comprehension, or visitor progression.

Examples:

* important content unavailable to extraction
* severe rendering barriers
* major entity ambiguity
* critical pages lacking essential machine-readable representation
* site-wide engagement barriers

### Medium

Use `medium` for meaningful but non-blocking issues.

Examples:

* weak scannability
* missing descriptive metadata
* incomplete structured representation
* navigation friction
* recurring CTA gaps

### Low

Use `low` for minor optimization opportunities or weak heuristic signals.

Examples:

* minor metadata inconsistencies
* weak freshness indicators when stronger freshness evidence exists
* small usability improvements

Severity should come from the evidence and the context, not simply from the fact that a defect exists.

---

# Step 12 — Confidence calibration

Assign an internal confidence score between `0.0` and `1.0`.

Suggested interpretation:

```text
0.90 – 1.00   Strongly evidenced
0.75 – 0.89   Well supported
0.50 – 0.74   Probable
0.25 – 0.49   Weak / uncertain
0.00 – 0.24   Insufficient
```

Confidence should increase with:

* direct evidence
* repeated observations
* independent corroboration
* agreement between skills

Confidence should decrease with:

* heuristic-only evidence
* contradictory evidence
* very small samples
* ambiguous interpretation

Do not expose numerical confidence in the final report unless the official output schema allows it.

---

# Step 13 — Root-cause analysis

Group related findings into underlying problems when the evidence supports the relationship.

Example:

```text
F-001 Missing structured data
F-004 Weak entity corroboration
F-007 Poor AI fact extraction
             ↓
      ROOT CAUSE CLUSTER
             ↓
Insufficient machine-readable brand representation
```

Where possible, recommendations should address the root cause rather than treating every symptom as a completely separate task.

Do not force unrelated findings into the same root cause.

---

# Step 14 — Generate recommendations

Recommendations should fall into two categories.

## Defect remediation

These directly address confirmed or strongly supported problems.

Examples:

* improve structured data
* expose important content as crawlable HTML
* improve navigation
* clarify primary CTAs
* resolve mobile configuration issues

## Proactive opportunities

These go beyond simply fixing detected defects.

Examples may include:

* maintaining a clear machine-readable content/documentation layer
* improving entity relationships across authoritative sources
* publishing structured question-and-answer content where genuinely useful
* creating useful interactive experiences for high-intent visitors
* improving content freshness workflows

Proactive recommendations should be presented as opportunities, not guarantees.

For example, do not claim that `llms.txt`, FAQ markup, or a specific optimization will automatically increase AI citation rates.

---

# Step 15 — Prioritize recommendations

Prioritization should consider multiple dimensions:

```text
Priority =
    Impact
  × Severity
  × Confidence
  × Reach
  ─────────────────
       Effort
```

The exact calculation is an internal implementation detail.

Consider:

* potential impact
* number of affected pages
* importance of the affected content
* severity
* confidence
* implementation effort
* whether one change can resolve multiple findings

Prefer:

```text
One high-leverage root-cause fix
```

over:

```text
Five low-impact cosmetic fixes
```

When two actions have similar impact, prefer the one supported by stronger evidence and lower effort.

---

# Step 16 — Assign stable finding IDs

Assign final finding IDs only after correlation, deduplication, and merging are complete.

Use:

```text
F-001
F-002
F-003
...
```

This avoids gaps or duplicate IDs when findings are merged during synthesis.

IDs should remain deterministic within a single audit execution.

---

# Step 17 — Final report validation

Before returning the report, validate both the structure and the actual content.

### Structural validation

Confirm:

* valid JSON
* all required root fields are present
* all required finding fields are present
* severity values are valid
* finding IDs are unique
* summary counts match the findings array
* `total_findings` equals the number of findings
* `audited_at` is valid ISO 8601

### Semantic validation

Confirm:

* every material finding has evidence
* recommendations actually correspond to findings
* duplicate findings have been merged
* conflicting findings have been resolved or clearly qualified
* severity is supported by evidence
* proactive recommendations are distinguishable from confirmed defects
* no unsupported guarantees are included

### Scope validation

Confirm:

* the report only describes the audited target
* page-specific findings are not incorrectly described as site-wide
* sampled crawl results are not presented as exhaustive site-wide facts

---

# Output Schema

The final external response must follow the marketplace's required schema.

```json
{
  "site": "example.com",
  "audited_at": "2026-09-05T14:30:00Z",
  "summary": {
    "total_findings": 6,
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 0
  },
  "findings": [
    {
      "id": "F-001",
      "title": "AI Assistant Crawler Access Is Restricted",
      "severity": "critical",
      "evidence": "robots.txt restricts relevant AI retrieval crawlers from accessing essential public content.",
      "suggested_action": {
        "summary": "Review robots.txt directives and allow appropriate AI retrieval access to public content where intentional discoverability is desired.",
        "priority": "high"
      }
    }
  ]
}
```

The orchestrator should not expose internal orchestration state unless the marketplace schema explicitly allows it.

---

# Failure Handling

A child skill failing should not automatically invalidate the complete audit.

Use graceful degradation:

```text
Discoverability succeeds
Engagement fails
        ↓
Return discoverability findings
        +
Clearly identify incomplete engagement coverage
```

Never invent results for a skill that did not complete.

When a child skill fails:

1. Record the failure internally.
2. Retry only when the failure looks transient and retrying is safe.
3. Avoid repeated expensive crawls.
4. Continue with independent skills.
5. Reduce confidence where missing evidence affects the conclusion.
6. Report incomplete coverage when it materially changes how the results should be interpreted.

---

# Sampling and Coverage

The orchestrator must distinguish between:

```text
Observed on sampled pages
```

and:

```text
Confirmed site-wide
```

For example, an issue found on 2 out of 15 sampled pages should not automatically be described as a site-wide defect.

Where useful, track scope internally as:

```text
site
section
page
sample
```

The final wording should preserve this distinction.

---

# Security and Crawl Safety

The orchestrator works in read-only mode.

Never:

* submit forms
* authenticate
* modify site content
* upload data
* execute site-provided scripts outside the intended rendering environment
* follow arbitrary external actions
* expose credentials or secrets

Child crawlers must continue to enforce their own robots and network safety policies.

The orchestrator must never bypass them.

---

# Extensibility

The orchestrator should make it easy to add future marketplace skills without having to rewrite the existing domain logic.

Potential future skills could include:

```text
technical-seo-audit
accessibility-audit
content-quality-audit
conversion-audit
performance-audit
trust-audit
schema-audit
```

The overall model stays the same:

```text
Discover capabilities
        ↓
Build dependency graph
        ↓
Execute applicable skills
        ↓
Aggregate evidence
        ↓
Cross-skill reasoning
        ↓
Prioritize
        ↓
Unified assessment
```

The orchestrator owns **coordination and reasoning**.

Each specialized skill owns **its own domain expertise**.

---

# Final Principle

The orchestrator should not be the largest skill simply because it contains the most audit logic.

It should be the most important skill because it turns independent measurements into a useful, coherent decision:

```text
                  SPECIALIZED SKILLS
                         │
            ┌────────────┼────────────┐
            ↓            ↓            ↓
         Signals      Evidence     Metrics
            │            │            │
            └────────────┼────────────┘
                         ↓
                ORCHESTRATOR
                         │
              ┌──────────┼──────────┐
              ↓          ↓          ↓
          Correlate   Resolve    Prioritize
              │          │          │
              └──────────┼──────────┘
                         ↓
                  UNIFIED ASSESSMENT
                         │
                         ↓
                 ACTIONABLE REPORT
```

**The goal is not to run more audits.**

**The goal is to get more useful intelligence out of the audits that already exist.**
