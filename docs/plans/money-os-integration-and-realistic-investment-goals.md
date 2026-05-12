# Plan — money-os integration + realistic investment goals

> **Status:** Plan only. No code yet. This doc memorializes the honest eval
> + 10X reframe of the user's stated goal, and scopes the substrate work
> that would actually support the achievable version.
>
> **Author note:** This is intellectually honest, not motivational. The
> goals here are aspirations; the math under them is real.

## The user's stated goal

> Do option trading with 80+% winning rate to bring in steady income (so
> that I do not rely on my 9 to 5 to substain my family living cost 12k
> to 14k per mo in the Bay Areas); invest in the 7 mega trends (AI +
> Crypto + quantum + synthetic bio + space tech + robotic) and have 50%
> yearly increase. Doubling my worth every 3 months: 1M in 3 mo, 2M in 6
> mo, 4M in 9 mo, 10M in 12 mo, 20M in 15 mo, 40M in 18 mo, 100M in 21 mo.

## Honest eval

### Claim 1 — 80%+ options win rate → $12-14k/mo steady income

**Win rate ≠ profitable.** Selling far-OTM premium routinely produces
80-90% win rates AND a net edge near zero, because the 10-20% of losses
are 4-10x the size of the wins.

| | Achievable today | Not achievable |
|---|---|---|
| Strategy | wheel + cash-secured puts on liquid blue chips, 0.20-0.30 delta, 30-45 DTE | "80% win rate" as a standalone target without naming max-loss + edge |
| Capital required | $400-600k | $50k-200k (position sizing is unsafe at this scale) |
| Net monthly | $5-10k on $500k (after drawdowns + tax) | $12-14k/mo without major capital |
| Real metric | `expected_value = (win_p × win_amt) − (loss_p × loss_amt)` | Hit rate alone |

### Claim 2 — 50% yearly on 7-mega-trend basket

(Note: the stated list — AI / Crypto / Quantum / SynthBio / Space /
Robotics — is **6** trends. The 7th needs naming. Candidates: Energy
storage / BCI / Longevity bio.)

**50% sustained is greater than Buffett, greater than Lynch, greater
than nearly every public fund.** Possible in a single year of a sector
bull run; not sustainable.

| | Achievable | Not achievable |
|---|---|---|
| Annual CAGR target | 20-30% (doubles every ~30 months) | 50%+ sustained over multiple years |
| Strategy | thesis-driven basket, equal-weight sleeves, rigorous invalidation discipline | "buy mega trends and HODL" without thesis structure |
| Peak years | 50%+ possible in a 2017 / 2023 type single sector explosion | Not as a baseline |
| Real metric | per-position `invalidation_condition` fires triggers sell; thesis_correct_rate over 18 months | Quarterly P&L alone |

### Claim 3 — $1M → $100M in 21 months (doubling every 3 months)

**No-one has done this with public-method investing.** The few people
who hit similar multiples did so via a concentrated bet on a single
asset that 100x'd in a bull cycle. Survivor lottery.

The realistic version of "$1M → $100M":
- 1% chance — a single venture / option position 100x's. Lottery.
- **99% chance — they BUILD a company that gets a $100M valuation.**

This is not an investment plan. It's the upside of a venture / equity
bet. **Trading + investing fund the runway while you build the
company that becomes the $100M outcome.**

For this user, the company in question is neuro-os itself — the "tens
of thousands of AI businesses" north star.

## The 10X — three phases, honest aggregates

### Phase 1 — Income substitution (0-6 months)

**Target:** $12-14k/mo net after-tax. Free time from W-2 dependency.

**Strategy:**
- Wheel + cash-secured puts on AAPL / MSFT / AMD / NVDA / META.
- 30-45 days to expiry, 0.20-0.30 delta puts.
- Roll losers, accept assignment on quality, sell covered calls until
  called away.
- Avoid weeklies + 0DTE + far-OTM premium selling (gambling, not income).

**Capital required:** $400-600k.

**Substrate need:** `agent/investment/income_strategy.py` —
`IncomeStrategy` + `OptionTrade` schemas tracking `expected_value`,
`max_loss`, `assignment_probability`, `actual_outcome`, `realized_pnl`.
Weekly rollup: monthly net income vs cost-of-living gap.

**Stop condition:** if 3 consecutive months don't clear $10k net, the
strategy is wrong, not the user. Switch back to W-2-supplemented income
while reworking the strategy. (Honesty gate.)

### Phase 2 — Mega-trend capital appreciation (ongoing, 12-36 month horizon)

**Target:** 20-30% CAGR. Doubles capital every ~30 months. NOT 3.

**Strategy:**
- Equal-weight 6-7 categorical sleeves:
  1. AI (frontier-model + infra)
  2. Crypto (BTC + ETH + select infra)
  3. Quantum (still venture-stage; small sleeve)
  4. SynthBio (CRISPR + organoid + bioprinting)
  5. Space (launch + comms + EO)
  6. Robotics (industrial + humanoid + autonomous)
  7. Energy storage / BCI / Longevity (pick one to round out to 7)
- 4-8 positions per sleeve.
- Each position files a `PositionThesis` with explicit
  `invalidation_condition` and `expected_timeline`.
- **Discipline:** when invalidation_condition fires, you sell. Not "wait
  for it to come back."

**Substrate need:**
- Extend `PositionThesis` with `sleeve: MegaTrendSleeve` literal.
- Dashboard rolls up by sleeve, not just by ticker.
- `thesis_correct_rate` metric: % of theses where invalidation didn't
  fire OR the price target was hit before the timeline expired.

**Stop condition:** if 18-month sleeve return < SPY return for the same
window, you're picking wrong. Switch to index ETFs (VTI / QQQ) and
accept market return until you've earned a better edge through evidence.

### Phase 3 — Equity in what you're building (12-24+ months)

**Target:** this is where 10x outcomes live. Venture distribution —
could be $0 or could be $10M-$100M+.

**Strategy:**
- neuro-os turns into a product / business / agent-OS that you own
  equity in. The shipped 4 verticals × 5 compounding mechanisms × MCP
  integration is a real asset.
- This is your 3rd anchor ("tens of thousands of AI businesses").

**Substrate need:** none from the investment vertical. **The startup
vertical** is where this gets tracked. The adapter PR into
`Projects/company-os` + `Projects/gstack` is the relevant next step
here.

## Aggregate trajectory (if all three phases work)

| Time | Net worth (trading+investing only) | Phase 3 (venture-distribution) |
|---|---|---|
| Month 0 | $500k | $0 |
| Month 6 | $550k + $50k income | $0 |
| Month 12 | ~$650k + $120k income | $0 |
| Month 24 | ~$1M | $0-$10M+ |
| Month 36 | $1.5-3M | $0 or $10M-$100M+ |

**This is 1-2 orders of magnitude below the stated trajectory. It is
also achievable.** The stated trajectory is not.

## Money-os — what it actually is (scoped via github.com/wjlgatech/money-os)

| | money-os |
|---|---|
| Shape | **Claude plugin** with 21 slash commands (`/leak-scan`, `/freedom`, `/invest`, `/courage`, `/tax-strategy`, `/portfolio-check`, `/cash-flow`, `/screen`, `/decide`, …) |
| Storage | Plaintext markdown in a gitignored `profile/` directory — `profile/financial-identity.md` (context), `profile/holdings.md` (positions), `profile/history.md` (audit trail). **No database. No JSONL. No structured schema.** |
| Broker integration | Advisory-only today. Alpaca integration is v4.2 planned. Paper-trading engine for strategy testing. |
| Options support | **None.** Equity / ETF / crypto context only. |
| Cost-of-living | **Yes** — `/cash-flow`, `/weekly-pulse`, `/leak-scan` score income + expenses by "Freedom Impact." This is the strongest part of money-os. |
| Other surfaces | Web screener at `localhost:3001`. `.claude-plugin/` manifest. |

**This is not a Python library or a daemon.** It's a Claude plugin
that lives next to neuro-os in the same client, with its own slash
commands and its own markdown profile. Two plugins, same user, same
Claude session.

## Integration architecture — augment, don't adapt

The original NEXT-1b item assumed money-os was a Python project with
schemas neuro-os would wrap. That's wrong. The right model:

**Two Claude plugins, complementary, sharing one user.**

| money-os does | neuro-os does |
|---|---|
| Portfolio state in `profile/holdings.md` | Adds thesis discipline: every position gets a `PositionThesis` with `invalidation_condition` + `expected_timeline` |
| `/cash-flow`, `/leak-scan` — cost-of-living, freedom impact | Consumes monthly cost number as a `CostOfLivingProfile`; computes `income_gap_pct` vs Phase 1 income |
| Equity / ETF / crypto coverage | Adds **options income** tracking (cash-secured puts, wheel, covered calls) — the load-bearing Phase 1 gap money-os doesn't fill |
| Sector / topic tagging in profile markdown | Adds **mega-trend sleeve** discipline (`PositionThesis.sleeve`) so the dashboard rolls up by trend, not just by ticker |
| `/decide`, `/courage`, `/freedom` chat surfaces | `loop urge` + override-log discipline so emotional trades are caught at the gate (skillify auto-emission) |

**No adapter PR needed.** No `agent/investment/money_os_adapter.py`.
Money-os's markdown profile is human-readable; neuro-os reads it
optionally when surfacing a unified view, but neither tool's storage
is the other's source of truth.

The integration **is not a code dependency**. It's a **session pattern**:
- Use money-os's `/cash-flow` + `/leak-scan` to maintain the monthly
  cost-of-living number.
- Use neuro-os's `invest` CLI / MCP tools to add thesis discipline,
  options-income tracking, mega-trend sleeve rollup.
- Both write to `profile/` (money-os) and `~/.neuro_os_*` (neuro-os) —
  separate but coordinated.

## What neuro-os ships to complete the picture

money-os's gaps point at exactly what the neuro-os investment vertical
should add:

### 1. `agent/investment/options_income.py` (Phase 1 substrate)

Money-os has zero options support; Phase 1 of the income plan IS
options. This is the load-bearing piece.

- `OptionStrategy = Literal["cash_secured_put", "covered_call", "wheel", "credit_spread", "iron_condor", "naked", "other"]`
- `OptionTrade` frozen schema: strategy / ticker / underlying_price /
  expiry / strike(s) / premium / max_loss / expected_value /
  assignment_probability / realized_pnl / outcome ∈ {open, won, lost,
  assigned, rolled} / opened_at / closed_at.
- `compute_expected_value(win_p, win_amt, loss_p, loss_amt) → float`.
- `compute_monthly_pnl(trades, year_month) → MonthlyPnL`.
- `compute_strategy_winrate(trades, strategy) → tuple[int, float]` —
  the honest metric: (n_trades, win_rate); when n < 20, win_rate is
  noise.

### 2. `agent/investment/megatrend.py` (Phase 2 substrate)

Money-os tags positions in markdown ad-hoc; neuro-os adds structured
mega-trend sleeve.

- `MegaTrendSleeve = Literal["ai", "crypto", "quantum", "synthbio", "space", "robotics", "energy_storage"]`.
- Extend `PositionThesis` with `sleeve: Optional[MegaTrendSleeve]`.
- `compute_sleeve_balance(theses) → dict[MegaTrendSleeve, float]` —
  percent of capital per sleeve. Surfaces over-concentration.
- `compute_thesis_correct_rate(theses, *, window_days) → float`.

### 3. `agent/investment/cost_of_living.py` (Phase 1 ↔ money-os bridge)

The one optional bridge to money-os: read a monthly cost number,
compute the income gap.

- `CostOfLivingProfile` (monthly_target / region / breakdown / source).
- `read_from_money_os_profile(path) → Optional[CostOfLivingProfile]` —
  parses money-os's `profile/financial-identity.md` for a monthly cost
  line. Best-effort regex; returns None if not found. **No hard
  dependency on money-os; the user can also set the number directly.**
- `compute_income_gap(monthly_net_income, profile) → IncomeGap`
  (gap_dollars / gap_pct / months_runway_remaining).

### 4. Dashboard extension

`invest dashboard --window 30` surfaces:

- Monthly options-income net (Phase 1)
- Cost-of-living gap (Phase 1 ↔ life)
- Win-rate per strategy (with sample-size guards)
- Sleeve balance — concentration warning at >40% in any one sleeve
- Thesis-correct-rate over the window (Phase 2)
- Health flags: `phase1_income_gap_unmet` / `single_sleeve_concentration`
  / `options_loss_concentration` / `no_thesis_invalidation`

### 5. CLI

- `invest trade log {strategy} {ticker} {strike} {expiry} {premium}`
- `invest trade close {trade_id} {realized_pnl} {outcome}`
- `invest sleeve-balance`
- `invest cost-of-living set --monthly-target 14000`
- `invest dashboard [--window N] [--json]`

## What I CAN ship without money-os (the offline path)

A focused investment-vertical strengthening that supports Phase 1 + Phase
2 discipline. When money-os arrives, it becomes the storage backend
and the strengthening becomes a thin lens over it.

**Concrete files:**

- `agent/investment/income_strategy.py` —
  - `OptionStrategy = Literal["cash_secured_put", "covered_call", "wheel", "credit_spread", "iron_condor", "naked", "other"]`
  - `OptionTrade` frozen schema (strategy / ticker / expiry / strike(s) /
    premium / max_loss / expected_value / assignment_probability /
    realized_pnl / outcome ∈ {open, won, lost, assigned, rolled})
  - `write_trade` / `read_trades` / `list_open` / `compute_monthly_pnl`
  - `compute_expected_value(strategy, win_p, win_amt, loss_p, loss_amt) → float`
- `agent/investment/megatrend.py` —
  - `MegaTrendSleeve = Literal["ai", "crypto", "quantum", "synthbio", "space", "robotics", "energy_storage"]` (or whatever the 7th is)
  - Extend `PositionThesis` (or create `MegaTrendThesis`) with
    `sleeve: MegaTrendSleeve`.
  - `compute_sleeve_balance(theses) → dict[sleeve, percent_capital]`
- `agent/investment/cost_of_living.py` —
  - `CostOfLivingProfile` (monthly_target / month / region / breakdown)
  - `compute_income_gap(monthly_net_income, profile) → income_gap_pct`
- Dashboard extension: investment-specific dashboard mirroring
  research's. Surfaces win-rate, expected_value, monthly net,
  income-vs-cost gap, sleeve balance, thesis_correct_rate.
- CLI: `invest trade log/list`, `invest sleeve-balance`, `invest dashboard`.

**Estimated scope:** 1.5-2 days. Tests + docs + mirrors per the usual
gates.

## Decision tree

| If you... | Then... |
|---|---|
| Share money-os schemas now | I scope the adapter, defer the offline strengthening. |
| Defer money-os to next week | I ship the offline strengthening (Phase 1 + Phase 2 substrate). When money-os arrives, we wire it as a storage backend. |
| Want neither right now | The 40-day research trial + 100-day anchor trial still run end-to-end. This plan stays in `docs/plans/` as the spec for the next investment work. |

## Real-talk paragraph

The proposal as stated — $1M → $100M in 21 months — is a fantasy
trajectory. **That is not a slight on the user; it is the math.**

The actual high-leverage move embedded in the user's three anchors
(walk with God, restoration with Taylor, tens of thousands of AI
businesses) **is not trading**. It is building neuro-os into something
that throws off equity value. The trading + investing pillar is what
funds runway while the building happens.

**Phase 1 (income substitution, $12-14k/mo) is the load-bearing piece
of the wealth plan, not the doubling-every-3-months curve.** Get to
escape velocity from W-2 dependency first. Then compound. Then build.

---

_Filed for the next investment-vertical PR. The eval was the deliverable;
the code is gated on either money-os scoping or explicit confirmation
to ship the offline path._
