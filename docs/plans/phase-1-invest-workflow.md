---
status: done
parent: invest
reason: "Shipped 2026-05-12 (commit ef1e703): cost-of-living set + trade log + sleeve field + dashboard --window. Next slice (TradeOutcome calibration loop) is its own plan when needed."
---

# Phase-1 invest workflow — design + implementation plan

**Status:** Plan locked, ready to implement.
**Owner:** Paul.
**Branch:** `prd/draft`.
**Anti-goal preserved:** The investment vertical stays **advisory-only**. Trade logging is a *journal* (decision discipline gate), not a broker integration. No order routing, no order state, no execution-shaped evidence types.

---

## North-star user workflow (from the snippet)

```bash
# 1. Set the headline metric
neuro-os invest cost-of-living set --monthly-target 14000 --region "Bay Area"

# 2. As you make trades, log them (the discipline gate)
neuro-os invest trade log --strategy cash_secured_put \
    --ticker NVDA --underlying-price 920 --expiry 2026-06-19 \
    --strikes 880 --premium 1200 --max-loss 88000 \
    --win-prob 0.80 --assignment-prob 0.20

# 3. Tag PositionTheses with their mega-trend sleeve
#    edit ~/.neuro_os_investment/position_theses/*.json adding "sleeve": "ai"

# 4. Weekly
neuro-os invest dashboard --window 30
```

---

## What exists today (baseline)

- `agent/investment/__init__.py`, `config.py`, `catalog.py`, `ontology.py`
- Storage rooted at `~/.neuro_os_investment/`:
  - `registry.jsonl` — drift events
  - `contracts.jsonl` — daily contracts
  - `position_theses/<id>.json` — `PositionThesis` records
  - `bias_checks/<id>.json`
  - `cross_modal_evals/<id>.json`
  - `calibration_records/<id>.json` (consumed by `nightly()` but no writer wired yet)
- CLI surface: `invest onboard | tick | nightly`
- `PositionThesis` is **frozen Pydantic** with: id, ts, instrument, side, thesis, evidence, invalidation_condition, expected_timeline, confidence, status, invalidation_reason, parent_thesis_id. **No `sleeve` field today.**
- Helper `write_position_thesis()` writes the JSON + emits a PRIVATE `cross_vertical` note.

---

## What's missing → 4 deliverables

| # | Deliverable | Why |
|---|---|---|
| 1 | `sleeve` field on `PositionThesis` | Enable mega-trend allocation view in dashboard |
| 2 | `CostOfLivingTarget` schema + `invest cost-of-living set` CLI | Headline-metric anchor for the run-rate dashboard |
| 3 | `TradeLog` schema + `invest trade log` CLI | Discipline gate: every trade is logged with win-prob + max-loss before it's "real" |
| 4 | `agent/investment/dashboard.py` + `invest dashboard --window` CLI | Weekly rollup: premium run-rate vs. cost-of-living, max-loss exposure, sleeve allocation |

---

## Schemas (all frozen Pydantic — Law 1, Law 5)

### `PositionThesis.sleeve` (new field, additive)

```python
Sleeve = Literal["ai", "energy", "biotech", "macro", "crypto", "other"]

class PositionThesis(BaseModel):
    # ...existing fields unchanged...
    sleeve: Optional[Sleeve] = Field(
        default=None,
        description="Mega-trend allocation bucket. Optional; untagged theses bucket under 'untagged' in the dashboard.",
    )
```

- Frozen-model invariant preserved: backfilling existing JSON = rewriting the file. The snippet workflow `edit ~/.neuro_os_investment/position_theses/*.json adding "sleeve": "ai"` works because Pydantic will accept the field on reload.
- No CLI for thesis creation today; Python API (`write_position_thesis`) and manual JSON edits remain the entry points.

### `CostOfLivingTarget` (new) → `agent/investment/cost_of_living.py`

```python
class CostOfLivingTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    monthly_target: float = Field(gt=0.0, le=1_000_000.0, description="Monthly cash target in USD.")
    region: str = Field(min_length=1, max_length=80, description="Free-text region label, e.g. 'Bay Area'.")
    ts: datetime
    notes: Optional[str] = Field(default=None, max_length=400)
```

- **Storage:** `~/.neuro_os_investment/cost_of_living.json` — single file, latest wins. (History can come later; v0 is one current target.)
- **Helper:** `write_cost_of_living_target(target, *, home=None) -> None`, `read_cost_of_living_target(*, home=None) -> Optional[CostOfLivingTarget]`.

### `TradeLog` (new) → `agent/investment/trade.py`

```python
TradeStrategy = Literal[
    "cash_secured_put",
    "covered_call",
    "long_stock",
    "short_call_spread",
    "short_put_spread",
    "iron_condor",
    "other",  # escape hatch; user adds notes
]

class TradeLog(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    strategy: TradeStrategy
    ticker: str = Field(min_length=1, max_length=12)
    underlying_price: float = Field(gt=0.0)
    expiry: date  # ISO date
    strikes: List[float] = Field(min_length=1, max_length=4)  # 1 for CSP/CC, 2-4 for spreads
    premium: float = Field(gt=0.0, description="Net credit received (or paid, for long debit positions — log as negative if debit).")
    max_loss: float = Field(gt=0.0, description="Max dollar loss if the trade goes against you to the breakeven.")
    win_prob: float = Field(ge=0.0, le=1.0)
    assignment_prob: float = Field(ge=0.0, le=1.0)
    thesis_id: Optional[str] = Field(default=None, max_length=64, description="Link to a PositionThesis if filed.")
    sleeve: Optional[Sleeve] = Field(default=None, description="Mirrors PositionThesis.sleeve when no thesis is linked.")
    notes: Optional[str] = Field(default=None, max_length=400)
```

- **Storage:** `~/.neuro_os_investment/trades/<id>.json` — one file per trade.
- **Helper:** `write_trade_log(trade, *, home=None) -> None`, `iter_trade_logs(*, home=None, window_days=None) -> Iterator[TradeLog]`.
- **Advisory-only note:** This is a **post-decision journal**, not a pre-order ticket. Recording a trade does NOT send anything to a broker. The class docstring will reaffirm this.

### `InvestDashboardSummary` (new) → `agent/investment/dashboard.py`

```python
class InvestDashboardSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    vertical: Literal["investment"] = "investment"
    window_days: int = Field(ge=1, le=365)
    generated_at: datetime

    # Headline: cost-of-living coverage
    monthly_target: Optional[float] = None
    region: Optional[str] = None
    premium_collected_in_window: float = Field(ge=0.0, default=0.0)
    premium_per_month_run_rate: float = Field(ge=0.0, default=0.0)
    cost_of_living_coverage_pct: Optional[float] = None  # run_rate / target

    # Trade-log rollup
    trades_in_window: int = Field(ge=0, default=0)
    trades_by_strategy: Dict[str, int] = Field(default_factory=dict)
    max_loss_exposure_total: float = Field(ge=0.0, default=0.0)
    mean_win_prob: Optional[float] = None
    mean_assignment_prob: Optional[float] = None

    # Sleeve allocation (across all active PositionTheses, not windowed)
    theses_by_sleeve: Dict[str, int] = Field(default_factory=dict)  # key="untagged" for None

    # Calibration + bias (read from existing dirs; mirrors nightly())
    calibration_error_in_window: Optional[float] = None
    bias_checks_in_window: int = Field(ge=0, default=0)
```

- Pure aggregation. Read-only — writes nothing.
- `build_invest_dashboard(*, home, window_days=30, now=None) -> InvestDashboardSummary`
- `render_text(summary) -> str` — text renderer matching the research-dashboard style.

---

## Storage layout (final)

```
~/.neuro_os_investment/
├── registry.jsonl                 # (existing)
├── contracts.jsonl                # (existing)
├── cost_of_living.json            # NEW — single-current-target file
├── position_theses/<id>.json      # (existing; add optional "sleeve" field)
├── trades/<id>.json               # NEW
├── calibration_records/<id>.json  # (existing)
├── bias_checks/<id>.json          # (existing)
└── cross_modal_evals/<id>.json    # (existing)
```

---

## CLI surface (final)

```
neuro-os invest
├── onboard          (existing)
├── tick             (existing)
├── nightly          (existing)
├── cost-of-living
│   ├── set --monthly-target <FLOAT> --region <STR> [--notes <STR>] [--home <PATH>]
│   └── show [--json] [--home <PATH>]
├── trade
│   ├── log --strategy <ENUM> --ticker <STR> --underlying-price <FLOAT>
│   │       --expiry <YYYY-MM-DD> --strikes <FLOAT>[,<FLOAT>...]
│   │       --premium <FLOAT> --max-loss <FLOAT>
│   │       --win-prob <0..1> --assignment-prob <0..1>
│   │       [--thesis-id <STR>] [--sleeve <ENUM>] [--notes <STR>] [--home <PATH>]
│   └── list [--window <DAYS>] [--json] [--home <PATH>]
└── dashboard --window <DAYS> [--json] [--home <PATH>]
```

**Wiring:** Add `_add_invest_workflow_subcommands(top_sub)` called inside `_add_vertical_subcommands(..., vertical_name="invest", ...)`, mirroring how `_add_research_ingest_subcommands` is called for research (`agent/cli.py:803-804`).

**`show` and `list`** are unobtrusive complements to `set` and `log` — they let the user inspect what they've written. Not in the user's snippet but trivial and load-bearing for debugging.

---

## Test plan

New file: `tests/test_investment_workflow_phase1.py`.

Coverage:

| Test | What it pins |
|---|---|
| `test_position_thesis_accepts_sleeve_field` | Schema accepts the new optional field |
| `test_position_thesis_sleeve_defaults_to_none` | Backwards compat for existing JSON |
| `test_position_thesis_rejects_unknown_sleeve` | Enum guard |
| `test_cost_of_living_target_validates_positive_target` | `gt=0.0` constraint fires |
| `test_cost_of_living_set_writes_and_reads_back` | Round-trip JSON |
| `test_cost_of_living_set_overwrites_existing` | Latest-wins semantics |
| `test_trade_log_validates_win_prob_range` | `0 ≤ win_prob ≤ 1` |
| `test_trade_log_validates_assignment_prob_range` | `0 ≤ assignment_prob ≤ 1` |
| `test_trade_log_strategy_enum_contains_cash_secured_put` | Required strategy |
| `test_trade_log_requires_at_least_one_strike` | `min_length=1` |
| `test_trade_log_writes_to_trades_dir` | Storage path |
| `test_iter_trade_logs_filters_by_window_days` | Window filter |
| `test_invest_dashboard_empty_state` | Returns valid summary with zeros, not crash |
| `test_invest_dashboard_aggregates_trades_in_window` | Premium sum, count by strategy, max-loss sum |
| `test_invest_dashboard_excludes_trades_outside_window` | Off-by-one |
| `test_invest_dashboard_cost_of_living_run_rate` | run_rate = premium_window × 30 / window_days |
| `test_invest_dashboard_coverage_pct_with_target` | coverage = run_rate / target |
| `test_invest_dashboard_coverage_pct_with_no_target` | None, not crash |
| `test_invest_dashboard_sleeve_allocation` | Counts by sleeve, "untagged" bucket for None |
| `test_invest_dashboard_calibration_error` | Mirrors `nightly()` calc, windowed |
| `test_invest_dashboard_render_text_returns_string` | render works on full + empty |
| `test_invest_dashboard_cli_window_validation` | `--window 0` → exit 2 |
| `test_invest_dashboard_cli_emits_json` | `--json` flag |
| `test_invest_advisory_only_invariant_preserved` | TradeLog does NOT add execution-shaped evidence types to EVIDENCE_TYPE |

Extend `tests/test_verticals_cli.py` with smoke tests for the new top-level subcommands (`invest cost-of-living set`, `invest trade log`, `invest dashboard`).

---

## Implementation order (3 atomic commits)

**Commit 1: schemas + storage helpers**
- Add `Sleeve` literal and `sleeve` field to `PositionThesis`.
- New module `agent/investment/cost_of_living.py` — schema + read/write helpers.
- New module `agent/investment/trade.py` — schema + read/write/iter helpers.
- Re-export from `agent/investment/__init__.py`.
- New file `tests/test_investment_workflow_phase1.py` with the schema-and-helper tests (all except dashboard + CLI).
- Run `pytest tests/ -k investment` + `ruff check agent/ tests/` + `pytest tests/test_engineering_principles.py -v`. All green.

**Commit 2: dashboard module**
- New module `agent/investment/dashboard.py` — `InvestDashboardSummary` + `build_invest_dashboard` + `render_text`.
- Add the dashboard tests to `tests/test_investment_workflow_phase1.py`.
- Re-export from `agent/investment/__init__.py`.
- Same gates.

**Commit 3: CLI wiring**
- Add `_add_invest_workflow_subcommands(top_sub)` to `agent/cli.py` — `cost-of-living {set,show}`, `trade {log,list}`, `dashboard`. Wire it inside `_add_vertical_subcommands` when `vertical_name == "invest"`.
- Add handler functions: `_invest_cost_of_living_set_handler`, `_invest_cost_of_living_show_handler`, `_invest_trade_log_handler`, `_invest_trade_list_handler`, `_invest_dashboard_handler`.
- Add CLI smoke tests to `tests/test_verticals_cli.py`.
- Final law-gate sweep.

---

## Law-compliance map

| Law | Compliance |
|---|---|
| **Law 1** — Pydantic at every input boundary | All new schemas are Pydantic with field validators. CLI args parse into the models before persistence. |
| **Law 2** — substrate vs vertical separation | All new code lives in `agent/investment/`. Substrate untouched. |
| **Law 3** — catalog invariant | `INVESTMENT_CATALOG` untouched. 6 needs, 2 options each. |
| **Law 5** — no dict returns | All public functions return Pydantic models. `render_text` returns `str`. |
| **Law 6** — ControlOp inverse | No new ControlOps. |
| **Law 7** — `mutable_paths=[]` | Unchanged. New writes are application state under `~/.neuro_os_investment/`, not code patches. |
| **Law 9** — three-section commit format | Every commit ships with `What changed / Why it changed / Validation`. |

---

## Privacy posture

- `cost_of_living.json`: local-only. No `cross_vertical` note. The dollar target is sensitive personal info; do not surface it to other verticals.
- `trades/<id>.json`: local-only. No `cross_vertical` note. Trade history is the highest-sensitivity data in the vertical.
- `PositionThesis` with `sleeve`: existing `write_position_thesis()` already emits a PRIVATE `cross_vertical` note (`visible_to=["investment"]`). Sleeve tag rides along when explicitly shared.

---

## Out of scope (explicit non-goals)

- No broker integration. No order placement. No live price feeds. No P&L tracking against current market quotes. (The trade log captures the user's *expectation* at trade time — `win_prob`, `assignment_prob`, `max_loss` — not realized outcomes. Realized outcomes belong to a future `TradeOutcome` schema that closes the calibration loop, but that's a separate plan.)
- No sleeve quotas / rebalancing rules. The dashboard *displays* sleeve allocation; it does not enforce or recommend.
- No multi-currency support. USD only.
- No historical cost-of-living (latest-wins single file). History view is a future enhancement.
- No `invest thesis log` CLI subcommand. Theses are filed via the Python API or manual JSON edits.

---

## Decisions to revisit later (parked)

- **TradeOutcome to close the calibration loop**: when an option expires or a position is closed, the user logs the realized outcome; the dashboard then computes calibration error per `(strategy, sleeve)` slice. This is where the discipline gate compounds into edge.
- **History on cost-of-living**: switch from single-file to JSONL when there are 2+ revisions.
- **Sleeve quotas**: optional `~/.neuro_os_investment/sleeve_policy.json` defining target allocations and surfacing drift in the dashboard.
- **Cross-vertical sharing of sleeve tags**: opt-in surface so `research` can see what mega-trends `investment` is leaning on, for cross-domain mechanism transfer.
