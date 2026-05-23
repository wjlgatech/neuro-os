# agentskills.io ecosystem — honest integration evaluation

**Status:** REFERENCE — design note. Update when new agentskills.io-style tools
appear and someone (Paul or an AI agent) asks "should we integrate it?"

**Date written:** 2026-05-23 (Opus 4.7 evaluation of a "you should install
these three skills today" recommendation)

---

## Tools evaluated

| Tool | Source | What it is (stripped of marketing) |
|---|---|---|
| `nuwa-skill` (女娲.skill) | `alchaincyf/nuwa-skill` (20.9k ⭐) | A skill generator + 10 pre-distilled persona skills (Jobs, Munger, Naval, Musk, Feynman, Karpathy, Ilya, MrBeast, PG, Sun Yuchen). Output: SKILL.md files an agent loads to imitate someone's thinking style. |
| `skill-distillery` | `kylezantos/skill-distillery` (14 ⭐) | Meta-skill creator. Takes article/URL/recent-AI-session → bottom-up extracts principles → emits a SKILL.md. **Output is another skill file.** |
| `skill-seekers` | PyPI `skill-seekers` v3.6, 3194+ tests | Bulk content-to-skill converter. Crawls docs sites / GitHub repos / PDFs / videos / notebooks → emits SKILL.md skills. |

**Common pattern:** All three are "X → SKILL.md" generators following the
[agentskills.io](https://agentskills.io) protocol. They are **producers** for
the Claude Code / Codex / Hermes / OpenClaw / Cursor runtime ecosystem.

---

## The conflation pitfall (must read)

Neuro-os has a module at `agent/skillify/` that ALSO uses the word "skill."
**These are unrelated concepts that share a name.**

| Concept | Lives in | What it is |
|---|---|---|
| Neuro-OS skillify | `agent/skillify/` | Catalog evolution from real override events (Law-7 gated). A "SkillProposal" is a candidate **failure-mode taxonomy entry** that surfaces when ≥5 same-mode overrides accumulate. |
| agentskills.io SKILL.md | `~/.hermes/skills/`, `~/.claude/skills/`, etc. | A markdown file an LLM loads at prompt time. A cookbook. No loop, no state, no failure-mode taxonomy. |

**Anyone telling you "install these three skills and they integrate with your
skillify catalog" is wrong.** They are different layers of different systems.
The Chinese-speaking nuwa-skill audience and the English-speaking
skill-distillery audience are both talking about agentskills.io SKILL.md, not
neuro-os skillify.

---

## Loop vs cookbook (the actual framing)

For each tool, the engineering question is **"does this feed a loop or
replace one?"**

Neuro-os is a closed-loop OEC machine: Observe → Evaluate → Control → Validate.
The value of the system is in the **loop closing** (URL → MechanismCardProposal
→ accept → goal-link → compress → expression → behaviour change), not in any
single step.

Cookbook tools (SKILL.md generators) live at a different abstraction:
"load this rubric, run this workflow." Useful for one-shot interactive
prompting; not a substitute for a closed loop.

| Tool | Feeds neuro-os loop? | Replaces a step? | Verdict |
|---|---|---|---|
| nuwa-skill | No | Maybe a Layer-1 deepening step at `research review` ("what would Munger see in this?") if invoked manually from Hermes. | **Install in Hermes; do not integrate with neuro-os.** Useful as a thinking-partner side tool. |
| skill-distillery | No | Yes — its "extract principles from article" job IS `agent/research/ingest.py::extract_mechanisms`. | **Don't install for neuro-os work.** Would create a parallel extractor that drifts from the research vertical's. Fine as a standalone Claude-Code skill for non-neuro-os tasks. |
| skill-seekers | Yes (as a one-shot ingestor) | No — it expands source-type coverage; the existing `research ingest --source-dir` consumes its output. | **Install as CLI; bridge via `skill-seekers-to-inbox` Hermes skill.** Use on-demand for docs sites / repos / PDFs. |

---

## Recommended install (the one that survived the eval)

```bash
# 1. nuwa-skill — thinking-partner persona, lives in Hermes
git clone --depth 1 https://github.com/alchaincyf/nuwa-skill ~/.hermes/skills/nuwa-skill
# Registered as /huashu-nuwa in Hermes's scan_skill_commands; carries 10
# pre-distilled persona examples (Jobs/Munger/Naval/Musk/Feynman/...).

# 2. skill-seekers — CLI, called from a Hermes bridge skill on demand
pip3.11 install --user skill-seekers
# Bridge skill at ~/.hermes/skills/skill-seekers-to-inbox/ (in this repo:
# see hermes-agent/skills/research/skill-seekers-to-inbox/) feeds output
# into neuro-os's research inbox.

# 3. skill-distillery — SKIP for neuro-os integration
# (Install only if you want a standalone Claude-Code skill for non-neuro-os
#  workflows. Don't try to wire it into agent/research/ingest.py.)
```

---

## How `skill-seekers-to-inbox` composes with neuro-os

The bridge skill (`hermes-agent/skills/research/skill-seekers-to-inbox/`)
turns the upstream tool into a one-shot ingestor for the URL-to-Living-Knowledge
loop. Pipeline:

```
SOURCE (docs site URL / GitHub repo / PDF / video)
        │
        │  skill-seekers create --url ... --output /tmp/out
        ▼
/tmp/out/references/section_*.md   ← one .md per scraped page
        │
        │  flush_references.py --references-dir ... --base-url ...
        ▼
~/.neuro_os_research/inbox.jsonl   ← one InboxRecord per page
        │
        │  neuro-os research inbox ingest
        ▼
MechanismCardProposals → research review → goal-link → compression
```

The bridge **imports** `append_inbox.py` from the `url-to-inbox` sibling skill
instead of duplicating the InboxRecord schema — single producer in the
codebase, automatic schema-evolution propagation. See
`hermes-agent/skills/research/skill-seekers-to-inbox/SKILL.md` for the full
contract.

---

## Why we don't auto-extract via skill-distillery

`skill-distillery`'s "bottom-up extract principles + mental models" framing
overlaps significantly with the research vertical's
`MechanismCardProposal` extraction (`agent/research/ingest.py`). Specifically:

- `skill-distillery` extracts: principles, mental models, decision heuristics.
- `MechanismCardProposal` extracts: mechanism, invariant, prediction, failure_mode.

These are **different vocabularies for related work** — the neuro-os schema is
tighter (Law 1: typed, Pydantic-validated, exactly four required fields, with
optional Layer-1 deepening — first_principle / anti_pattern /
transferability_test / verdict). If you ran both extractors on the same
article, you'd get two related-but-not-identical artifacts and have to
reconcile them at review time.

**Decision:** keep one extractor. The neuro-os one is the one with the closed
loop, the privacy boundary, the cross-vertical entity propagation, and the
substrate's 6-failure-mode invariant. It's the load-bearing one. Don't fork it.

If skill-distillery's interactive design ("5-lens audit framework", "wait
gates") inspires improvements to `research review --cli`, port the ideas; do
not run the tool in parallel.

---

## When this eval becomes stale

Re-evaluate when:

- agentskills.io publishes a spec change that lets SKILL.md skills consume
  external schemas (today they are LLM-prompt-only artifacts; if they grow
  typed I/O, the integration story changes).
- Neuro-os's `agent/skillify/` ever begins emitting agentskills.io-shaped
  artifacts (today it emits `SkillProposal` for the catalog evolution loop,
  which is a different thing — the names happen to collide).
- A skill generator appears that targets neuro-os's `MechanismCardProposal`
  schema directly instead of generic SKILL.md.

Until then, the recommended install above is the answer.

---

## Related

- [`docs/url-to-living-knowledge.md`](../url-to-living-knowledge.md) — the inbox
  contract this evaluation references.
- [`docs/plans/url2livingknowledge.md`](./url2livingknowledge.md) — the design
  rationale for the inbox + why we didn't ship the "email-to-skill pipeline"
  plan as written.
- `hermes-agent/skills/research/url-to-inbox/SKILL.md` — single-URL producer.
- `hermes-agent/skills/research/skill-seekers-to-inbox/SKILL.md` — bulk-ingest
  producer using the upstream `skill-seekers` CLI.
- [agentskills.io](https://agentskills.io) — the open protocol; the ecosystem
  context this eval lives in.
