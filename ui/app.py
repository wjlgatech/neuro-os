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

import copy

import streamlit as st  # noqa: E402

from agent.api import ingest_documents, process_text  # noqa: E402
from agent.domains import get_domain  # noqa: E402
from agent.ingestion_pipeline import (  # noqa: E402
    PRIORITY_RULES_PATH,
    _canonical_ontology,
    classify_evidence_strength,
    get_priority_rules,
    run_pipeline,
)
from agent import primitive_feedback, version_registry  # noqa: E402
# Importing the module registers personal_epistemic_v1 with the domain registry.
from agent import personal_epistemic_domain  # noqa: E402, F401
from agent.personal_epistemic_domain import (  # noqa: E402
    PERSONAL_EPISTEMIC_GOLDEN_CASES,
    PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
    personal_epistemic_extractor,
)
from agent.self_modification import run_self_modification  # noqa: E402
from flywheel_loop.readiness import QUESTIONS, score_readiness  # noqa: E402

# Local sibling import — works whether streamlit is launched from repo root
# or from the ui/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from viz import ontology_dot, routing_dot  # noqa: E402


# Hardcoded canonical reference for the routing graph diff. Reading
# from disk at import time would be wrong if the live file happens to
# be degraded from a prior session — the graph needs the *intended*
# state to compare against.
_CANONICAL_RULES = [
    ("reward prediction error", "reinforcement_learning"),
    ("dopamine", "reinforcement_learning"),
    ("td learning", "reinforcement_learning"),
    ("td error", "reinforcement_learning"),
    ("query key value", "attention"),
    ("fire together", "hebbian_learning"),
    ("stdp", "hebbian_learning"),
]


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
      /* Pulse badge that fires for ~3s after a successful flywheel
         promotion. The CSS animation runs once per render, so a fresh
         st.rerun gives the badge a fresh dose of attention. */
      @keyframes neuroPulse {
        0%   { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22,163,74,0.6); }
        50%  { transform: scale(1.05); box-shadow: 0 0 12px 8px rgba(22,163,74,0.0); }
        100% { transform: scale(1.00); box-shadow: 0 0 0 0 rgba(22,163,74,0.0); }
      }
      .neuro-pulse {
        display: inline-block;
        padding: 6px 14px;
        margin: 6px 0 12px 0;
        font-weight: 600;
        font-size: 0.95rem;
        color: #065f46;
        background: #d1fae5;
        border: 2px solid #16a34a;
        border-radius: 8px;
        animation: neuroPulse 0.9s ease-out 3;
      }
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
        "🧭 Belief OS",
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

    baseline_ontology = _canonical_ontology()

    run_ingest = st.button("Ingest", type="primary", key="run_ingest")

    # Side-by-side ontology graphs: baseline (left) and post-ingestion
    # (right). The right pane is a placeholder until Ingest fires; after
    # that, green-bordered nodes mark primitives that accreted citations.
    final_ontology = None
    last_report = None
    if run_ingest:
        docs = [d.strip() for d in docs_text.split("\n\n") if d.strip()]
        if not docs:
            st.warning("Provide at least one document.")
        else:
            tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_ui_ingest_"))
            ontology_path = tmp_dir / "ontology.json"
            version_registry.set_registry_path(tmp_dir / "registry.jsonl")
            primitive_feedback.FEEDBACK_PATH = tmp_dir / "feedback.jsonl"
            primitive_feedback.reset_for_tests()

            ontology_copy = copy.deepcopy(baseline_ontology)
            with st.spinner("Running self-evolving loop..."):
                last_report = ingest_documents(
                    docs,
                    ontology=ontology_copy,
                    ontology_path=ontology_path,
                )
            if ontology_path.exists():
                final_ontology = json.loads(ontology_path.read_text())
            st.session_state["last_ingest_report"] = last_report
            st.session_state["last_ingest_ontology"] = final_ontology

    # Pull from session state so the side-by-side persists across reruns.
    final_ontology = final_ontology or st.session_state.get("last_ingest_ontology")
    last_report = last_report or st.session_state.get("last_ingest_report")

    col_l, col_r = st.columns(2, gap="medium")
    with col_l:
        st.markdown("##### 📊 Baseline ontology")
        st.graphviz_chart(ontology_dot(baseline_ontology), use_container_width=True)
    with col_r:
        st.markdown("##### 🌱 After ingestion")
        if final_ontology is not None:
            st.graphviz_chart(
                ontology_dot(final_ontology, baseline=baseline_ontology),
                use_container_width=True,
            )
            st.caption("Green-bordered nodes accreted citations from the input.")
        else:
            st.info(
                "Click **Ingest** to run the self-evolving loop. "
                "The right-hand graph will populate with the post-ingestion ontology."
            )

    if last_report is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Documents", len(last_report["ingested"]))
        c2.metric("Merges applied", last_report["merges_applied"])
        c3.metric("Merges reverted", last_report["merges_reverted"])

        actions = [e["action"] for e in last_report["evolutions"]]
        st.markdown(
            "**Evolution actions:** " + " ".join(f"`{a}`" for a in actions)
        )

        if final_ontology is not None:
            changed = []
            for name, primitive in final_ontology["primitives"].items():
                if primitive.get("sources"):
                    changed.append({
                        "primitive": name,
                        "definition": primitive.get("definition", ""),
                        "sources_added": len(primitive.get("sources", [])),
                    })
            if changed:
                st.markdown("**Primitives that mutated:**")
                st.dataframe(changed, use_container_width=True)

        with st.expander("Full report"):
            st.json(last_report)


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

    # Live routing-graph viz: blue edges are canonical+present, gray dashed
    # are canonical-but-missing (degraded), green are restored/freshly added.
    current_rules = [tuple(r) for r in current]
    fresh = []
    last = st.session_state.get("last_repair_report")
    if last and last.get("results"):
        for outcome in last["results"]:
            payload = outcome.get("patch", {}).get("payload", {})
            cue = payload.get("cue")
            mech = payload.get("mechanism")
            if cue and mech:
                fresh.append((cue, mech))
    st.graphviz_chart(
        routing_dot(current_rules, _CANONICAL_RULES, freshly_promoted=fresh),
        use_container_width=True,
    )
    # Pulse badge fires for ~3 seconds after a successful flywheel
    # promotion. The CSS animation runs `3` times each render, so the
    # badge re-attracts attention every time the user watches the
    # post-promotion state.
    if fresh:
        for cue, mech in fresh:
            st.markdown(
                f'<div class="neuro-pulse">✨ Patch promoted: '
                f'<code>{cue} → {mech}</code></div>',
                unsafe_allow_html=True,
            )
    legend = (
        "🔵 canonical & present &nbsp;&nbsp;"
        "🟢 freshly added by flywheel &nbsp;&nbsp;"
        "⬜ canonical & missing (degraded)"
    )
    st.markdown(legend)

    cb1, cb2, cb3 = st.columns(3)
    if cb1.button("⚠️  Break it (drop RL cues)", key="break_btn"):
        rules = json.loads(st.session_state.snapshot_rules)
        degraded = [r for r in rules if r[1] != "reinforcement_learning"]
        PRIORITY_RULES_PATH.write_text(
            json.dumps(degraded, indent=2) + "\n", encoding="utf-8"
        )
        st.session_state.pop("last_repair_report", None)
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
        # Stash the report for the next rerun and force one so the
        # graph + metrics at the top of the tab pick up the
        # newly-promoted priority rule.
        st.session_state["last_repair_report"] = report
        st.rerun()

    # Result panel rendered from session_state so it survives reruns.
    last_report = st.session_state.get("last_repair_report")
    if last_report is not None:
        st.markdown(
            f"**Last run:** {_decision_pill(last_report['status'])}",
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Baseline accuracy", f"{last_report['baseline']['accuracy']}")
        c2.metric("Patches proposed", last_report["patched_proposals"])
        c3.metric("Merges applied", last_report.get("merges_applied", 0))

        if last_report["results"]:
            outcome = last_report["results"][0]
            cp1, cp2 = st.columns(2)
            with cp1:
                st.markdown("**Patch payload**")
                st.json(outcome["patch"])
            with cp2:
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
        st.session_state.pop("last_repair_report", None)
        st.success("Priority rules restored from session snapshot.")
        st.rerun()

    with st.expander("Current priority_rules.json"):
        st.code(
            PRIORITY_RULES_PATH.read_text(encoding="utf-8"),
            language="json",
        )


# ---------------------------------------------------------------------------
# Tab 4 — Belief OS (personal_epistemic_v1 domain)
# ---------------------------------------------------------------------------

with tabs[3]:
    st.subheader("Belief OS — contradiction-aware reasoning ontology")
    st.caption(
        "Same closed loop, repointed: 6 reasoning primitives instead of "
        "neuroscience mechanisms. Paste a claim from something you read "
        "and watch it classify against Bayesian updating, base-rate reasoning, "
        "falsifiability, expected value, second-order thinking, and "
        "survivorship bias — with the same TRUE-rubric and golden-case gate."
    )

    belief_domain = get_domain("personal_epistemic_v1")
    belief_ontology = belief_domain.ontology

    belief_presets = {
        "(write your own)": "",
        "Survivorship bias (founder mythology)": (
            "Successful founders dropped out of college, so dropping out helps. "
            "The reference class of dropouts who tried and failed is invisible — "
            "this is classic survivorship bias and the denominator is missing."
        ),
        "Base-rate (Linda problem)": (
            "Linda is 31, single, outspoken, philosophy major. Most respondents "
            "incorrectly judge 'Linda is a feminist bank teller' as more likely "
            "than 'Linda is a bank teller', a conjunction-fallacy violation of "
            "the base rate of bank tellers."
        ),
        "Falsifiability (vague forecast)": (
            "The claim 'markets will be volatile next year' forbids no observation; "
            "it is unfalsifiable and therefore not a real prediction about the world."
        ),
        "Out-of-domain (rejection)": (
            "Bananas turn yellow when ripe. They float in fresh water."
        ),
    }
    belief_choice = st.selectbox(
        "Preset (or write your own below):",
        list(belief_presets.keys()),
        key="belief_preset",
    )
    belief_text = st.text_area(
        "Claim to classify:",
        value=belief_presets[belief_choice],
        height=120,
        placeholder="Paste a claim from a book, article, or note...",
        key="belief_text",
    )

    bcol_run, _ = st.columns([1, 5])
    if bcol_run.button("Classify", type="primary", key="belief_run"):
        if not belief_text.strip():
            st.warning("Paste a claim first.")
        else:
            with st.spinner("Running pipeline against Belief OS..."):
                pipeline = personal_epistemic_extractor(belief_text)
            knowledge = pipeline["knowledge"]
            scores = pipeline["true_validation"]["scores"]
            decision = pipeline["decision"]

            bc1, bc2, bc3 = st.columns(3)
            bc1.metric("Reasoning primitive", knowledge.get("mechanism", "unknown"))
            bc2.markdown(
                f"**Decision**<br/>{_decision_pill(decision)}",
                unsafe_allow_html=True,
            )
            bc3.metric("Composite TRUE", f"{scores.get('TRUE', 0):.2f}")

            st.markdown(
                "**TRUE per dimension** "
                "(E = experimentable, U = usable, R = repeatable, T = transferable)"
            )
            st.bar_chart(
                {k: scores.get(k, 0) for k in ("E", "U", "R", "T")},
                horizontal=True,
                use_container_width=True,
            )
            st.markdown(
                "**Evidence strength** "
                "(year/author/DOI/URL/arXiv markers): "
                f"`{classify_evidence_strength(belief_text)}`"
            )
            with st.expander("Synthesized knowledge dict"):
                st.json(knowledge)

    st.divider()
    st.subheader("Watch your priors update")
    st.caption(
        "Feed a citation-rich note that contradicts the current definition of a "
        "reasoning primitive. The L1 loop proposes a refinement, gates it against "
        "the 6 Belief OS goldens, and merges only if accuracy holds."
    )

    belief_default_doc = (
        "Tetlock & Gardner (2015) Superforecasting (https://doi.org/10.1234/sf.2015) "
        "argue that base-rate reasoning works only when the reference class is also "
        "selected for the question being asked — anchoring on the wrong reference class "
        "is worse than ignoring base rates entirely. arXiv:1503.04567"
    )
    belief_docs = st.text_area(
        "Document(s) to ingest (one per blank-line block):",
        value=belief_default_doc,
        height=140,
        key="belief_ingest_text",
    )

    if st.button("Ingest into Belief OS", type="primary", key="belief_ingest_btn"):
        docs = [d.strip() for d in belief_docs.split("\n\n") if d.strip()]
        if not docs:
            st.warning("Provide at least one document.")
        else:
            tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_belief_ingest_"))
            ontology_path = tmp_dir / "belief_ontology.json"
            version_registry.set_registry_path(tmp_dir / "registry.jsonl")
            primitive_feedback.FEEDBACK_PATH = tmp_dir / "feedback.jsonl"
            primitive_feedback.reset_for_tests()

            ontology_copy = copy.deepcopy(belief_ontology)
            with st.spinner("Running self-evolving loop on Belief OS..."):
                belief_report = ingest_documents(
                    docs,
                    ontology=ontology_copy,
                    ontology_path=ontology_path,
                    golden_cases=list(PERSONAL_EPISTEMIC_GOLDEN_CASES),
                    priority_rules_path=PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
                )
            st.session_state["belief_report"] = belief_report
            if ontology_path.exists():
                st.session_state["belief_ontology_after"] = json.loads(
                    ontology_path.read_text()
                )
            else:
                st.session_state["belief_ontology_after"] = None

    bel_after = st.session_state.get("belief_ontology_after")
    bel_report = st.session_state.get("belief_report")
    bcol_l, bcol_r = st.columns(2, gap="medium")
    with bcol_l:
        st.markdown("##### 📊 Baseline Belief OS ontology")
        st.graphviz_chart(ontology_dot(belief_ontology), use_container_width=True)
    with bcol_r:
        st.markdown("##### 🌱 After ingestion")
        if bel_after is not None:
            st.graphviz_chart(
                ontology_dot(bel_after, baseline=belief_ontology),
                use_container_width=True,
            )
            st.caption("Green-bordered nodes accreted citations from the input.")
        else:
            st.info("Click **Ingest into Belief OS** to populate this graph.")

    if bel_report is not None:
        m1, m2, m3 = st.columns(3)
        m1.metric("Documents", len(bel_report["ingested"]))
        m2.metric("Merges applied", bel_report["merges_applied"])
        m3.metric("Merges reverted", bel_report["merges_reverted"])
        actions = [e["action"] for e in bel_report["evolutions"]]
        st.markdown("**Evolution actions:** " + " ".join(f"`{a}`" for a in actions))
        with st.expander("Full report"):
            st.json(bel_report)


# ---------------------------------------------------------------------------
# Tab 5 — Readiness
# ---------------------------------------------------------------------------

with tabs[4]:
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
# Tab 6 — About
# ---------------------------------------------------------------------------

with tabs[5]:
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
