"""Camada de acesso a dados (data access) do Relatório SGP.

Este módulo concentra TODO o SQL do relatório e a transformação dos resultados
em DataFrames / dicionários prontos para consumo. As páginas (app.py e os
componentes em components/) nunca escrevem SQL: elas chamam as funções públicas
`get_*` daqui e recebem estruturas já mastigadas. Isso mantém as queries em um só
lugar e permite cachear de forma agressiva (Redis via @cached e lru_cache em
processo).

Roteamento por tipo de matriz (ver MEMORY "Matriz vs pipeline de dados"):
  - Paragon            -> tabela analise_gerencial_intervencoes_iap  (pipeline IAP,
                          conceito/solução corretiva, projeção contínua de IAP);
  - "Matriz Cadastrada"-> tabela analise_gerencial_intervencoes_dnit (pipeline DNIT,
                          Matriz Revitaliza DNIT/RO, eventos discretos de obra).
As funções `get_dnit_*` atendem o pipeline DNIT; as demais `get_*` atendem o
Paragon. Quando uma rodovia não tem análise Cadastrada, algumas telas DNIT caem
no Paragon como fallback (documentado em cada função).

Regras de negócio hardcoded (nomes, cores, limiares, priorização) estão
catalogadas no README.md Parte II (§11 Terminologia/Cores, §12 Limiares) e no
doc docs/06 (requisitos-regras-negocio-v2). A v2 propõe migrar isso para tabelas
rel_* no banco.

ATENÇÃO — pontos frágeis já conhecidos (marcados ao longo do arquivo):
  - a classificação de IAP existe DUPLICADA: em Python (`_classify_iap`) e em SQL
    (CASE WHEN em `_get_iap_extraction_from_database`) — manter os dois em sincronia;
  - `get_overview_data` ainda carrega valores fake/fallback de demonstração
    (plan_cost_mi=51.8, last_update_minutes=12, distribuição fallback) — remover na v2.
"""

from __future__ import annotations

import re
import json
import bisect
import math
from functools import lru_cache
from typing import Any

import pandas as pd

from core.constants import AVAILABLE_ROADS, DEFAULT_ROAD
from services.cache import cached, cache_flush_all, get_meta, set_meta
from src.database import MySQLConnection


# ============================================================================
# CONSTANTES E MAPEAMENTOS (regras hardcoded — ver README Parte II §11 e §12)
# ============================================================================

# Regex de parsing de rótulos de rodovia e da geometria WKT.
_ROAD_CODE_RE = re.compile(r"(\d+)")  # 1º grupo de dígitos = código da BR (ex.: "BR-364" -> 364)
_ROAD_UF_RE = re.compile(r"BR[-\s]*(?P<code>\d+)\s*/\s*(?P<uf>[A-Z]{2})", re.IGNORECASE)  # extrai UF de "BR-364/RO"
_LINESTRING_RE = re.compile(r"LINESTRING\s*\((?P<coords>.*)\)", re.IGNORECASE)  # captura os pares de coords do WKT
# Salto máximo (em graus) tolerado entre pontos de uma LINESTRING; acima disso o
# traçado é considerado quebrado/deslocado e é descartado (~3,3 km).
_MAX_MAP_LINE_DEGREES = 0.03
# Ordem canônica das classes de conceito IAP (melhor -> pior). Usada para ordenar
# as barras de composição/distribuição. README §11.4 / §12.1.
_IAP_CLASS_ORDER = [
    "Excelente",
    "Bom",
    "++ Regular",
    "+ Regular",
    "- Regular",
    "Mau",
    "Péssimo",
]
# Paleta oficial das classes IAP (README §11.4). A MESMA paleta é repetida em
# overview_map.py e linear_diagram.py — mantê-las em sincronia (candidata a rel_* na v2).
_IAP_CLASS_COLORS = {
    "Excelente": "#00c2e8",
    "Bom": "#00a651",
    "++ Regular": "#b6d7a8",
    "+ Regular": "#f4f1a6",
    "- Regular": "#fff200",
    "Mau": "#f2a51a",
    "Péssimo": "#d71920",
}
# Ordem canônica dos códigos de solução corretiva (menos -> mais severa). Usada
# para ordenar as composições por intervenção. README §11.1.
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
# Cores das soluções = mesmas cores do conceito IAP correspondente (Quadro 37 DNIT).
_IAP_INTERVENTION_COLORS = {
    "OK": "#00c2e8",
    "RL": "#00a651",
    "RL+RS": "#b6d7a8",
    "RL+REF": "#f4f1a6",
    "RPS": "#fff200",
    "RPS+REF": "#f2a51a",
    "REC": "#d71920",
    "Sem intervenção": "#82929d",
}
# Código de solução -> conceito IAP correspondente (Quadro 37 DNIT). README §11.3.
# É o que permite colorir o mapa PELA solução em vez do IAP numérico (ver
# _classify_iap_for_map e README §11.5).
_IAP_INTERVENTION_TO_CLASS = {
    "OK": "Excelente",
    "RL": "Bom",
    "RL+RS": "++ Regular",
    "RL+REF": "+ Regular",
    "RPS": "- Regular",
    "RPS+REF": "Mau",
    "REC": "Péssimo",
}
# Classes de condição (ICDS/ICDP/ICDE, escala 0-5) — 5 níveis, sem "Regular" duplo. README §12.2.
_CONDITION_CLASS_ORDER = ["Excelente", "Bom", "Regular", "Mau", "Péssimo"]
_CONDITION_CLASS_COLORS = {
    "Excelente": "#00c2e8",
    "Bom": "#00a651",
    "Regular": "#fff200",
    "Mau": "#f2a51a",
    "Péssimo": "#d71920",
}
# Paleta IAP usada no diagrama linear (herda _IAP_CLASS_COLORS; "Excelente" fixado
# explicitamente para não depender da ordem de merge).
_LINEAR_IAP_CLASS_COLORS = {
    **_IAP_CLASS_COLORS,
    "Excelente": "#00c2e8",
}
# Código de solução corretiva -> nome legível exibido ao usuário. README §11.1.
# Fonte primária dos rótulos quando não há JSON de soluções gravado no banco.
_SOLUTION_LABELS = {
    "OK": "Sem intervenção",
    "RL": "Reparo localizado",
    "RL+RS": "Reparo localizado + Recarga Superficial",
    "RL+REF": "Reparo localizado + reforço",
    "RPS": "Fresagem e recomposição",
    "RPS+REF": "Fresagem e recomposição + reforço",
    "REC": "Reconstrução",
}


# ============================================================================
# HELPERS DE FORMATAÇÃO / PARSING (rótulos de rodovia, floats, geometria WKT)
# ============================================================================


def _road_sort_key(label: str) -> tuple[int, str]:
    """Chave de ordenação de rótulos de rodovia: ordena pelo número da BR (ex.: 364)."""
    match = _ROAD_CODE_RE.search(label)
    return (int(match.group(1)) if match else 9999, label)


def _normalize_road_code(value: str | int | None) -> str | None:
    """Normaliza qualquer forma de rodovia ("BR-364/RO", 364, "364") para o código
    de 3 dígitos com zeros à esquerda ("364"). Retorna None se vazio."""
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
    """Monta o rótulo de exibição "BR-<code>/<UF>" (ou "BR-<code>" se a UF não for
    encontrada no nome). A UF é extraída do texto de `name` via _ROAD_UF_RE."""
    uf = None
    if name:
        match = _ROAD_UF_RE.search(str(name).upper())
        if match:
            uf = match.group("uf")

    return f"BR-{code}/{uf}" if uf else f"BR-{code}"


def _extract_uf_from_road_label(label: str) -> str:
    """Extrai a sigla da UF do rótulo "BR-364/RO" -> "RO"; retorna "--" se não houver."""
    if "/" not in label:
        return "--"
    return label.rsplit("/", 1)[-1].split()[0].strip() or "--"


def _to_float(value: Any, fallback: float = 0.0) -> float:
    """Converte valor do banco em float, tratando None com `fallback` (default 0.0)."""
    if value is None:
        return fallback
    return float(value)


# ============================================================================
# HELPERS DE CLASSIFICAÇÃO (IAP, condição ICDS/ICDP/ICDE) — README §12
# ============================================================================


def _classify_iap(value: Any) -> str:
    """IAP numérico (campo `iapa`, gravado ×100) -> classe de conceito. README §12.1.

    ATENÇÃO: estes MESMOS limiares estão DUPLICADOS em SQL, no CASE WHEN de
    `_get_iap_extraction_from_database` — qualquer ajuste precisa ser feito nos dois
    lugares. Nota conhecida: esta função numérica nunca retorna "+ Regular"
    (existe na legenda mas não tem faixa própria aqui) — ver README §12.1.
    """
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
    """Classe usada no mapa/diagrama, derivada diretamente do IAP numérico.

    Mantido como fachada para preservar chamadas existentes no projeto.
    A solução recomendada continua existindo como informação separada, mas não
    define mais a classe visual do trecho.
    """
    return _classify_iap(value)


def _classify_condition(value: Any) -> str:
    """Índice de condição (ICDS/ICDP/ICDE, escala 0-5) -> classe. README §12.2."""
    index = _to_float(value)
    if index >= 4.5:
        return "Excelente"
    if index >= 3.5:
        return "Bom"
    if index >= 2.5:
        return "Regular"
    if index >= 1.5:
        return "Mau"
    return "Péssimo"


# ============================================================================
# HELPERS DE SOLUÇÃO (nome legível e custo a partir do JSON `solucoes`)
# ============================================================================


def _normalize_solution_label(name: str) -> str:
    """Terminologia do cliente: 'Microrrevestimento' -> 'Recarga Superficial'. README §11.2.

    Cobre o nome vindo do código (_SOLUTION_LABELS) e o `tipoNome` gravado no banco,
    com uma ou duas letras 'r' (microrevestimento / microrrevestimento).
    Obs.: aplicado SÓ no pipeline Paragon; no DNIT o nome permanece "Microrrevestimento".
    """
    return re.sub(r"[Mm]icrorr?evestimento", "Recarga Superficial", name)


def _solution_name(solution_code: str | None, solutions_json: Any = None) -> str:
    """Nome legível da solução de um segmento (Paragon).

    Prefere os `tipoNome` do JSON `solucoes` (concatenados com " + ", sem repetir);
    se não houver JSON, usa o rótulo de _SOLUTION_LABELS a partir do código corretivo.
    Sempre passa pela renomeação de terminologia (_normalize_solution_label).
    """
    if solutions_json:
        try:
            solutions = json.loads(solutions_json) if isinstance(solutions_json, str) else solutions_json
            names = [
                str(item.get("tipoNome", "")).strip()
                for item in solutions
                if isinstance(item, dict) and item.get("tipoNome")
            ]
            if names:
                return _normalize_solution_label(" + ".join(dict.fromkeys(names)))
        except (TypeError, ValueError):
            pass

    return _normalize_solution_label(
        _SOLUTION_LABELS.get(str(solution_code or ""), str(solution_code or "Sem intervenção"))
    )


def _solution_cost(solutions_json: Any = None) -> float:
    """Soma o campo `orcamento` de todos os itens do JSON `solucoes` (custo do segmento)."""
    if not solutions_json:
        return 0.0

    try:
        solutions = json.loads(solutions_json) if isinstance(solutions_json, str) else solutions_json
    except (TypeError, ValueError):
        return 0.0

    total = 0.0
    for item in solutions or []:
        if isinstance(item, dict):
            total += _to_float(item.get("orcamento"))
    return total


# ============================================================================
# HELPERS DE GEOMETRIA (WKT -> polylines para o mapa; merge/simplificação)
# ============================================================================


def _parse_linestring_latlon(wkt: str | None) -> list[list[float]]:
    """Converte um WKT "LINESTRING(lat lon, ...)" numa lista de pares [lat, lon].

    Os pontos vêm de principal_levantamentos via ST_AsText(geometria). Retorna []
    para WKT vazio/inválido. (Assume ordem lat lon no texto do banco.)
    """
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
    """True se algum trecho da polyline dá um salto maior que _MAX_MAP_LINE_DEGREES.

    Usado para descartar geometrias quebradas/deslocadas (que ligariam pontos
    distantes com uma reta espúria atravessando o mapa).
    """
    for start, end in zip(coords, coords[1:]):
        lat_delta = abs(end[0] - start[0])
        lon_delta = abs(end[1] - start[1])
        if max(lat_delta, lon_delta) > _MAX_MAP_LINE_DEGREES:
            return True
    return False


def _merge_consecutive_paths(
    paths: list[list[list[float]]], gap_tol: float = 0.0002
) -> list[list[list[float]]]:
    """Mescla mini-polylines contíguas em traçados maiores.

    Os pontos de levantamento chegam como N segmentos de 2 pontos cada — cada um
    é uma LINESTRING isolada. Como o final de uma costuma ser o início da próxima
    (mesma estrada), juntamos tudo em polylines contínuas para reduzir o JSON
    do mapa de centenas de mini-pares para 1-2 polylines por SNV.

    `gap_tol`: tolerância em graus para considerar "mesmo ponto" no encontro (~22 m).
    """
    if not paths:
        return []
    # Ordena por primeiro ponto (lat, lon) — uma heurística simples para garantir
    # que polylines adjacentes fiquem próximas. Se já vierem ordenadas (caso comum),
    # a ordem é preservada.
    sorted_paths = sorted(paths, key=lambda p: (p[0][0], p[0][1]) if p else (0, 0))
    merged: list[list[list[float]]] = []
    current: list[list[float]] = []
    for path in sorted_paths:
        if not path:
            continue
        if not current:
            current = list(path)
            continue
        last = current[-1]
        first = path[0]
        # se o fim do atual está próximo do início do próximo, conecta.
        if abs(last[0] - first[0]) < gap_tol and abs(last[1] - first[1]) < gap_tol:
            current.extend(path[1:] if path[0] == last else path)
        else:
            merged.append(current)
            current = list(path)
    if current:
        merged.append(current)
    return merged


def _simplify_path(coords: list[list[float]], tolerance: float = 0.00012) -> list[list[float]]:
    """Simplifica uma polyline removendo pontos colineares/redundantes (Ramer-Douglas-Peucker iterativo).

    `tolerance` em graus (~13 m em RO). Reduz drasticamente o tamanho do JSON
    enviado pro iframe do mapa sem perder o traçado visual.
    """
    n = len(coords)
    if n <= 4:
        return coords

    # Implementação iterativa com pilha (evita recursão profunda em traços longos).
    keep = [False] * n
    keep[0] = True
    keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        # Encontra o ponto com maior distância perpendicular ao segmento i-j.
        x1, y1 = coords[i][1], coords[i][0]
        x2, y2 = coords[j][1], coords[j][0]
        dx, dy = x2 - x1, y2 - y1
        seg_len_sq = dx * dx + dy * dy
        max_dist = 0.0
        max_k = i
        for k in range(i + 1, j):
            x0, y0 = coords[k][1], coords[k][0]
            if seg_len_sq == 0:
                d = ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
            else:
                # área do paralelogramo / base = altura
                d = abs(dx * (y1 - y0) - (x1 - x0) * dy) / (seg_len_sq ** 0.5)
            if d > max_dist:
                max_dist = d
                max_k = k
        if max_dist > tolerance:
            keep[max_k] = True
            stack.append((i, max_k))
            stack.append((max_k, j))

    return [coords[i] for i in range(n) if keep[i]]


# ============================================================================
# PIPELINE PARAGON — rodovias, cenários e extração de IAP
# (tabela analise_gerencial_intervencoes_iap)
# ============================================================================


def get_available_roads() -> list[str]:
    """Retorna rodovias cadastradas no banco, com fallback local."""
    roads = _get_available_roads_from_database()
    return roads or AVAILABLE_ROADS


def get_available_scenarios(selected_road: str, matrix_type: str = "Paragon") -> list[dict[str, Any]]:
    """Lista os cenários (análises × ciclos) disponíveis para a rodovia e tipo de matriz.

    Fachada que normaliza a rodovia e delega para _get_iap_scenarios_from_database.
    `matrix_type` é "Paragon" ou "Matriz Cadastrada".
    """
    code = _normalize_road_code(selected_road)
    if not code:
        return []

    return _get_iap_scenarios_from_database(code, matrix_type)


def get_available_years(
    selected_road: str | None,
    matrix_type: str = "Paragon",
    scenario_key: str | None = None,
) -> list[int]:
    """Lista os anos disponíveis para a rodovia/cenário informado.

    A lista é buscada no ciclo resolvido para o cenário selecionado. Se não houver
    cenário explícito, usa o cenário default da metodologia pedida.
    """
    code = _normalize_road_code(selected_road)
    if not code:
        return []

    db = MySQLConnection()
    if matrix_type == "Matriz Cadastrada":
        analysis = _get_dnit_analysis_for_road(code, scenario_key)
        if not analysis:
            return []
        rows = db.execute_query(
            """
            SELECT DISTINCT ano
            FROM analise_gerencial_intervencoes_dnit
            WHERE gerencial_ciclo_id = %s
              AND ano IS NOT NULL
            ORDER BY ano
            """,
            (analysis["ciclo_id"],),
        ) or []
    else:
        scenario = _get_iap_scenario_by_key(code, scenario_key) or _get_default_iap_scenario(db, code)
        if not scenario:
            return []
        rows = db.execute_query(
            """
            SELECT DISTINCT ano
            FROM analise_gerencial_intervencoes_iap
            WHERE gerencial_ciclo_id = %s
              AND ano IS NOT NULL
            ORDER BY ano
            """,
            (scenario["ciclo_id"],),
        ) or []

    return [int(row["ano"]) for row in rows if row.get("ano") is not None]


def get_iap_extraction(
    selected_road: str,
    year: int | None = None,
    scenario_key: str | None = None,
) -> dict[str, Any] | None:
    """Extrai IAP médio, composição por solução e distribuição por classe IAP.

    A extração devolve duas leituras diferentes:
    - `composition`: agrupamento por solução corretiva final;
    - `class_distribution`: agrupamento por classe derivada do IAP numérico.
    """
    code = _normalize_road_code(selected_road)
    if not code:
        return None

    return _get_iap_extraction_from_database(code, year, scenario_key)


@cached(ttl=1800)
def _get_iap_extraction_from_database(
    road_code: str,
    year: int | None,
    scenario_key: str | None = None,
) -> dict[str, Any] | None:
    """Extração Paragon do IAP para um cenário/ano (tabela intervencoes_iap).

    Resolve o cenário (pela key ou o default Paragon) e o ano-base, e roda 3 queries
    sobre analise_gerencial_intervencoes_iap × analise_gerencial_segmento_pistas:
      1) médias/totais (iap médio ponderado por extensão, km/percentual crítico);
      2) composição por solução corretiva final (% sobre trechos com intervenção);
      3) distribuição por classe de conceito IAP (via CASE WHEN em SQL).
    Retorna dict com métricas + composição por solução + distribuição por classe,
    ou None se não houver dados.
    """
    db = MySQLConnection()
    scenario = _get_iap_scenario_by_key(road_code, scenario_key) or _get_default_iap_scenario(db, road_code)
    if not scenario:
        return None

    # Quando o ano não é informado, usa o primeiro ano de projeção disponível
    # para o ciclo. Evita amarrar o default a um ano fixo no código.
    if year is None:
        year = _get_first_projection_year(scenario["ciclo_id"])
        if year is None:
            return None

    # Médias/totais: IAP médio ponderado pela extensão (iapa vem ×100 -> /100); km
    # crítico = extensão com solução 'RPS+REF'/'REC'; % crítico = km crítico sobre a
    # EXTENSÃO TOTAL do recorte; extensão e nº seg.
    averages = db.execute_query(
        """
        SELECT
          ROUND(SUM(sp.extensao * i.iapa) / SUM(sp.extensao) / 100, 4) AS iap_medio,
          ROUND(SUM(CASE WHEN i.solucao_corretiva_final IN ('RPS+REF', 'REC') THEN sp.extensao ELSE 0 END), 2) AS critical_km,
          ROUND(
            SUM(CASE WHEN i.solucao_corretiva_final IN ('RPS+REF', 'REC') THEN sp.extensao ELSE 0 END)
            / NULLIF(SUM(sp.extensao), 0) * 100,
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

    # Composição por solução corretiva: percentual calculado SOMENTE sobre os
    # trechos que têm intervenção (base filtra solucao_corretiva_final IS NOT NULL).
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

    # Distribuição por classe de conceito IAP. ATENÇÃO: este CASE WHEN é a CÓPIA em
    # SQL dos limiares de _classify_iap (README §12.1) — manter os dois em sincronia.
    # O percentual usa window function: km da classe / km total (SUM(SUM(...)) OVER ()).
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
        "critical_rule": "SUM(extensao) where solucao_corretiva_final in ('RPS+REF', 'REC') over total extension",
        "segmentos": int(average.get("segmentos") or 0),
        "composition": composition,
        "class_distribution": class_distribution,
    }


@cached(ttl=3600)
def _get_iap_map_segments_from_database(
    analise_id: int,
    ciclo_id: int,
    year: int,
) -> pd.DataFrame:
    """Segmentos do mapa IAP (Paragon) com geometria real e cor por conceito.

    Junta o IAP/solução de cada segmento (intervencoes_iap) com a geometria
    reconstruída a partir dos pontos do levantamento IRI (principal_levantamentos),
    e devolve um DataFrame com paths simplificados prontos para o mapa. Cada linha
    traz iap, classe/cor derivada do valor numérico e a polyline do trecho.
    """
    db = MySQLConnection()

    # IAP e solução corretiva por segmento no ano (para colorir o traçado).
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

    # Segmentos da análise (km + código SNV p/ rótulo), ordenados por km. O `codigo`
    # vem de uma subquery correlata: o pista_shape cuja faixa de km CONTÉM o segmento
    # (o mais recente por km_inicial DESC).
    seg_rows = db.execute_query(
        """
        SELECT
          seg.id AS id_segmento,
          seg.rodovia AS rodovia,
          seg.km_inicial AS km_inicial_segmento,
          seg.km_final AS km_final_segmento,
          (
            SELECT ps.codigo FROM pista_shape ps
            WHERE ps.rodovia = seg.rodovia
              AND ps.km_inicial <= seg.km_inicial
              AND ps.km_final >= seg.km_final
            ORDER BY ps.km_inicial DESC
            LIMIT 1
          ) AS codigo
        FROM analise_gerencial_segmento_pistas seg
        WHERE seg.analise_gerencial_id = %s
        ORDER BY seg.km_inicial, seg.id
        """,
        (analise_id,),
    ) or []
    # mantém só os segmentos que têm IAP no ano (os demais não vão pro mapa)
    seg_rows = [r for r in seg_rows if int(r["id_segmento"]) in iap_by_segment]
    if not seg_rows:
        return pd.DataFrame()

    rodovia = seg_rows[0].get("rodovia")

    # Geometria real: TODOS os pontos do levantamento IRI da rodovia em UMA
    # consulta (sem join por segmento, que estourava o read_timeout nas longas).
    # Os pontos seguem a estrada na ordem de km → agrupamos por faixa de km. Isso
    # mantém o traçado contínuo (sem os saltos do pista_shape, que tem peças
    # duplicadas/deslocadas em algumas rodovias).
    point_rows = db.execute_query(
        """
        SELECT pt.km_inicial AS km, ST_AsText(pt.geometria) AS wkt
        FROM principal_levantamentos pt
        WHERE pt.levantamento_importacao_id IN (
            SELECT li.id FROM levantamento_importacoes li
            WHERE li.nome_arquivo LIKE CONCAT('BR-', %s, '%%IRI%%')
          )
          AND pt.rodovia = %s
        ORDER BY pt.km_inicial, pt.levantamento_importacao_id
        """,
        (rodovia, rodovia),
    ) or []

    points: list[tuple[float, list[list[float]]]] = []
    for p in point_rows:
        coords = _parse_linestring_latlon(p.get("wkt"))
        if len(coords) >= 2 and not _has_large_coordinate_jump(coords):
            points.append((_to_float(p.get("km")), coords))
    point_kms = [k for k, _ in points]

    segments: list[dict[str, Any]] = []
    for srow in seg_rows:
        segment_id = int(srow["id_segmento"])
        iap_data = iap_by_segment[segment_id]
        seg_km_i = _to_float(srow.get("km_inicial_segmento"))
        seg_km_f = _to_float(srow.get("km_final_segmento"))

        lo = bisect.bisect_left(point_kms, seg_km_i)
        hi = bisect.bisect_right(point_kms, seg_km_f)
        # Cada km do levantamento traz vários pontos (faixas/sentidos, em posições
        # distintas). Concatenar todos faz a linha ziguezaguear entre carreiros, e
        # infla o comprimento. Colapsamos num ponto médio por km → eixo central,
        # traçado contínuo e limpo.
        by_km: dict[float, list[list[float]]] = {}
        for km, coords in points[lo:hi]:
            by_km.setdefault(round(km, 4), []).append(coords[0])
        flat: list[list[float]] = []
        for km in sorted(by_km):
            grp = by_km[km]
            avg = [
                sum(c[0] for c in grp) / len(grp),
                sum(c[1] for c in grp) / len(grp),
            ]
            if not flat or flat[-1] != avg:
                flat.append(avg)
        if len(flat) < 2:
            continue

        segments.append(
            {
                "segment_id": segment_id,
                "sre": srow.get("codigo") or f"Segmento {segment_id}",
                "km_inicial": seg_km_i,
                "km_final": seg_km_f,
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
                "paths": [_simplify_path(flat)],
            }
        )

    return pd.DataFrame(segments)


@cached(ttl=1800)
def _get_linear_diagram_segments_from_database(
    analise_id: int,
    ciclo_id: int,
    year: int,
) -> pd.DataFrame:
    """Segmentos para o diagrama linear (Paragon): por segmento, os índices ICDS/ICDP/
    ICDE e o IAP, já classificados e com cor. Lê intervencoes_iap × segmento_pistas.

    Retorna DataFrame com um registro por segmento (ordenado por km), cada índice
    com sua classe (_classify_condition) e cor, além da classe/cor de IAP pelo valor numérico.
    """
    db = MySQLConnection()
    # `codigo` = SNV/SRE via subquery correlata pelo range de km (mesmo padrão dos
    # outros SELECTs). Índices: icdsb=ICDS (superfície), icdpb=ICDP (panela),
    # icdeb=ICDE (estrutural); iapa vem ×100.
    rows = db.execute_query(
        """
        SELECT
          sp.id AS segment_id,
          (
            SELECT ps.codigo
            FROM pista_shape ps
            WHERE ps.rodovia = sp.rodovia
              AND ps.km_inicial <= sp.km_inicial
              AND ps.km_final >= sp.km_final
            ORDER BY ps.km_inicial DESC
            LIMIT 1
          ) AS codigo,
          sp.km_inicial,
          sp.km_final,
          sp.extensao,
          i.icdsb,
          i.icdpb,
          i.icdeb,
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
            "ICDS": _classify_condition(row.get("icdsb")),
            "ICDP": _classify_condition(row.get("icdpb")),
            "ICDE": _classify_condition(row.get("icdeb")),
        }
        iap_class = _classify_iap_for_map(row.get("iapa"), intervention)
        records.append(
            {
                "segment_id": int(row["segment_id"]),
                "km_inicial": _to_float(row.get("km_inicial")),
                "km_final": _to_float(row.get("km_final")),
                "extensao": _to_float(row.get("extensao")),
                "icds": _to_float(row.get("icdsb")),
                "icdp": _to_float(row.get("icdpb")),
                "icde": _to_float(row.get("icdeb")),
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


def _get_solution_table_from_database(
    analise_id: int,
    ciclo_id: int,
    year: int,
) -> pd.DataFrame:
    """Tabela de soluções recomendadas (Paragon): uma linha por segmento com IAP, IRI,
    IGG, VMDA, deflexão, ICDS/ICDP, solução recomendada e custo estimado.

    Cruza intervencoes_iap (solução) com roughness (IRI), igg (IGG) e desempenho
    (VMDA) do mesmo ciclo/ano. Ordena da solução MAIS severa (REC) para a menos
    severa e, dentro do grupo, por pior IAP e km. Retorna DataFrame para a página.
    """
    db = MySQLConnection()
    # `codigo` = SNV/SRE por subquery correlata; d0b = deflexão D0 (coluna DEF);
    # `solucoes` = JSON de itens (nome/custo); IRI/IGG vêm por LEFT JOIN opcional
    # (roughness/igg) casados por segmento+ciclo+ano; VMDA por subquery em
    # desempenho_pavimento (ignora soft-delete). O ORDER BY/CASE ordena da solução
    # mais severa (REC=1) à menos severa (NULL por último) e, no grupo, pior IAP e km.
    rows = db.execute_query(
        """
        SELECT
          sp.id AS segment_id,
          (
            SELECT ps.codigo
            FROM pista_shape ps
            WHERE ps.rodovia = sp.rodovia
              AND ps.km_inicial <= sp.km_inicial
              AND ps.km_final >= sp.km_final
            ORDER BY ps.km_inicial DESC
            LIMIT 1
          ) AS codigo,
          sp.km_inicial,
          sp.km_final,
          sp.extensao,
          i.iapa,
          i.solucao_corretiva_final,
          i.solucoes,
          i.d0b,
          i.icdsb,
          i.icdpb,
          r.iria,
          g.igga,
          (
            SELECT dp.vmda
            FROM analise_gerencial_desempenho_pavimento dp
            WHERE dp.segmento_pista_id = sp.id
              AND dp.gerencial_ciclo_id = i.gerencial_ciclo_id
              AND dp.ano = i.ano
              AND dp.deleted_at IS NULL
            ORDER BY dp.id DESC
            LIMIT 1
          ) AS vmda
        FROM analise_gerencial_intervencoes_iap i
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = i.segmento_pista_id
        LEFT JOIN analise_gerencial_roughness r
          ON r.segmento_pista_id = sp.id
         AND r.gerencial_ciclo_id = i.gerencial_ciclo_id
         AND r.ano = i.ano
        LEFT JOIN analise_gerencial_igg g
          ON g.segmento_pista_id = sp.id
         AND g.gerencial_ciclo_id = i.gerencial_ciclo_id
         AND g.ano = i.ano
        WHERE sp.analise_gerencial_id = %s
          AND i.gerencial_ciclo_id = %s
          AND i.ano = %s
        ORDER BY
          CASE
            WHEN i.solucao_corretiva_final = 'REC' THEN 1
            WHEN i.solucao_corretiva_final = 'RPS+REF' THEN 2
            WHEN i.solucao_corretiva_final = 'RPS' THEN 3
            WHEN i.solucao_corretiva_final = 'RL+REF' THEN 4
            WHEN i.solucao_corretiva_final = 'RL+RS' THEN 5
            WHEN i.solucao_corretiva_final = 'RL' THEN 6
            WHEN i.solucao_corretiva_final = 'OK' THEN 7
            WHEN i.solucao_corretiva_final IS NULL THEN 8
            ELSE 7
          END,
          i.iapa ASC,
          sp.km_inicial ASC
        """,
        (analise_id, ciclo_id, year),
    ) or []

    records = []
    for row in rows:
        iap = _to_float(row.get("iapa")) / 100
        solution_code = row.get("solucao_corretiva_final")
        segment_id = int(row["segment_id"])
        records.append(
            {
                "SNV": row.get("codigo") or f"Segmento {segment_id}",
                "Km Inicial": _to_float(row.get("km_inicial")),
                "Km Final": _to_float(row.get("km_final")),
                "Extensão": _to_float(row.get("extensao")),
                "IAP": iap,
                "IRI": _to_float(row.get("iria")),
                "IGG": _to_float(row.get("igga")),
                "VMDA": _to_float(row.get("vmda")),
                "DEF": _to_float(row.get("d0b")),
                "ICDS": _to_float(row.get("icdsb")),
                "ICDP": _to_float(row.get("icdpb")),
                "Solução recomendada": _solution_name(solution_code, row.get("solucoes")),
                "Custo estimado": _solution_cost(row.get("solucoes")),
                "_classe_iap": _classify_iap_for_map(row.get("iapa"), solution_code),
                "_solucao_codigo": solution_code or "Sem intervenção",
                "_cor_iap": _LINEAR_IAP_CLASS_COLORS.get(
                    _classify_iap_for_map(row.get("iapa"), solution_code),
                    "#fff200",
                ),
                "_segment_id": segment_id,
            }
        )

    return pd.DataFrame(records)


def _get_budget_solution_items_from_database(
    analise_id: int,
    ciclo_id: int,
) -> pd.DataFrame:
    """Itens de orçamento Paragon: lê analise_gerencial_orcamentos e explode o JSON
    `solucoes` em uma linha por (segmento × ano × item de solução) com custo > 0.

    Cada linha traz SNV, km, extensão, nome/valor/quantidade do item e o custo.
    Base para o cenário econômico Paragon. Ignora itens sem orçamento positivo.
    """
    db = MySQLConnection()
    # `solucoes` = JSON de itens orçados do segmento no ano; `codigo` = SNV/SRE via
    # subquery correlata pelo range de km.
    rows = db.execute_query(
        """
        SELECT
          o.id AS budget_id,
          o.ano,
          o.solucoes,
          sp.id AS segment_id,
          (
            SELECT ps.codigo
            FROM pista_shape ps
            WHERE ps.rodovia = sp.rodovia
              AND ps.km_inicial <= sp.km_inicial
              AND ps.km_final >= sp.km_final
            ORDER BY ps.km_inicial DESC
            LIMIT 1
          ) AS codigo,
          sp.km_inicial,
          sp.km_final,
          sp.extensao
        FROM analise_gerencial_orcamentos o
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = o.segmento_pista_id
        WHERE sp.analise_gerencial_id = %s
          AND o.gerencial_ciclo_id = %s
          AND o.solucoes IS NOT NULL
        ORDER BY o.ano, sp.km_inicial
        """,
        (analise_id, ciclo_id),
    ) or []

    records = []
    for row in rows:
        try:
            solutions = json.loads(row["solucoes"]) if isinstance(row.get("solucoes"), str) else row.get("solucoes")
        except (TypeError, ValueError):
            solutions = []

        segment_id = int(row["segment_id"])
        for item in solutions or []:
            if not isinstance(item, dict):
                continue

            budget = _to_float(item.get("orcamento"))
            if budget <= 0:
                continue

            records.append(
                {
                    "Ano": int(row["ano"]),
                    "SNV": row.get("codigo") or f"Segmento {segment_id}",
                    "Km Inicial": _to_float(row.get("km_inicial")),
                    "Km Final": _to_float(row.get("km_final")),
                    "Extensão": _to_float(row.get("extensao")),
                    "Solução": _normalize_solution_label(str(item.get("tipoNome") or item.get("sigla") or "Sem nome").strip()),
                    "Custo": budget,
                    "Quantidade": _to_float(item.get("quantidades")),
                    "Unidade": str(item.get("quantidades_formatada") or "").split(" ")[-1] if item.get("quantidades_formatada") else "",
                    "_segment_id": segment_id,
                    "_budget_id": int(row["budget_id"]),
                }
            )

    return pd.DataFrame(records)


# ============================================================================
# RESOLUÇÃO DE CENÁRIOS E RODOVIAS (metadados: análise, ciclo, ano-base)
# ============================================================================


def _scenario_key(analise_id: Any, ciclo_id: Any) -> str:
    """Chave estável de um cenário no formato "analise_id:ciclo_id"."""
    return f"{int(analise_id)}:{int(ciclo_id)}"


def _scenario_segment_type(name: str | None) -> tuple[str, str, int]:
    """Deduz o tipo de segmentação do NOME do cenário -> (código, rótulo, ordem).

    "(SH)"/"homogene" = Segmento Homogêneo; "1km" = 1km; senão "Outros".
    A ordem (1/2/3) é usada para posicionar os cenários no seletor.
    """
    normalized = str(name or "").lower()
    if "(sh)" in normalized or "homogene" in normalized:
        return "sh", "Segmento Homogêneo", 1
    if "1km" in normalized or "1 km" in normalized:
        return "1km", "1km", 2

    return "outros", "Outros", 3


def _get_iap_scenario_by_key(road_code: str, scenario_key: str | None) -> dict[str, Any] | None:
    """Localiza o cenário pela key, procurando nos dois tipos de matriz (Paragon e
    Matriz Cadastrada). Retorna o dict do cenário ou None."""
    if not scenario_key:
        return None

    for matrix_type in ("Paragon", "Matriz Cadastrada"):
        for scenario in _get_iap_scenarios_from_database(road_code, matrix_type):
            if scenario["key"] == scenario_key:
                return scenario

    return None


def get_scenario_label(selected_road: str, scenario_key: str | None) -> str | None:
    """Nome do cenário a partir da key, buscando em qualquer tipo de matriz."""
    code = _normalize_road_code(selected_road)
    if not code or not scenario_key:
        return None

    scenario = _get_iap_scenario_by_key(code, scenario_key)
    return scenario["cenario"] if scenario else None


def _get_default_iap_scenario(db: MySQLConnection, road_code: str) -> dict[str, Any] | None:
    """Cenário Paragon default da rodovia = o primeiro da lista ordenada (SH primeiro,
    depois mais recente). Retorna None se a rodovia não tiver cenário Paragon."""
    scenarios = _get_iap_scenarios_from_database(road_code, "Paragon")
    if scenarios:
        return scenarios[0]

    return None


@lru_cache(maxsize=128)
def _get_first_projection_year(ciclo_id: int) -> int | None:
    """Menor ano de projeção (ano-base) do ciclo em intervencoes_iap. None se vazio.
    Cacheado em processo (lru_cache) — limpo por _clear_local_caches."""
    db = MySQLConnection()
    rows = db.execute_query(
        "SELECT MIN(ano) AS ano FROM analise_gerencial_intervencoes_iap WHERE gerencial_ciclo_id = %s",
        (ciclo_id,),
    ) or []
    if not rows or rows[0].get("ano") is None:
        return None
    return int(rows[0]["ano"])


@lru_cache(maxsize=64)
def _get_iap_scenarios_from_database(road_code: str, matrix_type: str) -> list[dict[str, Any]]:
    """Cenários (análise × ciclo) da rodovia para um tipo de matriz.

    Lê analise_gerencial_dados_trechos (só não deletadas) juntando os ciclos. Ordena
    priorizando SH, depois 1km, depois o resto — e, dentro disso, os mais recentes.
    Cacheado em processo (lru_cache); invalidado por ensure_fresh_data quando os
    cenários mudam no banco. Retorna lista de dicts com key/analise_id/ciclo_id/etc.
    """
    db = MySQLConnection()
    # ordem_cenario (CASE) prioriza Segmento Homogêneo (SH), depois 1km, depois outros;
    # deleted_at IS NULL ignora análises com soft-delete; tipo_matriz faz o roteamento
    # Paragon vs Matriz Cadastrada.
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
    """Lista de rótulos "BR-xxx/UF" das rodovias com dados no banco.

    Une as rodovias de analise_gerencial_dados_trechos (têm nome -> permitem extrair
    UF) com as de analise_gerencial_segmento_pistas, dedup por código; prefere o
    rótulo que traz a UF. Cacheado em processo (lru_cache maxsize=1).
    """
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


def get_overview_data(
    selected_road: str | None = None,
    scenario_key: str | None = None,
    year: int | None = None,
) -> dict:
    """Monta os dados fake da tela de visão geral.

    O contrato já separa métricas, segmentos e distribuição para facilitar a
    futura troca por consultas reais no banco.
    """
    road = selected_road or get_available_roads()[0]

    iap_extraction = get_iap_extraction(road, year=year, scenario_key=scenario_key)
    # Métricas reais vêm da extração; os literais são fallback de DEMONSTRAÇÃO usados
    # só quando não há extração (rodovia sem cenário) — remover na v2.
    iap_average = iap_extraction["iap_medio"] if iap_extraction else 3.66
    extension_km = iap_extraction["total_km"] if iap_extraction else 90
    critical_km = iap_extraction["critical_km"] if iap_extraction else 14
    critical_percent = iap_extraction["critical_percent"] if iap_extraction else 15.6
    segment_count = iap_extraction["segmentos"] if iap_extraction else 90

    metrics = {
        "road": road,
        "uf": _extract_uf_from_road_label(road),
        "ano": iap_extraction["ano"] if iap_extraction else None,
        "segment_count": segment_count,
        "extension_km": extension_km,
        "critical_km": critical_km,
        "critical_percent": critical_percent,
        "iap_average": iap_average,
        # FAKE / demonstração — valores fixos ainda não vêm do banco. Remover na v2.
        "plan_cost_mi": 51.8,        # custo do plano em R$ milhões (placeholder)
        "last_update_minutes": 12,   # "atualizado há X min" (placeholder)
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
            "subtitle": "Percentual da extensão total em Mau + Péssimo",
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

    if iap_extraction and iap_extraction["class_distribution"]:
        distribution = pd.DataFrame(iap_extraction["class_distribution"])
    else:
        # Distribuição FAKE de demonstração por classe IAP (sem extração real). Remover na v2.
        distribution = pd.DataFrame(
            [
                {"classe": "Excelente", "km": 22.60, "percentual": 25.1, "color": _IAP_CLASS_COLORS["Excelente"]},
                {"classe": "Bom", "km": 31.40, "percentual": 34.9, "color": _IAP_CLASS_COLORS["Bom"]},
                {"classe": "++ Regular", "km": 18.10, "percentual": 20.1, "color": _IAP_CLASS_COLORS["++ Regular"]},
                {"classe": "- Regular", "km": 10.30, "percentual": 11.4, "color": _IAP_CLASS_COLORS["- Regular"]},
                {"classe": "Mau", "km": 5.40, "percentual": 6.0, "color": _IAP_CLASS_COLORS["Mau"]},
                {"classe": "Péssimo", "km": 2.20, "percentual": 2.5, "color": _IAP_CLASS_COLORS["Péssimo"]},
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


def get_solutions_data(
    selected_road: str | None = None,
    scenario_key: str | None = None,
    year: int | None = None,
) -> dict:
    """Dados da página de Soluções (Paragon): geometria do mapa, tabela de soluções
    recomendadas e itens de orçamento para a rodovia/cenário.

    Agrega _get_iap_map_segments/_get_solution_table/_get_budget_solution_items a
    partir da extração IAP; devolve DataFrames vazios se não houver cenário.
    """
    road = selected_road or get_available_roads()[0]
    iap_extraction = get_iap_extraction(road, year=year, scenario_key=scenario_key)

    if iap_extraction:
        segments = _get_iap_map_segments_from_database(
            iap_extraction["analise_id"],
            iap_extraction["ciclo_id"],
            iap_extraction["ano"],
        )
        table = _get_solution_table_from_database(
            iap_extraction["analise_id"],
            iap_extraction["ciclo_id"],
            iap_extraction["ano"],
        )
        budget_items = _get_budget_solution_items_from_database(
            iap_extraction["analise_id"],
            iap_extraction["ciclo_id"],
        )
        extension_km = iap_extraction["total_km"]
    else:
        segments = pd.DataFrame()
        table = pd.DataFrame()
        budget_items = pd.DataFrame()
        extension_km = 0

    return {
        "road": road,
        "segments": segments,
        "table": table,
        "budget_items": budget_items,
        "extension_km": extension_km,
        "iap_extraction": iap_extraction,
    }


# Metas de IAP usadas na projeção (README §12.3).
# Meta mínima de IAP: abaixo disso o trecho está em situação de problema.
IAP_META = 2.5
# Margem de atenção: trechos cujo IAP projetado fica abaixo disso entram na lista de alerta.
IAP_ATENCAO = 3.5


# ============================================================================
# PIPELINE DNIT — constantes e helpers de classificação (Matriz Cadastrada)
# Limiares IRI/IGG/zona de cor: README §12.4. Roteamento: tabela intervencoes_dnit.
# ============================================================================


# --- Diagnóstico DNIT (IRI / IGG) ---
# Paleta e ordem dos conceitos DNIT (5 níveis: Ótimo -> Péssimo).
_DNIT_COLORS = {
    "Ótimo": "#00a651",
    "Bom": "#8bd95a",
    "Regular": "#fff200",
    "Ruim": "#f2a51a",
    "Péssimo": "#d71920",
}
_DNIT_ORDER = ["Ótimo", "Bom", "Regular", "Ruim", "Péssimo"]
_DNIT_SEV = {"Ótimo": 0, "Bom": 1, "Regular": 2, "Ruim": 3, "Péssimo": 4}
# Penalidade de condição quando a estrutura está deficiente (Dc > Dadm).
_DNIT_DEFL_PENALIDADE = "Ruim"
_DNIT_SITUACAO = {
    "ótimo": "Ótimo", "otimo": "Ótimo", "bom": "Bom", "regular": "Regular",
    "ruim": "Ruim", "péssimo": "Péssimo", "pessimo": "Péssimo",
}


def _classify_iri_dnit(value: float) -> str:
    """Conceito DNIT a partir do IRI (m/km)."""
    if value <= 2.0:
        return "Ótimo"
    if value <= 2.7:
        return "Bom"
    if value <= 3.5:
        return "Regular"
    if value <= 4.6:
        return "Ruim"
    return "Péssimo"


def _classify_igg_dnit(value: float) -> str:
    """Conceito DNIT a partir do IGG (DNIT 006/2003)."""
    if value <= 20:
        return "Ótimo"
    if value <= 40:
        return "Bom"
    if value <= 80:
        return "Regular"
    if value <= 160:
        return "Ruim"
    return "Péssimo"


def _dnit_situacao(value: Any) -> str | None:
    """Normaliza o texto de situação IGG gravado no banco ("otimo", "péssimo"...) para
    o rótulo canônico ("Ótimo", "Péssimo"). Retorna None se vazio/desconhecido."""
    if not value:
        return None
    return _DNIT_SITUACAO.get(str(value).strip().lower())


# --- Avaliação da matriz DNIT "Matriz Revitaliza DNIT/RO" (id 5) ---
_DNIT_MATRIZ_ID = 5
# Cor da matriz DNIT (imagem CBUQ): faixa de IRI define a cor da célula.
_DNIT_ZONA_ORDER = ["IRI ≤ 3", "3 < IRI ≤ 4", "4 < IRI ≤ 5,5", "IRI > 5,5"]
_DNIT_ZONA_COLORS = {
    "IRI ≤ 3": "#8bd95a",
    "3 < IRI ≤ 4": "#fff200",
    "4 < IRI ≤ 5,5": "#f2a51a",
    "IRI > 5,5": "#d71920",
}


def _dnit_matriz_zona(iri: float) -> tuple[str, str]:
    """(zona, cor) da matriz DNIT pela faixa de IRI, igual à imagem do DNIT."""
    if iri <= 3:
        zona = "IRI ≤ 3"
    elif iri <= 4:
        zona = "3 < IRI ≤ 4"
    elif iri <= 5.5:
        zona = "4 < IRI ≤ 5,5"
    else:
        zona = "IRI > 5,5"
    return zona, _DNIT_ZONA_COLORS[zona]


@lru_cache(maxsize=1)
def _load_dnit_matrix() -> dict:
    """Carrega e estrutura a matriz de decisão DNIT (linhas=Número N, colunas=IRI×IGG×Dc/Dadm)."""
    db = MySQLConnection()
    limites = db.execute_query(
        "SELECT id, config_table, logica_intervencao, tipo FROM matriz_limites WHERE matriz_id = %s AND deleted_at IS NULL",
        (_DNIT_MATRIZ_ID,),
    ) or []
    interv_rows = db.execute_query(
        """
        SELECT mli.matriz_limite_id AS ml, i.nome
        FROM matriz_limite_intervencao mli
        JOIN intervencoes i ON i.id = mli.intervencao_id
        WHERE mli.deleted_at IS NULL
        """,
    ) or []
    interv_by_limite: dict[int, list[str]] = {}
    for r in interv_rows:
        interv_by_limite.setdefault(int(r["ml"]), []).append(r["nome"])

    n_rows: list[tuple[int, list]] = []
    col_iri: dict[int, list] = {}
    col_igg: dict[int, list] = {}
    col_dc: dict[int, list] = {}
    cells: dict[tuple[int, int], list[str]] = {}

    # Cada limite descreve uma célula (posição linha×coluna) da matriz do DNIT.
    # linha 1 = faixas de IRI, linha 2 = IGG, linha 3 = Dc/Dadm; linha>=4 = Número N.
    for lim in limites:
        cfg = json.loads(lim["config_table"]) if isinstance(lim["config_table"], str) else (lim["config_table"] or {})
        raw_logic = lim["logica_intervencao"]
        logic = json.loads(raw_logic) if isinstance(raw_logic, str) and raw_logic else raw_logic
        linha = cfg.get("linha")
        coluna = cfg.get("coluna")
        merged = cfg.get("colunasMescladas") or ([coluna] if coluna else [])

        if lim["tipo"] == "intervencao":
            cells[(linha, coluna)] = interv_by_limite.get(int(lim["id"]), [])
        elif lim["tipo"] == "condicao" and logic:
            cond = logic.get("condicoes", [])
            if linha == 1:
                for c in merged:
                    col_iri[c] = cond
            elif linha == 2:
                col_igg[coluna] = cond
            elif linha == 3:
                for c in merged:
                    col_dc[c] = cond
            elif coluna == 1 and linha and linha >= 4:
                n_rows.append((linha, cond))

    n_rows.sort(key=lambda t: t[0])
    return {"n_rows": n_rows, "col_iri": col_iri, "col_igg": col_igg, "col_dc": col_dc, "cells": cells}


def _dnit_cond_ok(condicoes: list, p: dict) -> bool:
    """Avalia se o segmento (params em `p`: iri/igg/numero_n/dc/dadm) satisfaz TODAS as
    condições da célula da matriz (AND). Suporta comparação especial dc<=dadm quando o
    valor é o select "dadm". Qualquer condição inválida/ausente retorna False.
    """
    for c in condicoes:
        op = c.get("operador")
        if c.get("tipoValor") == "select" and c.get("valor") == "dadm":
            left, right = p.get("dc"), p.get("dadm")
        else:
            left = p.get(c.get("parametro"))
            try:
                right = float(c.get("valor"))
            except (TypeError, ValueError):
                return False
        if left is None or right is None:
            return False
        if op == "<=" and not left <= right:
            return False
        if op == "<" and not left < right:
            return False
        if op == ">" and not left > right:
            return False
        if op == ">=" and not left >= right:
            return False
    return True


def _eval_dnit_matrix(matrix: dict, iri: float, igg: float, numero_n: float, dc: float | None, dadm: float | None) -> list[str]:
    """Retorna as intervenções da célula da matriz para o segmento."""
    # Dc ausente -> assume estrutura OK (Dc <= Dadm).
    if dc is None or dadm is None:
        dc, dadm = 0.0, 1e9
    p = {"iri": iri, "igg": igg, "numero_n": numero_n, "dc": dc, "dadm": dadm}

    linha = next((ln for ln, cond in matrix["n_rows"] if _dnit_cond_ok(cond, p)), None)
    if linha is None and matrix["n_rows"]:
        linha = matrix["n_rows"][-1][0]

    for col in sorted({k[1] for k in matrix["cells"] if k[0] == linha}):
        if (
            _dnit_cond_ok(matrix["col_iri"].get(col, []), p)
            and _dnit_cond_ok(matrix["col_igg"].get(col, []), p)
            and _dnit_cond_ok(matrix["col_dc"].get(col, []), p)
        ):
            return matrix["cells"].get((linha, col), [])
    return []


def get_dnit_overview_data(
    selected_road: str | None = None,
    scenario_key: str | None = None,
    year: int | None = None,
) -> dict:
    """Dados da visão geral DNIT: segmentos com IRI e IGG classificados (faixas DNIT)."""
    road = selected_road or get_available_roads()[0]
    code = _normalize_road_code(road)
    if not code:
        return {}

    # Análise Cadastrada (pipeline DNIT) honrando o cenário escolhido; se a rodovia não
    # tiver matriz Cadastrada, cai no Paragon (intervencoes_iap) — comportamento anterior.
    analysis = _get_dnit_analysis_for_road(code, scenario_key)
    if analysis:
        analise_id, ciclo_id = analysis["analise_id"], analysis["ciclo_id"]
        year = int(year if year is not None else analysis["ano"])
    else:
        extraction = get_iap_extraction(road, year=year, scenario_key=scenario_key)
        if not extraction:
            return {}
        analise_id, ciclo_id, year = extraction["analise_id"], extraction["ciclo_id"], extraction["ano"]

    data = _get_dnit_overview_from_database(analise_id, ciclo_id, year)
    if data:
        data["road"] = road
        # Enriquece cada segmento com a Solução recomendada (pipeline de soluções DNIT).
        sol = _get_dnit_solutions_from_database(analise_id, ciclo_id, year) or {}
        sol_segs = sol.get("segments")
        sol_by_seg: dict[int, Any] = {}
        if sol_segs is not None and not sol_segs.empty and "solucao_grupo" in sol_segs.columns:
            sol_by_seg = dict(zip(sol_segs["segment_id"].astype(int), sol_segs["solucao_grupo"]))
        segs = data.get("segments")
        if segs is not None and not segs.empty:
            segs["solucao"] = segs["segment_id"].astype(int).map(sol_by_seg)
    return data


@cached(ttl=1800)
def _get_dnit_overview_from_database(analise_id: int, ciclo_id: int, year: int) -> dict:
    """Visão geral DNIT: por segmento, IRI e IGG classificados (faixas DNIT), critério
    estrutural Dc×Dadm e a zona de cor da matriz DNIT (por faixa de IRI).

    Lê IRI de roughness, IGG de igg, D0 de parametros_iniciais e Dadm de
    desempenho_pavimento; combina com a geometria (mapa IAP ou geometria DNIT).
    Retorna dict com o DataFrame de segmentos + médias ponderadas por extensão
    (IRI/IGG), % com deflexão ruim e % crítico, além das paletas/ordens DNIT.
    """
    # Paragon usa a geometria do mapa IAP; Cadastrada (sem intervencoes_iap) cai na
    # geometria DNIT, que não depende de IAP e traz as mesmas colunas.
    geo = _get_iap_map_segments_from_database(analise_id, ciclo_id, year)
    if geo is None or geo.empty:
        geo = _get_dnit_geometry_from_database(analise_id)
    if geo is None or geo.empty:
        return {}

    db = MySQLConnection()
    # IRI por segmento no ano (roughness)
    iri_rows = db.execute_query(
        "SELECT segmento_pista_id AS seg, iria FROM analise_gerencial_roughness WHERE gerencial_ciclo_id = %s AND ano = %s",
        (ciclo_id, year),
    ) or []
    # IGG + situação textual por segmento no ano (igg)
    igg_rows = db.execute_query(
        "SELECT segmento_pista_id AS seg, igga, situacao_igga FROM analise_gerencial_igg WHERE gerencial_ciclo_id = %s AND ano = %s",
        (ciclo_id, year),
    ) or []
    iri_by = {int(r["seg"]): _to_float(r["iria"]) for r in iri_rows}
    igg_by = {int(r["seg"]): (_to_float(r["igga"]), r.get("situacao_igga")) for r in igg_rows}

    # Deflexão: Dc = parametros_iniciais.d0 (mm); Dadm = desempenho.dadm (0,01 mm -> /100).
    d0_rows = db.execute_query(
        "SELECT fk_segmento_id AS seg, MAX(d0) AS d0 FROM analise_gerencial_parametros_iniciais WHERE fk_ciclo_id = %s GROUP BY fk_segmento_id",
        (ciclo_id,),
    ) or []
    dadm_rows = db.execute_query(
        "SELECT segmento_pista_id AS seg, MAX(dadm) AS dadm FROM analise_gerencial_desempenho_pavimento WHERE gerencial_ciclo_id = %s AND ano = %s GROUP BY segmento_pista_id",
        (ciclo_id, year),
    ) or []
    d0_by = {int(r["seg"]): _to_float(r["d0"]) for r in d0_rows if r["d0"] is not None}
    dadm_by = {int(r["seg"]): _to_float(r["dadm"]) for r in dadm_rows if r["dadm"] is not None}

    records = []
    for row in geo.to_dict("records"):
        seg = int(row["segment_id"])
        iri = iri_by.get(seg)
        igg_val, situacao = igg_by.get(seg, (None, None))
        if iri is None and igg_val is None:
            continue
        iri = iri or 0.0
        igg_val = igg_val or 0.0
        iri_classe = _classify_iri_dnit(iri)
        igg_classe = _dnit_situacao(situacao) or _classify_igg_dnit(igg_val)

        # Critério estrutural Dc vs Dadm (mesma unidade: mm).
        dc = d0_by.get(seg)
        dadm_raw = dadm_by.get(seg)
        dadm_mm = dadm_raw / 100 if dadm_raw else None
        if dc is not None and dadm_mm:
            defl_ok = dc <= dadm_mm
            defl_classe = "Estrutura OK" if defl_ok else "Reforço (Dc>Dadm)"
            defl_color = "#7f909c" if defl_ok else "#d71920"
            defl_contrib = "Ótimo" if defl_ok else _DNIT_DEFL_PENALIDADE
        else:
            defl_ok = None
            defl_classe = "Sem deflexão"
            defl_color = "#46586a"
            defl_contrib = None

        # Cor da matriz DNIT pela faixa de IRI (sem intervenção nesta tela).
        zona, zona_color = _dnit_matriz_zona(iri)

        records.append(
            {
                "segment_id": seg,
                "sre": row.get("sre"),
                "km_inicial": _to_float(row.get("km_inicial")),
                "km_final": _to_float(row.get("km_final")),
                "paths": row["paths"],
                "iri": round(iri, 2),
                "iri_classe": iri_classe,
                "iri_color": _DNIT_COLORS[iri_classe],
                "igg": round(igg_val, 1),
                "igg_classe": igg_classe,
                "igg_color": _DNIT_COLORS.get(igg_classe, "#fff200"),
                "dc": round(dc, 3) if dc is not None else None,
                "dadm": round(dadm_mm, 3) if dadm_mm else None,
                "matriz_categoria": zona,
                "matriz_color": zona_color,
            }
        )

    segments = pd.DataFrame(records)
    if segments.empty:
        return {}

    # Agregados ponderados por extensão (km) do segmento.
    ext = (segments["km_final"] - segments["km_inicial"]).clip(lower=0)
    total = float(ext.sum()) or 1.0
    # % de km com deficiência estrutural (Dc > Dadm)
    dc_gt = segments["dc"].notna() & segments["dadm"].notna() & (segments["dc"] > segments["dadm"])
    defl_bad = float(ext[dc_gt].sum()) / total * 100
    # % de km crítico = zonas de IRI pior (4-5,5 e >5,5)
    critico_pct = float(ext[segments["matriz_categoria"].isin(["4 < IRI ≤ 5,5", "IRI > 5,5"])].sum()) / total * 100
    return {
        "segments": segments,
        "iri_avg": round(float((segments["iri"] * ext).sum() / total), 2),
        "igg_avg": round(float((segments["igg"] * ext).sum() / total), 1),
        "defl_bad_pct": round(defl_bad, 1),
        "critico_pct": round(critico_pct, 1),
        "total_km": round(total, 1),
        "colors": _DNIT_COLORS,
        "order": _DNIT_ORDER,
        "zona_order": _DNIT_ZONA_ORDER,
        "zona_colors": _DNIT_ZONA_COLORS,
    }


# ============================================================================
# PIPELINE DNIT — Soluções (Matriz Revitaliza DNIT/RO) e geometria
# Lê analise_gerencial_intervencoes_dnit; nomes/cores hardcoded (candidato a rel_* na v2).
# ============================================================================

# --- Soluções DNIT (Matriz Revitaliza DNIT/RO) ---
# Categoria macro da solução DNIT (para a distribuição/cor da barra). A tabela mostra a solução detalhada.
_DNIT_GROUP_COLORS = {
    "Reconstrução": "#d71920",
    "Fresagem + CBUQ": "#f2a51a",
    "Recapeamento CBUQ": "#fff200",
    "Microrrevestimento": "#b6d7a8",
    "Reparo localizado": "#00a651",
    "Outras soluções": "#9fb9d9",
    "A avaliar em campo": "#9fb9d9",
}


def _dnit_solution_group(solucoes: list[str]) -> str:
    """Agrupa a solução detalhada da matriz numa categoria macro (mais severa vence)."""
    if not solucoes:
        return "A avaliar em campo"
    texto = " ".join(solucoes).lower()
    tokens = texto.replace("+", " ").split()
    if any(t.startswith("rec") for t in tokens):
        return "Reconstrução"
    if "fr5" in texto or "fresagem" in texto:
        return "Fresagem + CBUQ"
    if "cbuq" in texto:
        return "Recapeamento CBUQ"
    if "micro" in texto:
        return "Microrrevestimento"
    if "rl" in tokens or "reparo" in texto:
        return "Reparo localizado"
    return "Outras soluções"


# Tipos de intervenção "reparo localizado / conservação" (tabela `intervencao_tipos`): aparecem em
# quase todo segmento como complemento → entram na solução COMPLETA da tabela, mas saem do NÚCLEO do gráfico.
# (9 Reparo de bordo · 10 Selagem de trincas · 11 Tapa-buraco · 12 Remendo-trincas · 13 Remendo-desgaste)
_DNIT_COMPLEMENTARY_TIPOS = {9, 10, 11, 12, 13}


def _dnit_is_complementar(nome: str) -> bool:
    """Fallback por nome quando o tipoId não vier no JSON."""
    n = (nome or "").strip().lower()
    return n.startswith("rl") or "selagem de trincas" in n or "tapa-buraco" in n or "reparo localizado" in n


def _dnit_parse_solucoes(solucoes_json: Any) -> list[tuple[int | None, str]]:
    """Lista [(tipo_id, nome)] das soluções gravadas, sem duplicar nome, na ordem do banco."""
    if not solucoes_json:
        return []
    try:
        items = json.loads(solucoes_json) if isinstance(solucoes_json, str) else solucoes_json
    except (TypeError, ValueError):
        return []
    out: list[tuple[int | None, str]] = []
    seen: set[str] = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        nome = str(it.get("tipoNome", "")).strip()
        if not nome or nome in seen:
            continue
        seen.add(nome)
        try:
            tid = int(it.get("tipoId")) if it.get("tipoId") is not None else None
        except (TypeError, ValueError):
            tid = None
        out.append((tid, nome))
    return out


def _dnit_solution_core_label(parsed: list[tuple[int | None, str]]) -> str:
    """Núcleo da solução (intervenção de pavimento), sem os complementares — para o gráfico.

    Classifica pelo `tipoId` gravado (= `intervencao_tipo_id`); cai p/ heurística de nome se faltar.
    """
    def is_comp(tid: int | None, nome: str) -> bool:
        """True se o item é complementar (conservação) — por tipoId, ou por nome se faltar."""
        return tid in _DNIT_COMPLEMENTARY_TIPOS if tid is not None else _dnit_is_complementar(nome)

    core = [nome for tid, nome in parsed if not is_comp(tid, nome)]
    if core:
        return " + ".join(dict.fromkeys(core))
    return " + ".join(dict.fromkeys(n for _, n in parsed)) if parsed else "—"


def get_dnit_available_roads() -> list[str]:
    """Rodovias (labels) que têm soluções DNIT gravadas (processadas com a Matriz Cadastrada)."""
    db = MySQLConnection()
    rows = db.execute_query(
        """
        SELECT DISTINCT agdt.rodovia
        FROM analise_gerencial_dados_trechos agdt
        JOIN analise_gerencial_ciclos agc ON agc.analise_gerencial_id = agdt.id
        WHERE agdt.deleted_at IS NULL
          AND agdt.tipo_matriz = 'Matriz Cadastrada'
          AND EXISTS (SELECT 1 FROM analise_gerencial_intervencoes_dnit d WHERE d.gerencial_ciclo_id = agc.id)
        """
    ) or []
    codes = {_normalize_road_code(r.get("rodovia")) for r in rows}
    return [road for road in get_available_roads() if _normalize_road_code(road) in codes]


def get_dnit_solutions_data(selected_road: str | None = None, scenario_key: str | None = None) -> dict:
    """Soluções DNIT **gravadas no banco** (análise 'Matriz Cadastrada' / Matriz Revitaliza DNIT/RO).

    A matriz de cores (faixa de IRI) define só a COR no mapa; a SOLUÇÃO vem de
    `analise_gerencial_intervencoes_dnit`. Só rodovias processadas com essa matriz têm dados
    (hoje, apenas a BR-429); as demais usam Paragon.
    """
    road = selected_road or get_available_roads()[0]
    code = _normalize_road_code(road)
    analysis = _get_dnit_analysis_for_road(code, scenario_key) if code else None
    base = {
        "road": road,
        "available": False,
        "segments": pd.DataFrame(),
        "table": pd.DataFrame(),
        "zona_order": _DNIT_ZONA_ORDER,
        "zona_colors": _DNIT_ZONA_COLORS,
    }
    if not analysis:
        return base

    data = _get_dnit_solutions_from_database(analysis["analise_id"], analysis["ciclo_id"], analysis["ano"])
    if not data:
        return base
    data["road"] = road
    data["available"] = True
    data["cenario"] = analysis.get("nome")
    data["ano"] = analysis.get("ano")
    return data


def _scenario_ciclo_id(scenario_key: str | None) -> int | None:
    """Extrai o ciclo_id de uma key 'analise_id:ciclo_id'."""
    if not scenario_key:
        return None
    parts = str(scenario_key).split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


@lru_cache(maxsize=32)
def _get_dnit_analysis_for_road(road_code: str, scenario_key: str | None = None) -> dict | None:
    """Análise 'Matriz Cadastrada' da rodovia com soluções DNIT gravadas (ano-base = 1º ano).

    Se `scenario_key` apontar para um ciclo Cadastrada com intervenções DNIT, usa-o
    (respeita o seletor de Cenários: CRESCENTE/DECRESCENTE etc.); caso contrário, cai
    no último ciclo Cadastrada processado da rodovia.
    """
    db = MySQLConnection()
    base_select = """
        SELECT agdt.id AS analise_id, agdt.nome, agc.id AS ciclo_id,
               (SELECT MIN(d.ano) FROM analise_gerencial_intervencoes_dnit d WHERE d.gerencial_ciclo_id = agc.id) AS ano
        FROM analise_gerencial_dados_trechos agdt
        JOIN analise_gerencial_ciclos agc ON agc.analise_gerencial_id = agdt.id
        WHERE agdt.deleted_at IS NULL
          AND agdt.rodovia = %s
          AND agdt.tipo_matriz = 'Matriz Cadastrada'
          AND EXISTS (SELECT 1 FROM analise_gerencial_intervencoes_dnit d WHERE d.gerencial_ciclo_id = agc.id)
    """
    ciclo_id = _scenario_ciclo_id(scenario_key)
    params: list[Any] = [str(int(road_code))]
    where_extra = ""
    if ciclo_id is not None:
        where_extra = " AND agc.id = %s"
        params.append(ciclo_id)

    rows = db.execute_query(
        base_select + where_extra + " ORDER BY agc.id DESC LIMIT 1",
        tuple(params),
    ) or []

    # Cenário escolhido não é Cadastrada / sem intervenção DNIT → usa o último ciclo.
    if not rows and ciclo_id is not None:
        return _get_dnit_analysis_for_road(road_code, None)

    if not rows:
        return None
    r = rows[0]
    return {
        "analise_id": int(r["analise_id"]),
        "ciclo_id": int(r["ciclo_id"]),
        "ano": int(r["ano"]),
        "nome": r.get("nome"),
    }


@cached(ttl=3600)
def _get_dnit_geometry_from_database(analise_id: int) -> pd.DataFrame:
    """Geometria/SRE/km de TODOS os segmentos da análise (sem depender de IAP).

    Geometria pelos pontos do levantamento IRI agrupados por km (eixo central),
    numa única consulta — evita o timeout do join por segmento nas rodovias longas
    (mesmo fix do `_get_iap_map_segments_from_database`).
    """
    db = MySQLConnection()
    seg_rows = db.execute_query(
        """
        SELECT
          seg.id AS id_segmento,
          seg.rodovia AS rodovia,
          seg.km_inicial AS km_inicial_segmento,
          seg.km_final AS km_final_segmento,
          (
            SELECT ps.codigo FROM pista_shape ps
            WHERE ps.rodovia = seg.rodovia
              AND ps.km_inicial <= seg.km_inicial
              AND ps.km_final >= seg.km_final
            ORDER BY ps.km_inicial DESC LIMIT 1
          ) AS codigo
        FROM analise_gerencial_segmento_pistas seg
        WHERE seg.analise_gerencial_id = %s
        ORDER BY seg.km_inicial, seg.id
        """,
        (analise_id,),
    ) or []
    if not seg_rows:
        return pd.DataFrame()

    rodovia = seg_rows[0].get("rodovia")
    point_rows = db.execute_query(
        """
        SELECT pt.km_inicial AS km, ST_AsText(pt.geometria) AS wkt
        FROM principal_levantamentos pt
        WHERE pt.levantamento_importacao_id IN (
            SELECT li.id FROM levantamento_importacoes li
            WHERE li.nome_arquivo LIKE CONCAT('BR-', %s, '%%IRI%%')
          )
          AND pt.rodovia = %s
        ORDER BY pt.km_inicial, pt.levantamento_importacao_id
        """,
        (rodovia, rodovia),
    ) or []
    points: list[tuple[float, list[list[float]]]] = []
    for p in point_rows:
        coords = _parse_linestring_latlon(p.get("wkt"))
        if len(coords) >= 2 and not _has_large_coordinate_jump(coords):
            points.append((_to_float(p.get("km")), coords))
    point_kms = [k for k, _ in points]

    segments: list[dict[str, Any]] = []
    for srow in seg_rows:
        km_i = _to_float(srow.get("km_inicial_segmento"))
        km_f = _to_float(srow.get("km_final_segmento"))
        lo = bisect.bisect_left(point_kms, km_i)
        hi = bisect.bisect_right(point_kms, km_f)
        by_km: dict[float, list[list[float]]] = {}
        for km, coords in points[lo:hi]:
            by_km.setdefault(round(km, 4), []).append(coords[0])
        flat: list[list[float]] = []
        for km in sorted(by_km):
            grp = by_km[km]
            avg = [
                sum(c[0] for c in grp) / len(grp),
                sum(c[1] for c in grp) / len(grp),
            ]
            if not flat or flat[-1] != avg:
                flat.append(avg)
        if len(flat) < 2:
            continue
        segments.append(
            {
                "segment_id": int(srow["id_segmento"]),
                "sre": srow.get("codigo") or f"Segmento {int(srow['id_segmento'])}",
                "km_inicial": km_i,
                "km_final": km_f,
                "paths": [_simplify_path(flat)],
            }
        )

    return pd.DataFrame(segments)


@cached(ttl=1800)
def _get_dnit_solutions_from_database(
    analise_id: int, ciclo_id: int, year: int, all_years: bool = False
) -> dict:
    """Soluções DNIT gravadas (analise_gerencial_intervencoes_dnit) por segmento.

    Combina a geometria DNIT com IRI/IGG e o JSON `solucoes` de cada segmento;
    calcula a zona de cor por IRI, o texto da solução, o núcleo (sem complementares)
    e o grupo macro. Retorna segments (mapa) + table (ordenada por severidade de IRI).
    `all_years=True` amplia o escopo para segmentos tratados em QUALQUER ano do
    horizonte (usado no cenário econômico); preferindo a solução do ano-base.
    Só entram segmentos que têm solução DNIT gravada.
    """
    geo = _get_dnit_geometry_from_database(analise_id)
    if geo is None or geo.empty:
        return {}

    db = MySQLConnection()
    iri_rows = db.execute_query(
        "SELECT segmento_pista_id AS seg, iria FROM analise_gerencial_roughness WHERE gerencial_ciclo_id = %s AND ano = %s",
        (ciclo_id, year),
    ) or []
    igg_rows = db.execute_query(
        "SELECT segmento_pista_id AS seg, igga, situacao_igga FROM analise_gerencial_igg WHERE gerencial_ciclo_id = %s AND ano = %s",
        (ciclo_id, year),
    ) or []
    if all_years:
        # Econômico: inclui os segmentos tratados em QUALQUER ano do horizonte
        # (scope = via toda, coerente com o custo do horizonte). Pega a solução do
        # ano-base se houver; senão, a do primeiro ano de intervenção.
        sol_rows = db.execute_query(
            "SELECT segmento_pista_id AS seg, ano, solucoes FROM analise_gerencial_intervencoes_dnit "
            "WHERE gerencial_ciclo_id = %s AND solucoes IS NOT NULL ORDER BY ano",
            (ciclo_id,),
        ) or []
        sol_by = {}
        for r in sol_rows:
            seg = int(r["seg"])
            if seg not in sol_by:  # ordenado por ano → 1º ano de intervenção
                sol_by[seg] = r["solucoes"]
            if int(r["ano"]) == year:  # prefere a solução do ano-base
                sol_by[seg] = r["solucoes"]
    else:
        sol_rows = db.execute_query(
            "SELECT segmento_pista_id AS seg, solucoes FROM analise_gerencial_intervencoes_dnit WHERE gerencial_ciclo_id = %s AND ano = %s",
            (ciclo_id, year),
        ) or []
        sol_by = {int(r["seg"]): r["solucoes"] for r in sol_rows}

    iri_by = {int(r["seg"]): _to_float(r["iria"]) for r in iri_rows}
    igg_by = {int(r["seg"]): (_to_float(r["igga"]), r.get("situacao_igga")) for r in igg_rows}

    seg_records = []
    table_records = []
    for row in geo.to_dict("records"):
        seg = int(row["segment_id"])
        parsed = _dnit_parse_solucoes(sol_by.get(seg))
        if not parsed:
            continue  # só segmentos com solução DNIT gravada
        nomes = [n for _, n in parsed]

        iri = iri_by.get(seg) or 0.0
        igg_val = igg_by.get(seg, (0.0, None))[0] or 0.0
        zona, zona_color = _dnit_matriz_zona(iri)
        solucao_txt = " + ".join(nomes)
        nucleo = _dnit_solution_core_label(parsed)
        solucao_grupo = _dnit_solution_group(nomes)

        km_i = _to_float(row.get("km_inicial"))
        km_f = _to_float(row.get("km_final"))
        ext = max(km_f - km_i, 0.0)

        seg_records.append(
            {
                "segment_id": seg,
                "sre": row.get("sre"),
                "km_inicial": km_i,
                "km_final": km_f,
                "paths": row["paths"],
                "iri": round(iri, 2),
                "igg": round(igg_val, 1),
                "matriz_categoria": zona,
                "matriz_color": zona_color,
                "solucao_grupo": solucao_grupo,
            }
        )
        table_records.append(
            {
                "SNV": row.get("sre"),
                "Km Inicial": km_i,
                "Km Final": km_f,
                "Extensão": ext,
                "IRI": round(iri, 2),
                "IGG": round(igg_val, 1),
                "Faixa": zona,
                "Solução recomendada": solucao_txt,
                "Solução núcleo": nucleo,
                "_segment_id": seg,
                "_zona_color": zona_color,
            }
        )

    segments = pd.DataFrame(seg_records)
    table = pd.DataFrame(table_records)
    if table.empty:
        return {}

    # Ordena pela faixa mais severa (pior IRI primeiro), depois km.
    zona_sev = {z: i for i, z in enumerate(_DNIT_ZONA_ORDER)}
    table["_sev"] = table["Faixa"].map(lambda z: zona_sev.get(z, 0))
    table = (
        table.sort_values(["_sev", "Km Inicial"], ascending=[False, True])
        .drop(columns="_sev")
        .reset_index(drop=True)
    )

    return {
        "segments": segments,
        "table": table,
        "extension_km": round(float(table["Extensão"].sum()), 1),
        "group_colors": _DNIT_GROUP_COLORS,
        "zona_order": _DNIT_ZONA_ORDER,
        "zona_colors": _DNIT_ZONA_COLORS,
    }


# ============================================================================
# PIPELINE PARAGON — Projeção de IAP ao longo dos anos
# (curva contínua de IAP; tabela analise_gerencial_intervencoes_iap)
# ============================================================================


def get_projection_data(selected_road: str | None = None, scenario_key: str | None = None) -> dict:
    """Série de projeção do IAP ao longo dos anos para a rodovia/cenário."""
    road = selected_road or get_available_roads()[0]
    code = _normalize_road_code(road)
    if not code:
        return {}

    scenario = _get_iap_scenario_by_key(code, scenario_key)
    if not scenario:
        defaults = _get_iap_scenarios_from_database(code, "Paragon")
        scenario = defaults[0] if defaults else None
    if not scenario:
        return {}

    data = _get_projection_from_database(scenario["analise_id"], scenario["ciclo_id"])
    if data:
        data["road"] = road
        data["scenario"] = scenario
    return data


@cached(ttl=3600)
def _get_projection_from_database(analise_id: int, ciclo_id: int) -> dict:
    """Motor da projeção Paragon: toda a série anual de IAP do ciclo, agregada em
    várias visões para os gráficos (lê intervencoes_iap de TODOS os anos).

    Percorre cada (segmento, ano) e monta, ponderando por extensão:
      - por ano: IAP médio antes/depois, IAP mínimo, km abaixo da meta, km com obra
        e composição por conceito;
      - por trecho (SRE): série de IAP, anos com intervenção e histórico de soluções;
      - alertas dos trechos com pior IAP projetado (crítico/atenção) e faixas de
        conceito (limite = menor IAP observado em cada conceito).
    Retorna um dict grande com todas essas séries prontas para a página de projeção.
    """
    db = MySQLConnection()

    # Extensão e código SNV/SRE de cada segmento (rótulo e ponderação por km).
    seg_rows = db.execute_query(
        """
        SELECT
          sp.id AS seg,
          sp.extensao,
          (
            SELECT ps.codigo
            FROM pista_shape ps
            WHERE ps.rodovia = sp.rodovia
              AND ps.km_inicial <= sp.km_inicial
              AND ps.km_final >= sp.km_final
            ORDER BY ps.km_inicial DESC
            LIMIT 1
          ) AS sre
        FROM analise_gerencial_segmento_pistas sp
        WHERE sp.analise_gerencial_id = %s
        """,
        (analise_id,),
    ) or []
    seg_info = {
        int(r["seg"]): {"ext": _to_float(r["extensao"]), "sre": r.get("sre") or f"Segmento {r['seg']}"}
        for r in seg_rows
    }

    # Todos os anos do ciclo. iapa = IAP DEPOIS da intervenção do ano (×100);
    # iapb = IAP ANTES; conceito_iapa = classe já calculada no pipeline.
    rows = db.execute_query(
        """
        SELECT ano, segmento_pista_id AS seg, iapa, iapb, conceito_iapa, solucao_corretiva_final
        FROM analise_gerencial_intervencoes_iap
        WHERE gerencial_ciclo_id = %s
        ORDER BY ano
        """,
        (ciclo_id,),
    ) or []
    if not rows:
        return {}

    per_year: dict[int, dict[str, float]] = {}
    per_seg: dict[int, list[tuple[int, float]]] = {}
    per_sre: dict[str, dict[int, dict[str, float]]] = {}
    conceito_min: dict[str, float] = {}
    max_iap = 0.0
    for row in rows:
        seg = int(row["seg"])
        info = seg_info.get(seg)
        if info is None:
            continue
        ext = info["ext"]
        ano = int(row["ano"])
        iap_after = _to_float(row.get("iapa")) / 100
        iap_before = _to_float(row.get("iapb")) / 100
        solution = row.get("solucao_corretiva_final")

        bucket = per_year.setdefault(
            ano,
            {"ext": 0.0, "w_after": 0.0, "w_before": 0.0, "min_after": iap_after, "below_km": 0.0, "interv_km": 0.0, "conceitos": {}},
        )
        bucket["ext"] += ext
        bucket["w_after"] += ext * iap_after
        bucket["w_before"] += ext * iap_before
        bucket["min_after"] = min(bucket["min_after"], iap_after)
        if iap_after < IAP_META:
            bucket["below_km"] += ext
        has_interv = bool(solution and str(solution).upper() != "OK")
        if has_interv:
            bucket["interv_km"] += ext

        per_seg.setdefault(seg, []).append((ano, iap_after))

        # série por trecho (SRE), ponderada por extensão
        sre = info["sre"]
        sd = per_sre.setdefault(sre, {}).setdefault(ano, {"ext": 0.0, "w": 0.0, "interv": 0.0, "solucoes": {}})
        sd["ext"] += ext
        sd["w"] += ext * iap_after
        if has_interv:
            sd["interv"] = 1.0
            code = str(solution)
            sd["solucoes"][code] = sd["solucoes"].get(code, 0.0) + ext

        # limiar de cada conceito = menor IAP observado naquele conceito
        conceito = row.get("conceito_iapa")
        if conceito:
            cur = conceito_min.get(conceito)
            if cur is None or iap_after < cur:
                conceito_min[conceito] = iap_after
            bucket["conceitos"][conceito] = bucket["conceitos"].get(conceito, 0.0) + ext
        max_iap = max(max_iap, iap_after)

    years = sorted(per_year)
    base_year = years[0]
    iap_axis_max = max(6.0, math.ceil(max_iap))

    def col(key: str) -> list[float]:
        """Extrai a coluna `key` do bucket de cada ano como lista alinhada a `years`."""
        return [round(per_year[y][key], 3) for y in years]

    avg_after = [round(per_year[y]["w_after"] / per_year[y]["ext"], 3) if per_year[y]["ext"] else 0.0 for y in years]
    avg_before = [round(per_year[y]["w_before"] / per_year[y]["ext"], 3) if per_year[y]["ext"] else 0.0 for y in years]
    min_after = col("min_after")
    below_km = col("below_km")
    interv_km = col("interv_km")

    # Alertas por SRE: menor IAP projetado (anos > ano base) e quando ocorre.
    sre_min: dict[str, tuple[float, int]] = {}
    for seg, series in per_seg.items():
        sre = seg_info[seg]["sre"]
        future = [(ano, iap) for ano, iap in series if ano > base_year]
        if not future:
            continue
        min_iap = min(iap for _, iap in future)
        min_year = min(ano for ano, iap in future if iap == min_iap)
        current = sre_min.get(sre)
        if current is None or min_iap < current[0]:
            sre_min[sre] = (min_iap, min_year)

    ranked = sorted((m, y, s) for s, (m, y) in sre_min.items())
    alerts = [
        {
            "sre": s,
            "year": y,
            "iap": round(m, 2),
            "tipo": "critico" if m < IAP_META else ("atencao" if m < IAP_ATENCAO else "ok"),
        }
        for m, y, s in ranked
        if m < IAP_ATENCAO
    ][:15]
    critical_count = sum(1 for m, _, _ in ranked if m < IAP_META)

    future_idx = [i for i, y in enumerate(years) if y > base_year] or [len(years) - 1]
    worst_future_val = min(min_after[i] for i in future_idx)
    worst_future_year = years[min(future_idx, key=lambda i: min_after[i])]

    # Composição da rodovia por conceito (% de km) em cada ano — visão executiva.
    composition = []
    for y in years:
        total = per_year[y]["ext"] or 1.0
        conc = per_year[y].get("conceitos", {})
        segments = [
            {
                "conceito": c,
                "pct": round(conc[c] / total * 100, 1),
                "color": _IAP_CLASS_COLORS.get(c, "#fff200"),
            }
            for c in _IAP_CLASS_ORDER
            if conc.get(c, 0) > 0
        ]
        composition.append({"year": y, "segments": segments})
    pct_above_meta = [
        round((per_year[y]["ext"] - per_year[y]["below_km"]) / (per_year[y]["ext"] or 1.0) * 100, 1)
        for y in years
    ]

    # Séries por trecho (SRE) para o gráfico individual.
    sre_series: dict[str, dict] = {}
    for sre, year_data in per_sre.items():
        yrs = sorted(year_data)
        sre_series[sre] = {
            "years": yrs,
            "iap": [round(year_data[y]["w"] / year_data[y]["ext"], 3) if year_data[y]["ext"] else 0.0 for y in yrs],
            "interv": [bool(year_data[y]["interv"]) for y in yrs],
            "solucoes": [
                list(dict.fromkeys(
                    _solution_name(code)
                    for code, _ in sorted((year_data[y].get("solucoes") or {}).items(), key=lambda kv: -kv[1])
                ))
                for y in yrs
            ],
        }
    sre_list = sorted(sre_series)

    # Histórico de intervenções por ano, por trecho (o que foi feito em cada ano).
    sre_history: dict[str, list[dict]] = {}
    for sre, year_data in per_sre.items():
        hist = []
        for y in sorted(year_data):
            solucoes = year_data[y].get("solucoes") or {}
            if solucoes:
                names = list(dict.fromkeys(_solution_name(code) for code, _ in sorted(solucoes.items(), key=lambda kv: -kv[1])))
                label = " + ".join(names)
                km = round(sum(solucoes.values()), 2)
            else:
                names = []
                label = ""
                km = 0.0
            hist.append({"year": y, "label": label, "km": km, "solucoes": names})
        sre_history[sre] = hist
    # Trecho padrão = o de menor IAP projetado (mais ilustrativo da degradação).
    default_sre = min(
        sre_list,
        key=lambda s: min((v for y, v in zip(sre_series[s]["years"], sre_series[s]["iap"]) if y > base_year), default=9.9),
    ) if sre_list else None

    # Faixas de conceito: limite inferior = menor IAP observado em cada conceito.
    ordered = sorted(conceito_min.items(), key=lambda kv: kv[1])
    bands = []
    for i, (conceito, low) in enumerate(ordered):
        band_low = 0.0 if i == 0 else round(low, 3)
        band_high = round(ordered[i + 1][1], 3) if i + 1 < len(ordered) else iap_axis_max
        bands.append(
            {
                "conceito": conceito,
                "low": band_low,
                "high": band_high,
                "color": _IAP_CLASS_COLORS.get(conceito, "#fff200"),
            }
        )

    return {
        "years": years,
        "avg_after": avg_after,
        "avg_before": avg_before,
        "min_after": min_after,
        "below_km": below_km,
        "interv_km": interv_km,
        "meta": IAP_META,
        "base_year": base_year,
        "base_avg": avg_after[0],
        "base_below_km": below_km[0],
        "final_avg": avg_after[-1],
        "worst_future_val": round(worst_future_val, 2),
        "worst_future_year": worst_future_year,
        "total_km": round(sum(seg_info[s]["ext"] for s in seg_info), 1),
        "segment_count": len(seg_info),
        "alerts": alerts,
        "critical_count": critical_count,
        "iap_axis_max": iap_axis_max,
        "bands": bands,
        "sre_series": sre_series,
        "sre_list": sre_list,
        "default_sre": default_sre,
        "sre_history": sre_history,
        "composition": composition,
        "pct_above_meta": pct_above_meta,
    }


# ============================================================================
# DNIT — Cenário Econômico e Projeção
# ============================================================================


@cached(ttl=1800)
def _get_dnit_budget_items(ciclo_id: int, analise_id: int) -> pd.DataFrame:
    """Lê analise_gerencial_orcamentos e retorna 1 linha por (segmento × ano × solução)
    com o custo já tabulado. SRE/SNV vem da geometria DNIT cacheada."""
    db = MySQLConnection()
    rows = db.execute_query(
        """
        SELECT o.segmento_pista_id, o.ano, o.solucoes,
               sp.km_inicial, sp.km_final, sp.extensao
        FROM analise_gerencial_orcamentos o
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = o.segmento_pista_id
        WHERE o.gerencial_ciclo_id = %s
          AND sp.analise_gerencial_id = %s
          AND o.solucoes IS NOT NULL
        ORDER BY o.ano, sp.km_inicial
        """,
        (ciclo_id, analise_id),
    ) or []

    geo = _get_dnit_geometry_from_database(analise_id)
    sre_by_seg: dict[int, Any] = {}
    if geo is not None and not geo.empty:
        sre_by_seg = {
            int(r["segment_id"]): (r.get("sre") or f"Segmento {int(r['segment_id'])}")
            for _, r in geo.iterrows()
        }

    items: list[dict[str, Any]] = []
    budget_seq = 0
    for r in rows:
        seg_id = int(r["segmento_pista_id"])
        sre = sre_by_seg.get(seg_id, f"Segmento {seg_id}")
        sols = r.get("solucoes")
        if isinstance(sols, str):
            try:
                sols = json.loads(sols)
            except Exception:
                sols = []
        for sol in sols or []:
            custo = _to_float(sol.get("orcamento"))
            if custo <= 0:
                continue
            budget_seq += 1
            items.append(
                {
                    "SNV": sre,
                    "_segment_id": seg_id,
                    "_budget_id": budget_seq,
                    "Ano": int(r["ano"]),
                    "Solução": sol.get("tipoNome") or "Sem nome",
                    "Custo": custo,
                    "Km Inicial": _to_float(r["km_inicial"]),
                    "Km Final": _to_float(r["km_final"]),
                    "Extensão": _to_float(r["extensao"]),
                }
            )
    return pd.DataFrame(items)


def get_dnit_economic_data(
    selected_road: str | None = None,
    scenario_key: str | None = None,
    year: int | None = None,
) -> dict:
    """Cenário econômico DNIT — mesma shape de get_solutions_data (Paragon).

    Devolve table (segmentos com Custo estimado), budget_items (por seg×ano×solução)
    e segments (geometria) — pronto para alimentar a página de cenário econômico DNIT.
    """
    road = selected_road or get_available_roads()[0]
    code = _normalize_road_code(road)
    analysis = _get_dnit_analysis_for_road(code, scenario_key) if code else None
    if not analysis:
        return {"road": road, "available": False, "table": pd.DataFrame(),
                "budget_items": pd.DataFrame(), "segments": pd.DataFrame()}

    sol_data = _get_dnit_solutions_from_database(
        analysis["analise_id"], analysis["ciclo_id"], analysis["ano"], all_years=True
    )
    if not sol_data:
        return {"road": road, "available": False, "table": pd.DataFrame(),
                "budget_items": pd.DataFrame(), "segments": pd.DataFrame()}

    budget_items = _get_dnit_budget_items(analysis["ciclo_id"], analysis["analise_id"])

    table = sol_data["table"].copy()
    if not budget_items.empty:
        custo_seg = budget_items.groupby("_segment_id")["Custo"].sum().to_dict()
    else:
        custo_seg = {}
    table["Custo estimado"] = table["_segment_id"].astype(int).map(custo_seg).fillna(0.0)
    table["_solucao_codigo"] = table["Solução núcleo"].astype(str)
    # _classe_iap não existe no DNIT — usa Faixa como proxy. Permite o filtro existente
    # (que tira "Excelente") ficar inerte aqui sem quebrar o pipeline.
    table["_classe_iap"] = table["Faixa"]

    return {
        "road": road,
        "available": True,
        "table": table,
        "budget_items": budget_items,
        "segments": sol_data["segments"],
        "extension_km": sol_data.get("extension_km"),
        "zona_order": sol_data.get("zona_order"),
        "zona_colors": sol_data.get("zona_colors"),
        "analise_id": analysis["analise_id"],
        "ciclo_id": analysis["ciclo_id"],
        "ano_base": analysis["ano"],
    }


@cached(ttl=3600)
def _get_dnit_projection_intervencoes(ciclo_id: int, analise_id: int) -> pd.DataFrame:
    """Lê analise_gerencial_intervencoes_dnit + orcamentos e devolve 1 linha por
    (segmento × ano) com a solução principal e o custo daquele ano."""
    db = MySQLConnection()
    rows = db.execute_query(
        """
        SELECT i.segmento_pista_id, i.ano, i.solucoes AS solucoes_intervencao,
               o.solucoes AS solucoes_orcamento
        FROM analise_gerencial_intervencoes_dnit i
        LEFT JOIN analise_gerencial_orcamentos o
               ON o.gerencial_ciclo_id = i.gerencial_ciclo_id
              AND o.segmento_pista_id = i.segmento_pista_id
              AND o.ano = i.ano
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = i.segmento_pista_id
        WHERE i.gerencial_ciclo_id = %s
          AND sp.analise_gerencial_id = %s
          AND i.solucoes IS NOT NULL
        ORDER BY sp.km_inicial, i.ano
        """,
        (ciclo_id, analise_id),
    ) or []

    geo = _get_dnit_geometry_from_database(analise_id)
    sre_by_seg = {}
    if geo is not None and not geo.empty:
        sre_by_seg = {int(r["segment_id"]): r.get("sre") for _, r in geo.iterrows()}

    items = []
    for r in rows:
        seg_id = int(r["segmento_pista_id"])
        parsed = _dnit_parse_solucoes(r.get("solucoes_intervencao"))
        nomes = [n for _, n in parsed]
        nucleo = _dnit_solution_core_label(parsed) if parsed else "—"
        grupo = _dnit_solution_group(nomes) if nomes else "Outras soluções"

        sols_o = r.get("solucoes_orcamento")
        if isinstance(sols_o, str):
            try:
                sols_o = json.loads(sols_o)
            except Exception:
                sols_o = []
        custo = sum(_to_float(s.get("orcamento")) for s in (sols_o or []))

        items.append({
            "SRE": sre_by_seg.get(seg_id) or f"Segmento {seg_id}",
            "_segment_id": seg_id,
            "Ano": int(r["ano"]),
            "Solução núcleo": nucleo,
            "Solução grupo": grupo,
            "Custo": custo,
        })
    return pd.DataFrame(items)


@cached(ttl=3600)
def _get_dnit_iri_projection(ciclo_id: int, analise_id: int) -> pd.DataFrame:
    """Série anual de IRI projetado por segmento + flag de ano com intervenção.

    `intervencao_irib` é NOT NULL quando há obra programada naquele ano (o valor
    é o IRI pós-intervenção). `iria` é o IRI projetado antes da intervenção.
    """
    db = MySQLConnection()
    rows = db.execute_query(
        """
        SELECT r.segmento_pista_id AS seg, r.ano,
               r.iria, r.intervencao_irib
        FROM analise_gerencial_roughness r
        JOIN analise_gerencial_segmento_pistas sp ON sp.id = r.segmento_pista_id
        WHERE r.gerencial_ciclo_id = %s
          AND sp.analise_gerencial_id = %s
          AND r.iria IS NOT NULL
        ORDER BY r.segmento_pista_id, r.ano
        """,
        (ciclo_id, analise_id),
    ) or []
    if not rows:
        return pd.DataFrame()

    geo = _get_dnit_geometry_from_database(analise_id)
    sre_by_seg = {}
    ext_by_seg = {}
    if geo is not None and not geo.empty:
        for _, r in geo.iterrows():
            seg_id = int(r["segment_id"])
            sre_by_seg[seg_id] = r.get("sre") or f"Segmento {seg_id}"
            ext_by_seg[seg_id] = max(_to_float(r.get("km_final")) - _to_float(r.get("km_inicial")), 0.0)

    records = []
    for r in rows:
        seg_id = int(r["seg"])
        iria = _to_float(r.get("iria"))
        interv = r.get("intervencao_irib")
        records.append({
            "_segment_id": seg_id,
            "SRE": sre_by_seg.get(seg_id) or f"Segmento {seg_id}",
            "Extensão": ext_by_seg.get(seg_id, 0.0),
            "Ano": int(r["ano"]),
            "IRI": iria,
            "Intervenção": interv is not None,
        })
    return pd.DataFrame(records)


def get_dnit_iri_projection(selected_road: str | None = None, scenario_key: str | None = None) -> dict:
    """Para cada SRE da rodovia, série anual de IRI médio ponderado por extensão
    e o conjunto de anos com intervenção (≥ 1 segmento recebendo obra)."""
    road = selected_road or get_available_roads()[0]
    code = _normalize_road_code(road)
    analysis = _get_dnit_analysis_for_road(code, scenario_key) if code else None
    if not analysis:
        return {"road": road, "available": False}

    df = _get_dnit_iri_projection(analysis["ciclo_id"], analysis["analise_id"])
    if df.empty:
        return {"road": road, "available": False}

    # Média ponderada por extensão dentro de cada (SRE, Ano).
    df["_iri_ext"] = df["IRI"] * df["Extensão"]
    grouped = (
        df.groupby(["SRE", "Ano"])
        .agg(
            iri_sum=("_iri_ext", "sum"),
            ext_sum=("Extensão", "sum"),
            interv=("Intervenção", "any"),
        )
        .reset_index()
    )
    grouped["IRI"] = grouped["iri_sum"] / grouped["ext_sum"].where(grouped["ext_sum"] > 0, 1)

    sre_series: dict[str, dict] = {}
    for sre, sub in grouped.groupby("SRE"):
        sub = sub.sort_values("Ano")
        sre_series[str(sre)] = {
            "years": sub["Ano"].astype(int).tolist(),
            "iri": [round(float(v), 2) for v in sub["IRI"].tolist()],
            "interv": sub["interv"].astype(bool).tolist(),
        }

    sre_list = sorted(sre_series.keys())
    anos = sorted(grouped["Ano"].astype(int).unique().tolist())

    return {
        "road": road,
        "available": True,
        "sre_series": sre_series,
        "sre_list": sre_list,
        "anos": anos,
        "ano_inicial": min(anos) if anos else None,
        "ano_final": max(anos) if anos else None,
    }


def get_dnit_projection_schedule(selected_road: str | None = None, scenario_key: str | None = None) -> dict:
    """Cronograma de intervenções DNIT por trecho (SRE) × ano.

    Diferente do Paragon (curva contínua de IAP), o DNIT trabalha com eventos
    discretos: para cada SRE, lista os anos em que receberá obra e a solução.
    """
    road = selected_road or get_available_roads()[0]
    code = _normalize_road_code(road)
    analysis = _get_dnit_analysis_for_road(code, scenario_key) if code else None
    if not analysis:
        return {"road": road, "available": False}

    df = _get_dnit_projection_intervencoes(analysis["ciclo_id"], analysis["analise_id"])
    if df.empty:
        return {"road": road, "available": False}

    sre_list = sorted(df["SRE"].dropna().astype(str).unique().tolist())
    anos = sorted(df["Ano"].dropna().astype(int).unique().tolist())
    custo_total = float(df["Custo"].sum())
    custo_por_ano = (
        df.groupby("Ano", as_index=False)["Custo"]
        .sum()
        .sort_values("Ano")
    )

    return {
        "road": road,
        "available": True,
        "schedule": df,
        "sre_list": sre_list,
        "anos": anos,
        "ano_inicial": min(anos) if anos else None,
        "ano_final": max(anos) if anos else None,
        "custo_total": custo_total,
        "custo_por_ano": custo_por_ano,
        "group_colors": _DNIT_GROUP_COLORS,
    }


# ---------------------------------------------------------------------------
# Invalidação automática de cache quando os cenários mudam no banco.
#
# O SIGMA grava/edita/remove cenários (analise_gerencial_dados_trechos) direto
# no banco, mas o relatório cacheia de forma agressiva em duas camadas:
#   - Redis  (sgp:*), compartilhado entre workers;
#   - lru_cache, em processo, que SOBREVIVE ao flush do Redis e só some no
#     restart — por isso uma rodovia/cenário novo não aparecia.
#
# Em vez de depender de flush manual, a cada entrada no relatório calculamos
# uma assinatura barata dos cenários (quantidade + última atualização + maior
# id). Se mudou, invalidamos o cache. Mesma quantidade e mesma data => nada
# muda. Quantidade diferente ou data mais nova => recarrega tudo.
# ---------------------------------------------------------------------------

# Funções com cache em processo (lru_cache): precisam ser limpas explicitamente.
_LOCAL_CACHED_FUNCS = (
    _get_first_projection_year,
    _get_iap_scenarios_from_database,
    _get_available_roads_from_database,
    _load_dnit_matrix,
    _get_dnit_analysis_for_road,
)

# Assinatura já vista POR ESTE processo (cada worker mantém a sua).
_LAST_SCENARIOS_SIGNATURE: str | None = None
_SCENARIOS_SIGNATURE_META_KEY = "scenarios_signature"


def _compute_scenarios_signature() -> str:
    """Assinatura barata dos cenários no banco (sem cache).

    Detecta inserção (count/maior id sobem), edição (max updated_at muda) e
    remoção lógica (count cai, pois conta só deleted_at IS NULL).
    """
    db = MySQLConnection()
    rows = db.execute_query(
        """
        SELECT
            COUNT(*)                       AS n,
            COALESCE(MAX(updated_at), '')  AS u,
            COALESCE(MAX(id), 0)           AS mx
        FROM analise_gerencial_dados_trechos
        WHERE deleted_at IS NULL
        """
    ) or []
    if not rows:
        return "0::0"
    r = rows[0]
    return f"{r['n']}:{r['u']}:{r['mx']}"


def _clear_local_caches() -> None:
    """Limpa os lru_cache em processo deste worker."""
    for fn in _LOCAL_CACHED_FUNCS:
        try:
            fn.cache_clear()
        except Exception:
            pass


def ensure_fresh_data() -> bool:
    """Garante que o relatório reflita os cenários atuais do banco.

    Chamada a cada entrada/rerun. Compara a assinatura dos cenários com a
    última vista por este processo (fast path). Se mudou, limpa o cache em
    processo (lru_cache) deste worker e, se a assinatura global no Redis também
    estiver defasada, faz flush do cache compartilhado — assim apenas o
    primeiro worker a notar a mudança paga o flush, mas todos atualizam o
    próprio lru_cache.

    Retorna True se invalidou o cache compartilhado.
    """
    global _LAST_SCENARIOS_SIGNATURE
    try:
        signature = _compute_scenarios_signature()
    except Exception:
        # Em falha ao calcular a assinatura, não mexe no cache.
        return False

    # Fast path: este processo já está atualizado.
    if signature == _LAST_SCENARIOS_SIGNATURE:
        return False

    # Mudou (ou é a 1ª execução deste worker): limpa o cache local sempre.
    _clear_local_caches()

    # A chave de meta é por banco: v1 (sigma_dnitro) e v2/gestao
    # (sigma_dnitro_backup) compartilham o mesmo Redis/prefixo, então sem o
    # sufixo do banco eles ficariam invalidando um ao outro a cada acesso.
    meta_key = f"{_SCENARIOS_SIGNATURE_META_KEY}:{MySQLConnection().database}"

    # Flush do cache compartilhado só se a assinatura global estiver defasada.
    invalidated = False
    stored = get_meta(meta_key)
    if stored != signature:
        cache_flush_all()
        set_meta(meta_key, signature)
        invalidated = True

    _LAST_SCENARIOS_SIGNATURE = signature
    return invalidated
