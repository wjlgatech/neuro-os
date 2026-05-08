"""
``agent.domain_app`` — substrate for verticals (research, investment,
startup, founder_loop).

This module factors out the **structural pattern** every vertical
follows:

1. **Daily contract** — yesterday-self signs a typed commitment for
   today (priorities + a quantified resource budget + an abuse-tax).
2. **Tank score** — pure-function reduce over an append-only registry
   that quantifies "how much has today-self earned vs spent".
3. **Diagnosis catalog** — when an "urge" / "drift" event fires, the
   substrate diagnoses one of 6 named *underlying needs* and proposes
   ≥1 *constructive expression* with a tank-credit bonus.
4. **Action allowlist** — every emitted ``ControlAction`` carries a
   ``contract_check`` audit trail and an inverse op (no silent
   denials, every action reversible).
5. **Nightly summary** — 4 first-class metrics + a per-vertical
   ``extra`` dict (verticals pick the 4 that matter; substrate
   doesn't impose them).
6. **Cross-vertical interface** — every vertical's outputs become
   ``VerticalNote`` rows that other verticals can read (subject to
   visibility rules, default-private, see ``agent.cross_vertical``).

This package contains the **Protocols + base schemas + orchestrator
shell** that any vertical can plug into. ``founder_loop/`` already
implements the same pattern (this is what we factored from); it
continues to work unchanged. New verticals (``research/``,
``investment/``, ``startup/``) plug in by providing a
``DomainConfig``.

Phase 1 design choice: substrate is **interface-first**, NOT a
big-bang refactor of ``founder_loop``. The 222 existing founder_loop
tests stay green untouched. Verticals built on this substrate are
fully independent. Founder_loop can be backported to consume the
substrate later if it provides clear value (deferred — see
``docs/roadmap.md``).
"""
from __future__ import annotations

from agent.domain_app.protocol import (
    DomainConfig,
    DomainAppProtocol,
    DiagnosisCatalogProtocol,
)
from agent.domain_app.state import (
    DailyContractBase,
    TankStateBase,
    ControlActionBase,
    DiagnosisBase,
    ConstructiveExpressionBase,
    NightlySummaryBase,
    ContractCheck,
    ControlOp,
    Confidence,
)
from agent.domain_app.app import DomainApp


__all__ = [
    "DomainConfig",
    "DomainAppProtocol",
    "DiagnosisCatalogProtocol",
    "DailyContractBase",
    "TankStateBase",
    "ControlActionBase",
    "DiagnosisBase",
    "ConstructiveExpressionBase",
    "NightlySummaryBase",
    "ContractCheck",
    "ControlOp",
    "Confidence",
    "DomainApp",
]
