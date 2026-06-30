from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetAllocation:
    contingency_cny: float
    categories: dict[str, float]


class BudgetPolicy:
    def __init__(self, contingency_ratio: float = 0.10) -> None:
        self.contingency_ratio = contingency_ratio

    def allocate(self, budget_cny: float) -> BudgetAllocation:
        contingency = round(budget_cny * self.contingency_ratio, 2)
        usable = round(budget_cny - contingency, 2)
        ratios = {
            "intercity": 0.30,
            "accommodation": 0.35,
            "attractions": 0.15,
            "local_transport": 0.10,
            "fixed_costs": 0.10,
        }
        categories = {
            name: round(usable * ratio, 2) for name, ratio in ratios.items()
        }
        rounding_delta = round(usable - sum(categories.values()), 2)
        categories["fixed_costs"] += rounding_delta
        return BudgetAllocation(
            contingency_cny=contingency,
            categories=categories,
        )

    def deficit(self, *, budget_cny: float, planned_cost_cny: float) -> float:
        usable = budget_cny * (1 - self.contingency_ratio)
        return round(max(0, planned_cost_cny - usable), 2)
