# Roadmap

Three columns. Honest.

- **SHIPPED** is verifiable in the current commit. Run the tests; if
  they pass, it works.
- **NEXT** is what we're focused on this week or next.
- **LATER** is real work that's worth doing but isn't started.

If you're reading this and something in **SHIPPED** doesn't actually
work for you, that's a bug — please file it. If something in
**NEXT** is taking too long, that's a different kind of bug.

---

## SHIPPED (v0.5 — four verticals on a shared substrate)

The reward-economy + sublimation engine, three UI surfaces, AND three
new verticals (research / investment / startup) on the
`agent/domain_app/` substrate. All verifiable: 308 tests pass, 12
skipped (10 e2e Playwright tests skip when chromium isn't installed;
1 Law 9 enforcer skips when no commits ahead of main; 1 LLM test is
permanently skipped).

| Area | Status | What's there |
|---|---|---|
| **`agent/domain_app/` substrate** | Complete | Protocol-based shared loop. `DomainApp` orchestrator validates every vertical has exactly 6 named failure modes + ≥1 constructive expression per mode (Law 3). 4 first-class metrics + `extra: dict` (anti-metric-overload). Frozen base schemas for `Contract`, `Tank`, `ControlAction`, `Diagnosis`. 18 substrate tests pin the contract. |
| **`agent/cross_vertical.py`** | Complete | Typed inter-vertical reads. `VerticalNote` frozen. **Default-PRIVATE** to source vertical; explicit `share_with=[...]` to broaden. `share_note` broadens via append-only event without mutating original row. 12 tests pin the visibility model. |
| **Research vertical** (`agent/research/`) | Complete | 6 failure modes (paper_collector / topic_hopper / memorizer / authority_acceptor / overloaded / forgetting). MechanismCard / AssumptionMap / PredictionLog / ResearchThesis ontology. Single-thesis enforcement via required `thesis_id`. 19 tests. |
| **Investment vertical** (`agent/investment/`) | Complete — advisory-only | 6 failure modes (emotional / narrative_following / price_obsessed / overconfident / social_proof_following / ego_attached). PositionThesis (requires `invalidation_condition`), BiasCheck, CalibrationRecord. **Anti-goal: no broker integration, no trade execution.** Reuses `agent/belief_os.py::check_decision_text` for bias detection. 17 tests. |
| **Startup vertical** (`agent/startup/`) | Complete | 6 failure modes (idea_chaos / broadcasting / feature_creep / vision_intoxicated / vanity_metrics / random_execution). StartupHypothesis / Bottleneck (typed enum) / AudienceSignal (typed channel) / StartupPriority. Hard cap: thesis_pivots/day ≤ 1. Trust density via repeat-engagement count. 20 tests. |
| **Cross-vertical demo** | Complete | `examples/09_cross_vertical_demo.py` walks research → investment → bias_check via belief_os, with privacy boundary verified end-to-end. |
| **Engine** | Complete | Five boxes (sensors → brain → contract → carrot/stick → memory) wired end-to-end. 14 user-acceptance scenarios pass. |
| **Local daemon** | Complete | `127.0.0.1:8765`, twelve endpoints, refuses non-loopback bind, no auth (boundary is the loopback). |
| **Conversational morning ritual** | Complete | `/onboard` chat page. Users tell the AI what matters; AI extracts structured priorities via tool use. Falls back to a state-machine without an API key. |
| **Conversational nightly review** | Complete | `/review` chat page. Daemon injects today's summary (MAE, contract-honor, evidenced priorities) as kickoff context; AI walks reflection → tomorrow's contract → Sign. |
| **Conversational queue maintenance** | Complete | `/queues` chat page. AI mutates `bookmarks_queue.json`, `social_queue.json`, `rubber_duck_venues.json` via tool use. Side panel re-renders after each turn. |
| **Browser extension (Manifest V3)** | Complete | Toolbar badge, popup, new-tab dashboard, sublimation overlay on 8 distraction hosts. Honors agency: nothing blocks. |
| **System tray app** | Complete | Cross-platform (Linux / macOS / Windows). Tank gauge in the menu bar; menu actions for tick / show contract / quit. |
| **`neuro-os start` alias** | Complete | One-shot: starts daemon with `~/.founder_loop/*` defaults, opens `/onboard` in the default browser, runs hourly internal ticks. |
| **Workflowx auto-detect** | Complete | `loop workflowx-detect` and the daemon boot path now scan platform-specific known directories (macOS `Library/Application Support/workflowx/exports/`, Linux `.config/workflowx/exports/`, etc.), honor `WORKFLOWX_EXPORTS_PATH`, and pick the most-recent `.jsonl`. Falls back to `~/.founder_loop/workflowx.jsonl` and logs which branch fired so the user knows whether real signal is flowing. |
| **User-logged urge events** | Complete | `neuro-os loop urge entertainment --context "..."` writes a `UrgeEvent` to `founder_events.jsonl`. The daemon's next tick reads recent events (15-min window) and treats user-reported urges as ground truth — overrides the predictor's guess. Browser extension's "I'm tempted right now" maps to the same surface via `POST /events`. Closes V0 acceptance criterion #2. |
| **Daily report — four metrics** | Complete | `NightlySummary` and the `/review` kickoff now surface all four V0 metrics: prediction MAE, contract-honor rate, entertainment minutes used, and sublimation success rate. The last metric is the signal that says whether the philosophy is actually working (proposals that "stuck" without subsequent override). |
| **End-to-end test catalog** | Complete | `tests/e2e/scenarios.md` lists 20 deterministic scenarios (S01–S20: morning ritual, sublimation card, override, nightly review, edge cases) plus 3 judgment scenarios (J1–J3) for Computer Use. Three harnesses share the same scenario IDs: `test_http_scenarios.py` (10 HTTP-only, runs in CI), `test_browser_scenarios.py` (10 Playwright, runs locally), `computer_use_runner.py` (3 judgment scenarios driven by Claude). |
| **Daemon-internal tick scheduler** | Complete | `--tick-interval-min N` spawns a background thread that calls `loop.tick()` every N minutes. No cron required. |
| **Auto-start on login** | Complete | `neuro-os autostart {install,uninstall,status}` writes a launchd plist (macOS) / systemd-user unit (Linux) / Task Scheduler XML (Windows) and enables it. `--dry-run` previews the unit. |
| **Plain-English doc trio + roadmap** | Complete | `docs/{what-is-this,how-to-use-it,how-it-works,roadmap}.md`. Daemon serves them rendered at `/about`, `/how-to-use`, `/how-it-works`, `/roadmap` (markdown→HTML in-process, no new dep). |
| **Sublimation catalog** | 6 needs | fatigue, novelty_hunger, social, frustration, decision_fatigue, embodied (hunger / eye-strain). |
| **Per-user queues** | 3 queues | bookmarks, social, rubber_duck. JSON files; populated via `/queues` chat OR by hand. |
| **First-run defaults** | Complete | `neuro-os start` with no args creates `~/.founder_loop/` and an empty workflowx fixture. |

---

## NEXT (this week)

The previous "NEXT" list shipped — see SHIPPED above. These are the
follow-ups that the now-shipped surfaces revealed:

| # | Item | Why now | Days |
|---|---|---|---|
| 1 | **40-day real-user trial of one vertical** *(Phase D of A-C-B-D plan)* | The 6 named failure modes per vertical were hand-guessed from the PRDs; the constructive expressions are educated guesses. Until a real user (Paul) runs one vertical for 40 days, the catalog can't be refined against evidence. Suggested: research vertical (lowest stakes, shippable today). After 40 days the registry will show which failure modes fired most often, which constructive expressions stuck (no later override), which categories were missing. Then revise the catalog from data, not opinion. | 40 days of YOUR time, no engineer time |
| 2 | **Research-vertical corpus ingestion sensor + Yang walkthrough** | Today the research vertical has no automated input — users type `MechanismCard`s by hand. A user proposal asked for a 10-layer KB with GraphRAG/TypeDB/RDFLib/AtomSpace; eval found L2–L9 already exists in `MechanismCard` + cross_vertical + Belief OS, and what's missing is L0–L1 (corpus ingestion). This entry ships **one sensor + one chat surface + one walkthrough** instead. The sensor (`agent/research/ingest.py`) reads .txt/.md/.vtt/.srt sources and emits `MechanismCardProposal` rows to `~/.neuro_os_research/proposals/pending/`; the `/research-review` chat surface gates acceptance (Law 7 — human-in-loop); the walkthrough (`examples/10_research_to_invest_yang.py`) proves the **whole 4-vertical strange loop closes on one corpus**: research extracts → researcher shares 2 cards with investment → invest files PositionThesis citing them → Belief OS bias-checks → privacy assertion holds. Reuses every shipped primitive. No graph DB dependency. **Design:** `~/.claude/plans/research-graphrag-sensor.md`. | 5 days, 1 PR |
| 3 | **Founder_loop full structural refactor onto the substrate** *(continuation of Phase B)* | The Phase B adapter (`agent/founder_loop/domain_app_adapter.py`) proves founder_loop satisfies the substrate's `DomainConfig` protocol but DOESN'T replace founder_loop's internal `state.py`/`reward_ledger.py` with substrate-base subclasses. The full refactor would let bug fixes propagate uniformly across all 4 verticals (Story 3 of the before/after writeup). Risky: 222 founder_loop tests are the regression bar. | 3 days, 1 PR |
| 4 | **Tests against the live LLM path** | The conversation manager has 11 fallback tests but only one (skipped) LLM test. A small fixture-based recording test would prevent prompt regressions. | 1 |
| 5 | **`/today` MAE chart** | Currently a CLI nightly print. A small chart in the new-tab dashboard once real ≥7-day data exists. | 0.5 |
| 6 | **Queue-mutation undo** | `/queues` writes immediately; an "undo last change" button would make experimentation safer. | 0.5 |
| 7 | **Browser extension store listings** | "Load unpacked" is dev-only. Chrome Web Store + Firefox AMO need review. | 1 (+ wait time) |

---

## LATER (next quarter or v1)

Real work, not started.

### Reach + delivery

| Area | Why it matters | Cost (rough) |
|---|---|---|
| **One-click installer** (`.dmg` / `.exe` / `.AppImage`) | Today's `pip install` is a barrier for non-coders. Real installers solve it. | 1 week + ongoing code-signing certs (~$300/yr Apple, free on others). |
| **Chrome Web Store + Firefox AMO listings** | "Load unpacked" is dev-only. Store listings need review. | 1 week + ongoing reviewer back-and-forth. |
| **iOS / Android companion app** | Phone is where many urges fire (Instagram, TikTok). Desktop-only is a real gap. | 4–6 weeks + Apple Developer account. |
| **Apple Watch complication** | The watch is the embodied-need sensor (HRV → fatigue, stand time → eye-strain). Massive accuracy upgrade. | 2 weeks + iOS app prerequisite. |
| **Native Screen Time integration** (`pre_authorized_blocks` actually fires) | Currently `block_url` is a logged event, not a real block. Real blocks need OS-level permission. | 1 week (macOS first via Family Controls API). |
| **Apple Health / HealthKit pull** for sleep | Removes the workflowx-fixture dependency for the most-load-bearing signal. | 3 days inside the iOS app. |
| **Multi-user / team mode** | Today single-user only. A founders' chat where teams hold each other accountable would be powerful — but is its own product. | 4+ weeks. Defer. |
| **Voice morning ritual** | Speaking your priorities is faster than typing for the daily ceremony. Whisper API + iOS Shortcut. | 3 days. |
| **iMessage / SMS bot** | Universal-fallback intercept on any device. | 1 week + Twilio costs. |
| **Hosted (cloud) version** | Some users would happily trade privacy for "works on every device." We'd need to build it carefully — encrypted-at-rest, e2e if possible. | 4–6 weeks + ongoing infra. |

### Self-modification (v1 graduation)

| Area | Why it matters | Cost (rough) |
|---|---|---|
| **L2 self-modification of the sublimation catalog** | Currently the catalog is hand-edited; v1 promotes it under `mutable_paths` so failed-golden runs can rewrite catalog entries automatically. | 1 week + careful safety testing. |
| **`/catalog-review` chat surface** | The user-facing approval surface for catalog mutations. Without this the L2 graduation has no consent gate. Each accepted change writes atomically with a backup of the prior version; two consecutive reverts pause auto-proposals for 7 days. | 3 days (depends on L2 above). |
| **Laws-as-self-modifying-domain** | Today `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md` is treated as immutable Scripture. The 10x reframe: extract the 10 laws to `agent/data/principles_v1.json`, register a flywheel `Domain` for them, make the JSON mutable under `mutable_paths` with golden-case gates. The markdown is auto-generated from the JSON. CI logs every enforcer run to `versions/principles_runs.jsonl`; after enough data, a law that fires consistently AND whose violations don't actually break anything is *the law that's wrong*, and the L2 loop proposes a refinement. Closes the OEC loop on the laws themselves. Three benefits: (1) audit trail per law, (2) falsifiable laws over time, (3) self-correcting from real violation data. **Prerequisite:** measurement layer must show ≥10 PRs of enforcer-run data so the L2 loop has signal — currently `versions/principles_runs.jsonl` exists and logs every run but has minutes-of-data, not weeks. Earn this with use, then build. | 3 days build + 4–6 weeks of measurement before L2 gets real signal. |

### Alchemical override — converting distraction into research

A bigger v1 chapter. The premise: when a user proceeds anyway to a distraction, the *experience itself* can sometimes be converted into research that advances long-term work. Three terms required: distraction + named observation + produced artifact. Designed in detail in `~/.claude/plans/understand-the-code-base-fancy-phoenix.md` (Chapters 2–3); deliberately deferred until v0 ships and we have real capture data to validate the safeguards.

| Area | Why it matters | Cost (rough) |
|---|---|---|
| **Fundamental questions (`/questions` chat surface)** | User signs 3–5 long-term research questions tagged as project-shaped or theoretical. Captures must reference one to count. Without this anchor, "alchemical override" becomes "everything is research." | 1 day. |
| **Capture endpoint + browser-extension "Convert to research" button** | One-click on the Sublimation Card opens a 200-char observation modal tagged to a fundamental question. Pre-debits 50% of the override cost upfront; remainder forgiven only if a downstream artifact is produced within 7 days. Hard cap of 2 captures/day. | 2 days. |
| **`/synthesize` weekly digest (two-mode)** | Project-tagged captures emit structured catalog-edit proposals (feed `/catalog-review`); theoretical-tagged captures synthesize into draft research notes. Closes the loop: distraction time → product improvement OR publishable insight. | 2 days. |
| **Construction Law (artifact_kind enum)** | Final tank credit only when the linked artifact matches a fixed enum: `insight_published / code_committed / design_doc / conversation_logged / teaching_shared / action_with_outcome / catalog_proposal_accepted / transformation_logged`. Closes the "publish slop" backdoor. | 0.5 day. |
| **Alignment Gradient at capture time** | Three small structured fields per capture: direction (toward/ambiguous/away from the question's stakes), integration target (which question id), intended artifact kind. `away`-direction captures decay to zero credit unless the artifact is `insight_published` or `teaching_shared`. | 0.5 day. |
| **Meaning Density (third research bet)** | `artifact_conversion_rate = captures-with-artifact / total captures`. Tracked alongside MAE and contract-honor rate on the nightly summary. Day-28 success: ≥0.5. Lower means rationalization; >0.8 means raise the daily cap. | 0.5 day. |

### Smaller follow-ups

| Area | Why it matters | Cost (rough) |
|---|---|---|
| **MAE-trend dashboard** in `/today` | Currently a CLI nightly print. Worth a small chart in the dashboard once we have ≥7 days of real data. | 0.5 day. |

---

## Anti-goals

Things we are *not* going to build, and why.

- **A blocking mode.** Hard URL/app blocks defeat the philosophy. The
  "stick" in carrot/stick is making cost visible, not removing
  agency. If a user wants a hard block, they have plenty of other
  apps.
- **Gamification (streaks, leaderboards, achievements).** Distorts
  the contract from "promise to yourself" to "score in someone
  else's game." If it makes the user perform for the app instead of
  for themselves, it's wrong.
- **A social feed.** The data is yours; we don't share it. If
  community accountability becomes a feature, it'll be opt-in,
  per-message, and never automatic.
- **Telemetry / "anonymous usage data".** Even anonymized telemetry
  is a leak of attention patterns. If we ever add it, it'll be
  per-feature opt-in with a visible kill-switch.

---

## How to read this

If you're a user: focus on **SHIPPED**. That's what works today.
**NEXT** is what removes the rough edges in the next week or two.
**LATER** is "we'd love to" — don't count on any specific timeline.

If you're a contributor: pick from **NEXT** — those are scoped and
ready to start. Don't pick from **LATER** without first writing a
short design note here in `docs/` so we can align.

If you're trying to decide whether to use this: today the rough edges
are real (terminal install, manual workflowx, no phone). The
philosophy and core engine are solid. If those rough edges are too
much, watch the **NEXT** column ship.
