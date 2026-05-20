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

## SHIPPED (v0.7 — five compounding mechanisms on the four-vertical substrate)

**Latest:** PR-1 + PR-2 of Paul's week-of-May-11 cycle landed (PRs #23, #24). All five compounding lanes from the plan + the two follow-ups Paul's actual week needed are merged. **523 tests pass, 12 skipped** (10 e2e Playwright tests skip when chromium isn't installed; 1 Law 9 enforcer skips when no commits ahead of main; 1 LLM test is permanently skipped).

### Just-shipped: 5-lane compounding cycle + Paul-week unblockers

| Area | PR | Status | What's there |
|---|---|---|---|
| **Lane 1 — gbrain adapter (corpus ingestion)** | #18 | Complete | `agent/research/gbrain_adapter.py` + `proposals.py` + `ingest_router.py`. `--from-gbrain --export-file` reads gbrain export JSON → `MechanismCardProposal` queue. Conservative skip policy; 0 LLM calls in v0 adapter; 34 tests. |
| **Lane 5 — research dashboard** | #19 | Complete | `agent/research/dashboard.py` + `research dashboard [--window N] [--json]` CLI. Pure-aggregation rollup over `registry.jsonl` + `ingestion_runs.jsonl` + `proposals/*` + `mechanism_cards/*`. Compound curve, drift histogram, stick-rate, never-fired-catalog signal, action queue. 22 tests. |
| **Lane 4 — entity propagation** | #20 | Complete | `Entity` frozen schema in `agent/cross_vertical.py` (default-PRIVATE), `upsert_entity` / `share_entity` / `read_entity` / `list_entities`. `MechanismCardProposal` + `MechanismCard` carry `entity_mentions: List[str]`; `research review --cli` accept-prompt asks for slugs. CLI: `research entity-list / entity-read --reader <vertical>`. 23 tests. |
| **Lane 3 — cross-modal Belief OS** | #21 | Complete | `agent/cross_modal.py` — `CrossModalEval` frozen schema, `run_cross_modal_check` (K-scorer fan-out), `make_default_scorers` (3 Haiku/Sonnet/Opus pairs), `make_fixture_scorers` for tests. `agent/investment/config.py::run_cross_modal_bias_check` persists `(BiasCheck, CrossModalEval)` pair under same id; low-confidence prefix on disagreement. 19 tests. |
| **Lane 2 — skillify (catalog evolution)** | #22 | Complete | `agent/skillify/` package: `OverrideEvent` + `SkillProposal` frozen schemas, `extract_pattern` (bucket → threshold-gate → most-frequent user_action with recency tiebreak), `run_extraction` (skips already-proposed buckets). Top-level `skillify` CLI: `log-override / extract / proposals / review --cli`. 32 tests. **Law 7 honored: catalog mutation is a separate human commit; acceptance only moves the file to `accepted/`**. |
| **PR-1 — Plan A native extractor (Paul's week)** | #23 | Complete | `agent/research/ingest.py` — 4-stage pipeline for `.txt` / `.md` / `.pdf` (via `pypdf`). Anthropic Haiku LLM call OR regex-heuristic fallback. `--prefer {auto,gbrain,local}` flag activates Plan A; works without gbrain. 27 tests. |
| **PR-2 — Paul-week feature bundle** | #24 | Complete | (a) `loop urge --override-of <mode> --override-vertical <v>` auto-emits skillify OverrideEvent in same CLI call; (b) `cross-vertical share-note / query` CLI subtree; (c) `loop anchor --kind {faith,relational}` typed log + `count_anchors_per_day` for "5/7" rendering; (d) `Priority.time_window` regex-validated `HH:MM-HH:MM`. 25 tests. |
| **Three-Layer Research OS — Layer-1 deepening + Layer 2 + Layer 3 + checkpoint + dashboard health** | #28 | Complete | `agent/research/framework.py` (generic user-supplied framework, hand-edited JSON; **no hard-coded axes**). Extended `MechanismCard{Proposal}` with `first_principle` / `anti_pattern` / `transferability_test` / `verdict` / `one_sentence_compression` / `framework_alignment` (all optional — back-compat). `RawSource.tier ∈ {seed,frontier,lateral}` for source-pipeline classification. `agent/research/synthesis.py` (cluster by *mechanism* not topic; heuristic Jaccard + LLM clusterer — Plan-A-style placeholder for graphify adapter). `agent/research/briefs.py` (decision-ready brief from a `ProjectContext`; LLM + heuristic templated). `agent/research/checkpoints.py` (stop-condition `brief_produced + mental_model_clearer`; ≥2 consecutive non-converging → `system_not_converging` flag). Dashboard extended with `tier_balance` / `verdict_histogram` / `synthesis_run_count` / `briefs_produced_in_window` / 5-item `system_health_flags` (`chaser_mode` / `hoarder_mode` / `rubber_stamping` / `no_synthesis` / `system_not_converging`). CLI: `research synthesize` / `research brief` / `research checkpoint`. 46 new tests + 1 drive-by fix to dashboard time-boundary flake. |
| **MCP server / plugin (drive neuro-os from any AI agent)** | #29 | Complete | `agent/mcp_server.py` — FastMCP-based stdio server exposing 9 high-leverage neuro-os tools (`research_ingest` / `research_synthesize` / `research_brief` / `research_checkpoint` / `research_dashboard` / `loop_anchor` / `loop_urge` / `cross_vertical_share_note` / `cross_vertical_query`). `.mcp.json` at repo root wires Claude Code automatically when started from a checkout that has `pip install -e ".[mcp]"`. `neuro-os-mcp` console-script for other MCP clients (Cursor, `mcp-cli`, etc.). All tools are thin wrappers around existing `agent.*` functions; persistence flows through the same on-disk queues the CLI uses (MCP-driven writes are visible to subsequent CLI runs and vice versa). 23 tests. **Optional dependency** — `mcp` SDK is in `pyproject.toml`'s `[mcp]` extra so the core install stays small. |
| **Investment vertical Phase 1 + Phase 2 substrate (money-os complement)** | #30 | Complete | New: `agent/investment/options_income.py` (`OptionTrade` frozen schema; `expected_value` first-class with sample-size-guarded `win_rate`; `cash_secured_put` / `covered_call` / `wheel` / `credit_spread` / `iron_condor` / `naked` strategies). `agent/investment/megatrend.py` (`MegaTrendSleeve` literal; `compute_sleeve_balance` with 40% concentration warning; `compute_thesis_correct_rate`). `agent/investment/cost_of_living.py` (`CostOfLivingProfile`; `compute_income_gap`; best-effort `read_from_money_os_profile` bridge that parses money-os's `profile/financial-identity.md`). `agent/investment/dashboard.py` (5 health flags: `no_cost_of_living_target` / `phase1_income_gap_unmet` / `single_sleeve_concentration` / `no_thesis_invalidation` / `options_loss_concentration`). Extended `PositionThesis` with optional `sleeve` field (back-compat). CLI: `invest trade log/list/close`, `invest sleeve-balance`, `invest cost-of-living set/read`, `invest dashboard`. 33 tests. **Complements money-os** (the user's other Claude plugin) by filling 3 specific gaps: options support, mega-trend sleeve rollup, thesis-discipline invalidation tracking. Plan doc: `docs/plans/money-os-integration-and-realistic-investment-goals.md`. |
| **Investment MCP — talk-to-your-portfolio surface (8 new tools)** | this branch | Complete | `agent/mcp_server.py` extended with `invest_dashboard` / `invest_cost_of_living_set` / `invest_cost_of_living_read` / `invest_trade_log` / `invest_trade_close` / `invest_sleeve_balance` (6 wrappers) + `invest_propose_order` (HITL surface — returns EV math + risk banner ∈ {OK, NEGATIVE_EV, POOR_RATIO, DEEP_OTM}; never writes to disk) + `invest_next_action` (priority-ordered decision tree: returns ONE concrete next move based on dashboard flags). Server now exposes **17 tools total**. Combined with any speech-to-text feeding Claude Code, the investment vertical becomes voice-pilotable (read + propose + record cycle). 21 new tests; 44 MCP tests pass total. Plan doc: `docs/plans/voice-pilot-and-broker-mcp.md` names the still-missing pieces (broker MCP for execution; money-os MCP for analysis surface). |
| **Living-knowledge MVP — Layer 4 compression + Layer 5 expression + feedback loop** | #35 | Complete | `agent/research/compress.py` — frozen `HierarchicalCompression` schema with 3 levels (L0 = 3–5 core nodes, L1 = ≤30 cluster nodes, L2 = all accepted MechanismCards). `compress_from_synthesis` consumes a `SynthesisRun`, maps clusters 1:1 to L1, rolls up to ≤5 L0 nodes by `framework_axes_touched` overlap then smallest-pair merge. Pure function; persistence via `~/.neuro_os_research/compressions/<id>.json`. `agent/research/expression.py` — frozen `Expression` schema, 7 modalities (visual / musical / physical / organizational / game / biological / narrative). `record_expression` validates the source node exists in the named compression. `reveal_expression` closes the compress→express→refine loop: writes `reveals` + optional `feeds_back_to_node_id` (validated against the same compression). Content is text only; `tool_hint` names the external renderer (Tone.js / p5.js / Isaac Sim / markdown / etc.). CLI: `research compress [--from <id>] [--list] [--show <id>]` and `research express ...` (record / `--list` / `--show` / `--reveal --insight "..."`). 35 new tests. **Implements the aligned subset of the TRUE-E3 Living Knowledge Framework** ([`/Users/.../TRUE-E3-Living-Knowledge-Framework.md`](TRUE-E3-Living-Knowledge-Framework.md)) — specifically the compression and expression directions; E1 (embodied/VR via 3d-force-graph-vr / Isaac Sim) and E2 (interactive parameter dashboards via Streamlit wiring) deliberately deferred. End-to-end demo seeded with the framework doc itself: 4 MechanismCards → 4 clusters → 3-level compression → narrative expression of the feedback-closure principle → reveal recorded against the source L0 node. |

### Earlier: v0.5 substrate (the foundation those built on)

The reward-economy + sublimation engine, three UI surfaces, AND three
new verticals (research / investment / startup) on the
`agent/domain_app/` substrate.

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

**This week (May 11-17, 2026)** is Paul's first real-user week with the system: 40-day trial begins; daily reading + investment + company-building blocks tracked end-to-end. **Engineer-time deliverables for this week have shipped (PR-1 + PR-2).** The work that remains is non-engineering: actually running the trial. See [`docs/paul-week-may-11.md`](paul-week-may-11.md) for the daily-block CLI runbook.

| # | Item | Why now | Days |
|---|---|---|---|
| 1 | **40-day real-user trial of the research vertical** *(now actually unblocked)* | Lane 1 + PR-1 mean Paul can ingest the 3 papers + 2 books WITHOUT manual MechanismCard typing; Lane 5 means he can SEE the compound curve daily; Lane 2 + PR-2 (auto-emission) means the catalog will evolve from override evidence; Lane 4 means cross-vertical entity graph forms automatically. The Three-Layer Research OS extensions (Layer 2 synthesis / Layer 3 briefs / checkpoint / dashboard health flags) close the per-paper → cluster → brief loop. The trial that was previously "40 days of YOUR time, no engineer time" is now actually executable end-to-end. | 40 days of Paul's time |
| 1a | **graphify adapter for Layer 2 synthesis** | The in-tree `agent/research/synthesis.py` ships a heuristic Jaccard + LLM clusterer as Plan-A-style placeholders. The user has an external `Projects/graphify` that does graph-shaped entity clustering — the right long-term backend. Follow-up PR mirrors `agent/research/gbrain_adapter.py` to delegate synthesis to graphify when available, falling back to the in-tree paths otherwise. **Requires scoping graphify's output schema first; do not write code blind.** | 1–2 d (after graphify audit) |
| 1b | **money-os adapter for investment vertical** | The investment vertical today has its own schemas (`PositionThesis`, `BiasCheck`, etc.). The user has an external `Projects/money-os` that owns the actual money state. The follow-up wires `invest review --cli` + `invest dashboard` to read FROM money-os rather than implementing parallel storage. **Anti-goal: do NOT ship parallel invest review/dashboard before this adapter is scoped.** | 1–2 d (after money-os audit) |
| 1c | **company-os / gstack / workflowx adapters for startup vertical** | Same pattern: startup vertical becomes a thin lens over the user's existing `Projects/{company-os,gstack,workflowx}` outputs instead of duplicating their data model. | 2 d (after audit of the three) |
| 2 | **`/research-review` chat surface** *(replaces Lane 1's CLI REPL for high-volume review)* | The CLI REPL handles 10-30 proposals/week comfortably. If Paul scales to 50+ MechanismCardProposals/week (e.g. ingests his entire reading-list backlog), an LLM-driven review surface that batches approvals + suggests entity_mentions auto-fill would save real time. Defer until usage proves the need. | 2 days, 1 PR |
| 3 | **Tests against the live LLM path** | The conversation manager has 11 fallback tests but only one (skipped) LLM test. A small fixture-based recording test would prevent prompt regressions. | 1 |
| 4 | **`/today` MAE chart** | Currently a CLI nightly print. A small chart in the new-tab dashboard once real ≥7-day data exists. | 0.5 |
| 5 | **Queue-mutation undo** | `/queues` writes immediately; an "undo last change" button would make experimentation safer. | 0.5 |
| 6 | **Browser extension store listings** | "Load unpacked" is dev-only. Chrome Web Store + Firefox AMO need review. | 1 (+ wait time) |

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

A bigger v1 chapter. The premise: when a user proceeds anyway to a distraction, the *experience itself* can sometimes be converted into research that advances long-term work. Three terms required: distraction + named observation + produced artifact. Designed in detail in [`docs/plans/understand-the-code-base-fancy-phoenix.md`](plans/understand-the-code-base-fancy-phoenix.md) (Chapters 2–3); deliberately deferred until v0 ships and we have real capture data to validate the safeguards.

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
| **Founder_loop full structural refactor onto the substrate** *(continuation of Phase B)* | The Phase B adapter (`agent/founder_loop/domain_app_adapter.py`) proves founder_loop satisfies the substrate's `DomainConfig` protocol but DOESN'T replace founder_loop's internal `state.py`/`reward_ledger.py` with substrate-base subclasses. The full refactor would let bug fixes propagate uniformly across all 4 verticals. Risky: 222 founder_loop tests are the regression bar. Defer until a substrate bug actually requires a 4-vertical fix that the adapter pattern can't deliver. | 3 days, 1 PR. |

### Deferred follow-ups from the Lane 1-5 cycle (filed honestly, not lost)

These were proposed, scoped, and consciously deferred. Each is named with WHY it's not on NEXT.

| Area | Why it's deferred | Cost (rough) |
|---|---|---|
| **gbrain MCP live wiring** (Lane 1) | Paul has no gbrain installed on his machine; PR-1 (Plan A native extractor) replaces this for his actual week. ROI = 0 today. Revisit if Paul installs gbrain OR if a second user appears who has it. The wiring would replace the `--export-file` step with a live `gbrain serve` subprocess; same `MechanismCardProposal` schema. | 1 day, 1 PR. |
| **Parallel scorer execution** (Lane 3) | Engineering hygiene only. Saves ~4 sec on a flow Paul does maybe twice a week (cross-modal bias check on a position thesis). User-value rating: 1/5. Filed here so it's grep-able when someone has spare time; do NOT prioritize over real Paul-week work. | 0.5 day. |
| **Text-normalization clustering** (Lane 2) | Skillify's `_pick_candidate_action` uses exact-string match today. Normalization (lowercase + strip trailing punctuation + collapse whitespace) would cluster "Wrote a Markdown brief." and "wrote a markdown brief" as the same action. **Useless without cumulative data**: with only 7 days of one user's overrides, exact-match works fine. Revisit after the 40-day trial when there's enough data to cluster. | 0.5 day. |
| **Semantic-similarity clustering for skillify** (Lane 2 v2) | The "10x" version of the above: real embedding-based similarity (sentence-transformers OR Anthropic embeddings) would catch semantically-equivalent overrides like "wrote a brief" and "did a one-pager." New runtime dep + per-cluster cost. Defer until text-normalization proves insufficient on real data. | 1 day, 1 PR + new dep gate. |
| **Auto-emission from chat surfaces** | PR-2 ships `loop urge --override-of` for the existing CLI surface. The new chat surfaces (`/research-review`, `/skillify-review`) don't exist yet — only their CLI REPLs do. Auto-emission FROM chat surfaces requires those surfaces to ship first. Folded into the future `/research-review` chat surface ticket above. | Bundled. |
| **Anchor counts in NightlySummary** | PR-2 ships the typed anchor log + `count_anchors_per_day()` query function. Folding the count into `NightlySummary.extra` requires adding an `extra` field (schema change with regression risk). Defer until the dashboard surfaces the streak (then it's worth the schema change). | 1 day. |

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
