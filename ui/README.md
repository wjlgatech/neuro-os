# Neuro-OS UI

A Streamlit app that makes neuro-os legible in 60 seconds.

## Run

```bash
pip install -e ".[ui]"
streamlit run ui/app.py
```

(or `pip install streamlit` if you don't want the optional extra)

The app opens at http://localhost:8501.

## Tabs

| Tab | What it does | What you'll see |
|---|---|---|
| **🟢 Try It** | Paste a sentence; the pipeline classifies it. | Mechanism, decision (ACCEPT / REFINE / REJECT), TRUE per dimension, evidence strength. |
| **🌱 Watch It Learn** | Feed a citation-rich contradiction. | The ontology mutates — you see the new definition + sources persisted. Uses a temp ontology so live state isn't touched. |
| **🔧 Self-Repair** | Click "Break it" then "Run flywheel". | The meta-loop observes the regression, proposes an allowlisted patch, validates in a sandbox, and promotes back to disk. |
| **📊 Readiness** | Toggle the 5 questions for your own X. | Live verdict (READY / INVEST_TO_BE_READY / WRONG_TOOL) + advice on the missing piece. |
| **ℹ️ About** | Links to repos + CLI cheatsheet. | |

## Safety

- The Self-Repair tab is the only path that writes to the live tree, and only to `agent/data/priority_rules.json`.
- A session snapshot is taken on first load so you can restore canonical state at any time.
- All other tabs use `tempfile.mkdtemp` to keep the live registry / feedback log clean.
