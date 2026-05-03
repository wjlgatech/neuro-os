"""
Neuro-OS — Streamlit UI.

Run::

    streamlit run ui/app.py

Four tabs designed for first-time visitors:

* **Try It** — paste a sentence, see TRUE scores + decision.
* **Watch It Learn** — feed a citation-rich contradiction, see the
  ontology mutate.
* **Self-Repair** — degrade the priority routing, watch the loop
  find the regression, sandbox-validate a patch, promote it.
* **Readiness** — 5-question gate for whether your own X is a fit
  for ``flywheel-loop``.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Allow running from `streamlit run ui/app.py` at repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from agent.api import ingest_documents, process_text  # noqa: E402
from agent.domains import get_domain  # noqa: E402
from agent.ingestion_pipeline import (  # noqa: E402
    PRIORITY_RULES_PATH,
    classify_evidence_strength,
    run_pipeline,
)
from agent import primitive_feedback, version_registry  # noqa: E402
from agent.self_modification import run_self_modification  # noqa: E402
from flywheel_loop.readiness import QUESTIONS, score_readiness  # noqa: E402


st.set_page_config(
    page_title="Neuro-OS — self-evolving knowledge OS",
    page_icon="🧠",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
      .neuro-hero { padding: 0.5rem 0 1rem 0; }
      .neuro-hero h1 { margin-bottom: 0.25rem; font-size: 2.4rem; }
      .neuro-hero p { color: #6b7280; font-size: 1.05rem; margin-top: 0; }
      .neuro-mech-card {
        border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem;
        background: #f9fafb;
      }
      .pill { padding: 2px 8px; border-radius: 999px; font-size: 0.85rem; }
      .pill.ok    { background: #d1fae5; color: #065f46; }
      .pill.warn  { background: #fef3c7; color: #92400e; }
      .pill.fail  { background: #fee2e2; color: #991b1b; }
      .pill.muted { background: #e5e7eb; color: #374151; }
      code, pre { font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="neuro-hero">
      <h1>🧠 Neuro-OS</h1>
      <p>A self-evolving, self-modifying knowledge OS. Watch it ingest,
         contradict, refine, and (when you break it) repair itself.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def _decision_pill(decision: str) -> str:
    cls = {
        "ACCEPT": "ok",
        "REFINE": "warn",
        "REJECT": "fail",
        "PROMOTED": "ok",
        "ROLLED_BACK": "fail",
    }.get(decision, "muted")
    return f'<span class="pill {cls}">{decision}</span>'


tabs = st.tabs(
    [
        "🟢 Try It",
        "🌱 Watch It Learn",
        "🔧 Self-Repair",
        "📊 Readiness",
        "ℹ️  About",
    ]
)


# ---------------------------------------------------------------------------
# Tab 1 — Try It
# ---------------------------------------------------------------------------

with tabs[0]:
    st.subheader("Paste a sentence. Watch it classify.")
    st.caption(
        "The pipeline maps text to one of five neuroscience primitives, "
        "synthesizes a TRUE-fielded knowledge dict, and decides "
        "ACCEPT / REFINE / REJECT."
    )

    presets = {
        "(write your own)": "",
        "Predictive coding (paper)": (
            "Predictive coding minimizes sensory prediction error across cortical "
            "hierarchy. Friston (2010) frames this as free-energy minimization."
        ),
        "Reinforcement learning (paper)": (
            "Dopamine neurons encode reward prediction error signals — Schultz (1997)."
        ),
        "Attention (paper)": (
            "Attention uses query, key, value gating to route relevant signals — "
            "Vaswani et al. (2017) https://doi.org/10.48550/arXiv.1706.03762."
        ),
        "Out-of-domain (rejection)": (
            "Bananas turn yellow when ripe. They float in fresh water."
        ),
    }
    choice = st.selectbox("Preset (or write your own below):", list(presets.keys()))
    text = st.text_area(
        "Document text:",
        value=presets[choice],
        height=120,
        placeholder="Paste a sentence or paragraph...",
    )

    col_run, _ = st.columns([1, 5])
    if col_run.button("Run", type="primary", key="run_extract"):
        if not text.strip():
            st.warning("Paste some text first.")
        else:
            with st.spinner("Running pipeline..."):
                pipeline = run_pipeline(text)
            knowledge = pipeline["knowledge"]
            scores = pipeline["true_validation"]["scores"]
            decision = pipeline["decision"]

            c1, c2, c3 = st.columns(3)
            c1.metric("Mechanism", knowledge.get("mechanism", "unknown"))
            c2.markdown(
                f"**Decision**<br/>{_decision_pill(decision)}",
                unsafe_allow_html=True,
            )
            c3.metric("Composite TRUE", f"{scores.get('TRUE', 0):.2f}")

            st.markdown("**TRUE per dimension** "
                       "(E = experimentable, U = usable, R = repeatable, T = transferable)")
            st.bar_chart(
                {k: scores.get(k, 0) for k in ("E", "U", "R", "T")},
                horizontal=True,
                use_container_width=True,
            )

            st.markdown(
                f"**Evidence strength** "
                f"(year/author/DOI/URL/arXiv markers): "
                f"`{classify_evidence_strength(text)}`"
            )

            with st.expander("Synthesized knowledge dict"):
                st.json(knowledge)


# ---------------------------------------------------------------------------
# Tab 2 — Watch It Learn (ingestion + ontology mutation)
# ---------------------------------------------------------------------------

with tabs[1]:
    st.subheader("Feed a contradiction. See the ontology mutate.")
    st.caption(
        "When ingestion accepts a contradicting refinement that passes the "
        "golden gate, the canonical definition is overwritten on disk. "
        "This tab uses a temporary ontology file so your live state is untouched."
    )

    default_text = (
        "Vaswani et al. (2017) https://doi.org/10.48550/arXiv.1706.03762 shows "
        "attention does not gate signals; routing is via softmax similarity. "
        "arXiv:1706.03762."
    )
    docs_text = st.text_area(
        "Document(s) to ingest (one per blank-line block):",
        value=default_text,
        height=150,
    )

    if st.button("Ingest", type="primary", key="run_ingest"):
        docs = [d.strip() for d in docs_text.split("\n\n") if d.strip()]
        if not docs:
            st.warning("Provide at least one document.")
        else:
            tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_ui_ingest_"))
            ontology_path = tmp_dir / "ontology.json"
            # Snapshot registry + feedback paths so the UI run doesn't pollute live state.
            version_registry.set_registry_path(tmp_dir / "registry.jsonl")
            primitive_feedback.FEEDBACK_PATH = tmp_dir / "feedback.jsonl"
            primitive_feedback.reset_for_tests()

            with st.spinner("Running self-evolving loop..."):
                report = ingest_documents(
                    docs,
                    ontology_path=ontology_path,
                )

            c1, c2, c3 = st.columns(3)
            c1.metric("Documents", len(docs))
            c2.metric("Merges applied", report["merges_applied"])
            c3.metric("Merges reverted", report["merges_reverted"])

            actions = [e["action"] for e in report["evolutions"]]
            st.markdown(
                "**Evolution actions:** "
                + " ".join(f"`{a}`" for a in actions)
            )

            if ontology_path.exists():
                st.markdown("**Ontology after ingestion** (changed primitives only)")
                final = json.loads(ontology_path.read_text())
                changed = []
                for name, primitive in final["primitives"].items():
                    if primitive.get("sources"):
                        changed.append({
                            "primitive": name,
                            "definition": primitive.get("definition", ""),
                            "sources_added": len(primitive.get("sources", [])),
                        })
                if changed:
                    st.dataframe(changed, use_container_width=True)
                else:
                    st.caption("No primitives mutated — nothing was merged.")

            with st.expander("Full report"):
                st.json(report)


# ---------------------------------------------------------------------------
# Tab 3 — Self-Repair
# ---------------------------------------------------------------------------

with tabs[2]:
    st.subheader("Break a priority rule. Watch flywheel fix it.")
    st.caption(
        "Removes every reinforcement-learning cue from the live priority "
        "routing table. The dopamine golden then misclassifies. Click "
        "**Run flywheel** and the meta-loop observes the regression, "
        "proposes an allowlisted patch, validates it in a sandbox subprocess, "
        "and promotes it back to disk if it passes the golden gate."
    )

    if "snapshot_rules" not in st.session_state:
        st.session_state.snapshot_rules = PRIORITY_RULES_PATH.read_text(
            encoding="utf-8"
        )

    current = json.loads(PRIORITY_RULES_PATH.read_text(encoding="utf-8"))
    rl_count = sum(1 for r in current if r[1] == "reinforcement_learning")

    c1, c2 = st.columns(2)
    c1.metric("Total priority rules", len(current))
    c2.metric("RL cues remaining", rl_count)

    cb1, cb2, cb3 = st.columns(3)
    if cb1.button("⚠️  Break it (drop RL cues)", key="break_btn"):
        rules = json.loads(st.session_state.snapshot_rules)
        degraded = [r for r in rules if r[1] != "reinforcement_learning"]
        PRIORITY_RULES_PATH.write_text(
            json.dumps(degraded, indent=2) + "\n", encoding="utf-8"
        )
        st.success(
            f"Dropped {len(rules) - len(degraded)} reinforcement-learning cues."
        )
        st.rerun()

    if cb2.button("▶️  Run flywheel", type="primary", key="run_flywheel"):
        # Use a temp registry so the UI run doesn't pollute the live log.
        tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_ui_repair_"))
        version_registry.set_registry_path(tmp_dir / "registry.jsonl")
        primitive_feedback.FEEDBACK_PATH = tmp_dir / "feedback.jsonl"
        primitive_feedback.reset_for_tests()

        with st.spinner("Observing → proposing → sandboxing → validating..."):
            report = run_self_modification(
                get_domain("neuro_os_self_v1")
            )

        st.markdown(
            f"**Status:** {_decision_pill(report['status'])}",
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Baseline accuracy", f"{report['baseline']['accuracy']}")
        c2.metric("Patches proposed", report["patched_proposals"])
        c3.metric("Merges applied", report.get("merges_applied", 0))

        if report["results"]:
            outcome = report["results"][0]
            st.markdown("**Patch payload**")
            st.json(outcome["patch"])
            st.markdown("**Rollback patch**")
            st.json(outcome["apply"]["inverse"])
            if outcome.get("validators"):
                st.markdown("**Validators**")
                st.dataframe(
                    [
                        {
                            "name": v.get("name"),
                            "success": v.get("success"),
                            "details": (
                                f"acc={v['accuracy']}"
                                if "accuracy" in v
                                else (
                                    f"imported={len(v.get('imported', []))}"
                                    if "imported" in v
                                    else ""
                                )
                            ),
                        }
                        for v in outcome["validators"]
                    ],
                    use_container_width=True,
                )
            promote = outcome.get("promote") or {}
            if promote.get("live_apply_success"):
                st.success(
                    f"✓ Promoted to live tree: {promote.get('files', [])}"
                )

    if cb3.button("↩️  Restore canonical", key="restore_btn"):
        PRIORITY_RULES_PATH.write_text(
            st.session_state.snapshot_rules, encoding="utf-8"
        )
        st.success("Priority rules restored from session snapshot.")
        st.rerun()

    with st.expander("Current priority_rules.json"):
        st.code(
            PRIORITY_RULES_PATH.read_text(encoding="utf-8"),
            language="json",
        )


# ---------------------------------------------------------------------------
# Tab 4 — Readiness
# ---------------------------------------------------------------------------

with tabs[3]:
    st.subheader("Is your X ready for flywheel?")
    st.caption(
        "5 questions. Answer honestly. The verdict points to the missing "
        "piece if any."
    )
    answers = {}
    for q in QUESTIONS:
        with st.container():
            cols = st.columns([5, 1])
            cols[0].markdown(f"**{q['label']}** — {q['prompt']}")
            answers[q["key"]] = cols[1].toggle(
                "yes", value=False, key=f"readiness_{q['key']}"
            )

    result = score_readiness(answers)
    verdict_color = {
        "READY": "ok",
        "INVEST_TO_BE_READY": "warn",
        "WRONG_TOOL": "fail",
    }
    st.markdown(
        f"### Verdict: <span class='pill {verdict_color[result.verdict]}'>"
        f"{result.verdict}</span> &nbsp; (score {result.score}/5)",
        unsafe_allow_html=True,
    )
    if result.advice:
        st.markdown("**Missing pieces:**")
        for a in result.advice:
            st.markdown(f"- {a}")
    if result.verdict == "READY":
        st.success(
            "Ship a Domain. See https://github.com/wjlgatech/flywheel"
        )
    elif result.verdict == "WRONG_TOOL":
        st.warning(
            "flywheel needs more structure than your X has. "
            "Consider human-in-the-loop tools instead."
        )


# ---------------------------------------------------------------------------
# Tab 5 — About
# ---------------------------------------------------------------------------

with tabs[4]:
    st.subheader("About")
    st.markdown(
        """
        **Neuro-OS** is a self-evolving, self-modifying knowledge OS for
        neuroscience texts. It ingests documents, validates them against the
        TRUE model (Experimentable / Usable / Repeatable / Transferable),
        merges valid refinements into a persistent ontology with a golden-case
        gate, and (in the meta-loop) rewrites its own priority routing data
        when classification regressions appear.

        It's built on **flywheel-loop** — a closed-loop self-improvement
        substrate that anyone can adopt. ``flywheel(X) = X_self_improved``
        for any X meeting five readiness conditions (see the **Readiness** tab).

        ### Repos
        - https://github.com/wjlgatech/neuro-os
        - https://github.com/wjlgatech/flywheel

        ### CLI
        ```bash
        pip install -e .
        python -m agent extract "Predictive coding minimizes prediction error."
        python -m agent self-modify --domain neuro_os_self_v1
        flywheel readiness
        ```

        ### What this UI does NOT do
        - It does not call any external LLM. The default extractor is offline keyword routing.
        - It does not write to your live registry — every run uses a temp directory.
        - It DOES write to ``agent/data/priority_rules.json`` when you click
          "Break it" and "Restore" on the Self-Repair tab. The session
          snapshot is restored when you click "Restore canonical".
        """
    )
