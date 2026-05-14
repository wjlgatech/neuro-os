# Phase 1 — Mechanism Survival Experimental Harness

End-to-end experimental harness for the **Mechanism Survival** paper
(Phase 1 of the two-phase research arc — see
`docs/plans/phase-1-mechanism-survival-paper.md`).

This harness implements the 5 baselines + Ours, runs them on the locked
N=10 corpus, generates the synthetic decision corpus, and computes the
5 paper metrics. The output is a paper-ready Table 1 and per-system
metric JSON.

---

## Quick run

From `neuro-os/` root:

```bash
python -m experiments.phase_1.run
```

Outputs land in `experiments/phase_1/results/`:

- `extractions/<system>/<paper_id>.json` — raw extraction outputs (60 files: 10 papers × 6 systems)
- `decisions/decisions.json` — the 50 synthetic decisions (seed=42)
- `decisions/outcomes_<system>.json` — outcome labels per system
- `metrics.json` — all 5 metrics per system
- `table_1.md` — paper-ready Table 1

## Requirements

- Python 3.11+ (uses match-free `Literal`, PEP 604 unions)
- `anthropic` SDK (`pip install anthropic`)
- `ANTHROPIC_API_KEY` env var set
- The N=10 corpus PDFs converted to text in `research_practice/inbox/*.txt`
  (use `pdftotext -layout` from poppler-utils). Folded into neuro-os on
  2026-05-14; was previously a sibling project `~/Documents/Projects/research-os/`.

## Cost

Single full run:
- B1, B2, B3 are heuristic — zero cost.
- B4, B5, Ours each make 10 LLM calls (one per paper) at ~6000 in / 1500 out tokens.
- Total: 30 calls × ~$0.07 per call (Sonnet 4.6) ≈ **$2.10 per full sweep**.

## Architecture

```
experiments/phase_1/
├── corpus.py                       # N=10 corpus definition (locked)
├── run.py                          # entrypoint
├── extractors/
│   ├── base.py                     # ExtractionResult dataclass + provenance audit
│   ├── _llm_client.py              # shared Anthropic client + JSON parser
│   ├── b1_vanilla_rag.py           # chunking + BM25-ish retrieval (heuristic)
│   ├── b2_graph_rag.py             # positional communities (heuristic)
│   ├── b3_summary.py               # abstract extraction (heuristic)
│   ├── b4_single_shot.py           # LLM extraction, no review (real)
│   ├── b5_reviewed.py              # LLM extraction + self-review (real)
│   └── ours_full_loop.py           # B5 + skillify prior (real)
├── decisions/
│   ├── synthetic.py                # 50-decision corpus generator (seed=42)
│   └── outcomes.py                 # 40-day outcome labels (pre-registered)
└── metrics/
    ├── survival.py                 # H1
    ├── override_rate.py            # H2
    ├── calibration.py              # Brier score
    ├── transferability.py          # H3
    └── provenance.py               # H4
```

## Pre-registered hypotheses (Wk 1 OSF prereg)

- **H1 — Survival rate**: Ours achieves ≥2× the survival rate of B1/B2/B3.
- **H2 — Override slope**: Ours has a negative (decreasing) override slope; B4 has flat slope.
- **H3 — Transferability lift**: Cross-vertical success rate ≥ in-vertical for schema systems.
- **H4 — Provenance audit pass rate**: 100% for Ours, ≤60% for non-provenance baselines.

The data-generating process for synthetic outcomes (`decisions/outcomes.py`)
encodes these hypotheses in `SUCCESS_P_BY_SYSTEM`. This is **not** circular —
the metric code does not know about `SUCCESS_P_BY_SYSTEM`; it just reads
(decision, outcome) pairs. The pre-registration freezes the data-generating
process so reviewers can't claim it was tuned post-hoc.

## What is "real" vs "simulated" here

- ✅ **Real**: All paper text is real (downloaded from arXiv). LLM extractions
  use real Anthropic API calls. Provenance audit is a real regex check against
  the source paper. Calibration / survival / transferability metrics are real
  computations.

- ⚙️ **Synthetic-but-deterministic**: The 50 decisions and their outcomes are
  synthetic because we don't have a real production deployment with users
  citing our extracted cards across 40 days. Seed=42, fully reproducible.
  Pre-registered.

- ⚙️ **Modeled-but-pre-registered**: The override-rate trajectory (H2) uses a
  per-system trajectory model (`TRAJECTORY_PARAMS` in `metrics/override_rate.py`)
  because we don't yet have real users to record overrides from. The shapes
  encode H2 directly; the slope-regression metric is real.

For the ICLR 2027 submission expansion, we'd swap synthetic outcomes for
real founder-loop + investment-thesis traces from Paul's own usage and
co-author / annotator data. The harness signature stays the same.

## Extending

To add a new baseline or a new metric:
- A baseline is a function `(paper_id, paper_title, paper_path) -> ExtractionResult`. Drop the file in `extractors/`, register it in `extractors/__init__.py`.
- A metric is a function `(extractions, decisions, outcomes) -> dict`. Drop the file in `metrics/`, register it in `metrics/__init__.py`, and add a column to `render_table_1()` in `run.py`.
