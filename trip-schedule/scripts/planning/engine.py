from __future__ import annotations

from itertools import product

from pydantic import BaseModel

from models import Attraction, CandidatePlan, HotelStageOption, TransportOffer
from planning.budget import BudgetPolicy
from planning.scoring import score_plan


class PlanningInputs(BaseModel):
    budget_cny: float
    travelers: int
    transports: list[TransportOffer]
    attractions: list[Attraction]
    hotel_stage_options: list[HotelStageOption]


class PlanningResult(BaseModel):
    plans: list[CandidatePlan]
    minimum_deficit_cny: float = 0


class PlanningEngine:
    def __init__(self) -> None:
        self.budget_policy = BudgetPolicy()

    def build(self, inputs: PlanningInputs) -> PlanningResult:
        attraction_cost = sum(
            (item.ticket_price_cny or 0) * inputs.travelers
            for item in inputs.attractions
        )
        candidates: list[CandidatePlan] = []
        deficits: list[float] = []

        combinations = list(product(inputs.transports, inputs.hotel_stage_options))
        if not combinations:
            return PlanningResult(plans=[], minimum_deficit_cny=0)

        max_duration = max(item[0].duration_minutes for item in combinations)
        for transport, hotel_stage in combinations:
            if transport.total_price_cny is None:
                continue
            route_cost = sum(
                item.estimated_cost_cny for item in hotel_stage.routes
            )
            total_cost = (
                transport.total_price_cny * inputs.travelers
                + hotel_stage.total_hotel_cost_cny
                + attraction_cost
                + route_cost
            )
            deficit = self.budget_policy.deficit(
                budget_cny=inputs.budget_cny,
                planned_cost_cny=total_cost,
            )
            deficits.append(deficit)
            if deficit > 0:
                continue
            affordability = max(0, 1 - total_cost / inputs.budget_cny)
            time_score = 1 - transport.duration_minutes / max_duration
            confidence = (
                transport.evidence.confidence
                + sum(
                    evidence.confidence
                    for hotel in hotel_stage.hotels
                    for evidence in hotel.evidence
                )
                / max(
                    1,
                    sum(len(hotel.evidence) for hotel in hotel_stage.hotels),
                )
            ) / 2
            candidates.append(
                CandidatePlan(
                    plan_id=f"{transport.service_id}-{hotel_stage.option_id}",
                    label="unassigned",
                    transport=transport,
                    hotels=hotel_stage.hotels,
                    attractions=inputs.attractions,
                    days=hotel_stage.days,
                    routes=hotel_stage.routes,
                    total_cost_cny=round(total_cost, 2),
                    contingency_cny=round(inputs.budget_cny * 0.10, 2),
                    score=score_plan(
                        affordability=affordability,
                        door_to_door_time=max(0, time_score),
                        convenience=0.5,
                        data_confidence=confidence,
                    ),
                )
            )

        if not candidates:
            positive = [value for value in deficits if value > 0]
            return PlanningResult(
                plans=[],
                minimum_deficit_cny=min(positive) if positive else 0,
            )

        def pick_distinct(
            ordered: list[CandidatePlan],
            used_ids: set[str],
        ) -> CandidatePlan:
            for candidate in ordered:
                if candidate.plan_id not in used_ids:
                    used_ids.add(candidate.plan_id)
                    return candidate
            return ordered[0]

        used_ids: set[str] = set()
        balanced = pick_distinct(
            sorted(candidates, key=lambda item: item.score, reverse=True),
            used_ids,
        )
        economy = pick_distinct(
            sorted(candidates, key=lambda item: item.total_cost_cny),
            used_ids,
        )
        time_saving = pick_distinct(
            sorted(candidates, key=lambda item: item.transport.duration_minutes),
            used_ids,
        )
        selected: list[CandidatePlan] = []
        for label, candidate in (
            ("balanced", balanced),
            ("economy", economy),
            ("time-saving", time_saving),
        ):
            item = candidate.model_copy(
                update={"label": label, "plan_id": f"{label}-{candidate.plan_id}"}
            )
            selected.append(item)
        return PlanningResult(plans=selected)
