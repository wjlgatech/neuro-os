# URL-to-Living-Knowledge

**Audience:** anyone forwarding links (YouTube videos, blog posts, X threads, PDFs) into Neuro-OS and wanting them to land as accepted MechanismCards linked to revenue goals — not as flat tickets that decay.

**TL;DR:** drop a JSONL line into `~/.neuro_os_research/inbox.jsonl`, run `neuro-os research inbox ingest`, accept what's good in `research review`, link the keepers to a startup goal with `research goal`. That's the loop.

---

## The shape of the flow

```
EXTERNAL PRODUCER          NEURO-OS (already exists)
(Hermes / curl / shell)
       │
       │  append InboxRecord
       ▼
~/.neuro_os_research/
       inbox.jsonl                 ← append-only, one InboxRecord per line
       │
       ▼
research inbox ingest             ← consumes new records (cursor-tracked)
       │
       ▼                            (existing review surface)
MechanismCardProposals  ──→  research review --cli  ──→  accept
       │                                                    │
       │                                                    ▼
       │                                            mechanism_cards/<id>.json
       │                                                    │
       ▼                                                    ▼
(future) research compress ──→ Layer 3 / 4 / 5  ←─ research goal --card-id <id>
                                  hierarchical          --entity-slug <slug>
                                                              │
                                                              ▼
                                                    startup vertical sees a
                                                    goal-linked research note
```

Everything after the inbox is the existing pipeline. The inbox is the only new thing.

---

## The InboxRecord schema (the contract)

One JSON object per line. All required fields are validated by Pydantic at consume time — bad records are skipped with a logged warning, not silently accepted.

| Field | Required | Notes |
|---|---|---|
| `url` | ✅ | Original URL. Becomes `paper_source` on the proposal. |
| `source_type` | ✅ | One of `youtube` / `blog` / `twitter` / `pdf` / `email-body` / `other`. |
| `title` | ✅ | Human-readable source title. |
| `extracted_text` | ✅ | Pre-extracted body text (transcript / markdown / thread). 1–400k chars. |
| `extracted_at` | ✅ | ISO-8601 datetime. |
| `author` |   | Default `"unknown"`. |
| `sender` |   | E.g. email From: header. Checked against `inbox_allowlist.json` if it exists. |
| `urge_tag` |   | The active founder-loop drift mode (`novelty` / `social` / `frustration` / `fatigue` / `decision_fatigue` / `embodied`) if the producer knows it. Surfaces as `[urge:<tag>]` prefix in the proposal's reasoning so the reviewer sees provenance. |
| `topic_tags` |   | Free list of tags carried through to the proposal. |

---

## Minimum-slice walkthrough (drop a YouTube transcript by hand)

```bash
# 1. Save the transcript anywhere.
cat > /tmp/distribution-talk.txt <<'EOF'
Distribution beats product quality whenever buyers can't easily
self-discover alternatives. When two products are equal, then the
broader-distributed one wins share. Fails when buyers actively
comparison-shop on price.
EOF

# 2. Append it to the inbox.
neuro-os research inbox append \
  --url "https://youtube.com/watch?v=abc123" \
  --source-type youtube \
  --title "Distribution is the moat" \
  --author "Speaker Name" \
  --text-file /tmp/distribution-talk.txt \
  --sender paul@example.com \
  --urge-tag novelty

# 3. Inspect (no side effects).
neuro-os research inbox status
# → { "pending_count": 1, "cursor": -1, "total_lines": 1, ... }

# 4. Consume (LLM-based by default; pass --no-llm to use the regex heuristic).
neuro-os research inbox ingest --no-llm
# → InboxRunSummary JSON: records_seen, proposals_emitted, cursor_advanced_to

# 5. Review the proposals.
neuro-os research review --cli
#   id:         inbox-...
#   confidence: low
#   ...
#   [a]ccept / [r]eject / [s]kip / [q]uit ?  a
#   entity mentions (comma-separated kebab slugs, blank = none):  distribution-moat
#   accepted: inbox-... (with 1 entity mention(s))

# 6. Link the accepted card to a startup goal.
neuro-os research goal \
  --card-id <copy-the-id-from-step-5> \
  --entity-slug wfx-revenue-q1 \
  --entity-title "WorkflowX Revenue Q1"
# → { "entity_id": "...", "note_id": "...", "visible_to": ["research","startup"] }
```

That's the whole loop end-to-end. Roughly 10 seconds of attention per URL once you have a Hermes producer wired up.

---

## Multi-channel producer (the typical setup)

In production you don't `append` by hand — you point a multi-channel producer at the inbox and ignore it. The producer's job is "URL → pre-extracted text → JSONL line." Examples:

| Channel | How it works |
|---|---|
| **Gmail** | Hermes Gmail watcher polls `~/.gmail-credentials.json`, pulls links from new emails (sender allowlist enforced upstream OR via `inbox_allowlist.json`), extracts content per source-type, writes one InboxRecord per URL. |
| **Telegram forward** | Forward a message to your bot → bot extracts URLs from the message body → same `url-to-inbox` skill. |
| **Browser share** | macOS Share Sheet / Android Share Intent → POSTs to a local Hermes endpoint → same pipeline. |
| **Manual curl** | `curl -X POST localhost:<hermes-port>/url-to-inbox -d '{"url": "..."}'` for shell scripts. |

The producers all collapse onto the same JSONL contract. Neuro-os doesn't know or care which channel sent the record.

---

## Sender allowlist (optional, recommended for non-solo use)

Drop a file at `~/.neuro_os_research/inbox_allowlist.json`:

```json
["paul@example.com", "claude@anthropic.com"]
```

or

```json
{ "senders": ["paul@example.com", "claude@anthropic.com"] }
```

When the file exists and is non-empty:
- Records with `sender` in the allowlist pass.
- Records with `sender` missing or not in the allowlist are skipped (`records_skipped_disallowed` in the run summary).

When the file is missing or empty, every record passes — appropriate for solo / local-only deployments.

---

## What happens if you re-run ingest?

Idempotent by design:

- `inbox.cursor` records the highest line offset already processed. Re-runs only look at lines past the cursor.
- If the cursor is lost (file deleted, etc.) and a record is re-staged, the sha256 dedup in `agent/research/proposals.py` catches it — the duplicate is counted in `records_skipped_duplicate` and no second proposal is written.
- If the user wants to re-extract on purpose (e.g. the LLM has improved), reject the existing proposal first, then delete the cursor.

---

## Cross-vertical privacy boundary

The `research goal` link creates:

1. A **startup-vertical Entity** (kind=`topic`, slug=user-supplied). Visible to research + startup; invisible to investment + founder_loop.
2. A **research-vertical note** (kind=`research_goal_link`, payload pins `card_id` + `entity_slug` + the mechanism + the prediction). Visible to research + startup.

Investment and founder_loop verticals are **NOT** automatically granted access. If the user wants to broaden, they call `cross-vertical share-note --note-id <id> --with investment` explicitly — same per-note opt-in model that every other cross-vertical artifact uses.

The end-to-end test (`tests/test_research_inbox.py::test_real_use_case_url_to_living_knowledge_end_to_end`) pins this boundary: investment queries return empty even when the link exists, until the user opts in.

---

## Failure modes (real ones, observed in dev)

| Symptom | Diagnosis | Fix |
|---|---|---|
| `neuro-os research inbox status` shows `pending_count=0` but I just appended | Cursor already past the appended line (you ran ingest in between). | Append again with new content, or delete `inbox.cursor` if you actually want to re-process. |
| `proposals_emitted=0` even though the LLM ran | The LLM returned non-JSON output or the JSON didn't have the required fields. Check `~/.neuro_os_research/.inbox_stage/` for the staged body if it persisted. | Re-run with `--no-llm` to confirm the heuristic emits at least 1 proposal; if it does, the LLM is the issue. |
| `records_skipped_disallowed > 0` and you didn't expect it | An allowlist file exists at `~/.neuro_os_research/inbox_allowlist.json`. | `cat` it; either add the sender or remove the file. |
| `records_skipped_duplicate > 0` after appending what looks like new content | The body text is byte-identical to a prior proposal (sha256 collision). | If genuinely new, tweak the text. If a legitimate re-extract, reject the old proposal first. |

---

## Where the code lives

| Concern | File |
|---|---|
| Schema (`InboxRecord`, `InboxRunSummary`) | `agent/research/inbox.py` |
| End-to-end driver (`process_inbox`) | `agent/research/inbox.py` |
| Allowlist load (`load_allowlist`) | `agent/research/inbox.py` |
| CLI surface (`research inbox`, `research goal`) | `agent/cli.py` — handlers `_research_inbox_*` + `_research_goal_handler` |
| Tests + the real-use-case end-to-end | `tests/test_research_inbox.py` |
| Design rationale + dropped non-goals | `docs/plans/url2livingknowledge.md` |
