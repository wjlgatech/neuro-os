"""
``founder_loop`` — the daily reward-economy + sublimation loop.

Public surface for consumers (company-os Founder OS Approval Gate is
the prime caller). Three entry points:

* ``FounderLoop`` — class. Holds per-user paths (registry, contracts,
  queues, workflowx export). Build once per user; reuse for the lifetime
  of the session.
* ``predict_next_hour(state, intent)`` — stateless one-off forecaster.
* ``diagnose_underlying_need(state, urge_type)`` — stateless one-off
  sublimator.

Philosophy is encoded in the type system (see ``state.py``) so a wrong
``ControlAction`` can't even be constructed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set, Union

from agent.founder_loop.contract import (
    bind_morning_contract,
    load_latest_contract,
)
from agent.founder_loop.evaluate import evaluate_intent, hourly_error
from agent.founder_loop.golden_cases import (
    PERSONAL_GOLDEN_CASES,
    choose_rebuild_target,
    evaluate_goldens,
)
from agent.founder_loop.memory import (
    append_registry_row,
    compute_contract_honor_rate,
    compute_entertainment_usage_min,
    compute_mae,
    compute_sublimation_success_rate,
    filter_by_day,
    read_registry,
)
from agent.founder_loop.observe import (
    FixtureWorkflowxAdapter,
    WorkflowxAdapter,
    observe,
)
from agent.founder_loop.policy import decide_control
from agent.founder_loop.predict import predict_next_hour
from agent.founder_loop.reward_ledger import compute_tank
from agent.founder_loop.state import (
    AbuseTax,
    ConstructiveExpression,
    Contract,
    ContractCheck,
    ControlAction,
    Diagnosis,
    ForecastedState,
    FounderState,
    NightlySummary,
    Priority,
    TankState,
    TickResult,
    UrgeType,
)
from agent.founder_loop.sublimate import diagnose as diagnose_underlying_need
from agent.founder_loop.urge_log import (
    UrgeEvent,
    log_urge_event,
    read_recent_urge,
    resolve_urge,
)


class FounderLoop:
    """Per-user instance of the loop.

    Construct once per user with persistence paths and a workflowx
    adapter. ``tick()`` is the unit of execution; ``nightly()`` is the
    end-of-day rollup; ``morning_ritual()`` binds tomorrow's contract.
    """

    def __init__(
        self,
        *,
        registry_path: Union[str, Path],
        contract_path: Union[str, Path],
        adapter: Optional[WorkflowxAdapter] = None,
        workflowx_export_path: Optional[Union[str, Path]] = None,
        events_path: Optional[Union[str, Path]] = None,
        use_llm: bool = False,
        api_key: Optional[str] = None,
        llm_model: str = "claude-haiku-4-5",
        graduated_auto_apply: Optional[Set[str]] = None,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.contract_path = Path(contract_path)
        self.events_path = (
            Path(events_path)
            if events_path is not None
            else self.registry_path.parent / "founder_events.jsonl"
        )
        self.use_llm = use_llm
        self.api_key = api_key
        self.llm_model = llm_model
        self.graduated_auto_apply = graduated_auto_apply or set()

        if adapter is not None:
            self.adapter = adapter
        elif workflowx_export_path is not None:
            self.adapter = FixtureWorkflowxAdapter(workflowx_export_path)
        else:
            raise ValueError(
                "Either ``adapter`` or ``workflowx_export_path`` must be "
                "provided to FounderLoop."
            )

    # ------------------------------------------------------------------
    # Urge logging — user-reported ground truth
    # ------------------------------------------------------------------

    def log_urge(
        self,
        urge_type: UrgeType,
        *,
        context: str = "",
        when: Optional[datetime] = None,
    ) -> UrgeEvent:
        """Record a user-reported urge to ``founder_events.jsonl``.

        The next ``tick()`` will see this urge (within the recency
        window) and treat it as ground truth over the predictor.
        """
        return log_urge_event(
            urge_type=urge_type,
            context=context,
            path=self.events_path,
            ts=when,
            source="user_logged",
        )

    # ------------------------------------------------------------------
    # Morning ritual
    # ------------------------------------------------------------------

    def morning_ritual(
        self,
        *,
        priorities: List[Priority],
        entertainment_ration_min: int,
        threshold_pct: int = 90,
        abuse_tax: Optional[AbuseTax] = None,
        pre_authorized_blocks: Optional[List[str]] = None,
        notes: Optional[str] = None,
        when: Optional[datetime] = None,
    ) -> Contract:
        """Sign today's contract. Yesterday-self's signature."""
        return bind_morning_contract(
            priorities=priorities,
            entertainment_ration_min=entertainment_ration_min,
            threshold_pct=threshold_pct,
            abuse_tax=abuse_tax,
            pre_authorized_blocks=pre_authorized_blocks,
            notes=notes,
            when=when,
            save_to=self.contract_path,
        )

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def tick(
        self,
        *,
        intent: Optional[str] = None,
        now: Optional[datetime] = None,
        dry_run: bool = False,
        urge_window_minutes: int = 15,
    ) -> TickResult:
        """One hourly tick. Returns the typed TickResult.

        ``dry_run=True`` returns the result without writing to the
        registry — used for previews and the example dry-run.

        ``urge_window_minutes`` controls how far back ``log_urge`` calls
        are considered ground truth. Defaults to 15min — the typical
        latency between urge-firing and the next tick.
        """
        now = now or datetime.now(timezone.utc)

        # 1. Observe.
        state = observe(self.adapter, now=now)

        # 2. Predict.
        forecasted = predict_next_hour(
            state,
            intent or state.last_intent,
            use_llm=self.use_llm,
            llm_model=self.llm_model,
            api_key=self.api_key,
        )

        # 3. Compute tank against today's contract.
        contract = load_latest_contract(self.contract_path)
        all_rows = read_registry(self.registry_path)
        today_rows = filter_by_day(all_rows, now.date())
        tank = compute_tank(today_rows, contract=contract)

        # 4. Belief OS gate on the user's intent.
        intent_flag = evaluate_intent(
            intent or state.last_intent,
            use_llm=self.use_llm,
            llm_model=self.llm_model,
            api_key=self.api_key,
        )

        # 5. Recent user-logged urge (ground truth, beats predictor).
        recent_urge = read_recent_urge(
            self.events_path,
            window_minutes=urge_window_minutes,
            only_unresolved=True,
            now=now,
        )

        # 6. Decide.
        action = decide_control(
            state=state,
            forecasted=forecasted,
            tank=tank,
            intent_flag=intent_flag,
            contract=contract,
            recent_rows=all_rows[-6:],  # last 6 hours for dead-sensor check
            graduated_auto_apply=self.graduated_auto_apply,
            recent_urge=recent_urge,
            now=now,
        )

        # 7. Persist.
        row_id: Optional[str] = None
        if not dry_run:
            row_id = append_registry_row(
                self.registry_path,
                state=state,
                forecasted=forecasted,
                tank=tank,
                action=action,
                intent_flag=intent_flag,
                extra=(
                    {"recent_urge_id": recent_urge.id}
                    if recent_urge is not None
                    else None
                ),
            )

        return TickResult(
            state=state,
            forecasted=forecasted,
            tank=tank,
            action=action,
            registry_row_id=row_id,
        )

    # ------------------------------------------------------------------
    # Nightly
    # ------------------------------------------------------------------

    def nightly(self, *, day: Optional[datetime] = None) -> NightlySummary:
        """End-of-day rollup."""
        day = day or datetime.now(timezone.utc)
        all_rows = read_registry(self.registry_path)
        today_rows = filter_by_day(all_rows, day.date())

        mae_today = compute_mae(today_rows)

        # 7d ago
        from datetime import timedelta
        seven_ago = (day - timedelta(days=7)).date()
        prior_rows = filter_by_day(all_rows, seven_ago)
        mae_prior = compute_mae(prior_rows)

        chr_today = compute_contract_honor_rate(today_rows)
        chr_7d = compute_contract_honor_rate(
            [r for r in all_rows
             if (day - timedelta(days=7)).isoformat() <= (r.get("state") or {}).get("timestamp", "") <= day.isoformat()]
        )

        failed_goldens = evaluate_goldens(all_rows)
        rebuild = choose_rebuild_target(failed_goldens)
        action_choice = "no_action"
        if rebuild == "predictor":
            action_choice = "rebuild_predictor"
        elif rebuild == "sublimation_catalog":
            action_choice = "rebuild_sublimation_catalog"
        elif rebuild == "morning_ritual_prompt":
            action_choice = "update_contract"

        entertainment_min = compute_entertainment_usage_min(today_rows)
        sublimation_rate = compute_sublimation_success_rate(today_rows)

        return NightlySummary(
            date=day.date().isoformat(),
            mae_today=mae_today,
            mae_7d_ago=mae_prior,
            contract_honor_rate_today=chr_today,
            contract_honor_rate_7d=chr_7d,
            entertainment_usage_min_today=entertainment_min,
            sublimation_success_rate_today=sublimation_rate,
            goldens_failed=[g.name for g in failed_goldens],
            action=action_choice,  # type: ignore[arg-type]
        )


__all__ = [
    "FounderLoop",
    # schemas
    "AbuseTax",
    "ConstructiveExpression",
    "Contract",
    "ContractCheck",
    "ControlAction",
    "Diagnosis",
    "ForecastedState",
    "FounderState",
    "NightlySummary",
    "Priority",
    "TankState",
    "TickResult",
    "UrgeEvent",
    "UrgeType",
    # functions
    "predict_next_hour",
    "diagnose_underlying_need",
    "compute_tank",
    "compute_entertainment_usage_min",
    "compute_sublimation_success_rate",
    "evaluate_intent",
    "hourly_error",
    "evaluate_goldens",
    "log_urge_event",
    "read_recent_urge",
    "resolve_urge",
    "PERSONAL_GOLDEN_CASES",
]
