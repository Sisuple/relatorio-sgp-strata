import pandas as pd

from services.work_plan_pdf import first_available_year_budget_items


def test_work_plan_uses_only_the_first_available_year():
    budget = pd.DataFrame(
        {
            "Ano": [2029, 2027, 2028, 2027],
            "Custo": [900.0, 100.0, 500.0, 200.0],
            "_segment_id": [4, 1, 3, 2],
        }
    )

    year, selected = first_available_year_budget_items(budget)

    assert year == 2027
    assert selected["Ano"].tolist() == [2027, 2027]
    assert selected["Custo"].sum() == 300.0


def test_work_plan_ignores_invalid_years_when_finding_the_first():
    budget = pd.DataFrame(
        {
            "Ano": [None, "inválido", "2028"],
            "Custo": [100.0, 200.0, 300.0],
        }
    )

    year, selected = first_available_year_budget_items(budget)

    assert year == 2028
    assert selected["Custo"].tolist() == [300.0]
