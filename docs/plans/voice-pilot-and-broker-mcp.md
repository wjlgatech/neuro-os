# Plan — voice-pilot the investment vertical + broker MCP

> **Status:** Architecture spec for the still-missing pieces of the
> talk-to-your-portfolio loop. The investment-vertical MCP tools that
> close the read + propose + record steps are SHIPPED in this PR. The
> broker MCP (the execute step) and the money-os MCP (analysis from
> money-os's slash commands) are documented here but **not built** —
> they're either out of scope or owned by other repos.

## What the user asked for

> *"Does the money-os tool provide actionable steps? Can Claude execute
> those actionable steps (using CLI or Computer Use) with human-in-the-
> loop to authorize transactions? Are there simple dashboards to give
> user pilot-view + manipulation options (by talking, no need to click
> button or fill in text)?"*

## The honest current state

| | Today (this PR) | Gap |
|---|---|---|
| **Q1 — money-os actionable** | money-os has 21 slash commands producing analysis + recommendations (`/leak-scan`, `/invest`, `/decide`, `/rebalance`, …). Advisory-only; Alpaca integration is v4.2 planned. | Slash commands are **Claude-Code-only**; not reachable as MCP tools from other clients or orchestrator loops. |
| **Q2 — Claude executes with HITL** | Claude Code's tool-permission system IS the HITL. Every Bash + MCP call prompts before running. Neuro-os MCP tools today: read dashboards, log thesis-driven trades, propose orders, record closes. No broker execution. | **No broker MCP** anywhere yet. Alpaca-MCP / IBKR-MCP / Schwab-MCP are unbuilt; user-built or community-built ports would close this. |
| **Q3 — Pilot-view + voice manipulation, no clicks** | Voice input is solved by any speech-to-text feeding Claude Code (Dictation / Wispr Flow / ChatGPT Voice clipboard). 17 neuro-os MCP tools — including 8 investment tools shipped in this PR — cover the read + propose + record surface for the investment vertical. Output is Claude prose, TTS-compatible. | Two-way duplex voice (no manual paste between voice→text and Claude UI) requires either a custom MCP voice gateway or a third-party voice-to-Claude bridge. Out of scope here. |

## The full closed-loop architecture (target end-state)

```
                 ┌──────────────────────────────────────────┐
                 │            USER (voice / chat)            │
                 └────────────────┬─────────────────────────┘
                                  │ "What's my income gap?"
                                  │ "Propose a CSP on AAPL"
                                  │ "Yes, execute it"
                                  │ "Sell 50% of NVDA"
                                  ▼
                  ┌─────────────────────────────────┐
                  │      CLAUDE (host: Claude Code,  │
                  │      Cursor, mcp-cli, or other)  │
                  │      HITL gate on every tool call│
                  └──┬───────────┬──────────────────┬┘
                     │           │                  │
       ┌─────────────┘           │                  └───────────────┐
       │                         │                                  │
       ▼                         ▼                                  ▼
┌──────────────────┐    ┌──────────────────────────┐    ┌──────────────────────┐
│ money-os MCP     │    │  neuro-os MCP            │    │  broker MCP          │
│ (analysis)       │    │  (discipline + audit)    │    │  (execution)         │
│                  │    │                          │    │                      │
│ /leak-scan       │    │  invest_dashboard        │    │  alpaca_buy          │
│ /invest          │    │  invest_propose_order    │    │  alpaca_sell         │
│ /portfolio-check │    │  invest_trade_log        │    │  alpaca_options_open │
│ /rebalance       │    │  invest_trade_close      │    │  alpaca_options_close│
│ /decide          │    │  invest_next_action      │    │  alpaca_cancel       │
│ … 21 commands    │    │  invest_sleeve_balance   │    │  alpaca_account_info │
│                  │    │  invest_cost_of_living_* │    │                      │
│ (Owner: money-os)│    │  (Shipped: this PR)      │    │  (Owner: TBD)        │
└──────────────────┘    └──────────────────────────┘    └──────────────────────┘
```

Each box has a clear owner. The three MCP servers run side-by-side as
peers in the host client; Claude orchestrates across them.

## What this PR ships

**Investment-vertical MCP tools** (8 new, total 17). Each is a thin
wrapper around an existing `agent.investment.*` function except the two
reasoning tools at the bottom.

### Read tools (3)

| Tool | What it does | Underlying function |
|---|---|---|
| `invest_dashboard` | Full rollup (Phase 1 + Phase 2 + 5 health flags) | `build_dashboard_summary` |
| `invest_sleeve_balance` | Mega-trend sleeve allocation | `compute_sleeve_balance` |
| `invest_cost_of_living_read` | Read target, optional money-os profile import | `load_profile` / `read_from_money_os_profile` |

### Write tools (3) — each HITL'd by Claude Code's permission prompt

| Tool | What it does | Underlying function |
|---|---|---|
| `invest_cost_of_living_set` | Set the monthly target | `save_profile` |
| `invest_trade_log` | Record a new options trade (EV computed at log time) | `write_trade` + `compute_expected_value` |
| `invest_trade_close` | Record a close (new row, parent stays frozen) | `write_trade` (with `parent_trade_id`) |

### Reasoning tools (2) — the voice-pilot surface

| Tool | What it does |
|---|---|
| `invest_propose_order` | Returns an order proposal with EV math + risk banner + recommendation ∈ {authorize_then_log, review, reject}. **Never writes to disk.** This is the HITL surface — voice user says "propose a CSP on AAPL", Claude reads back the proposal, user authorizes verbally, Claude calls `invest_trade_log` to record after the user executes on their broker. |
| `invest_next_action` | Given current dashboard state, returns the SINGLE highest-leverage next action with priority + cli_hint. Voice user says "what should I do next?" → Claude reads back one concrete action. |

### Risk banner taxonomy in `invest_propose_order`

| Banner | Triggers when | Recommendation |
|---|---|---|
| `NEGATIVE_EV` | computed EV < 0 | `reject` |
| `POOR_RATIO` | premium / max_loss < 1% | `review` |
| `DEEP_OTM` | win_probability ≥ 0.85 AND max_loss / premium > 30 | `review` |
| `OK` | else | `authorize_then_log` |

These are sample-size-free (each trade carries its own math); the
flag fires on the proposal itself, not on accumulated trade history.

## What this PR explicitly does NOT ship

### Broker MCP (the missing execute step)

**Out of scope; ~1-2 days when built.** The recommended path:

1. New repo (or branch in neuro-os): `neuro-os-broker-mcp/` or
   `agent/broker_mcp.py`.
2. Wraps `alpaca-py` (or `ib_insync` for IBKR, or Schwab's API).
3. Tools: `account_info`, `place_market_order`, `place_limit_order`,
   `place_options_order`, `cancel_order`, `list_open_orders`.
4. **Two HITL gates per transaction:** Claude proposes via
   `invest_propose_order`; user authorizes verbally; Claude calls the
   broker MCP tool, which prompts AGAIN at the host-client level
   before submitting; user authorizes once more; only THEN the
   network call to Alpaca / IBKR fires.
5. **Paper-mode by default.** Live-mode requires an explicit
   `--live` flag the user types (not voice — too easy to misfire).
6. Post-execution: the broker MCP returns the fill (or fill rejection),
   and Claude immediately calls `invest_trade_log` on the neuro-os MCP
   to record the canonical row.

### Money-os MCP (analysis surface from money-os)

**Out of scope; owned by money-os.** Two paths the money-os owner
could take:

1. Money-os ships its own `mcp.json` + MCP server alongside its
   plugin manifest. Each of the 21 slash commands becomes an MCP tool.
2. OR a tiny `money-os-mcp-bridge` repo that calls money-os's slash
   commands programmatically and re-exposes them as MCP tools.

Either way: not this PR's responsibility.

### True voice duplex

**Out of scope.** Today's loop assumes the user types or pastes voice
transcription into Claude Code; Claude's prose response is read
silently or via a system-level TTS. A true voice duplex (mic open,
ambient listening, voice activity detection, push-to-talk-or-keyword)
needs a custom voice gateway — separate component, separate PR if ever.

## Test plan after this PR is merged

End-to-end voice flow (manual smoke):

1. User dictates / types: *"What's my income gap?"*
2. Claude calls `invest_dashboard` (one HITL prompt; user approves).
3. Claude reads back: *"Your gap is $14k uncovered; last month
   realized $0; the next action is open an income trade."*
4. User dictates: *"Propose a CSP on AAPL strike 220 expiry June 19,
   premium 300, max-loss 1000, win prob 0.80."*
5. Claude calls `invest_propose_order` (HITL prompt; user approves).
6. Claude reads back: *"EV is +$40, banner OK, recommend authorize."*
7. User dictates: *"Yes, log it — I'll execute on Robinhood now."*
8. Claude calls `invest_trade_log` with the same parameters (HITL
   prompt; user approves). Trade is recorded.
9. User executes manually on their broker.
10. Later, user dictates: *"Close trade opt-abc123 for +$280 profit,
    outcome won."*
11. Claude calls `invest_trade_close` (HITL prompt; user approves).
    The close row is recorded; the gap shrinks; the dashboard updates.

This is the full read + propose + record cycle, voice-driven, with
HITL at every transaction-shaped step, **without a broker MCP**.

## Time horizon for the missing pieces

| Piece | Owner | Estimate | Trigger |
|---|---|---|---|
| Alpaca broker MCP (paper) | This repo (follow-up PR) | 1 day | When user opens an Alpaca account |
| Alpaca broker MCP (live + 2-gate HITL) | This repo (follow-up PR) | 0.5 day after paper | When user wants real execution |
| money-os MCP server | money-os owner | unknown | Out of our hands |
| Voice duplex gateway | Separate project | 2-4 days | Optional; the typed-voice path works today |
| Computer-Use fallback (broker web UI) | This repo (follow-up) | 2-3 days | Only if no broker API is available |

The smallest unit of additional progress that fully closes Q2 is the
Alpaca paper broker MCP. Filing as NEXT in the roadmap.
