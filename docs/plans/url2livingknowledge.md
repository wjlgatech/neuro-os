# URL-to-Living-Knowledge — design notes (10X reframe)

**Status:** SHIPPED (v0.1) — see `docs/url-to-living-knowledge.md` for the user-facing how-to.

**One-line summary:** External producers (Hermes / curl / shell) drop pre-extracted text into `~/.neuro_os_research/inbox.jsonl`. Neuro-os consumes it through the existing `research ingest` → review → compress pipeline. ~80% of the plumbing already existed; this is the glue that closes the loop.

---

## The reframe

An earlier draft of this plan (preserved below in **Appendix A: Original Draft**) proposed building an end-to-end pipeline inside Hermes that:
- Watches Gmail twice daily at 12 pm / 8 pm,
- Categorizes each link against a 5-dimensional taxonomy,
- Auto-generates SKILL.md scaffolds,
- Creates GitHub issues in neuro-os,
- Solicits approval over Telegram.

A critical eval surfaced 11 weaknesses (see commit history for the full list). The two load-bearing ones:

1. **GitHub issues are the wrong substrate for knowledge.** They don't compose, compress, or feed the OEC loop. Neuro-os already has `MechanismCardProposal` → `research review` → Layer-3/4/5 compression → cross-vertical entities. Routing through issues throws all of that away.

2. **A parallel skill source of truth violates Law 7.** `agent/skillify/` is the existing catalog-evolution module gated by `/catalog-review`. Auto-generating SKILL.md in a parallel codepath would create two competing skill catalogs that drift within a month.

So we inverted the labor split:

- **Hermes** = inbound channels + extraction + nudging. (Multi-channel messaging gateway — its native shape.)
- **Neuro-os** = knowledge substrate + compression + revenue linkage + review surfaces. (Closed-loop OEC machine — its native shape.)
- **Glue** = one append-only JSONL file + one CLI subcommand.

Net result: ~80% less code, all Law-compliant, knowledge actually compresses (Layer 4), revenue-goal linkage runs through the startup vertical instead of GitHub labels.

---

## Shipped surface (v0.1)

### Producer contract: `~/.neuro_os_research/inbox.jsonl`

Append-only JSONL. One `InboxRecord` per line (defined in `agent/research/inbox.py`):

```json
{
  "url": "https://youtube.com/watch?v=abc",
  "source_type": "youtube",
  "title": "Building Multi-Agent Systems",
  "author": "Author Name",
  "extracted_text": "<transcript or markdown body>",
  "extracted_at": "2026-05-23T12:00:00+00:00",
  "sender": "paul@example.com",
  "urge_tag": "novelty",
  "topic_tags": ["mlops", "agents"]
}
```

Producers (Hermes Gmail watcher, Telegram forward, browser share-target, manual curl) write the JSON line — neuro-os reads. Anything language-agnostic works: the schema is the contract.

### Consumer surface

| CLI | Purpose |
|---|---|
| `neuro-os research inbox status` | Show inbox depth, cursor position, allowlist activity (no side effects). |
| `neuro-os research inbox ingest [--no-llm]` | Consume new records → MechanismCardProposals. Idempotent (cursor advances; sha256 dedups). |
| `neuro-os research inbox append --url ... --source-type ... --title ... --text-file ...` | Shell-pipeline helper to drop a record from the command line. |
| `neuro-os research goal --card-id <id> --entity-slug <slug>` | Link an accepted MechanismCard to a startup-vertical goal entity. Writes a `research_goal_link` cross-vertical note (visible to research + startup); upserts a startup-owned topic entity (default-private cross-vertical pattern). |

### Hidden-but-load-bearing primitives

| Primitive | Purpose |
|---|---|
| `~/.neuro_os_research/inbox.cursor` | Highest 0-indexed line offset consumed. Persisted so re-runs are idempotent; loss at worst re-extracts (sha256 dedup catches it). |
| `~/.neuro_os_research/inbox_allowlist.json` | Optional `["sender@…", …]` allowlist. Empty/missing = no restriction (solo use). Populated = teams / public deployments. |
| `urge_tag` prefix in `proposal.reasoning` | When a producer attaches the active drift mode (e.g. `novelty`), it prefixes the proposal's reasoning as `[urge:novelty] …` so the reviewer sees at-a-glance whether a capture came from real intent or procrastination spelunking. |

---

## Non-goals (intentionally dropped from the original plan)

| Dropped feature | Why |
|---|---|
| 12 pm / 8 pm cron windows | Arbitrary — drive by inbox-non-empty + morning review surface instead. |
| 5-dimensional taxonomy (revenue / horizon / category / priority / type) | Use the substrate's existing "6 named failure modes per vertical" invariant. A hand-rolled 5×5 taxonomy is inconsistent after 60 emails. |
| Auto-create GitHub issue | Wrong substrate. Issues don't compose / compress / feed the OEC loop. Use neuro-os state. |
| Auto-generate SKILL.md from extracted text | Skillify already does catalog evolution with a Law-7-compliant human gate. Don't create a parallel skill source. |
| "Auto-upgrade SKILL.md to Claude + Codex plugin" | Out of scope; would need plugin manifest, distribution channel, version management. Drop or split. |
| Telegram as approval surface | Strips entity-slug prompt + cross-vertical context. Use Telegram-as-nudge + the existing `research review` (CLI + `/research-review` page). |

---

## Validation (real-use-case end-to-end test)

The documented validation lives in `tests/test_research_inbox.py::test_real_use_case_url_to_living_knowledge_end_to_end`. It walks through:

1. Producer drops 3 URL records into the inbox (YouTube + blog + X/Twitter).
2. `process_inbox` extracts → 3 `MechanismCardProposals` in pending queue.
3. User accepts one at `/research-review` (here: invoked via primitives).
4. User links the accepted card to a startup goal entity (`wfx-revenue-q1`).
5. **Privacy boundary asserted:** startup vertical sees the goal entity + the research_goal_link note; investment vertical sees neither (default-PRIVATE cross-vertical).

The test also pins:
- Source URLs are preserved as `paper_source` (no dropped provenance).
- The novelty-urge proposal carries `[urge:novelty]` in its reasoning.
- Duplicate body text dedups (sha256-based, URL-agnostic).
- Cursor advances are idempotent.

---

## Hermes side (separate repo, separate PR)

The Hermes-side glue is intentionally NOT in this neuro-os PR (per the workspace `CLAUDE.md`: do not span project boundaries). It needs three small Hermes skills:

| # | Skill | LOC | Purpose |
|---|---|---|---|
| 1 | `url-to-inbox` | ~200 | Fetch URL → extract text → emit `InboxRecord` to `~/.neuro_os_research/inbox.jsonl`. One skill, four channels (Gmail/Telegram/share/clipboard) plug into it. |
| 2 | `flush-inbox-to-neuro-os` (cron) | ~50 | Optional. Every 6 h, runs `neuro-os research inbox ingest` so the user doesn't have to. |
| 3 | `morning-review-nudge` | ~30 | If `research inbox status` shows non-zero pending, send a Telegram message with a link to `127.0.0.1:8765/research-review`. |

Each is independently shippable; Hermes can land them at its own cadence.

---

## Layered enforcement (per `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`)

| Law | How it's honored |
|---|---|
| Law 1 — no raw ingestion | `InboxRecord` is a frozen Pydantic model with allowlisted `source_type` literal. Malformed JSON lines and schema violations are logged and skipped, not silently accepted. |
| Law 5 — deterministic outputs | `InboxRunSummary` is a frozen Pydantic model returned to all callers. No dict escape hatch. |
| Law 7 — human-in-loop truth control | Inbox proposals land in the existing pending-review queue; acceptance still requires `research review`. The catalog itself (`agent/research/catalog.py`) is not touched. |
| Law 11 — generated data stays out of repo | `inbox.jsonl`, `inbox.cursor`, `inbox_allowlist.json`, and the `.inbox_stage/` temp dir all live under `~/.neuro_os_research/` (already in `.gitignore`). |

---

## Appendix A: Original Draft (preserved for audit)

The original plan (saved 2026-05-21, before the critical eval) lives at this anchor. It is preserved verbatim so future readers can see what was rejected and why.

> _If you want the historical draft, read this file's git history at the commit that introduced this section._
