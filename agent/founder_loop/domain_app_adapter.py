"""
Adapter: makes ``agent.founder_loop`` satisfy the ``agent.domain_app``
substrate's ``DomainConfig`` protocol.

This is **Phase B (minimal)** of the A-C-B-D plan. It does NOT
refactor founder_loop's internals — its 222 existing tests stay
green untouched. Instead, the adapter wraps the existing catalog +
schemas in the substrate's `DomainConfig` shape, so founder_loop
becomes one of the four verticals reachable via `DomainApp`.

The full structural refactor (replacing founder_loop's ``state.py``
with subclasses of the substrate base classes, replacing
``reward_ledger.compute_tank`` with the substrate's tank computation,
etc.) is deliberately deferred — see ``docs/roadmap.md`` LATER.

## What the adapter does

1. Maps founder_loop's 10 ``UnderlyingNeed`` values to the
   substrate's "exactly 6 named failure modes" rule:
   - ``fatigue``                  → ``fatigue``
   - ``novelty_hunger``           → ``novelty_hunger``
   - ``social``                   → ``social``
   - ``frustration``              → ``frustration``
   - ``decision_fatigue``         → ``decision_fatigue``
   - ``embodied_hunger``          → ``embodied`` (grouped)
   - ``embodied_eye_strain``      → ``embodied`` (grouped)
   - ``earned_reward``            → not a failure mode (state marker)
   - ``post_reward_fatigue``      → not a failure mode (state marker)
   - ``none``                     → not a failure mode (state marker)
2. Pulls constructive-expression options from
   ``founder_loop/data/sublimation_catalog.json`` and casts them to
   ``ConstructiveExpressionBase`` instances (substrate's frozen
   shape).
3. Exposes ``FOUNDER_LOOP_CONFIG`` as a module-level singleton
   satisfying the ``DomainConfig`` protocol.

After this adapter, all 4 verticals can be enumerated by the
substrate's invariant-checker; the OEC machinery treats them
uniformly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from agent.domain_app.state import ConstructiveExpressionBase
from agent.founder_loop.sublimate import load_catalog


# Substrate-canonical: exactly 6 named failure modes per vertical.
# Founder_loop's 10 needs collapse to 6 by grouping the embodied pair
# and dropping the 3 state-marker entries.
_FAILURE_MODES: List[str] = [
    "fatigue",
    "novelty_hunger",
    "social",
    "frustration",
    "decision_fatigue",
    "embodied",
]


# Map substrate failure-mode name → founder_loop catalog key(s).
_NEED_TO_CATALOG_KEYS: Dict[str, List[str]] = {
    "fatigue": ["fatigue"],
    "novelty_hunger": ["novelty_hunger"],
    "social": ["social"],
    "frustration": ["frustration"],
    "decision_fatigue": ["decision_fatigue"],
    "embodied": ["embodied_hunger", "embodied_eye_strain"],
}


class FounderLoopCatalog:
    """Concrete ``DiagnosisCatalogProtocol`` implementation that
    delegates to the existing founder_loop sublimation catalog.

    Loads JSON lazily; safe to instantiate at import time.
    """

    underlying_needs: List[str] = list(_FAILURE_MODES)

    def __init__(self) -> None:
        self._cache: Dict[str, List[ConstructiveExpressionBase]] = {}

    def _load(self) -> Dict[str, List[ConstructiveExpressionBase]]:
        if self._cache:
            return self._cache
        raw = load_catalog()
        needs_section = raw.get("needs") or {}
        for substrate_need, catalog_keys in _NEED_TO_CATALOG_KEYS.items():
            options: List[ConstructiveExpressionBase] = []
            for key in catalog_keys:
                entry = needs_section.get(key) or {}
                for opt in entry.get("options", []) or []:
                    options.append(
                        ConstructiveExpressionBase(
                            action=opt["action"],
                            duration_min=int(opt["duration_min"]),
                            tank_credit_pct=float(opt["tank_credit_pct"]),
                            references=list(opt.get("references", []) or []),
                        )
                    )
            if not options:
                # Substrate guarantees ≥1 option per need (Law 3).
                # If founder_loop's catalog is incomplete, ship a
                # placeholder rather than crash at import — the
                # adapter test will catch this in CI.
                options = [
                    ConstructiveExpressionBase(
                        action=f"address_{substrate_need}",
                        duration_min=10,
                        tank_credit_pct=2.0,
                    )
                ]
            self._cache[substrate_need] = options
        return self._cache

    def options_for(self, need: str) -> List[ConstructiveExpressionBase]:
        return list(self._load().get(need, []))


FOUNDER_LOOP_CATALOG: FounderLoopCatalog = FounderLoopCatalog()


class FounderLoopConfig:
    """Concrete ``DomainConfig`` for founder_loop. Module-level
    singleton; tests can construct their own with a custom home_dir."""

    vertical_name: str = "founder_loop"
    primary_resource_label: str = "entertainment minutes"
    primary_metric_label: str = "MAE"
    catalog: FounderLoopCatalog = FOUNDER_LOOP_CATALOG

    def __init__(self, home: Path = None) -> None:
        self.home_dir: Path = home or (Path.home() / ".founder_loop")


FOUNDER_LOOP_CONFIG: FounderLoopConfig = FounderLoopConfig()


__all__ = [
    "FounderLoopCatalog",
    "FounderLoopConfig",
    "FOUNDER_LOOP_CATALOG",
    "FOUNDER_LOOP_CONFIG",
]
