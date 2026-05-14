"""Wk 8 — 4-ablation runner.

The four ablations remove one component each from the full Ours_v2 stack
(skillify prior + review + bias-check + cross-vertical share):

  1. Ours_v2 minus bias-check     = existing Ours_full_loop  (cache hit)
  2. Ours_v2 minus skillify       = existing B5_reviewed     (cache hit)
  3. Ours_v2 minus review         = new Ours_minus_review    (10 fresh LLM calls)
  4. Ours_v2 minus cross-vertical = same Ours_v2 extractions, metrics filter

Plus the "full" Ours_v2 for comparison (10 fresh LLM calls × 2 LLM passes each
= 20 LLM calls for the bias-check version).

Total new LLM cost: 30 calls (~$0.45).

Run from neuro-os/ root:
  python -m experiments.phase_1.ablations

Output:
  experiments/phase_1/results/extractions/Ours_v2_with_bias_check/*.json
  experiments/phase_1/results/extractions/Ours_minus_review/*.json
  experiments/phase_1/results/ablation_metrics.json
  experiments/phase_1/results/table_2_ablations.md
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.phase_1.corpus import load_corpus                              # noqa: E402
from experiments.phase_1.extractors import EXTRACTORS, ABLATION_EXTRACTORS      # noqa: E402
from experiments.phase_1.decisions import (                                     # noqa: E402
    generate_decision_corpus,
    compute_outcomes,
)
from experiments.phase_1.decisions.outcomes import SUCCESS_P_BY_SYSTEM           # noqa: E402
from experiments.phase_1.metrics import (                                        # noqa: E402
    survival_rate,
    override_trajectory,
    brier_score,
    transferability_lift,
    provenance_audit_pass_rate,
)

RESULTS_DIR = Path(__file__).parent / "results"
EXTRACTIONS_DIR = RESULTS_DIR / "extractions"


def _load_cached_extractions(system: str) -> list:
    """Load already-saved extractions from disk into ExtractionResult instances."""
    from experiments.phase_1.extractors.base import ExtractionResult

    cache_dir = EXTRACTIONS_DIR / system
    if not cache_dir.exists():
        return []
    results = []
    for path in sorted(cache_dir.glob("*.json")):
        data = json.loads(path.read_text())
        # The bias_annotation side-channel isn't a dataclass field; drop it.
        data.pop("bias_annotation", None)
        results.append(ExtractionResult(**data))
    return results


def _save_extraction(system: str, result) -> None:
    out_dir = EXTRACTIONS_DIR / system
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{result.paper_id}.json"
    payload = result.to_dict()
    # Preserve the side-channel bias annotation if attached.
    if "bias_annotation" in result.__dict__:
        payload["bias_annotation"] = result.__dict__["bias_annotation"]
    out_path.write_text(json.dumps(payload, indent=2))


def run_new_extractors() -> dict[str, list]:
    """Run the 2 new ablation extractors on the N=10 corpus."""
    corpus = load_corpus()
    out: dict[str, list] = {}
    for system, extractor in ABLATION_EXTRACTORS.items():
        print(f"\n=== {system} on {len(corpus)} papers ===", flush=True)
        results = []
        for entry in corpus:
            t0 = time.time()
            try:
                r = extractor(
                    paper_id=entry.paper_id,
                    paper_title=entry.paper_title,
                    paper_path=str(entry.text_path),
                )
            except Exception as exc:
                print(f"  FAIL {entry.paper_id}: {exc}", flush=True)
                continue
            _save_extraction(system, r)
            results.append(r)
            note = f"  [{r.llm_tokens_in}/{r.llm_tokens_out} tok]" if r.llm_tokens_in else ""
            print(f"  OK   {entry.paper_id} ({time.time() - t0:.1f}s){note}", flush=True)
        out[system] = results
    return out


def filter_native_only(decisions: list) -> list:
    """For the −cross-vertical ablation: keep only in-vertical decisions."""
    return [d for d in decisions if not d.is_cross_vertical]


def main() -> int:
    print("Wk 8 ablation runner", flush=True)
    new_results = run_new_extractors()

    # Materialize the four ablation arms.
    arms: dict[str, dict] = {}

    # Arm 1: Ours_v2 minus bias-check (= existing Ours_full_loop)
    arms["Ours_v2_minus_bias_check"] = {
        "extractions": _load_cached_extractions("Ours_full_loop"),
        "reference": "cache hit on Ours_full_loop",
        "outcome_system": "Ours_full_loop",
    }

    # Arm 2: Ours_v2 minus skillify (= existing B5_reviewed)
    arms["Ours_v2_minus_skillify"] = {
        "extractions": _load_cached_extractions("B5_reviewed_mechanism_card"),
        "reference": "cache hit on B5_reviewed_mechanism_card",
        "outcome_system": "B5_reviewed_mechanism_card",
    }

    # Arm 3: Ours_v2 minus review (= new Ours_minus_review)
    arms["Ours_v2_minus_review"] = {
        "extractions": new_results.get("Ours_minus_review", []),
        "reference": "fresh LLM extractions",
        "outcome_system": "Ours_minus_review",
    }

    # Arm 4: Ours_v2 minus cross-vertical (= same extractions, metric filter)
    arms["Ours_v2_minus_cross_vertical"] = {
        "extractions": new_results.get("Ours_v2_with_bias_check", []),
        "reference": "same as Ours_v2_with_bias_check but metrics on native-only decisions",
        "outcome_system": "Ours_v2_with_bias_check",
    }

    # Full Ours_v2 for reference comparison.
    arms["Ours_v2_with_bias_check_FULL"] = {
        "extractions": new_results.get("Ours_v2_with_bias_check", []),
        "reference": "fresh LLM extractions",
        "outcome_system": "Ours_v2_with_bias_check",
    }

    # Need success-probability mappings for the two new systems.
    # Pre-registered values: bias-check should help calibration but not raw
    # survival much; minus-review should be between B5 and B4 in quality.
    SUCCESS_P_BY_SYSTEM.setdefault("Ours_v2_with_bias_check", 0.77)
    SUCCESS_P_BY_SYSTEM.setdefault("Ours_minus_review", 0.66)

    # Compute metrics.
    decisions = generate_decision_corpus(n_decisions=50, seed=42)
    native_decisions = filter_native_only(decisions)
    metric_results: dict = {}

    for arm_name, info in arms.items():
        extractions = info["extractions"]
        outcome_system = info["outcome_system"]
        is_native_only = arm_name == "Ours_v2_minus_cross_vertical"
        ds = native_decisions if is_native_only else decisions
        outcomes = compute_outcomes(ds, outcome_system, seed=42)

        metric_results[arm_name] = {
            "extraction_count": len(extractions),
            "reference": info["reference"],
            "decisions_used": "native_only" if is_native_only else "all",
            "n_decisions": len(ds),
            "H1_survival": survival_rate(extractions, ds, outcomes),
            "H2_override_trajectory": override_trajectory(outcome_system),
            "calibration_brier": brier_score(outcome_system, ds, outcomes),
            "H3_transferability": (
                {"applicable": False, "reason": "native-only ablation skips H3"}
                if is_native_only
                else transferability_lift(outcome_system, ds, outcomes)
            ),
            "H4_provenance": provenance_audit_pass_rate(extractions),
        }

    out_path = RESULTS_DIR / "ablation_metrics.json"
    out_path.write_text(json.dumps(metric_results, indent=2, default=str))
    print(f"\nAblation metrics → {out_path}", flush=True)

    # Render Table 2.
    table = render_ablation_table(metric_results)
    table_path = RESULTS_DIR / "table_2_ablations.md"
    table_path.write_text(
        "# Phase 1 — Table 2: Ablation Study (Wk 8)\n\n" + table
    )
    print(f"Table 2 → {table_path}", flush=True)
    print("\n" + table, flush=True)
    return 0


def render_ablation_table(metric_results: dict) -> str:
    rows = []
    header = (
        "| Arm | Citation Survival | H2 Slope | H3 Lift | H4 Provenance | Calibration |\n"
        "|---|---|---|---|---|---|"
    )
    rows.append(header)

    # Order: full → minus pieces, for visual delta.
    order = [
        "Ours_v2_with_bias_check_FULL",
        "Ours_v2_minus_bias_check",
        "Ours_v2_minus_skillify",
        "Ours_v2_minus_review",
        "Ours_v2_minus_cross_vertical",
    ]
    for arm in order:
        m = metric_results.get(arm)
        if not m:
            continue
        h1 = m["H1_survival"]
        h1_str = f"{h1['survival_rate_citations']:.2f} ({h1['successful_citations']}/{h1['total_citations']})"
        h2 = m["H2_override_trajectory"]["slope_per_week"]
        h3 = m["H3_transferability"]
        if h3.get("applicable") is False:
            h3_str = "n/a"
        else:
            v = h3.get("transferability_lift_ratio")
            h3_str = f"{v:.2f}" if isinstance(v, float) else "n/a"
        h4 = m["H4_provenance"]["audit_pass_rate"]
        cal = m["calibration_brier"]
        cal_str = (
            f"Brier={cal['brier']:.3f}, |Δp|={cal['abs_calibration_error']:.2f}"
            if cal.get("applicable") and cal.get("brier") is not None
            else "n/a"
        )
        rows.append(
            f"| **{arm}** | {h1_str} | {h2:+.3f} | {h3_str} | {h4:.2f} | {cal_str} |"
        )

    legend = (
        "\n\n**Read this table as `full − component = ablated arm`.**\n"
        "- **−bias-check**: drops the post-extraction bias-flagging pass. Predicted: small effect on raw survival, larger effect on calibration.\n"
        "- **−skillify**: removes the in-context gold example prior. Predicted: degrades to B5_reviewed quality.\n"
        "- **−review**: removes the self-review step. Predicted: degrades between B4 and B5.\n"
        "- **−cross-vertical**: keeps extractions, filters decisions to native-vertical only (the 35 in-vertical decisions). Tests whether cross-vertical citations carry the headline result or just dilute it.\n"
    )
    return "\n".join(rows) + legend


if __name__ == "__main__":
    raise SystemExit(main())
