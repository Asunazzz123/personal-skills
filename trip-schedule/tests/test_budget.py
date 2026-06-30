from planning.budget import BudgetPolicy


def test_budget_reserves_ten_percent_contingency() -> None:
    allocation = BudgetPolicy().allocate(5000)

    assert allocation.contingency_cny == 500
    assert sum(allocation.categories.values()) == 4500


def test_budget_reports_deficit_instead_of_hiding_it() -> None:
    deficit = BudgetPolicy().deficit(budget_cny=5000, planned_cost_cny=5600)

    assert deficit == 1100
