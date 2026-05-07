"""
Flywheel Domain registration for the founder_loop product.

Currently ships as **read-only L2** (``mutable_paths=[]``) — the
sublimation catalog and queues are hand-edited in v0. v1 will graduate
the catalog to a mutable path under the ``/catalog-review`` chat
surface (see ``docs/roadmap.md``); when that ships, ``mutable_paths``
expands AND ``tests/test_engineering_principles.py::test_law_7_*`` is
updated explicitly so the change can't slip through silently.

The domain registration is the lever that integrates founder_loop with
the rest of the OEC machinery — same Domain abstraction that drives the
neuroscience and neuro_os_self loops, just with founder_loop's golden
cases and (future) catalog mutations.
"""
from __future__ import annotations

from typing import Any, Dict

from agent.domains import (
    Domain,
    import_smoke_validator,
    list_domains,
    register_domain,
)
from agent.founder_loop.golden_cases import PERSONAL_GOLDEN_CASES


_FOUNDER_LOOP_NAME = "founder_loop_v1"


def _founder_loop_extractor(text: str) -> Dict[str, Any]:
    """Stub extractor for the founder_loop domain.

    The founder_loop product layer doesn't classify free text the way
    the L1 neuroscience loop does — it ingests structured ``RawEvent``
    rows from workflowx and structured ``UrgeEvent`` rows from the
    user. The Domain abstraction still requires an extractor for OEC
    completeness, so this returns a minimal-but-valid result that
    satisfies the validator contract without introducing a free-text
    classification surface (which would violate Law 1).
    """
    return {
        "knowledge": {"text": text[:200], "domain": "founder_loop"},
        "true_validation": {"scores": {"TRUE": 1.0}},
        "decision": "ACCEPT",
    }


def _founder_loop_domain() -> Domain:
    """Construct the Domain object. Use ``register_founder_loop_domain``
    for the idempotent registration."""
    return Domain(
        name=_FOUNDER_LOOP_NAME,
        ontology={
            "primitives": {
                "underlying_need": {},
                "constructive_expression": {},
                "tank": {},
                "contract": {},
            },
        },
        golden_cases=[
            {"name": g.name, "description": g.description}
            for g in PERSONAL_GOLDEN_CASES
        ],
        extractor=_founder_loop_extractor,
        validators=[import_smoke_validator],
        mutable_paths=[],  # read-only L2 in v0; v1 graduates via catalog-review
    )


def register_founder_loop_domain() -> Domain:
    """Idempotent registration of the founder_loop domain.

    Returns the (newly registered or pre-existing) Domain object.
    """
    domain = _founder_loop_domain()
    if domain.name not in list_domains():
        register_domain(domain)
    return domain


__all__ = ["register_founder_loop_domain"]
