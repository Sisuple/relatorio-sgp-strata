from utils.geo import road_local_scenario_offsets


def test_two_scenarios_are_centered_independently_for_each_road():
    pairs = [
        ("BR-174", "cenario-crescente"),
        ("BR-174", "cenario-decrescente"),
        ("BR-364", "cenario-crescente"),
        ("BR-364", "cenario-decrescente"),
    ]

    assert road_local_scenario_offsets(pairs) == [-0.5, 0.5, -0.5, 0.5]


def test_offsets_do_not_depend_on_road_order():
    pairs = [
        ("BR-174", "cenario-crescente"),
        ("BR-364", "cenario-crescente"),
        ("BR-174", "cenario-decrescente"),
        ("BR-364", "cenario-decrescente"),
    ]

    assert road_local_scenario_offsets(pairs) == [-0.5, -0.5, 0.5, 0.5]


def test_single_scenario_stays_on_the_original_geometry():
    pairs = [
        ("BR-174", "cenario-crescente"),
        ("BR-364", "cenario-crescente"),
    ]

    assert road_local_scenario_offsets(pairs) == [0.0, 0.0]
