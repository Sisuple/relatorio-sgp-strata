from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import pandas as pd

from core.constants import AVAILABLE_ROADS, DEFAULT_ROAD
from src.database import MySQLConnection


_ROAD_CODE_RE = re.compile(r"(\d+)")
_ROAD_UF_RE = re.compile(r"BR[-\s]*(?P<code>\d+)\s*/\s*(?P<uf>[A-Z]{2})", re.IGNORECASE)
_LINESTRING_RE = re.compile(r"LINESTRING\s*\((?P<coords>.*)\)", re.IGNORECASE)
_MAX_MAP_LINE_DEGREES = 0.03
_IAP_CLASS_ORDER = [
    "Excelente",
    "Bom",
    "++ Regular",
    "+ Regular",
    "- Regular",
    "Mau",
    "Péssimo",
]
_IAP_CLASS_COLORS = {
    "Excelente": "#9fb9d9",
    "Bom": "#00a651",
    "++ Regular": "#b6d7a8",
    "+ Regular": "#f4f1a6",
    "- Regular": "#fff200",
    "Mau": "#f2a51a",
    "Péssimo": "#d71920",
}
_IAP_INTERVENTION_ORDER = [
    "OK",
    "RL",
    "RL+RS",
    "RL+REF",
    "RPS",
    "RPS+REF",
    "REC",
    "Sem intervenção",
]
_IAP_INTERVENTION_COLORS = {
    "OK": "#1fa2ff",
    "RL": "#00a65a",
    "RL+RS": "#b6d7a8",
    "RL+REF": "#e2f0d9",
    "RPS": "#fff200",
    "RPS+REF": "#ff8a00",
    "REC": "#e31a1c",
    "Sem intervenção": "#82929d",
}
_IAP_INTERVENTION_TO_CLASS = {
    "OK": "Excelente",
    "RL": "Bom",
    "RL+RS": "++ Regular",
    "RL+REF": "+ Regular",
    "RPS": "- Regular",
    "RPS+REF": "Mau",
    "REC": "Péssimo",
}
_CONDITION_CLASS_ORDER = ["Excelente", "Bom", "Regular", "Mau", "Péssimo"]
_CONDITION_CLASS_COLORS = {
    "Excelente": "#26c6f9",
    "Bom": "#00a651",
    "Regular": "#fff200",
    "Mau": "#f2a51a",
    "Péssimo": "#d71920",
}
_LINEAR_IAP_CLASS_COLORS = {
    **_IAP_CLASS_COLORS,
    "Excelente": "#26c6f9",
}


def _road_sort_key(label: str) -> tuple[int, str]:
    match = _ROAD_CODE_RE.search(label)
    return (int(match.group(1)) if match else 9999, label)


def _normalize_road_code(value: str | int | None) -> str | None:
    if value is None:
        return None

    text = str(value).strip().upper()
    if not text:
        return None

    match = _ROAD_CODE_RE.search(text)
    if not match:
        return text

    return match.group(1).zfill(3)


def _format_road_label(code: str, name: str | None = None) -> str:
    uf = None
    if name:
        match = _ROAD_UF_RE.search(str(name).upper())
        if match:
            uf = match.group("uf")

    return f"BR-{code}/{uf}" if uf else f"BR-{code}"


def _extract_uf_from_road_label(label: str) -> str:
    if "/" not in label:
        return "--"
    return label.rsplit("/", 1)[-1].split()[0].strip() or "--"


def _to_float(value: Any, fallback: float = 0.0) -> float:
    if value is None:
        return fallback
    return float(value)


def _classify_iap(value: Any) -> str:
    iap = _to_float(value) / 100
    if iap >= 4.01:
        return "Excelente"
    if iap >= 3.01:
        return "Bom"
    if iap >= 2.51:
        return "++ Regular"
    if iap >= 2.01:
        return "- Regular"
    if iap >= 1.01:
        return "Mau"
    return "Péssimo"


def _classify_iap_for_map(value: Any, intervention: str | None) -> str:
    if intervention in _IAP_INTERVENTION_TO_CLASS:
        return _IAP_INTERVENTION_TO_CLASS[intervention]

    return _classify_iap(value)


def _classify_condition(value: Any) -> str:
    index = _to_float(value)
    if index >= 4.01:
        return "Excelente"
    if index >= 3.01:
        return "Bom"
    if index >= 2.01:
        return "Regular"
    if index >= 1.01:
        return "Mau"
    return "Péssimo"


def _parse_linestring_latlon(wkt: str | None) -> list[list[float]]:
    if not wkt:
        return []

    match = _LINESTRING_RE.match(wkt.strip())
    if not match:
        return []

    coords = []
    for pair in match.group("coords").split(","):
        parts = pair.strip().split()
        if len(parts) < 2:
            continue

        lat, lon = float(parts[0]), float(parts[1])
        coords.append([lat, lon])

    return coords


def _has_large_coordinate_jump(coords: list[list[float]]) -> bool:
    for start, end in zip(coords, coords[1:]):
        lat_delta = abs(end[0] - start[0])
        lon_delta = abs(end[1] - start[1])
        if max(lat_delta, lon_delta) > _MAX_MAP_LINE_DEGREES:
            return True
    return False


def get_available_roads() -> list[str]:
    """Retorna rodovias cadastradas no banco, com fallback local."""
    roads = _get_available_roads_from_database()
    return roads or AVAILABLE_ROADS


def get_available_scenarios(selected_road: str, matrix_type: str = "Paragon") -> list[dict[str, Any]]:
    code = _normalize_road_code(selected_road)
    if not code:
        return []

    return _get_iap_scenarios_from_database(code, matrix_type)


def get_iap_extraction(
    selected_road: str,
    year: int = 2026,
    scenario_key: str | None = None,
) -> dict[str, Any] | None:
    """Extrai IAP médio e composição IAP para uso nas telas do relatório.

    A composição replica o relatório Paragon: agrupa por solucao_corretiva_final
    e calcula o percentual somente sobre os trechos com intervenção final.
    """
    code = _normalize_road_code(selected_road)
    if not code:
        return None

    return _get_iap_extraction_from_database(code, year, scenario_key)


@lru_cache(maxsize=64)
def _get_iap_extraction_from_database(
    road_code: str,
    year: int,
    scenario_key: str | None = None,
) -> dict[str, Any] | None:
    db = MySQLConnection()
    scenario = _get_iap_scenario_by_key(road_code, scenario_key) or _get_default_iap_scenario(db, road_code)
    if not scenario:
        return None

    averages = db.execute_query(
        """
        SELECT
          ROUND(SUM(sp.extensao * i.iapa) / SUM(sp.extensao) / 100, 4) AS iap_medio,
          ROUND(SUM(CASE WHEN i.solucao_corretiva_final IN ('RPS+REF', 'REC') THEN sp.extensao ELSE 0 END), 2) AS critical_km,
          ROUND(
            SUM(CASE WHEN i.solucao_corretiva_final IN ('RPS+REF', 'REC') THEN sp.extensao ELSE 0 END)
            / NULLIF(SUM(CASE WHEN i.solucao_corretiva_final IS NOT NULL THEN sp.extensao ELSE 0 END), 0) * 100,
            1
          ) AS critical_percent,
          ROUND(SUM(sp.extensao), 2) AS total_km,
          COUNT(*) AS segmentos
        FROM analise_gerencial_intervencoes_iap i
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = i.segmento_pista_id
        WHERE sp.analise_gerencial_id = %s
          AND i.gerencial_ciclo_id = %s
          AND i.ano = %s
        """,
        (scenario["analise_id"], scenario["ciclo_id"], year),
    ) or []

    composition = db.execute_query(
        """
        WITH base AS (
            SELECT sp.extensao, i.solucao_corretiva_final
            FROM analise_gerencial_intervencoes_iap i
            JOIN analise_gerencial_segmento_pistas sp ON sp.id = i.segmento_pista_id
            WHERE sp.analise_gerencial_id = %s
              AND i.gerencial_ciclo_id = %s
              AND i.ano = %s
              AND i.solucao_corretiva_final IS NOT NULL
        ), total AS (
            SELECT SUM(extensao) AS total_km FROM base
        )
        SELECT b.solucao_corretiva_final AS intervencao,
               COUNT(*) AS segmentos,
               ROUND(SUM(b.extensao), 2) AS km,
               ROUND(SUM(b.extensao) / t.total_km * 100, 1) AS percentual
        FROM base b
        CROSS JOIN total t
        GROUP BY b.solucao_corretiva_final, t.total_km
        ORDER BY km DESC
        """,
        (scenario["analise_id"], scenario["ciclo_id"], year),
    ) or []

    composition = sorted(
        [
            {
                "classe": row["intervencao"],
                "intervencao": row["intervencao"],
                "segmentos": int(row.get("segmentos") or 0),
                "km": _to_float(row.get("km")),
                "percentual": _to_float(row.get("percentual")),
                "color": _IAP_INTERVENTION_COLORS.get(row.get("intervencao"), "#fff200"),
            }
            for row in composition
        ],
        key=lambda row: _IAP_INTERVENTION_ORDER.index(row["intervencao"])
        if row["intervencao"] in _IAP_INTERVENTION_ORDER
        else len(_IAP_INTERVENTION_ORDER),
    )

    class_distribution = db.execute_query(
        """
        SELECT
          CASE
            WHEN i.iapa / 100 >= 4.01 THEN 'Excelente'
            WHEN i.iapa / 100 >= 3.01 THEN 'Bom'
            WHEN i.iapa / 100 >= 2.51 THEN '++ Regular'
            WHEN i.iapa / 100 >= 2.01 THEN '- Regular'
            WHEN i.iapa / 100 >= 1.01 THEN 'Mau'
            ELSE 'Péssimo'
          END AS classe,
          ROUND(SUM(sp.extensao), 2) AS km,
          ROUND(SUM(sp.extensao) / SUM(SUM(sp.extensao)) OVER () * 100, 1) AS percentual
        FROM analise_gerencial_intervencoes_iap i
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = i.segmento_pista_id
        WHERE sp.analise_gerencial_id = %s
          AND i.gerencial_ciclo_id = %s
          AND i.ano = %s
        GROUP BY classe
        """,
        (scenario["analise_id"], scenario["ciclo_id"], year),
    ) or []

    class_distribution = sorted(
        [
            {
                **row,
                "km": _to_float(row.get("km")),
                "percentual": _to_float(row.get("percentual")),
                "color": _IAP_CLASS_COLORS.get(row.get("classe"), "#fff200"),
            }
            for row in class_distribution
        ],
        key=lambda row: _IAP_CLASS_ORDER.index(row["classe"])
        if row["classe"] in _IAP_CLASS_ORDER
        else len(_IAP_CLASS_ORDER),
    )

    average = averages[0] if averages else {}
    if average.get("iap_medio") is None:
        return None

    return {
        **scenario,
        "ano": year,
        "iap_medio": _to_float(average.get("iap_medio")),
        "total_km": _to_float(average.get("total_km")),
        "critical_km": _to_float(average.get("critical_km")),
        "critical_percent": _to_float(average.get("critical_percent")),
        "critical_rule": "SUM(extensao) where solucao_corretiva_final in ('RPS+REF', 'REC') over intervention total",
        "segmentos": int(average.get("segmentos") or 0),
        "composition": composition,
        "class_distribution": class_distribution,
    }


@lru_cache(maxsize=64)
def _get_iap_map_segments_from_database(
    analise_id: int,
    ciclo_id: int,
    year: int,
) -> pd.DataFrame:
    db = MySQLConnection()

    iap_rows = db.execute_query(
        """
        SELECT segmento_pista_id, iapa, solucao_corretiva_final
        FROM analise_gerencial_intervencoes_iap
        WHERE gerencial_ciclo_id = %s
          AND ano = %s
        """,
        (ciclo_id, year),
    ) or []

    iap_by_segment = {}
    for row in iap_rows:
        intervention = row.get("solucao_corretiva_final") or "Sem intervenção"
        iap_by_segment[int(row["segmento_pista_id"])] = {
            "iap": _to_float(row.get("iapa")),
            "intervencao": intervention,
        }

    if not iap_by_segment:
        return pd.DataFrame()

    geometry_rows = db.execute_query(
        """
        SELECT id_segmento, km_inicial_segmento, km_final_segmento,
               km_inicial_ponto, wkt
        FROM segmento_view_mapa_base
        WHERE analise_gerencial_id = %s
          AND gerencial_ciclo_id = %s
        ORDER BY id_segmento, km_inicial_ponto
        """,
        (analise_id, ciclo_id),
    ) or []

    segments: dict[int, dict[str, Any]] = {}
    for row in geometry_rows:
        segment_id = int(row["id_segmento"])
        iap_data = iap_by_segment.get(segment_id)
        if iap_data is None:
            continue

        segment = segments.setdefault(
            segment_id,
            {
                "segment_id": segment_id,
                "km_inicial": _to_float(row.get("km_inicial_segmento")),
                "km_final": _to_float(row.get("km_final_segmento")),
                "iap": iap_data["iap"] / 100,
                "classe_iap": _classify_iap_for_map(
                    iap_data["iap"],
                    iap_data["intervencao"],
                ),
                "intervencao_iap": iap_data["intervencao"],
                "intervencao_color": _IAP_INTERVENTION_COLORS.get(
                    iap_data["intervencao"],
                    "#fff200",
                ),
                "paths": [],
            },
        )

        line_coords = _parse_linestring_latlon(row.get("wkt"))
        if len(line_coords) >= 2 and not _has_large_coordinate_jump(line_coords):
            segment["paths"].append(line_coords)

    return pd.DataFrame(
        [
            segment
            for segment in segments.values()
            if segment.get("paths")
        ]
    )


@lru_cache(maxsize=64)
def _get_linear_diagram_segments_from_database(
    analise_id: int,
    ciclo_id: int,
    year: int,
) -> pd.DataFrame:
    db = MySQLConnection()
    rows = db.execute_query(
        """
        SELECT
          sp.id AS segment_id,
          sp.km_inicial,
          sp.km_final,
          sp.extensao,
          i.icdsa,
          i.icdpa,
          i.icdea,
          i.iapa,
          i.solucao_corretiva_final
        FROM analise_gerencial_intervencoes_iap i
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = i.segmento_pista_id
        WHERE sp.analise_gerencial_id = %s
          AND i.gerencial_ciclo_id = %s
          AND i.ano = %s
        ORDER BY sp.km_inicial
        """,
        (analise_id, ciclo_id, year),
    ) or []

    records = []
    for row in rows:
        intervention = row.get("solucao_corretiva_final")
        condition_classes = {
            "ICDS": _classify_condition(row.get("icdsa")),
            "ICDP": _classify_condition(row.get("icdpa")),
            "ICDE": _classify_condition(row.get("icdea")),
        }
        iap_class = _classify_iap_for_map(row.get("iapa"), intervention)
        records.append(
            {
                "segment_id": int(row["segment_id"]),
                "km_inicial": _to_float(row.get("km_inicial")),
                "km_final": _to_float(row.get("km_final")),
                "extensao": _to_float(row.get("extensao")),
                "icds": _to_float(row.get("icdsa")),
                "icdp": _to_float(row.get("icdpa")),
                "icde": _to_float(row.get("icdea")),
                "iap": _to_float(row.get("iapa")) / 100,
                "classe_icds": condition_classes["ICDS"],
                "classe_icdp": condition_classes["ICDP"],
                "classe_icde": condition_classes["ICDE"],
                "classe_iap": iap_class,
                "cor_icds": _CONDITION_CLASS_COLORS[condition_classes["ICDS"]],
                "cor_icdp": _CONDITION_CLASS_COLORS[condition_classes["ICDP"]],
                "cor_icde": _CONDITION_CLASS_COLORS[condition_classes["ICDE"]],
                "cor_iap": _LINEAR_IAP_CLASS_COLORS.get(iap_class, "#fff200"),
            }
        )

    return pd.DataFrame(records)


def _scenario_key(analise_id: Any, ciclo_id: Any) -> str:
    return f"{int(analise_id)}:{int(ciclo_id)}"


def _scenario_segment_type(name: str | None) -> tuple[str, str, int]:
    normalized = str(name or "").lower()
    if "(sh)" in normalized or "homogene" in normalized:
        return "sh", "Segmento Homogêneo", 1
    if "1km" in normalized or "1 km" in normalized:
        return "1km", "1km", 2

    return "outros", "Outros", 3


def _get_iap_scenario_by_key(road_code: str, scenario_key: str | None) -> dict[str, Any] | None:
    if not scenario_key:
        return None

    for scenario in _get_iap_scenarios_from_database(road_code, "Paragon"):
        if scenario["key"] == scenario_key:
            return scenario

    return None


def _get_default_iap_scenario(db: MySQLConnection, road_code: str) -> dict[str, Any] | None:
    scenarios = _get_iap_scenarios_from_database(road_code, "Paragon")
    if scenarios:
        return scenarios[0]

    return None


@lru_cache(maxsize=64)
def _get_iap_scenarios_from_database(road_code: str, matrix_type: str) -> list[dict[str, Any]]:
    db = MySQLConnection()
    rows = db.execute_query(
        """
        SELECT
            agdt.id AS analise_id,
            agdt.nome,
            agdt.tipo_matriz,
            agc.id AS ciclo_id,
            CASE
                WHEN LOWER(agdt.nome) LIKE '%%(sh)%%' THEN 1
                WHEN LOWER(agdt.nome) LIKE '%%(1km)%%' THEN 2
                ELSE 3
            END AS ordem_cenario
        FROM analise_gerencial_dados_trechos agdt
        JOIN analise_gerencial_ciclos agc
          ON agc.analise_gerencial_id = agdt.id
        WHERE agdt.deleted_at IS NULL
          AND agdt.rodovia = %s
          AND agdt.tipo_matriz = %s
        ORDER BY ordem_cenario, agdt.updated_at DESC, agc.id DESC
        """,
        (str(int(road_code)), matrix_type),
    ) or []

    scenarios = []
    for row in rows:
        segment_type, segment_type_label, _ = _scenario_segment_type(row["nome"])
        scenarios.append(
            {
                "key": _scenario_key(row["analise_id"], row["ciclo_id"]),
                "analise_id": int(row["analise_id"]),
                "ciclo_id": int(row["ciclo_id"]),
                "cenario": row["nome"],
                "label": segment_type_label,
                "tipo_matriz": row["tipo_matriz"],
                "segment_type": segment_type,
                "segment_type_label": segment_type_label,
            }
        )

    return scenarios


@lru_cache(maxsize=1)
def _get_available_roads_from_database() -> list[str]:
    db = MySQLConnection()
    roads_by_code: dict[str, str] = {}

    trecho_rows = db.execute_query(
        """
        SELECT rodovia, nome
        FROM analise_gerencial_dados_trechos
        WHERE deleted_at IS NULL
          AND rodovia IS NOT NULL
          AND rodovia <> ''
        ORDER BY rodovia, updated_at DESC
        """
    ) or []

    pista_rows = db.execute_query(
        """
        SELECT rodovia, NULL AS nome
        FROM analise_gerencial_segmento_pistas
        WHERE rodovia IS NOT NULL
          AND rodovia <> ''
        GROUP BY rodovia
        """
    ) or []

    for row in [*trecho_rows, *pista_rows]:
        code = _normalize_road_code(row.get("rodovia"))
        if not code:
            continue

        current_label = roads_by_code.get(code)
        next_label = _format_road_label(code, row.get("nome"))

        if not current_label or ("/" not in current_label and "/" in next_label):
            roads_by_code[code] = next_label

    return sorted(roads_by_code.values(), key=_road_sort_key)


def get_overview_data(selected_road: str | None = None, scenario_key: str | None = None) -> dict:
    """Monta os dados fake da tela de visão geral.

    O contrato já separa métricas, segmentos e distribuição para facilitar a
    futura troca por consultas reais no banco.
    """
    road = selected_road or get_available_roads()[0]

    iap_extraction = get_iap_extraction(road, scenario_key=scenario_key)
    iap_average = iap_extraction["iap_medio"] if iap_extraction else 3.66
    extension_km = iap_extraction["total_km"] if iap_extraction else 90
    critical_km = iap_extraction["critical_km"] if iap_extraction else 14
    critical_percent = iap_extraction["critical_percent"] if iap_extraction else 15.6
    segment_count = iap_extraction["segmentos"] if iap_extraction else 90

    metrics = {
        "road": road,
        "uf": _extract_uf_from_road_label(road),
        "segment_count": segment_count,
        "extension_km": extension_km,
        "critical_km": critical_km,
        "critical_percent": critical_percent,
        "iap_average": iap_average,
        "plan_cost_mi": 51.8,
        "last_update_minutes": 12,
    }

    cards = [
        {
            "title": "IAP MÉDIO",
            "value": f"{iap_average:.2f}",
            "subtitle": "Índice de aptidão do pavimento",
            "tone": "green",
            "icon": "↗",
        },
        {
            "title": "% TRECHOS CRÍTICOS",
            "value": f"{critical_percent:.1f}%",
            "subtitle": "Mau + Péssimo",
            "tone": "red",
            "icon": "△",
        },
        {
            "title": "KM CRÍTICOS",
            "value": f"{critical_km:.1f} km",
            "subtitle": "Extensão em Mau + Péssimo",
            "tone": "orange",
            "icon": "◎",
        },
        {
            "title": "EXTENSÃO TOTAL",
            "value": f"{extension_km:.1f} km",
            "subtitle": "Extensão total do trecho",
            "tone": "yellow",
            "icon": "⌁",
        },
    ]

    if iap_extraction:
        segments = _get_iap_map_segments_from_database(
            iap_extraction["analise_id"],
            iap_extraction["ciclo_id"],
            iap_extraction["ano"],
        )
        linear_diagram = _get_linear_diagram_segments_from_database(
            iap_extraction["analise_id"],
            iap_extraction["ciclo_id"],
            iap_extraction["ano"],
        )
    else:
        segments = pd.DataFrame()
        linear_diagram = pd.DataFrame()

    if iap_extraction and iap_extraction["composition"]:
        distribution = pd.DataFrame(iap_extraction["composition"])
    else:
        distribution = pd.DataFrame(
            [
                {"classe": "RL+RS", "km": 51.16, "percentual": 38.2, "color": _IAP_INTERVENTION_COLORS["RL+RS"]},
                {"classe": "RPS", "km": 81.18, "percentual": 60.7, "color": _IAP_INTERVENTION_COLORS["RPS"]},
                {"classe": "REC", "km": 1.50, "percentual": 1.1, "color": _IAP_INTERVENTION_COLORS["REC"]},
            ]
        )

    return {
        "metrics": metrics,
        "cards": cards,
        "segments": segments,
        "distribution": distribution,
        "linear_diagram": linear_diagram,
        "iap_extraction": iap_extraction,
    }
