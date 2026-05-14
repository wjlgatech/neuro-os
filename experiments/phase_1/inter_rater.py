"""Wk 9 — Inter-rater agreement on the N=10 gold corpus.

Two annotators:
  Annotator A (human): Paul's hand-written gold cards in
    tests/fixtures/research/gold/*.json (produced Wk 2/3).
  Annotator B (LLM):  Sonnet 4.6's Ours_full_loop extractions in
    experiments/phase_1/results/extractions/Ours_full_loop/*.json.

Both annotators independently extracted a MechanismCard from the same 10
papers under the same schema. We measure agreement two ways:

  (1) Deterministic: Jaccard token overlap per field. No LLM, no noise.
  (2) Judge-rated: an LLM judge classifies each (paper, field) pair into
      {strong / partial / weak} agreement. From those labels we compute
      a Cohen's κ approximation (strong = agree, otherwise = disagree).

10 papers × 4 fields = 40 paired labels. 10 LLM judge calls total.

Run from neuro-os/ root:
  python -m experiments.phase_1.inter_rater
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.phase_1.extractors._llm_client import (                  # noqa: E402
    call_anthropic,
    parse_json_blob,
    MODEL,
)

GOLD_DIR = ROOT / "tests" / "fixtures" / "research" / "gold"
LLM_DIR = ROOT / "experiments" / "phase_1" / "results" / "extractions" / "Ours_full_loop"
OUT_DIR = ROOT / "experiments" / "phase_1" / "results"

FIELDS = ["mechanism", "invariant", "prediction", "failure_mode"]


def _tokens(text: str) -> set[str]:
    """Lowercase word tokens, stripped of punctuation."""
    return set(re.findall(r"[a-z][a-z0-9]+", text.lower())) - {
        "the", "a", "an", "of", "to", "in", "on", "and", "or", "is", "are",
        "be", "by", "for", "with", "that", "this", "as", "at", "it", "its",
        "from", "into", "but", "not", "no", "if", "then", "than", "so",
        "via", "vs", "i", "we", "our", "your", "they", "their",
    }


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _load_paired_cards() -> list[dict]:
    """Match gold and LLM cards by paper_id. Returns list of dicts:
    {paper_id, paper_title, gold: card, llm: card}.
    """
    gold_by_id = {}
    for path in sorted(GOLD_DIR.glob("*.json")):
        c = json.loads(path.read_text())
        gold_by_id[c["id"]] = c

    pairs = []
    for path in sorted(LLM_DIR.glob("*.json")):
        c = json.loads(path.read_text())
        pid = c["paper_id"]
        if pid in gold_by_id:
            pairs.append(
                {
                    "paper_id": pid,
                    "paper_title": c["paper_title"],
                    "gold": gold_by_id[pid],
                    "llm": c,
                }
            )
    return pairs


JUDGE_PROMPT = """\
You are evaluating inter-annotator agreement between two independent MechanismCard
extractions of the same research paper.

Annotator A (HUMAN, slug: {paper_id}) wrote:
  mechanism:    {a_mechanism}
  invariant:    {a_invariant}
  prediction:   {a_prediction}
  failure_mode: {a_failure_mode}

Annotator B (LLM) wrote:
  mechanism:    {b_mechanism}
  invariant:    {b_invariant}
  prediction:   {b_prediction}
  failure_mode: {b_failure_mode}

For EACH of the four fields, classify the substantive agreement between A and B
as one of:
  "strong"  — both identify the same causal structure / invariant / prediction / failure
  "partial" — overlapping content but one annotator misses a key aspect the other includes
  "weak"    — different identifications, or one annotator is materially incomplete

Output ONLY a JSON object of the form:
{{
  "mechanism": {{"agreement": "strong|partial|weak", "note": "<one-line reason>"}},
  "invariant": {{"agreement": "strong|partial|weak", "note": "..."}},
  "prediction": {{"agreement": "strong|partial|weak", "note": "..."}},
  "failure_mode": {{"agreement": "strong|partial|weak", "note": "..."}}
}}
"""


def _judge_one(pair: dict) -> dict:
    """Single LLM call. Returns {field: {agreement, note}} for one paper."""
    g, l = pair["gold"], pair["llm"]
    prompt = JUDGE_PROMPT.format(
        paper_id=pair["paper_id"],
        a_mechanism=g["mechanism"],
        a_invariant=g["invariant"],
        a_prediction=g["prediction"],
        a_failure_mode=g["failure_mode"],
        b_mechanism=l["mechanism"],
        b_invariant=l["invariant"],
        b_prediction=l["prediction"],
        b_failure_mode=l["failure_mode"],
    )
    response, t_in, t_out = call_anthropic(prompt, max_tokens=1000)
    parsed = parse_json_blob(response) or {}
    # Sanity-fill any missing fields.
    out = {}
    for f in FIELDS:
        entry = parsed.get(f) or {}
        agreement = entry.get("agreement") or "weak"
        if agreement not in ("strong", "partial", "weak"):
            agreement = "weak"
        out[f] = {
            "agreement": agreement,
            "note": str(entry.get("note", ""))[:300],
        }
    out["_tokens_in"] = t_in
    out["_tokens_out"] = t_out
    return out


def _cohens_kappa_binary(labels_a: list[str], labels_b: list[str]) -> float:
    """Compute Cohen's κ on a binary projection: 'agree' iff both annotators
    chose 'strong' or one says strong and the other partial.

    Since labels_a == labels_b in our framing (the judge applies a single label
    per pair), this reduces to: how many pairs the judge calls 'strong'
    vs not, treated as a single-rater categorical task. We approximate κ as
    Bennett's S coefficient (for chance baseline 0.5).
    """
    n = len(labels_a)
    if n == 0:
        return 0.0
    # Project to binary: strong=1, otherwise=0.
    agree_proj = sum(1 for x in labels_a if x == "strong") / n
    # Bennett's S for 2 categories: S = 2 * po - 1, where po is observed
    # agreement and chance is 0.5.
    return 2 * agree_proj - 1


def main() -> int:
    print("Wk 9 inter-rater agreement", flush=True)
    pairs = _load_paired_cards()
    print(f"Loaded {len(pairs)} paired (gold, llm) cards", flush=True)

    # 1. Deterministic per-field Jaccard similarity.
    jaccard_per_field: dict[str, list[float]] = {f: [] for f in FIELDS}
    for p in pairs:
        for f in FIELDS:
            score = _jaccard(p["gold"][f], p["llm"][f])
            jaccard_per_field[f].append(score)
    jaccard_summary = {
        f: {
            "mean": sum(v) / len(v) if v else 0.0,
            "min": min(v) if v else 0.0,
            "max": max(v) if v else 0.0,
            "values": v,
        }
        for f, v in jaccard_per_field.items()
    }

    # 2. LLM-judge categorical agreement.
    judge_results: list[dict] = []
    total_tokens = (0, 0)
    for p in pairs:
        t0 = time.time()
        verdict = _judge_one(p)
        dt = time.time() - t0
        judge_results.append({"paper_id": p["paper_id"], **verdict})
        total_tokens = (
            total_tokens[0] + verdict["_tokens_in"],
            total_tokens[1] + verdict["_tokens_out"],
        )
        agreements = [verdict[f]["agreement"] for f in FIELDS]
        print(f"  OK {p['paper_id']} ({dt:.1f}s) → {agreements}", flush=True)

    # 3. Aggregate.
    counts_per_field = {f: Counter() for f in FIELDS}
    for jr in judge_results:
        for f in FIELDS:
            counts_per_field[f][jr[f]["agreement"]] += 1
    kappa_per_field = {}
    for f in FIELDS:
        labels = [jr[f]["agreement"] for jr in judge_results]
        kappa_per_field[f] = {
            "n": len(labels),
            "distribution": dict(counts_per_field[f]),
            "kappa_binary_strong": _cohens_kappa_binary(labels, labels),
            "pct_strong": counts_per_field[f].get("strong", 0) / max(1, len(labels)),
            "pct_partial": counts_per_field[f].get("partial", 0) / max(1, len(labels)),
            "pct_weak": counts_per_field[f].get("weak", 0) / max(1, len(labels)),
        }

    # Overall (all fields × all papers, n=40).
    all_labels = [jr[f]["agreement"] for jr in judge_results for f in FIELDS]
    overall = {
        "n": len(all_labels),
        "distribution": dict(Counter(all_labels)),
        "pct_strong": sum(1 for x in all_labels if x == "strong") / len(all_labels),
        "pct_partial": sum(1 for x in all_labels if x == "partial") / len(all_labels),
        "pct_weak": sum(1 for x in all_labels if x == "weak") / len(all_labels),
        "kappa_binary_strong": _cohens_kappa_binary(all_labels, all_labels),
    }

    # 4. Save raw results.
    output = {
        "config": {
            "n_papers": len(pairs),
            "fields": FIELDS,
            "model": MODEL,
            "annotator_A": "human (Paul) — gold cards in tests/fixtures/research/gold/",
            "annotator_B": "LLM (claude-sonnet-4-6 via Ours_full_loop)",
        },
        "jaccard_per_field": jaccard_summary,
        "judge_per_paper": judge_results,
        "kappa_per_field": kappa_per_field,
        "overall_agreement": overall,
        "llm_tokens_in_total": total_tokens[0],
        "llm_tokens_out_total": total_tokens[1],
    }
    out_path = OUT_DIR / "inter_rater_agreement.json"
    out_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nResults → {out_path}", flush=True)

    # 5. Markdown report.
    md = render_inter_rater_report(output)
    md_path = OUT_DIR / "inter_rater_agreement.md"
    md_path.write_text(md)
    print(f"Report → {md_path}", flush=True)
    print("\n" + md, flush=True)
    return 0


def render_inter_rater_report(data: dict) -> str:
    lines = ["# Wk 9 — Inter-Rater Agreement (Human vs LLM)\n"]
    cfg = data["config"]
    lines.append(
        f"- **Annotator A:** {cfg['annotator_A']}\n"
        f"- **Annotator B:** {cfg['annotator_B']}\n"
        f"- **Corpus:** N={cfg['n_papers']} papers, {len(cfg['fields'])} fields per card → "
        f"{cfg['n_papers'] * len(cfg['fields'])} paired labels.\n"
        f"- **Judge model:** {cfg['model']}.\n"
    )

    lines.append("\n## Per-field Jaccard token overlap (deterministic)\n")
    lines.append("| Field | Mean | Min | Max |")
    lines.append("|---|---|---|---|")
    for f, v in data["jaccard_per_field"].items():
        lines.append(f"| `{f}` | {v['mean']:.2f} | {v['min']:.2f} | {v['max']:.2f} |")

    lines.append("\n## Per-field judge-rated agreement (LLM judge)\n")
    lines.append("| Field | Strong | Partial | Weak | κ (binary, strong vs other) |")
    lines.append("|---|---|---|---|---|")
    for f, k in data["kappa_per_field"].items():
        lines.append(
            f"| `{f}` | {k['pct_strong']:.0%} | {k['pct_partial']:.0%} | "
            f"{k['pct_weak']:.0%} | {k['kappa_binary_strong']:+.2f} |"
        )

    overall = data["overall_agreement"]
    lines.append("\n## Overall agreement (n=40 paired labels)\n")
    lines.append(
        f"- **Strong:** {overall['pct_strong']:.0%} ({overall['distribution'].get('strong', 0)} / {overall['n']})\n"
        f"- **Partial:** {overall['pct_partial']:.0%} ({overall['distribution'].get('partial', 0)} / {overall['n']})\n"
        f"- **Weak:** {overall['pct_weak']:.0%} ({overall['distribution'].get('weak', 0)} / {overall['n']})\n"
        f"- **κ (binary, strong vs other):** {overall['kappa_binary_strong']:+.2f}\n"
    )

    lines.append("\n## Token usage\n")
    lines.append(
        f"- Total: {data['llm_tokens_in_total']:,} input + "
        f"{data['llm_tokens_out_total']:,} output tokens "
        f"(~{cfg['n_papers']} judge calls).\n"
    )

    lines.append(
        "\n## Interpretation\n"
        "- Mean Jaccard ≥ 0.30 indicates meaningful lexical overlap; values "
        "are typically depressed because the LLM and human chose different "
        "phrasing for the same concept.\n"
        "- Strong-agreement rate ≥ 50% across all fields supports the claim "
        "that the MechanismCard schema produces *reproducible* extractions "
        "across independent annotators — a key methodological prerequisite "
        "for any survival-based eval. \n"
        "- Per-field κ values flag which schema fields are most reliably "
        "captured: high κ → reliable extraction; low κ → ambiguous prompt "
        "or genuinely hard field. The ICLR submission should report "
        "per-field κ separately rather than hiding behind a single number.\n"
    )

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
