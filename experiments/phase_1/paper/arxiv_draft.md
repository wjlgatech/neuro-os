# Mechanism Survival: Toward a Downstream-Outcome Eval Methodology for AI Research Assistants

**Paul Wu** (independent)

Companion code: `https://github.com/wjlgatech/neuro-os`
Schema source: `agent/research/ontology.py`
N=10 gold cards: `tests/fixtures/research/gold/`
Experimental harness: `experiments/phase_1/`
**Live demo:** `streamlit run world_os/app.py` — interactive UI for the
provenance audit and inter-rater diff (see `world_os/DESIGN_BRIEF.md`).

> **Position paper.** This is a methodology proposal with a small empirical
> wedge — not a full empirical study. We argue for a new eval objective
> (mechanism survival in downstream decisions), release the schema and a
> 10-paper corpus of hand-extracted mechanism cards, and report two
> measured findings (the provenance audit gap and inter-rater agreement
> on the mechanism field). The full empirical validation — survival,
> override-rate, calibration, and transferability across real downstream
> citations — requires real-world citation data that we are integrating
> for a follow-up paper (see Section 7); we explicitly do not claim those
> results here.

---

## Abstract

Existing AI-for-research benchmarks evaluate language models on summary
fidelity (BLEU, ROUGE, retrieval@k, faithfulness) — proxies that fail to
ask whether the extracted understanding actually predicts reality.
We argue the right objective is **mechanism survival**: whether an
extracted mechanism continues to be cited in successful downstream
decisions over a sustained window. We propose three components: (1) a
`MechanismCard` schema operationalizing reading as four falsifiable
commitments (mechanism, invariant, prediction, failure mode) with
mandatory verbatim provenance pinning; (2) a 5-metric eval framework
(citation survival, override-rate trajectory, calibration,
transferability lift, provenance audit); (3) a closed-loop extraction
pipeline combining an in-context skillify prior and an LLM self-review
step. We release the schema (Pydantic-validated), a 10-paper hand-
extracted gold-card corpus spanning continual learning, world models,
embodied AI, and AI evaluation, and a reproducible experimental
harness. We report two empirical observations from this harness:
**LLMs (Sonnet 4.6) paraphrase verbatim source excerpts ~50% of the
time despite explicit prompt instructions and threatened regex audit**;
and **a single human annotator and the LLM independently agree at 90%
strong-agreement rate on the mechanism field, but only 10% on the
prediction field**, suggesting the mechanism field is reproducible
while predictions are intrinsically multimodal. Full empirical
validation of the survival metric on real downstream-citation data
(S2ORC, OpenReview multi-reviewer) is in progress for a follow-up
paper.

---

## 1. Introduction

A common pattern in 2025-era AI tooling: a researcher pipes a paper
through an LLM, asks for a summary, copies it into their notes, and
moves on. The community has invested heavily in making this pipeline
faster (better RAG, better embeddings) and more faithful (less
hallucination, better citation grounding). What we have *not* asked is
whether the resulting summaries help the researcher *do something
useful* — make a better investment thesis, ship a better product,
catch a real failure mode in their own work.

This paper argues that the right unit of evaluation for AI-assisted
research is not the summary but the **mechanism** — the causal
structure the paper rests on — and that the right test of whether the
mechanism was extracted correctly is whether it survives being cited
in adjacent decisions over a sustained window. We call this
**mechanism survival**.

### 1.1 The gap in current benchmarks

Existing benchmarks for AI research assistants fall into three families:

- **Retrieval-quality** (RAG, GraphRAG, BM25 leaderboards): whether
  the right chunks are retrieved for a query.
- **Faithfulness** (citation grounding, hallucination detection):
  whether generated text is supported by retrieved chunks.
- **Summary fidelity** (BLEU, ROUGE, judge-based scoring): whether the
  summary captures what's in the source.

None of these measure whether what was *extracted* actually predicts
reality. A perfectly faithful summary of a continual-learning paper
that doesn't capture the mechanism (e.g., Fisher-weighted parameter
protection in Kirkpatrick 2017) leaves the reader unable to predict
what happens when they apply the technique elsewhere. The summary
scored high on every existing benchmark and was useless.

### 1.2 What we propose

We propose three components:

1. **The `MechanismCard` schema** operationalizes reading as four
   falsifiable commitments — mechanism (causal structure), invariant
   (transferable property), prediction (falsifiable consequence),
   failure mode (specific breaking condition) — each pinned to a
   verbatim source excerpt for audit.

2. **A 5-metric eval framework** based on downstream citations:
   citation survival, override-rate trajectory, calibration on the
   prediction field, transferability lift across adjacent verticals,
   and provenance audit pass rate. The framework is implementable
   on real citation data (S2ORC, OpenReview); we describe the
   integration path in Section 7.

3. **A closed-loop extraction pipeline** that combines an in-context
   *skillify prior* (one or more high-quality gold cards as in-context
   examples) and an LLM self-review step. The pipeline is implemented
   in our companion repo and produces real extractions over the N=10
   corpus.

### 1.3 What we measure (and what we do not)

We measure two things in this paper, both empirically grounded in real
LLM behavior on real paper text:

1. **The provenance audit gap** (Section 5): LLM-extracted source
   excerpts substring-match the source paper only ~50% of the time,
   despite explicit prompt instructions to copy verbatim. This holds
   across our schema-based extractors. The deeper finding: removing
   the self-review step crashes audit pass rate from 50% to 10%.

2. **Inter-rater agreement on the mechanism field** (Section 6):
   one human annotator (author) and one LLM (Sonnet 4.6) given the
   same 10 papers and the same schema produce mechanism-field outputs
   that an independent LLM judge rates as strong-agreement 90% of the
   time. Other fields (invariant 40%, failure_mode 30%, prediction
   10%) show lower agreement, with the prediction field admitting
   multiple valid framings of the same paper.

We do **not** claim survival, override-trajectory, calibration, or
transferability results in this paper. Our experimental harness
includes synthetic decision-corpus and outcome modules that can run
end-to-end, but those modules produce parameter-dependent results, not
measurements. A reader interested in the methodology can examine the
harness; a reader looking for empirical evidence of the survival
hypothesis should wait for the real-data follow-up.

### 1.4 Contributions

1. The `MechanismCard` schema — a four-field falsifiable commitment
   structure with mandatory verbatim provenance. Pydantic-validated,
   open-source.
2. The N=10 MechanismCard Bench corpus — hand-extracted gold cards
   spanning continual learning, world models, embodied AI, and AI
   evaluation literature, with field-level audit notes.
3. A 5-metric eval framework specification (definitions, formal
   metric implementations in `experiments/phase_1/metrics/`) that is
   ready to run against real downstream-citation data.
4. Two empirical findings: the 50% provenance audit gap and the 90%
   strong-agreement rate on the mechanism field between independent
   annotators.
5. An open-source experimental harness reproducible end-to-end at
   ~$0.80 in Anthropic API spend.

---

## 2. Background: what reading means

The motivating framing is that a reader who has extracted a mechanism
from a paper can answer four questions:

- **Mechanism**: What CAUSAL structure generates the paper's behavior?
- **Invariant**: What stays the same across all the cases the paper
  covers?
- **Prediction**: A falsifiable consequence of the mechanism.
- **Failure mode**: A specific condition under which the mechanism
  breaks.

A reader who only has a summary can usually answer none of these, or
answers them with hedging that prevents downstream commitment. This
framing echoes Tetlock's forecasting calibration work (Karger et al.
2024), Pearl's causal hierarchy, and the AI evaluation methodology
critiques (Liang et al. 2022). What is new in our proposal is
operationalizing it as a schema mandatory at extraction time,
auditable post-hoc via verbatim provenance, and tied to a downstream
outcome window.

---

## 3. Related work

The closest neighbors to our work and where each falls short:

| Family | Representative | What it measures | What it misses |
|---|---|---|---|
| RAG / GraphRAG | Lewis 2020; Edge 2024 | retrieval@k, faithfulness | does the retrieved fact predict reality |
| LLM-as-judge for science | Lin 2024 | pairwise quality | no downstream outcome |
| KG extraction | REBEL; GenIE | triple F1 | triples ≠ mechanisms |
| Forecaster benchmarks | Karger 2024 | "did the prediction survive?" | per-question, not per-paper |
| Holistic LM eval | HELM (Liang 2022) | multi-metric matrix | scenarios ≠ research-assistant tasks |
| Citation classification | Scite.ai | supporting/contrasting | per-citation, not per-mechanism |
| Faithfulness benchmarks | TruthfulQA; attribution | source-supported claims | source presence ≠ mechanism extraction |

Closest in methodology stance is **HELM** (Liang 2022) — we adopt
its top-down taxonomy + multi-metric philosophy. Closest in evaluation
framing is **forecaster benchmarks** (Karger 2024; Halawi 2024) — we
adapt their "did the prediction survive?" loop to per-paper
granularity. Closest in data substrate is **Scite.ai** — but they
classify individual citations, not mechanism extractions.

What no prior work does: combine the schema (closest neighbor: KG
extraction, but they measure triple F1 not mechanism survival), the
downstream-outcome eval (closest: forecaster benchmarks, but not
per-paper), and the closed-loop reproducibility pipeline (closest:
nothing).

---

## 4. The MechanismCard schema

The schema is a frozen Pydantic model with four core falsifiable
fields plus mandatory provenance:

```
MechanismCard:
  id:                str (≤64)        # short slug
  paper_title:       str (≤400)
  paper_source:      str (≤400)       # DOI / arXiv id / cite
  mechanism:         str (≤600)       # causal structure
  invariant:         str (≤400)       # transferable property
  prediction:        str (≤400)       # falsifiable consequence
  failure_mode:      str (≤400)       # specific breaking condition
  source_excerpt:    str (≤500)       # VERBATIM, regex-audited
  # Layer-1 deepening (optional):
  first_principle, anti_pattern, transferability_test,
  verdict ∈ {foundational, useful, misleading, skip},
  one_sentence_compression
```

Field-length budgets are enforced at construction time. The
`source_excerpt` field is the load-bearing audit pin — its content
must substring-match the source paper after light whitespace
normalization, or the card fails provenance audit (Section 5).

We released 10 hand-extracted gold cards as the initial corpus,
covering papers selected for **mechanism diversity** rather than topic
coverage:

| Paper | Family |
|---|---|
| Kirkpatrick 2017 (EWC) | CL — regularization |
| Ha & Schmidhuber 2018 (World Models) | World Models — RNN+VAE |
| Pellegrini 2019 (Latent Replay) | CL — storage rehearsal |
| Lopez-Paz 2017 (GEM) | CL — gradient constraint |
| Rusu 2016 (Progressive Networks) | CL — architecture growth |
| Hafner 2023 (Dreamer V3) | World Models — RSSM |
| Micheli 2023 (IRIS) | World Models — Transformer |
| Brohan 2023 (RT-2) | Embodied AI — VLA |
| Open X-Embodiment 2023 | Embodied AI — cross-embodiment |
| Liang 2022 (HELM) | Eval methodology |

The four CL papers span four distinct mechanisms; the three
world-model papers span three distinct dynamics architectures. The
structural argument: if the schema can encode all 10 within field-
length budgets and the cards remain internally consistent, the schema
is doing its job. (It does; all 10 validate.) The corpus serves both
as benchmark and as the priors source for the closed-loop pipeline.

---

## 5. Empirical finding 1: the provenance audit gap

### 5.1 Setup

For each of the N=10 papers, we ran six extraction systems:

- **B1 — Vanilla RAG**: BM25-style retrieval over 500-char chunks.
- **B2 — GraphRAG-flavored**: positional communities (intro/method/discussion).
- **B3 — Summary-only**: abstract + first 2 sentences of introduction.
- **B4 — Single-shot MechanismCard**: LLM (Sonnet 4.6) with the schema prompt.
- **B5 — Reviewed MechanismCard**: LLM + self-review step.
- **Ours_full_loop**: B5 + in-context skillify prior (one gold card example).

For schema-based systems (B4, B5, Ours), the prompt explicitly
instructs the LLM to output a verbatim quote from the paper as
`source_excerpt`, and warns that this field will be regex-audited
against the source paper. The audit logic is in
`experiments/phase_1/extractors/base.py`:

```python
def verify_excerpt_in_text(excerpt, text) -> bool:
    def norm(s): return re.sub(r"\s+", " ", s.lower().strip())
    return norm(excerpt) in norm(text)
```

That is: case-insensitive, whitespace-normalized substring match.
This is the *most permissive* version of verbatim audit — punctuation
differences and casing don't count against the LLM.

### 5.2 Result

| System | Audit pass rate | Verbatim copy attempts |
|---|---|---|
| B1, B2, B3 | 0% | structurally impossible (no excerpt field) |
| B4 single-shot | **20%** | 2 of 10 |
| B5 reviewed | **50%** | 5 of 10 |
| Ours_full_loop | **50%** | 5 of 10 |
| Ours_minus_review (ablation) | **10%** | 1 of 10 |

**The headline: Sonnet 4.6 paraphrases roughly half of its claimed
verbatim quotes despite explicit instructions and threatened audit.**
The self-review step approximately doubles the verbatim-copy rate
(20% → 50%), and removing the review crashes it back to 10%. The
skillify prior in Ours_full_loop does not further improve over B5
on this specific metric (both 50%).

### 5.3 Why this matters

For a downstream-outcome eval methodology to be defensible, provenance
must be auditable. We pre-registered the expectation that Ours would
achieve 100% pass rate (since the prompt and the audit make the
requirement explicit). The observed 50% gap is the kind of LLM-behavior
finding that should constrain how schema-based extraction systems are
deployed in research-assistant tooling: **verbatim provenance is not
free, and explicit instructions are insufficient without a verify-and-
retry loop or grammar-constrained decoding.**

Two mitigations we did not implement, both straightforward:
- **Verify-and-retry**: if `verify_excerpt_in_text` returns False,
  regenerate with corrective feedback. Adds ~1 extra LLM call per
  failing extraction, costing roughly 50% more for the same audit pass
  rate ceiling.
- **Grammar-constrained decoding**: force the JSON output's
  `source_excerpt` field to be a copy from a token range in the input
  paper. Requires a constrained-decoding stack (e.g. lm-format-enforcer
  or guidance) but eliminates the failure mode by construction.

We flag both as the natural next steps for a v2 paper.

---

## 6. Empirical finding 2: inter-rater agreement on the mechanism field

### 6.1 Setup

To establish that the schema captures *reproducible* structure rather
than annotator-private associations, we compared two independent
extractions of the same N=10 papers:

- **Annotator A (human)**: hand-written gold cards
  (`tests/fixtures/research/gold/*.json`).
- **Annotator B (LLM)**: Sonnet 4.6 extractions from Ours_full_loop.

For each of 10 papers × 4 fields = 40 paired cells, we computed:
- **Jaccard token overlap** (deterministic).
- **Substantive agreement** via an independent LLM judge (same model,
  separate prompt) classifying each (paper, field) pair as
  `strong / partial / weak`.

### 6.2 Result

| Field | Strong-agreement % |
|---|---|
| **mechanism** | **90%** (9 of 10) |
| invariant | 40% (4 of 10) |
| failure_mode | 30% (3 of 10) |
| prediction | 10% (1 of 10) |

Overall: 42% strong / 50% partial / 8% weak across 40 paired labels.

### 6.3 Reading

**The 90% strong-agreement rate on the mechanism field is the
load-bearing reproducibility result.** Given the same paper text, a
human annotator and an LLM converge on the same causal structure 9
times out of 10. The schema's primary field captures real structure
of the paper, not annotator-private associations.

The lower agreement on `prediction` (10%) and `failure_mode` (30%) is
also a real finding: these fields admit multiple valid framings of
the same paper. For example, the EWC paper supports at least two
valid failure modes (nullspace under-estimation in the Laplace
approximation; adversarial distribution shift) and our two annotators
picked different ones. Both are correct; agreement is low because the
underlying answer space is intrinsically multimodal.

### 6.4 Honest caveats

The coefficient we report is **not Cohen's κ proper**. Cohen's κ
requires two independent judges making categorical assignments on the
same items; we have a single LLM judge per pair. We report
`Bennett's S = 2·P(strong) − 1`, an upper bound on chance-corrected
agreement. For a v2 paper, we plan to swap in a second independent
judge — either a paid human annotator or a different-family LLM
(e.g. GPT-5 or Gemini family) — to compute true κ. Additionally,
N=10 papers is small; the per-field agreement rates have meaningful
binomial confidence intervals (e.g. 90% on N=10 has 95% CI roughly
[55%, 99.8%]).

### 6.5 Methodological implication

We argue that **field-level reliability reporting is methodologically
necessary** for any schema-based eval to be trustworthy. A single
aggregate κ would have hidden the 90/40/30/10 split. Future
schema-based extraction work should report per-field reliability
explicitly.

---

## 7. Toward real-data validation

Our experimental harness includes synthetic decision-corpus and
outcome modules
(`experiments/phase_1/decisions/{synthetic.py,outcomes.py}`) that
make the pipeline runnable end-to-end. These modules use a
deterministic seed and hand-set per-system success probabilities to
demonstrate the metric implementations. **Their outputs are
parameter-dependent and do not constitute measurements of survival,
trajectory, calibration, or transferability.** We explicitly do not
claim those results in this paper.

The real-data substrate for the survival metric is openly available
and we are integrating it for a follow-up paper. The specific sources:

- **Semantic Scholar Open Research Corpus (S2ORC)** — each paper in
  our N=10 corpus has hundreds of real downstream citations with
  citation contexts. Real "decisions" citing our extracted cards.
- **OpenAlex** — citation-of-citation chains and venue / impact
  metadata. Real outcome signals (later citation count of the citing
  paper, venue tier).
- **Scite.ai** — citation classifications (supporting / contrasting /
  mentioning). Real human-annotated labels on citation quality.
- **OpenReview** — for accepted papers in N=10, multiple independent
  reviewers provided real inter-rater data. We will compute true
  Cohen's κ on the same 40 paired labels in v2.
- **Replication Markets / DARPA SCORE** — actual replication outcomes
  for a subset of papers, providing a ground-truth "did the
  mechanism survive in the world" signal.

The integration plan and function signatures are documented in
`experiments/phase_1/decisions/TODO_REAL_DATA.md` in the companion
repo. The metric implementations themselves do not change — they
read `(decision, outcome)` pairs regardless of source.

### 7.1 Honest scoping

The full empirical claims that depend on real-data integration —
"Ours achieves N% citation-level survival vs M% for vanilla RAG",
"the override-rate trajectory decreases monotonically", etc. — are
out of scope for this position paper. The next version of this paper
will include them once the S2ORC + OpenAlex pipelines are integrated
(target: Q3 2026).

We chose to release the methodology proposal + the two real findings
now rather than wait for the empirical scale-up because (a) the
schema, the corpus, and the eval framework are independently useful;
(b) the provenance gap and the mechanism-field reproducibility result
are themselves publishable findings; (c) other researchers may want
to integrate real-data sources independently rather than waiting for
us.

---

## 8. Conclusions

We argued that AI-for-research evaluation should be downstream and
mechanism-centric rather than intrinsic and summary-centric. We
released a four-field `MechanismCard` schema, a 10-paper hand-
extracted corpus, and a reproducible experimental harness ready to
run against real downstream-citation data. We reported two empirical
findings: (1) LLMs paraphrase ~50% of "verbatim" source excerpts
despite explicit instructions and audit threats; the self-review
step is the strongest mitigation we tested. (2) Independent human and
LLM annotators agree at 90% strong-agreement on the mechanism field
but only 10% on the prediction field, suggesting the mechanism field
captures real structure while predictions are intrinsically
multimodal.

We do **not** claim survival, trajectory, calibration, or
transferability results in this paper; those depend on real
downstream-decision data we are integrating from S2ORC, OpenAlex,
Scite.ai, and OpenReview for a follow-up paper.

### Open source

All artifacts under MIT in the companion repo:

- Schema: `agent/research/ontology.py`
- 10 gold cards: `tests/fixtures/research/gold/`
- 6 extractors: `experiments/phase_1/extractors/`
- 5 metric implementations: `experiments/phase_1/metrics/`
- Real-data integration roadmap: `experiments/phase_1/decisions/TODO_REAL_DATA.md`
- **Live demo UI**: `world_os/app.py` (`streamlit run`) — three working
  surfaces visualizing the provenance audit and the inter-rater finding
  on real data. v1 (Next.js 16) tracked in `world_os/DESIGN_BRIEF.md`.

Total Anthropic API cost to reproduce the two empirical findings:
~$0.50 (70 calls × ~$0.07/call at Sonnet 4.6 pricing). Wall-clock:
~15 minutes on a laptop with a valid `ANTHROPIC_API_KEY`.

---

## References

(Abbreviated — full BibTeX in source.)

1. Kirkpatrick, J., et al. (2017). Overcoming catastrophic forgetting in neural networks. *PNAS* 114(13). arXiv:1612.00796.
2. Ha, D., & Schmidhuber, J. (2018). World Models. *NeurIPS 2018*. arXiv:1803.10122.
3. Pellegrini, L., Graffieti, G., Lomonaco, V., & Maltoni, D. (2019). Latent Replay for Real-Time Continual Learning. *IROS 2020*. arXiv:1912.01100.
4. Lopez-Paz, D., & Ranzato, M. (2017). Gradient Episodic Memory for Continual Learning. *NeurIPS 2017*. arXiv:1706.08840.
5. Rusu, A. A., et al. (2016). Progressive Neural Networks. arXiv:1606.04671.
6. Hafner, D., et al. (2023). Mastering Diverse Domains through World Models (DreamerV3). arXiv:2301.04104.
7. Micheli, V., Alonso, E., & Fleuret, F. (2023). Transformers are Sample-Efficient World Models. *ICLR 2023*. arXiv:2209.00588.
8. Brohan, A., et al. (2023). RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control. arXiv:2307.15818.
9. Open X-Embodiment Collaboration. (2023). Open X-Embodiment: Robotic Learning Datasets and RT-X Models. arXiv:2310.08864.
10. Liang, P., et al. (2022). Holistic Evaluation of Language Models. *TMLR 2023*. arXiv:2211.09110.
11. Lewis, P., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*.
12. Edge, D., et al. (2024). GraphRAG: A Graph-based Approach to Question Answering. (Microsoft Research).
13. Karger, E., Schoelkopf, S., Halawi, D., et al. (2024). Forecasting future world events with neural networks.
14. Lo, K., Wang, L. L., Neumann, M., Kinney, R., & Weld, D. (2020). S2ORC: The Semantic Scholar Open Research Corpus. *ACL 2020*.
15. Nicholson, J. M., et al. (2021). scite: A smart citation index that displays the context of citations and classifies their intent using deep learning. *Quantitative Science Studies*.
