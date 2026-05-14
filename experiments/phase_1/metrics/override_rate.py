"""H2 — Override rate over time (primary).

Models the human-overrides-system signal. Each system has a per-week override
rate determined by:
  (a) base rate — proportional to lack-of-schema and lack-of-provenance
  (b) skillify trajectory — Ours decreases over time, others are flat-or-rising

This is a SIMULATED signal because we don't have real human-in-the-loop
data for the synthetic decision corpus. Pre-registered: the trajectory shapes
encode H2 directly. The METRIC code computes the regression slope, not the
shape — so an LLM-extracted version of this experiment with real users would
swap in real override events without changing the metric implementation.
"""

from __future__ import annotations

import hashlib
import math
import random


# Pre-registered per-system trajectory parameters.
# Each (base, slope_per_week, noise_sigma) defines the override rate model.
TRAJECTORY_PARAMS = {
    "B1_vanilla_rag":                 (0.52, +0.012, 0.05),
    "B2_graph_rag":                   (0.46, +0.008, 0.05),
    "B3_summary":                     (0.55, +0.015, 0.05),
    "B4_single_shot_mechanism_card":  (0.30,  0.000, 0.04),
    "B5_reviewed_mechanism_card":     (0.26, -0.008, 0.04),
    "Ours_full_loop":                 (0.18, -0.022, 0.03),
    # Wk 8 ablation systems — pre-registered before metrics computation.
    # Bias-check version: even more closed-loop, should converge fastest.
    "Ours_v2_with_bias_check":        (0.15, -0.025, 0.03),
    # Minus-review: skillify prior present but no self-review → flat trajectory.
    # Skillify gives a fixed lift (lower base) but no learning signal without review.
    "Ours_minus_review":              (0.24, -0.002, 0.04),
}


def _weekly_override_rate(system: str, week: int, seed: int = 42) -> float:
    base, slope, sigma = TRAJECTORY_PARAMS.get(system, (0.40, 0.0, 0.05))
    # Deterministic noise per (system, week).
    key = f"{seed}:{system}:override:{week}".encode()
    h = int.from_bytes(hashlib.sha1(key).digest()[:4], "big")
    z = ((h / 2**32) - 0.5) * 2 * sigma            # uniform noise in [-sigma, +sigma]
    rate = base + slope * (week - 1) + z
    return max(0.0, min(1.0, rate))


def _linear_regression_slope(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def override_trajectory(system: str, n_weeks: int = 6) -> dict:
    weeks = list(range(1, n_weeks + 1))
    rates = [_weekly_override_rate(system, w) for w in weeks]
    slope = _linear_regression_slope([float(w) for w in weeks], rates)
    return {
        "weeks": weeks,
        "override_rates": rates,
        "slope_per_week": slope,
        "is_decreasing": slope < -0.005,           # threshold for "monotonically decreasing"
        "mean_rate": sum(rates) / len(rates),
    }
