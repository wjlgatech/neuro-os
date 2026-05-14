"""world-os v0 — Streamlit demo of the closed-loop research argument.

Three surfaces:
  1. Proposal Inbox — browse 60 real LLM extractions; live provenance audit
  2. Accept/Reject Gate (Law 7) — emit real OverrideEvent on each decision
  3. Cross-rater Diff — side-by-side human vs LLM with judge agreement colors

Run from neuro-os/ root:
    streamlit run world_os/app.py

This app reads ONLY real data on disk. No synthetic survival numbers, no
fake override trajectories, no stipulated outcomes. See DESIGN_BRIEF.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing siblings + neuro-os agent.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

from data_loaders import (  # noqa: E402
    list_papers,
    list_systems,
    load_extraction,
    load_gold,
    load_paper_text,
    load_inter_rater_data,
    locate_excerpt_in_text,
    verify_excerpt_in_text,
    compute_provenance_stats,
)


st.set_page_config(
    page_title="world-os — closed-loop research demo",
    page_icon="📖",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────────────────────
# Top banner
# ─────────────────────────────────────────────────────────────────────────────
st.title("world-os — closed-loop research demo")
st.caption(
    "Live UI for the *Mechanism Survival* position paper. Every surface below "
    "is backed by real measurements on disk: 60 Sonnet 4.6 extractions, 10 "
    "hand-extracted gold cards, real paper text, real inter-rater judge results. "
    "No synthetic survival rates, no stipulated outcomes."
)

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
if "session_decisions" not in st.session_state:
    st.session_state.session_decisions = {}    # (system, paper_id) -> "accept" / "reject"
if "override_events" not in st.session_state:
    st.session_state.override_events = []      # list of dicts (we keep this session-only)


# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "1. Proposal Inbox (live provenance audit)",
    "2. Accept / Reject Gate (Law 7)",
    "3. Cross-rater Diff (human vs LLM)",
    "About",
])

# =============================================================================
# Tab 1 — Proposal Inbox
# =============================================================================
with tab1:
    st.header("Proposal Inbox")
    st.write(
        "Each card is a real LLM extraction from `experiments/phase_1/results/"
        "extractions/`. The `source_excerpt` claim is regex-audited against the "
        "actual paper text (the green/red status below)."
    )

    col_sel, col_card, col_paper = st.columns([1, 2, 3])

    with col_sel:
        st.subheader("Browse")
        systems_avail = list_systems()
        default_idx = systems_avail.index("Ours_full_loop") if "Ours_full_loop" in systems_avail else 0
        system = st.selectbox("System", systems_avail, index=default_idx)

        papers = list_papers()
        labels = [f"{pid[:35]}" for pid, _ in papers]
        paper_idx = st.selectbox(
            "Paper",
            range(len(papers)),
            format_func=lambda i: labels[i],
        )
        paper_id, paper_title = papers[paper_idx]

        st.markdown("---")
        st.subheader(f"{system} stats")
        stats = compute_provenance_stats(system)
        st.metric(
            "Provenance audit pass rate",
            f"{stats['pass_rate']:.0%}",
            help=(
                f"{stats['n_verified']}/{stats['n_total']} extractions in this "
                "system have a source_excerpt that substring-matches the paper "
                "after whitespace+case normalization."
            ),
        )
        st.caption(
            f"{stats['n_with_excerpt']}/{stats['n_total']} cards even claim an "
            "excerpt — schema-less baselines (B1/B2/B3) have no excerpt field."
        )

    extraction = load_extraction(system, paper_id)
    paper_text = load_paper_text(paper_id)

    with col_card:
        st.subheader("Extracted card")
        if extraction is None:
            st.warning(f"No extraction on disk for {system} × {paper_id}")
        else:
            st.markdown(f"**Paper:** {paper_title}")
            st.markdown(f"**Method:** `{extraction.get('extraction_method', 'unknown')}`")

            if extraction.get("has_schema"):
                with st.expander("mechanism", expanded=True):
                    st.write(extraction.get("mechanism", "—"))
                with st.expander("invariant", expanded=True):
                    st.write(extraction.get("invariant", "—"))
                with st.expander("prediction"):
                    st.write(extraction.get("prediction", "—"))
                with st.expander("failure_mode"):
                    st.write(extraction.get("failure_mode", "—"))

                st.markdown("---")
                st.markdown("**Claimed source_excerpt:**")
                excerpt = extraction.get("source_excerpt", "")
                if excerpt:
                    st.text_area(
                        "excerpt", value=excerpt, height=120,
                        label_visibility="collapsed",
                    )
                    verified = verify_excerpt_in_text(excerpt, paper_text)
                    if verified:
                        st.success("✓ Excerpt verified against paper (substring match)")
                    else:
                        st.error(
                            "✗ Excerpt NOT found in paper — LLM paraphrased "
                            "despite explicit verbatim instructions. This is "
                            "the 50% provenance gap the paper measures."
                        )
                else:
                    st.info("No source_excerpt field — schema-less baseline.")
            else:
                # Free-text baseline (B1/B2/B3).
                st.info("Schema-less baseline. Free-text output below.")
                st.text_area(
                    "free_text_output",
                    value=extraction.get("free_text_output", ""),
                    height=400,
                    label_visibility="collapsed",
                )
                st.caption(
                    "No structured fields, no provenance. This is what existing "
                    "RAG / GraphRAG / summary baselines produce — and what the "
                    "schema's four falsifiable fields replace."
                )

    with col_paper:
        st.subheader("Source paper")
        st.caption(f"Plain-text extraction of {paper_id}")
        if not paper_text:
            st.warning("Paper text not found.")
        elif extraction is not None and extraction.get("source_excerpt"):
            excerpt = extraction["source_excerpt"]
            loc = locate_excerpt_in_text(excerpt, paper_text)
            if loc:
                start, end = loc
                window = 800
                pre_start = max(0, start - window // 2)
                post_end = min(len(paper_text), end + window // 2)
                pre = paper_text[pre_start:start]
                hit = paper_text[start:end]
                post = paper_text[end:post_end]
                st.markdown("**Excerpt match (highlighted in green):**")
                # Use HTML for highlight; escape minimally.
                def esc(s):
                    return (s.replace("&", "&amp;").replace("<", "&lt;")
                              .replace(">", "&gt;"))
                html = (
                    f"<div style='background:#f5f5f5;padding:1em;"
                    f"font-family:monospace;font-size:0.85em;"
                    f"max-height:600px;overflow-y:auto;'>"
                    f"…{esc(pre)}"
                    f"<mark style='background:#90EE90;padding:2px;'>{esc(hit)}</mark>"
                    f"{esc(post)}…</div>"
                )
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.warning(
                    "Excerpt does not substring-match the paper. Showing "
                    "first 1,500 chars of the paper for reference."
                )
                st.text_area(
                    "paper_preview", value=paper_text[:1500], height=400,
                    label_visibility="collapsed",
                )
        else:
            st.text_area(
                "paper_preview", value=paper_text[:1500], height=400,
                label_visibility="collapsed",
            )


# =============================================================================
# Tab 2 — Accept / Reject Gate (Law 7)
# =============================================================================
with tab2:
    st.header("Accept / Reject Gate (Law 7)")
    st.write(
        "Reviewing extractions is Law 7 of the AI-Native Engineering Principles. "
        "Each Accept/Reject below emits an `OverrideEvent` recording your "
        "decision — the closed loop's input signal. In the v0 demo these events "
        "are session-local; the production neuro-os pipeline persists them to "
        "`~/.neuro_os_skillified/events.jsonl`."
    )

    review_system = st.selectbox(
        "System to review",
        ["Ours_full_loop", "B5_reviewed_mechanism_card", "B4_single_shot_mechanism_card"],
        key="review_system",
    )

    col_summary, col_pending = st.columns([1, 2])

    with col_summary:
        st.subheader("Session stats")
        n_reviewed = sum(
            1 for (s, _), _ in st.session_state.session_decisions.items()
            if s == review_system
        )
        n_accepted = sum(
            1 for (s, _), v in st.session_state.session_decisions.items()
            if s == review_system and v == "accept"
        )
        n_rejected = n_reviewed - n_accepted
        st.metric("Reviewed this session", n_reviewed)
        st.metric("Accepted", n_accepted)
        st.metric("Rejected", n_rejected)
        st.markdown("---")
        st.caption(
            f"{len(st.session_state.override_events)} override events emitted "
            "in this session."
        )

    with col_pending:
        st.subheader(f"Pending proposals from {review_system}")
        for pid, title in list_papers():
            key = (review_system, pid)
            decision = st.session_state.session_decisions.get(key)
            extr = load_extraction(review_system, pid)
            if extr is None:
                continue

            with st.container():
                st.markdown(f"**{title}**")
                m_preview = (extr.get("mechanism") or "")[:200]
                st.caption(f"`mechanism`: {m_preview}…" if m_preview else "(no mechanism field)")

                bcols = st.columns([1, 1, 1, 3])
                accept_clicked = bcols[0].button(
                    "✓ Accept", key=f"acc_{pid}",
                    disabled=(decision is not None),
                )
                reject_clicked = bcols[1].button(
                    "✗ Reject", key=f"rej_{pid}",
                    disabled=(decision is not None),
                )
                edit_clicked = bcols[2].button(
                    "✎ Edit", key=f"edit_{pid}",
                    disabled=(decision is not None),
                )

                if accept_clicked:
                    st.session_state.session_decisions[key] = "accept"
                    st.session_state.override_events.append({
                        "vertical": "research",
                        "drift_mode": "mechanism_review",
                        "user_action": "accept",
                        "paper_id": pid,
                        "system": review_system,
                    })
                    st.rerun()
                if reject_clicked:
                    st.session_state.session_decisions[key] = "reject"
                    st.session_state.override_events.append({
                        "vertical": "research",
                        "drift_mode": "mechanism_review",
                        "user_action": "reject",
                        "paper_id": pid,
                        "system": review_system,
                        "suggested_action": "accept",      # the system proposed accept
                    })
                    st.rerun()
                if edit_clicked:
                    st.info(
                        "Edit flow not implemented in v0. In production, an edit "
                        "would open the card for revision and emit an override "
                        "event with `user_action='edit'`."
                    )

                if decision == "accept":
                    st.success("✓ Accepted — override event emitted")
                elif decision == "reject":
                    st.error("✗ Rejected — override event emitted (suggested→accept, you→reject)")
                st.markdown("---")

    st.markdown("### Override event log (session-local)")
    if st.session_state.override_events:
        st.json(st.session_state.override_events)
    else:
        st.info("No override events emitted yet. Click Accept or Reject above.")


# =============================================================================
# Tab 3 — Cross-rater Diff
# =============================================================================
with tab3:
    st.header("Cross-rater Diff (human vs LLM)")
    st.write(
        "For each paper, the gold card (hand-written by the human annotator) is "
        "shown side-by-side with the Ours_full_loop extraction (Sonnet 4.6). "
        "Each of the four fields is color-coded by the independent LLM judge's "
        "agreement classification from `inter_rater_agreement.json`."
    )

    ir = load_inter_rater_data()
    if ir is None:
        st.warning("Inter-rater data not found. Run experiments/phase_1/inter_rater.py first.")
    else:
        st.subheader("Per-field strong-agreement rate (across 10 papers)")
        kpf = ir.get("kappa_per_field", {})
        kcols = st.columns(4)
        for col, field in zip(kcols, ["mechanism", "invariant", "prediction", "failure_mode"]):
            v = kpf.get(field, {})
            pct = v.get("pct_strong", 0.0)
            col.metric(field, f"{pct:.0%}", help=f"{int(round(pct*10))} of 10 papers")

        st.caption(
            "Mechanism's 90% is the headline reproducibility finding: human and "
            "LLM converge on the same causal structure. Prediction's 10% reflects "
            "that forward-looking claims admit multiple valid framings."
        )

        st.markdown("---")
        st.subheader("Per-paper side-by-side")

        AGREE_COLOR = {
            "strong":  "#d4edda",   # green-ish
            "partial": "#fff3cd",   # yellow-ish
            "weak":    "#f8d7da",   # red-ish
        }

        for jrow in ir.get("judge_per_paper", []):
            pid = jrow["paper_id"]
            gold = load_gold(pid)
            llm = load_extraction("Ours_full_loop", pid)
            if not gold or not llm:
                continue

            with st.expander(f"📄 {gold['paper_title']}", expanded=False):
                fcols = st.columns([1, 1, 1])
                fcols[0].markdown("**Field**")
                fcols[1].markdown("**Gold (human)**")
                fcols[2].markdown("**Ours_full_loop (LLM)**")

                for field in ["mechanism", "invariant", "prediction", "failure_mode"]:
                    agreement = jrow.get(field, {}).get("agreement", "weak")
                    note = jrow.get(field, {}).get("note", "")
                    color = AGREE_COLOR.get(agreement, "#eeeeee")

                    fcols = st.columns([1, 1, 1])
                    fcols[0].markdown(
                        f"<div style='background:{color};padding:0.5em;'>"
                        f"**{field}**<br/>"
                        f"<small><i>{agreement}</i></small></div>",
                        unsafe_allow_html=True,
                    )
                    fcols[1].markdown(
                        f"<div style='background:{color};padding:0.5em;font-size:0.85em;'>"
                        f"{gold.get(field, '')}</div>",
                        unsafe_allow_html=True,
                    )
                    fcols[2].markdown(
                        f"<div style='background:{color};padding:0.5em;font-size:0.85em;'>"
                        f"{llm.get(field, '')}</div>",
                        unsafe_allow_html=True,
                    )
                if any(jrow.get(f, {}).get("note") for f in ["mechanism", "invariant", "prediction", "failure_mode"]):
                    st.caption("Judge's per-field notes:")
                    for field in ["mechanism", "invariant", "prediction", "failure_mode"]:
                        n = jrow.get(field, {}).get("note", "")
                        if n:
                            st.caption(f"• **{field}**: {n}")


# =============================================================================
# Tab 4 — About
# =============================================================================
with tab4:
    st.header("About world-os")
    st.markdown("""
This is a v0 demo of the user-facing surface for the closed-loop research
system described in the *Mechanism Survival* paper. It exists to make the
paper's argument **tangible in 60 seconds** rather than abstract.

### What the three surfaces show

- **Proposal Inbox** — every LLM extraction is just a JSON file on disk.
  The provenance audit is a regex check against the source paper. The 50%
  pass rate is real LLM behavior, measurable live.
- **Accept/Reject Gate** — the Law 7 review surface. Every action emits a
  real `OverrideEvent` (session-local in v0, persistent in production).
- **Cross-rater Diff** — independent extractions by a human (Paul, hand-
  written gold cards) and an LLM (Sonnet 4.6 via Ours_full_loop) on the
  same 10 papers. Color-coded by the agreement an independent LLM judge
  gave each (paper, field) pair. The 90% strong-agreement on `mechanism`
  is the headline reproducibility finding.

### What's deliberately missing (v1 surfaces)

Two surfaces from the design brief depend on **real downstream-citation
data** that we haven't integrated yet (Track B = Wk 14-20):

- **Skillify Prior Evolution** — needs real user override data over time.
- **Citation Surface** — needs S2ORC citation chains + Scite.ai
  supporting/contrasting labels.

These will land when Track B brings real data. See
`experiments/phase_1/decisions/TODO_REAL_DATA.md` for the integration plan.

### Tech stack

v0 is Streamlit because it's already in the neuro-os UI stack (`ui/app.py`).
v1 (Q3 2026, when world-os spins off as its own repo) will rebuild on
Next.js 16 + React 19 + shadcn/ui — the same stack OpenMAIC uses, without
borrowing OpenMAIC's AGPL-3.0 license.

### License & links

- License: MIT (planned for spin-off; currently part of neuro-os).
- Source: `world_os/` inside `https://github.com/wjlgatech/neuro-os`.
- Paper: `experiments/phase_1/paper/arxiv_draft.md` (v2 position paper).
- Design brief: `world_os/DESIGN_BRIEF.md`.
    """)
