"""Helpers geométricos puros usados pelos componentes de mapa."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence


def road_local_scenario_offsets(
    road_scenario_pairs: Sequence[tuple[str, str]],
) -> list[float]:
    """Centraliza os cenários em torno da sua própria rodovia."""
    totals = Counter(str(road) for road, _ in road_scenario_pairs)
    positions: defaultdict[str, int] = defaultdict(int)
    offsets: list[float] = []

    for road, _ in road_scenario_pairs:
        road_key = str(road)
        index = positions[road_key]
        offsets.append(index - (totals[road_key] - 1) / 2.0)
        positions[road_key] += 1

    return offsets
