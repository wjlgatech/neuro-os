"""
``agent.startup`` — startup vertical (one of three verticals on the
domain_app substrate, alongside research and investment).

Audience: founders building a startup who want to convert
emotionally-reactive chaos into market-aligned convergence using
recursive OEC loops.

Built per ``docs/prd/enhanced_startup_prd.md`` with the Phase 0
sharpenings:

* 4 first-class metrics: strategic continuity, audience resonance,
  conversion quality, trust density.
* 6 named failure modes: idea_chaos, broadcasting, feature_creep,
  vision_intoxicated, vanity_metrics, random_execution.
* Single-thesis enforcement: changing ``current_thesis`` requires an
  explicit kill-event with reason; >3 changes/40d = penalty
  (borrowed from founder_loop's contract pattern).
* `Bottleneck` schema with explicit type enum.
* `AudienceSignal` carries a `social_channel` enum (v0 manual paste;
  v1 wires APIs).
* Reuses founder_loop's nightly-review pattern (no parallel ritual).
* Privacy: notes default-PRIVATE to startup. Founders explicitly opt
  into sharing hypotheses with research / investment.
"""
from __future__ import annotations

from agent.startup.catalog import STARTUP_CATALOG
from agent.startup.config import StartupConfig, make_startup_app
from agent.startup.ontology import (
    AudienceSignal,
    Bottleneck,
    EVIDENCE_TYPE,
    SocialChannel,
    StartupContract,
    StartupHypothesis,
    StartupPriority,
)


__all__ = [
    "STARTUP_CATALOG",
    "StartupConfig",
    "make_startup_app",
    "AudienceSignal",
    "Bottleneck",
    "EVIDENCE_TYPE",
    "SocialChannel",
    "StartupContract",
    "StartupHypothesis",
    "StartupPriority",
]
