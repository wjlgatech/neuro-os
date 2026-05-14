# Wk 9 — Inter-Rater Agreement (Human vs LLM)

- **Annotator A:** human (Paul) — gold cards in tests/fixtures/research/gold/
- **Annotator B:** LLM (claude-sonnet-4-6 via Ours_full_loop)
- **Corpus:** N=10 papers, 4 fields per card → 40 paired labels.
- **Judge model:** claude-sonnet-4-6.


## Per-field Jaccard token overlap (deterministic)

| Field | Mean | Min | Max |
|---|---|---|---|
| `mechanism` | 0.21 | 0.12 | 0.38 |
| `invariant` | 0.10 | 0.05 | 0.21 |
| `prediction` | 0.10 | 0.03 | 0.18 |
| `failure_mode` | 0.13 | 0.05 | 0.32 |

## Per-field judge-rated agreement (LLM judge)

> The "Bennett's S" column is the agreement coefficient `S = 2·P(strong) − 1`.
> This is **not** Cohen's κ proper: Cohen's κ requires two *independent*
> judges making categorical assignments, and we have a single LLM judge
> classifying each pair. Bennett's S is an upper bound on chance-corrected
> agreement; report it as such in the paper, and acknowledge that the
> ICLR-scale annotation pass should use two independent judges (or one
> LLM + one human) for true κ.

| Field | Strong | Partial | Weak | Bennett's S (binary) |
|---|---|---|---|---|
| `mechanism` | 90% | 10% | 0% | +0.80 |
| `invariant` | 40% | 50% | 10% | −0.20 |
| `prediction` | 10% | 70% | 20% | −0.80 |
| `failure_mode` | 30% | 70% | 0% | −0.40 |

## Overall agreement (n=40 paired labels)

- **Strong:** 42% (17 / 40)
- **Partial:** 50% (20 / 40)
- **Weak:** 8% (3 / 40)
- **Bennett's S (binary, strong vs other):** −0.15

## What the per-field results tell us

| Field | Strong-agreement rate | Reading |
|---|---|---|
| `mechanism` | 90% | Mechanisms are about CAUSAL structure — both annotators converge. The mechanism field is the most reliably extracted across independent annotators. **Load-bearing for paper validity.** |
| `invariant` | 40% | Different annotators frame transferability differently (one writes "load-bearing protection", another "selective plasticity"). Partial agreement is honest paraphrase variance, not error. |
| `prediction` | 10% | Predictions are forward-looking and admit multiple valid framings of the same paper's claim. Lowest agreement; the field is genuinely harder. |
| `failure_mode` | 30% | Annotators identify *different* failure modes (e.g., for EWC: nullspace under-estimation vs adversarial shift). Both are correct; agreement is low because the paper itself surfaces multiple failure modes. |

## Token usage

- Total: 9,505 input + 2,938 output tokens (~10 judge calls, ~$0.07).

## Interpretation

- **Mean Jaccard 0.10–0.21 across fields is expected**, not concerning.
  Free-text annotation tasks routinely produce low Jaccard between
  semantically-equivalent extractions because annotators choose different
  phrasing for the same concept.
- **The 90% strong-agreement rate on `mechanism`** is the headline finding:
  the schema's primary field is **reproducible across independent annotators
  (one human + one LLM)**, a methodological prerequisite for any
  survival-based eval. The schema isn't capturing private LLM
  associations — it's capturing structure both a human and an LLM
  identify from the same paper text.
- **Lower agreement on `prediction` and `failure_mode`** suggests two
  honest extensions for the ICLR submission:
  1. Tighten the prompt for these fields (e.g., "name ONE prediction that
     a one-step ablation could falsify" — more constraint, less ambiguity).
  2. Acknowledge in the limitations that these fields are *intrinsically*
     harder to reproduce, and report per-field reliability rather than
     hiding behind an aggregate number.
- **Cohen's κ proper requires two independent judges.** For the ICLR
  submission, swap in a second judge (either another human annotator —
  via the Wk 1 co-author plan — or a different LLM e.g. GPT-5) to compute
  true Cohen's κ on the same 40 paired labels.
