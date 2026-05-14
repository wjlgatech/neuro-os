# Phase 1 — Table 2: Ablation Study (Wk 8)

| Arm | Citation Survival | H2 Slope | H3 Lift | H4 Provenance | Calibration |
|---|---|---|---|---|---|
| **Ours_v2_with_bias_check_FULL** | 0.74 (37/50) | -0.022 | 1.12 | 0.40 | Brier=0.193, |Δp|=0.03 |
| **Ours_v2_minus_bias_check** | 0.78 (39/50) | -0.021 | 0.92 | 0.50 | Brier=0.172, |Δp|=0.03 |
| **Ours_v2_minus_skillify** | 0.70 (35/50) | -0.008 | 1.38 | 0.50 | Brier=0.220, |Δp|=0.10 |
| **Ours_v2_minus_review** | 0.74 (37/50) | -0.000 | 1.26 | 0.10 | Brier=0.199, |Δp|=0.08 |
| **Ours_v2_minus_cross_vertical** | 0.71 (25/35) | -0.022 | n/a | 0.40 | Brier=0.207, |Δp|=0.06 |

**Read this table as `full − component = ablated arm`.**
- **−bias-check**: drops the post-extraction bias-flagging pass. Predicted: small effect on raw survival, larger effect on calibration.
- **−skillify**: removes the in-context gold example prior. Predicted: degrades to B5_reviewed quality.
- **−review**: removes the self-review step. Predicted: degrades between B4 and B5.
- **−cross-vertical**: keeps extractions, filters decisions to native-vertical only (the 35 in-vertical decisions). Tests whether cross-vertical citations carry the headline result or just dilute it.
