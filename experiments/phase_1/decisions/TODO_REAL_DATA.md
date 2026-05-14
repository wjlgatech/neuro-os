# Track B — Real-data integration for the mechanism-survival eval

> **Status: Wk 14-20 (Q3 2026) scope.** Do not pull forward.
> Paired with co-author commit (Task #20) and ICLR 2027 submission (Task #23).
>
> The Wk 6-7 synthetic harness (`synthetic.py`, `outcomes.py`) is a **v1
> prototype only**. The Phase 1 position paper (arXiv v1) does NOT claim
> any results that depend on it. The ICLR 2027 submission (v2) replaces
> it with the real-data loaders described here.

---

## Why this file exists

At Wk 6-7 of the Phase 1 sprint (2026-05-12), the original implementation
generated 50 synthetic decisions with seed=42 and hard-coded per-system
success probabilities in `SUCCESS_P_BY_SYSTEM`. Every survival /
trajectory / calibration result downstream was arithmetic on those
stipulated values, not measurement.

The lesson: when real downstream-decision data is missing, the right
move is to **search openly available sources**, not to fabricate.
See `memory/feedback-synthetic-data-is-not-measurement.md` in the
companion memory directory for the structural rule.

The mechanism-survival framing maps cleanly onto real citation data
from open sources. This file lists the specific integrations to do.

---

## What stays the same

The module architecture is correct:

```
experiments/phase_1/decisions/
  __init__.py
  synthetic.py        # v1 prototype — DO NOT EXTEND, keep for reference
  outcomes.py         # v1 prototype — same
  s2orc_loader.py     # NEW (this file): real citation chains
  real_outcomes.py    # NEW (this file): real impact signals
  TODO_REAL_DATA.md   # this file
```

The metric code in `experiments/phase_1/metrics/` does **not** change.
It reads `(decision, outcome)` pairs irrespective of source.

---

## Data sources, ranked by integration cost

### Tier A — minimal cost, maximum coverage

**1. Semantic Scholar Open Research Corpus (S2ORC) — citation chains**
- API: `https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations`
- Free tier: 100 req/min, no signup; signup gets 1000 req/min.
- Pulls each citation of one of our N=10 papers with `paperId`,
  `title`, `year`, `abstract`, `contexts` (the sentences around the
  citation in the citing paper), `intents` (classification: methodology
  / background / result).
- **Implements:** `s2orc_loader.fetch_citations(paper_id) -> list[Citation]`
- **Effort:** ~1 day of coding + caching to avoid rate limits.

**2. OpenAlex — impact metadata**
- API: `https://api.openalex.org/works/{openalex_id}`
- Free, no auth needed. Bulk citation counts, publication venue,
  open-access status.
- **Implements:** `real_outcomes.fetch_impact(paper_id) -> ImpactSignal`
  with citation count at +12 months, +24 months, and venue tier.
- **Effort:** ~0.5 day.

### Tier B — moderate cost, high signal

**3. Scite.ai citation classifications**
- API: `https://api.scite.ai/` (paid; institutional access via
  partnership or ~$200/month individual).
- Returns supporting / contrasting / mentioning labels for each
  citation context — real human-annotated labels on citation quality.
- **Implements:** `real_outcomes.fetch_citation_quality(citation_id)
  -> Literal["supporting", "contrasting", "mentioning"]`
- **Effort:** ~1 day + budget approval for API access.
- **Fallback if budget is tight:** train an LLM-judge classifier on
  the public sample they release, applied to S2ORC citation contexts.

**4. OpenReview multi-reviewer data**
- API: `https://api.openreview.net/`
- For accepted papers in N=10 (most are ICLR/NeurIPS), pull all
  independent reviewers' assessments + meta-reviews + rebuttals.
- **Implements:** `real_outcomes.fetch_reviews(paper_openreview_id)
  -> list[Review]`. Use these as a real multi-rater set for the
  Wk 9-equivalent inter-rater study, computing TRUE Cohen's κ
  (the v1 inter-rater was Bennett's S because we had one LLM judge).
- **Effort:** ~1-2 days, plus careful per-paper mapping (some N=10
  papers are on arXiv-only and don't have OpenReview reviews —
  fall back to those that do).

### Tier C — high cost, optional

**5. Replication Markets / DARPA SCORE — actual replication outcomes**
- Datasets at `https://www.replicationmarkets.com/` (public dumps
  exist).
- Real predictions of paper replication + actual replication outcomes.
- **Use case:** validation of the "mechanism survival" framing on
  ground-truth replication data — does the field's prediction of
  replication correlate with whether the mechanism continues to be
  cited successfully? This is a separate empirical chapter, not a
  drop-in replacement for `outcomes.py`.
- **Effort:** ~2-3 days; depends on data-domain overlap (SCORE is
  social-science-heavy, less ML; need to find ML-replication datasets).

---

## Function signatures to implement

```python
# s2orc_loader.py
@dataclass(frozen=True)
class CitedDecision:
    """Replaces synthetic.Decision with real-data version."""
    decision_id: str               # f"s2orc_{citing_paper_id}_{cite_idx}"
    cited_paper_id: str            # one of our N=10 paper_ids
    citation_context: str          # text from citing paper around the citation
    citing_paper_id: str           # OpenAlex/S2 ID of the citing paper
    citing_paper_year: int
    citing_paper_venue: Optional[str]
    intent: Literal["methodology", "background", "result"]   # from S2

def fetch_real_decisions(
    paper_id: str,
    max_citations: int = 50,
    min_year: int = 2018,
) -> list[CitedDecision]: ...

# real_outcomes.py
@dataclass(frozen=True)
class RealOutcome:
    decision_id: str
    impact_score: float            # normalized citing-paper impact at +24 months
    accepted_at_top_venue: bool    # NeurIPS / ICLR / ICML / CVPR / ACL / ...
    citation_quality: Optional[Literal["supporting", "contrasting", "mentioning"]]
    # Note: success in real-data sense = accepted_at_top_venue AND citation_quality == "supporting"

def fetch_real_outcomes(decisions: list[CitedDecision]) -> list[RealOutcome]: ...
```

The existing metric code reads `(decision, outcome)` pairs. Mapping:
- `decision.cited_paper_id` → unchanged (matches `extraction.paper_id`)
- `decision.is_cross_vertical` → derive from venue (CL paper cited
  in a robotics venue = cross-vertical)
- `outcome.success` → `accepted_at_top_venue AND citation_quality == "supporting"`

---

## Validation checklist before claiming results

When swapping in real data, the paper claims must change from:

- ❌ "78% citation survival" (was: synthetic Bernoulli with p=0.74)
- ✅ "Of 312 real downstream citations of our N=10 corpus papers,
  Ours-extracted mechanism cards were cited as supporting evidence
  in X% of cases, vs Y% for vanilla RAG"

Specifically before the ICLR submission:

- [ ] Real `s2orc_loader.py` returns ≥200 real decisions across N=10
- [ ] Real `real_outcomes.py` returns outcomes for ≥80% of decisions
- [ ] Run `python -m experiments.phase_1.run` with the new loaders
- [ ] Verify Table 1 changes — old "synthetic" Brier scores must not appear
- [ ] Re-run Wk 8 ablations against real data; the −review provenance
  finding (the one real Wk 8 result) replicates or doesn't — report
  honestly either way.
- [ ] Replace Wk 9 single-judge inter-rater with multi-reviewer
  OpenReview data; compute TRUE Cohen's κ.
- [ ] Rewrite the limitations section to reflect real-data context.

---

## Timeline

- **2026-05-12 (today):** TODO_REAL_DATA.md filed. Position paper v1
  ships without synthetic claims.
- **Wk 14-17 (Aug 2026):** Implement Tier A integrations (S2ORC +
  OpenAlex). Run sanity checks on real citation counts.
- **Wk 18-19 (Sep 2026):** Tier B if budget allows (Scite.ai or
  LLM-judge fallback) + OpenReview multi-reviewer fetch.
- **Wk 19-20 (mid-Sep 2026):** Re-run full Phase 1 pipeline against
  real data. Generate new Table 1, Table 2, Table 3.
- **Sept 24, 2026:** ICLR 2027 submission with real-data v2.

---

## What is NOT in scope for this file

- Recruiting human users to use cards in their own research (that's a
  separate experimental track if the citation-chain proxy proves
  insufficient).
- Changing the schema or extractor logic — those are independent.
- Pulling Track B forward into the position paper (v1 ships without).

---

**Owner:** Paul Wu. Reviewed: 2026-05-12 after the v1 skeleton was
correctly diagnosed.

**Reference memory:** `feedback-synthetic-data-is-not-measurement`,
`phase-1-real-data-substrate` in the companion memory directory.
