# Phase 1 paper artifacts

This directory contains the arXiv preprint for the
[Phase 1 mechanism-survival paper](../../../docs/plans/phase-1-mechanism-survival-paper.md).

## Files

- **`arxiv_draft.md`** — the active position paper draft. Methodology
  proposal + two empirical findings (provenance audit gap, mechanism-
  field inter-rater agreement). ~3,500 words / ~4 typeset pages.
  This is what gets submitted to arXiv.
- **`arxiv_draft_v1_skeleton.md`** — the original 9-page draft that
  was correctly diagnosed as a skeleton because the survival /
  trajectory / calibration / transferability claims rested on
  hand-coded synthetic outcomes. Preserved as a learning artifact;
  **do not submit**.
- **`abstract.txt`** — short submission-form abstract (currently
  matches v1 — needs to be updated to v2 framing before submission).
- **`SUBMISSION_CHECKLIST.md`** — pre-submission gates and arXiv
  form walkthrough.

## What changed v1 → v2

The v1 draft claimed empirical results (78% survival, 1.86×–3.0×
lift, monotonic override trajectory, Brier=0.172, etc.) computed from
a synthetic decision corpus with hand-coded per-system success
probabilities in `decisions/outcomes.py::SUCCESS_P_BY_SYSTEM`. Those
results were arithmetic on stipulated parameters, not measurements.

The v2 draft removes every claim that depends on the synthetic
outcomes. It keeps only:

- The methodology proposal (schema + 5-metric framework).
- The two empirical findings that DO rest on real measurements:
  the provenance audit gap (real LLM behavior on real paper text)
  and the inter-rater agreement on the mechanism field (real human
  + real LLM extracting from real papers).
- A clearly-scoped "Toward real-data validation" section pointing
  at the S2ORC + OpenAlex + OpenReview integration path.

The full real-data validation is on the schedule for Wk 14-20
(Task #23 — Q3 2026, paired with the ICLR 2027 submission).
Track-B integration plan lives in
`../decisions/TODO_REAL_DATA.md`.

## Why we preserved v1

Two reasons. First, the v1 draft is a useful learning artifact for
the lesson encoded in `feedback-synthetic-data-is-not-measurement`
in the companion memory directory — it shows what fabrication
dressed in pre-registration language looks like. Second, the v1
narrative structure is reusable for the v2 paper once real-data
results land; we'll lift sections 6 (Results), 7 (Ablations), and
8 (Reproducibility) from v1 with real data substituted in.

## Updating before submission

Before `python -m experiments.phase_1.submit_arxiv` (or the manual
submission process described in `SUBMISSION_CHECKLIST.md`):

1. Update `abstract.txt` to match the v2 framing.
2. Convert `arxiv_draft.md` to PDF via pandoc or Overleaf.
3. Verify the OSF pre-registration aligns with v2 (the v1 prereg
   covered claims we no longer make; either narrow it to the two
   real findings or withdraw and re-file).
4. Rotate the API key referenced in the session log
   (separate from this directory; see SUBMISSION_CHECKLIST.md).
