"""
Protocols (typing.Protocol) that every vertical must implement.

A Protocol is a structural-typing contract: any object that has the
listed methods/attributes counts as "implementing" the protocol —
no inheritance required. This lets ``founder_loop`` (which predates
this substrate) satisfy the protocol incidentally without a
refactor, while new verticals can implement it explicitly.

The substrate's ``DomainApp`` orchestrator holds a reference to a
``DomainConfig`` and uses these protocols to delegate behavior. So:

* Substrate is dumb (knows nothing about needs / catalogs / etc.)
* DomainConfig is the strategy object that fills in the blanks
* Verticals provide a ``DomainConfig``

This is the **Strategy pattern** applied to the OEC loop.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Protocol, Optional, runtime_checkable

from agent.domain_app.state import (
    ConstructiveExpressionBase,
    DailyContractBase,
    NightlySummaryBase,
)


@runtime_checkable
class DiagnosisCatalogProtocol(Protocol):
    """The vertical's catalog of diagnoses. Each catalog has 6 named
    failure modes (per PRD critique) and a way to look up
    constructive expressions for each."""

    underlying_needs: List[str]
    """The 6 named failure modes for this vertical. Examples:
    * founder_loop: ['fatigue', 'novelty_hunger', 'social',
      'frustration', 'decision_fatigue', 'embodied']
    * research: ['paper_collector', 'topic_hopper', 'memorizer',
      'authority_acceptor', 'overloaded', 'forgetting']
    * investment: ['emotional', 'narrative_following',
      'price_obsessed', 'overconfident', 'social_proof_following',
      'ego_attached']
    * startup: ['idea_chaos', 'broadcasting', 'feature_creep',
      'vision_intoxicated', 'vanity_metrics', 'random_execution']
    """

    def options_for(self, need: str) -> List[ConstructiveExpressionBase]:
        """Look up constructive expressions for the given need.
        Must return ≥1 option per Law 3."""
        ...


@runtime_checkable
class DomainConfig(Protocol):
    """The strategy object every vertical provides.

    Tells the substrate:
    * Who am I (vertical name, file paths)
    * What's my catalog of diagnoses
    * What's my primary resource (and its unit)
    * What's my primary metric (and its label)
    * Where does my data live
    """

    vertical_name: str
    """One of 'founder_loop', 'research', 'investment', 'startup'."""

    primary_resource_label: str
    """The vertical's primary resource unit. Examples: 'entertainment
    minutes' (founder_loop), 'papers read' (research), 'position
    changes' (investment), 'thesis pivots' (startup)."""

    primary_metric_label: str
    """The vertical's primary metric label. Examples: 'MAE' (founder
    loop prediction error), 'mechanism cards/day' (research),
    'calibration error' (investment), 'strategic continuity score'
    (startup)."""

    catalog: DiagnosisCatalogProtocol
    """The 6 named failure modes for this vertical."""

    home_dir: Path
    """Where vertical-specific state lives. Examples:
    * founder_loop: ~/.founder_loop/
    * research: ~/.neuro_os_research/
    * investment: ~/.neuro_os_investment/
    * startup: ~/.neuro_os_startup/
    Privacy boundary: substrate guarantees nothing leaves these
    directories without explicit user opt-in (Law 7)."""


@runtime_checkable
class DomainAppProtocol(Protocol):
    """What every vertical's app exposes. founder_loop's
    ``FounderLoop`` class already satisfies this (informally); new
    verticals satisfy it explicitly via ``DomainApp[ConfigType]``.
    """

    def morning_ritual(self, **kwargs: Any) -> DailyContractBase:
        """Yesterday-self signs today's contract."""
        ...

    def tick(
        self,
        *,
        intent: Optional[str] = None,
        now: Optional[datetime] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """One observation → diagnose → decide → record cycle.
        Returns a TickResult-shaped dict."""
        ...

    def nightly(
        self,
        *,
        day: Optional[datetime] = None,
    ) -> NightlySummaryBase:
        """End-of-day rollup. Returns the typed NightlySummary with
        the 4 first-class metrics filled in."""
        ...
