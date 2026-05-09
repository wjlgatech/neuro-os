# Plan — 40-day trial dashboard (Lane 5)

> **Status:** design doc only. No code shipped.
>
> **One-line summary:** ship a per-vertical `dashboard` CLI subcommand that aggregates the registry + ingestion-run logs into a single human-scannable rollup, so the user can SEE the compound curve while running the 40-day trial.

## Why now

Lane 1 (gbrain adapter) just shipped: ingestion lands proposals in `~/.neuro_os_research/proposals/pending/`, the user accepts via `research review --cli`, and `MechanismCard` rows appear in `~/.neuro_os_research/mechanism_cards/`. There's also `ingestion_runs.jsonl` (Lane 1) and `registry.jsonl` (existing) accumulating evidence.

**Without a dashboard, the 40-day trial is a faith-based exercise.** The user can't tell:
- whether the prediction-MAE / calibration-error / continuity-score is trending the right direction,
- which drift modes fired more than expected,
- which constructive expressions stuck (no later override) vs. churned,
- whether ingested proposals converted to accepted cards at a healthy rate (translate quality).

Lane 5 ships ~1 day of pure-aggregation code — no new schemas, no new daemon, no new dependencies. It reads the artifacts the other lanes already write and prints a single rollup the user actually looks at every morning.

This is also the ground-truth feeder for **NEXT #1** (the 40-day real-user trial). Every catalog-revision argument we'll have a month from now will start with "the dashboard says ...".

## Goal

> *User runs `neuro-os <vertical> dashboard` once per day → sees the 40-day compound curve in one screen → makes a yes/no call on whether the catalog is calibrating to reality, before the cost of being wrong compounds.*

One day of work. One new module per vertical (~80 LOC each, 4 verticals × ~80 = ~320 LOC total but only `research` ships in Lane 5; the other three follow once `research` proves the format). One new CLI subcommand (`<vertical> dashboard`). Reads existing artifacts only.

## Architecture — file tree (delta against today)

```
agent/research/
├── dashboard.py              # NEW: pure-aggregation rollup over registry + ingestion logs
└── (everything else unchanged)

agent/cli.py                  # MODIFY: add `research dashboard` subcommand

tests/
└── test_research_dashboard.py    # NEW: golden-fixture rollup → expected counts
└── fixtures/research/
    ├── registry_40d.jsonl        # NEW: synthetic 40-day registry
    └── ingestion_runs_40d.jsonl  # NEW: synthetic 40-day ingestion log
```

Three new files (~150 LOC total). Zero modifications to schemas, zero modifications to existing handlers.

## Schemas — frozen Pydantic

One new schema, shipped as part of Lane 5. Pinned by `tests/test_research_dashboard.py`.

### `DashboardSummary` (new, in `agent/research/dashboard.py`)

```python
class DashboardSummary(BaseModel):
    """One-shot rollup of the last N days for the research vertical.

    Pure function of (registry.jsonl + ingestion_runs.jsonl + proposals/*).
    No mutation; the dashboard NEVER writes to disk. Reading the dashboard
    is idempotent; it does not change the trial state.
    """
    model_config = ConfigDict(frozen=True)

    vertical: Literal["research", "investment", "startup", "founder_loop"]
    window_days: int = Field(ge=1, le=365)
    generated_at: datetime

    # Compound-curve numbers (the headline). The 4 first-class metrics from
    # the substrate, computed over the window:
    primary_metric_today: float        # mechanism_cards/day for research
    primary_metric_7d_avg: float
    primary_metric_window_avg: float
    primary_metric_window_trend: Literal["up", "down", "flat"]

    # Drift-mode usage histogram — one bucket per named drift mode.
    drift_mode_counts: Dict[str, int]
    drift_mode_top_3: List[Tuple[str, int]]

    # Constructive-expression stick-rate — for each accepted CE, did the
    # user later override? (override = same drift mode fired again < 7 days
    # later AND the user picked a different CE that time.)
    constructive_expressions_offered: int
    constructive_expressions_accepted: int
    constructive_expressions_stuck: int   # accepted AND no override within 7d

    # Lane 1 health (research-only): translate-rate from gbrain ingestion.
    sources_scanned: int
    proposals_emitted: int
    proposals_accepted: int
    proposals_rejected: int

    # The "what's missing" signal — drift modes the catalog claims exist
    # but that NEVER fired. Strong evidence the catalog is wrong.
    drift_modes_never_fired: List[str]

    # The user-action queue (so the dashboard has a footer that's ACTIONABLE,
    # not just data):
    pending_proposals_count: int
    pending_proposals_oldest_age_hours: Optional[float]
```

## The aggregation pipeline — `agent/research/dashboard.py`

A pure function over three inputs. No state.

```python
def build_dashboard_summary(
    *,
    home: Optional[Path] = None,
    window_days: int = 40,
    now: Optional[datetime] = None,
) -> DashboardSummary:
    """Read the artifacts under `home` (default ~/.neuro_os_research/),
    aggregate, return a frozen DashboardSummary.

    Inputs (all read-only):
      - registry.jsonl                ← drift events + ConstructiveExpression offers
      - ingestion_runs.jsonl          ← Lane 1 audit log
      - proposals/{pending,accepted,rejected}/*.json ← proposal queue snapshot

    Output: a frozen DashboardSummary the CLI (or a future web view)
    renders.
    """
```

Three sub-functions, each a one-screen of code, each independently testable:

1. `_aggregate_drift_modes(registry_rows) -> Dict[str, int]` — counts drift events per mode.
2. `_compute_stick_rate(registry_rows) -> Tuple[int, int, int]` — for each offered CE, walk forward 7 days and check if the same drift_mode fired with a different CE.
3. `_aggregate_proposals(home) -> Tuple[int, int, int, int]` — count files in each proposal status dir.

The headline `primary_metric_*` numbers come from the existing nightly registry (which already records mechanism_cards/day per nightly). Lane 5 just trends them.

## CLI — one new subcommand

```bash
neuro-os research dashboard                   # 40-day window (default)
neuro-os research dashboard --window 7        # custom window (1–365)
neuro-os research dashboard --json            # machine-readable for piping
neuro-os research dashboard --home <path>     # tests pass explicit paths
```

Default output is text, single screen, ~30 lines. Example shape:

```
research vertical — 40-day dashboard (generated 2026-06-18 09:14:00 UTC)
======================================================================

Compound curve
  mechanism_cards/day:  today=1   7d-avg=2.1   40d-avg=1.8   trend=up
  thesis_continuity:    1.00  (40 of 40 days on the original thesis)
  prediction_accuracy:  0.62  (8 of 13 verified predictions correct)

Drift-mode usage (top 3)
  paper_collector  ████████████  17
  topic_hopper     ██████         8
  authority_acceptor ███          4
  (forgetting / overloaded / memorizer fired 0 times — catalog candidates?)

Constructive expressions
  offered:  29   accepted:  21   stuck:  18   stick-rate=86%

Lane 1 ingestion
  sources scanned:    8     proposals emitted:  14
  accepted:           9     rejected:           4     pending:  1

Action queue
  1 pending proposal — oldest 14h old.  Run `research review --cli`.
```

Pure text. No graphics. No web. The user can `--json` it into anything else they want.

## Privacy / Law gates

Lane 5 is read-only. Five gates inherited from existing code:

1. **No writes.** The dashboard reads `registry.jsonl`, `ingestion_runs.jsonl`, and `proposals/*` — never writes. Idempotent.
2. **Bounded read paths.** Only files under `home_dir` are read. No wandering.
3. **No cross-vertical reads.** The research dashboard only reads `~/.neuro_os_research/`. The investment dashboard reads only `~/.neuro_os_invest/`. Cross-vertical aggregation is a separate (LATER) concern.
4. **Frozen Pydantic at the boundary** (Law 5). `DashboardSummary` is frozen; CLI prints it but never mutates.
5. **No telemetry.** The dashboard never phones home, even for "anonymous usage stats." It's local-only forever.

## Test gates

| Test | Assertion |
|---|---|
| `test_build_dashboard_summary_against_fixture` | Synthetic 40-day fixture → DashboardSummary with known counts |
| `test_dashboard_handles_empty_home` | Brand-new install (no registry yet) → DashboardSummary with zeros, doesn't crash |
| `test_dashboard_window_clipping` | window_days=7 only counts last 7 days from registry |
| `test_drift_modes_never_fired_signal` | Modes in catalog but absent from registry → reported in `drift_modes_never_fired` |
| `test_constructive_expression_stick_rate` | Same drift_mode within 7d with different CE → "not stuck"; otherwise "stuck" |
| `test_dashboard_summary_is_frozen` | `summary.window_days = 1` raises (Pydantic ValidationError) |
| `test_cli_research_dashboard_prints_text` | `python -m agent research dashboard --home <fixture>` exits 0, output contains "Compound curve" |
| `test_cli_research_dashboard_json` | `--json` flag → stdout parses as DashboardSummary JSON |

## Implementation order — 1 day

| Hour | Deliverable | Test gate |
|---|---|---|
| 0–2 | `DashboardSummary` schema + `build_dashboard_summary` skeleton + `_aggregate_drift_modes` | Schema gate (frozen, round-trip); aggregation handles empty home |
| 2–4 | `_compute_stick_rate` + `_aggregate_proposals` | Stick-rate tests; proposal-count tests |
| 4–6 | CLI wiring (`research dashboard` + `--window` + `--json`) | Subprocess CLI tests pass |
| 6–8 | Synthetic fixture (`registry_40d.jsonl` + `ingestion_runs_40d.jsonl`) + golden-output test | Full rollup test passes |

### Gate priority

| Gate | Hour | If this fails |
|---|---|---|
| **Empty-home gate** | 2 | Stop. Brand-new users will hit this on day 1; if it crashes, day 1 is lost. |
| **Stick-rate accuracy** | 4 | Stop. The whole point of the 40-day trial is to learn which CEs stick; if the math is wrong, the trial is mistraining. |
| **Window clipping** | 4 | Continue with caveat. Off-by-one on the window matters less than stick-rate accuracy. |

## What this does NOT do (explicit cuts)

- **No web view.** Text + JSON only. A web dashboard is a follow-up if it's useful; the CLI is enough for the 40-day trial.
- **No automatic emailing / notifications.** Local-first, pull-only. The user looks at the dashboard when they choose to.
- **No cross-vertical aggregation.** Each vertical has its own dashboard. A single "platform-wide compound view" is a LATER concern.
- **No catalog mutation.** The dashboard SHOWS catalog candidates (drift modes never fired); it never writes to the catalog. That stays human-gated via `/catalog-review`.
- **No history retention beyond what's already on disk.** If `registry.jsonl` is rotated, the dashboard rolls up only what remains. Long-term archival is the user's call.

## The 4-vertical extension (LATER, deferred — same as Lane 1)

After research validates the dashboard format, the same module extends trivially:

```
agent/investment/dashboard.py      # calibration_error trend + position_edits/window
agent/startup/dashboard.py         # strategic_continuity_score + pivot_count/window
agent/founder_loop/dashboard.py    # prediction_MAE trend + tank-burn / contract-honor
```

Each is a copy-paste of the research dashboard with the vertical's specific metric labels swapped in. ~30 minutes per vertical. **Not in scope for Lane 5.**

## Closing the loop — what success looks like

The day this graduates to SHIPPED is the day this sequence runs:

1. User has been running the 40-day trial for ≥7 days, accepting cards via Lane 1.
2. User runs `research dashboard` first thing in the morning (it's a habit, like checking weather).
3. Dashboard shows: prediction_accuracy trending up, paper_collector firing 3× more than authority_acceptor, "memorizer" mode never fired in 7 days, two constructive expressions stuck with 100% rate, one CE got overridden 4 times.
4. User opens `/catalog-review` and proposes: drop "memorizer" mode (no signal), add "perfectionism" mode (the 4-override CE was actually addressing a different drift), bump "paper_collector"'s top constructive expression to first-position default.
5. Catalog mutation goes through Law 7 gate; substrate's 6-mode invariant holds (one out, one in).

That sequence is the closed loop the entire neuro-os bet is on. **Lane 5 is the visibility layer that makes it diagnosable instead of mystical.**

## Coupling with Lane 1 (this PR)

This design ships in the **same PR** as Lane 1 implementation, by the user's call. Two reasons:
1. The dashboard reads ingestion_runs.jsonl which Lane 1 just started writing — the moment Lane 1 ships, there's data to chart.
2. The 40-day trial value-prop is "you can SEE compounding"; ingest-without-dashboard means the user is flying blind for 7+ days waiting for Lane 5.

The PR includes Lane 1 implementation + this design doc. The actual Lane 5 implementation is the next PR after, scoped at exactly 1 day.
