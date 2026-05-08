"""
``DomainApp`` — the orchestrator shell.

This is the substrate's main entry point. Verticals construct a
``DomainApp`` with a ``DomainConfig``; the resulting object exposes
the canonical ``morning_ritual`` / ``tick`` / ``nightly`` API.

The shell is **deliberately thin** — it delegates almost all behavior
to the config. The substrate's value is in the *types and contracts*
(state.py, protocol.py), not in clever code. Each vertical can drop
in custom predict / sublimate / policy modules that the
``DomainApp`` calls via duck-typed hooks.

Phase 1 deliberately does NOT implement the full tick logic here.
Doing so would require either (a) a big-bang founder_loop refactor
(which we're avoiding for safety) or (b) re-implementing the whole
loop inside the substrate (wasted code). Instead, ``DomainApp``
exposes hooks that verticals override; the actual tick logic lives
in each vertical's own module.

So: ``DomainApp`` is a *contract-checking shell*. It validates
that:
* The config is well-formed.
* The catalog has the required 6 needs and ≥1 option per need.
* The home_dir is a real directory the substrate can write to.

And it provides:
* A canonical TickResult shape for verticals to fill in.
* Helpers for registry I/O (append / read / filter_by_day) that
  verticals reuse without re-implementing.

Verticals built on this substrate will look like:

    from agent.domain_app import DomainApp
    from agent.research.config import RESEARCH_CONFIG

    app = DomainApp(config=RESEARCH_CONFIG, registry_path=...)
    app.morning_ritual(...)  # delegates to vertical's specific shape
    app.tick()                # runs the vertical's policy
    app.nightly()             # produces NightlySummary
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.domain_app.protocol import DomainConfig
from agent.domain_app.state import (
    ConstructiveExpressionBase,
    DailyContractBase,
    DiagnosisBase,
    NightlySummaryBase,
)


class DomainAppError(Exception):
    """Raised when DomainApp construction or invariants fail."""


class DomainApp:
    """Orchestrator shell. Constructed with a ``DomainConfig``; exposes
    the canonical morning/tick/nightly surface.

    Verticals subclass this OR pass their own callable hooks via the
    optional ``hooks`` kwarg to override behavior without subclassing.
    """

    def __init__(
        self,
        *,
        config: DomainConfig,
        registry_path: Path,
        contract_path: Path,
        hooks: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._validate_config(config)
        self.config = config
        self.registry_path = Path(registry_path)
        self.contract_path = Path(contract_path)
        self.hooks = hooks or {}

        # Make sure the per-vertical home dir exists.
        self.config.home_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Validation (Law 5: deterministic outputs require well-typed config)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_config(config: DomainConfig) -> None:
        """Check the config satisfies the substrate's invariants:

        * 6 named underlying_needs (anti-metric-overload from PRD).
        * Each need has ≥1 constructive expression (Law 3).
        * vertical_name is one of the registered four.
        """
        valid_verticals = {"founder_loop", "research", "investment", "startup"}
        if config.vertical_name not in valid_verticals:
            raise DomainAppError(
                f"vertical_name {config.vertical_name!r} not in "
                f"{sorted(valid_verticals)}. Adding a 5th vertical "
                f"requires an explicit substrate update + a roadmap entry."
            )

        needs = list(config.catalog.underlying_needs)
        if len(needs) != 6:
            raise DomainAppError(
                f"vertical {config.vertical_name!r} has {len(needs)} "
                f"underlying_needs; substrate requires exactly 6. "
                f"Got: {needs}"
            )
        if len(set(needs)) != 6:
            raise DomainAppError(
                f"vertical {config.vertical_name!r} has duplicate "
                f"underlying_needs: {needs}"
            )

        for need in needs:
            options = config.catalog.options_for(need)
            if not options:
                raise DomainAppError(
                    f"vertical {config.vertical_name!r} need {need!r} has "
                    f"no constructive-expression options (Law 3 violation)."
                )
            for i, opt in enumerate(options):
                if not isinstance(opt, ConstructiveExpressionBase):
                    raise DomainAppError(
                        f"vertical {config.vertical_name!r} need {need!r} "
                        f"option {i} is not a ConstructiveExpressionBase: "
                        f"{type(opt).__name__}"
                    )

    # ------------------------------------------------------------------
    # Canonical surface (verticals override via hooks)
    # ------------------------------------------------------------------

    def morning_ritual(self, **kwargs: Any) -> DailyContractBase:
        """Sign today's contract.

        Verticals override this by providing a ``"morning_ritual"`` hook
        in the constructor. The default implementation raises — the
        substrate doesn't know the vertical's contract shape.
        """
        hook = self.hooks.get("morning_ritual")
        if hook is None:
            raise DomainAppError(
                f"vertical {self.config.vertical_name!r} did not provide a "
                f"'morning_ritual' hook. Pass it in the DomainApp constructor."
            )
        return hook(**kwargs)

    def tick(
        self,
        *,
        intent: Optional[str] = None,
        now: Optional[Any] = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """One tick. Delegates to the vertical's tick hook.

        Verticals can declare extra kwargs on their tick hook (e.g. the
        research vertical accepts ``observed_failure_mode``); they're
        forwarded transparently.
        """
        hook = self.hooks.get("tick")
        if hook is None:
            raise DomainAppError(
                f"vertical {self.config.vertical_name!r} did not provide a "
                f"'tick' hook."
            )
        return hook(intent=intent, now=now, dry_run=dry_run, **kwargs)

    def nightly(
        self,
        *,
        day: Optional[Any] = None,
        **kwargs: Any,
    ) -> NightlySummaryBase:
        """End-of-day rollup."""
        hook = self.hooks.get("nightly")
        if hook is None:
            raise DomainAppError(
                f"vertical {self.config.vertical_name!r} did not provide a "
                f"'nightly' hook."
            )
        return hook(day=day, **kwargs)

    # ------------------------------------------------------------------
    # Helpers verticals can reuse (no need to override)
    # ------------------------------------------------------------------

    def make_diagnosis(
        self,
        *,
        need: str,
        confidence: str,
        reasoning: str,
        options: Optional[List[ConstructiveExpressionBase]] = None,
    ) -> DiagnosisBase:
        """Build a typed ``DiagnosisBase`` for a need from this vertical's
        catalog. Looks up options from the catalog if not provided."""
        if need not in self.config.catalog.underlying_needs:
            raise DomainAppError(
                f"need {need!r} not in {self.config.vertical_name!r} "
                f"catalog. Valid: {self.config.catalog.underlying_needs}"
            )
        if options is None:
            options = self.config.catalog.options_for(need)
        return DiagnosisBase(
            underlying_need=need,
            confidence=confidence,  # type: ignore[arg-type]
            reasoning=reasoning,
            options=options,
        )
