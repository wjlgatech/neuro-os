# Phase 1 — Table 1: Mechanism Survival Eval (N=10 corpus, 50 decisions, seed=42)

| System | H1 Citation Survival | H2 Slope (Δ/wk) | H3 Lift | H4 Provenance | Calibration |
|---|---|---|---|---|---|
| **B1_vanilla_rag** | 0.26 (13/50) | +0.015 | 0.42 | 0.00 | n/a |
| **B2_graph_rag** | 0.42 (21/50) | +0.020 | 1.44 | 0.00 | n/a |
| **B3_summary** | 0.28 (14/50) | +0.026 | 1.30 | 0.00 | n/a |
| **B4_single_shot_mechanism_card** | 0.58 (29/50) | +0.004 | 0.74 | 0.20 | Brier=0.250, |Δp|=0.08 |
| **B5_reviewed_mechanism_card** | 0.70 (35/50) | -0.008 | 1.38 | 0.50 | Brier=0.220, |Δp|=0.10 |
| **Ours_full_loop** | 0.78 (39/50) | -0.021 | 0.92 | 0.50 | Brier=0.172, |Δp|=0.03 |

**Legend:**
- **H1 Citation Survival** — fraction of decisions citing this system's extraction that succeed at day 40. Card-level survival saturates at N=10 papers (every paper gets multiple citations); citation-level is the unsaturated signal.
- **H2 Slope** — regression slope of override rate vs week. **Negative** = override rate decreases (Ours: skillify prior accumulating evidence); flat/positive = no learning.
- **H3 Lift** — cross-vertical success rate ÷ native-vertical success rate. ≥1.0 means cross-vertical transfer works. Noisy at N=15 cross-vertical decisions; expected to stabilize at N=200+.
- **H4 Provenance** — fraction of cards whose source_excerpt was verbatim-located in the source paper. Schema-less baselines have no excerpt by construction (0%); LLM-based systems partially copy verbatim despite explicit instructions (50% — a real LLM-behavior finding).
- **Calibration** — Brier score + |expected_p − observed_p| for the prediction field. N/A for systems without a prediction field.

See `findings.md` for full per-hypothesis analysis and implications for the ICLR scale-up.
