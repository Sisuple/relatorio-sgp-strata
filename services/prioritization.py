"""
Módulo de Índice de Priorização de Trechos Rodoviários.

Calcula a criticidade **por segmento** e o SNV herda o valor do segmento mais
crítico (PIOR segmento define o SNV). Isso evita o efeito de "ilha crítica
diluída" quando um SNV longo tem alguns segmentos catastróficos misturados
com muitos trechos em condição regular.

Etapas (para cada SEGMENTO):

1) Normaliza VMDA, IRI e DEF usando o mínimo/máximo GLOBAIS dos segmentos:
   - VMDA -> normalização LOGARÍTMICA
   - IRI  -> normalização LINEAR
   - DEF  -> normalização LINEAR

2) IP técnico (escala 0..10):
       IPT = 10 * (0.15*VMDA_n + 0.50*IRI_n + 0.35*DEF_n)

3) IP econômico (escala 0..10):
       Eficiência = IPT / custo_km * 1000
       IPE = (Eficiência - efic_min) / (efic_max - efic_min) * 10

4) Priorização invertida (inteiro 0..10, menor = mais crítico):
       PRIORIZAÇÃO_SEG = round(10 - (0.60*IPT + 0.40*IPE))

5) Por SNV, herda a menor PRIORIZAÇÃO entre seus segmentos (= o pior).

Ordena os SNVs pela PRIORIZAÇÃO (menor primeiro) e atribui o ranking.

Uso típico:

    ranking = calcular_indice_priorizacao(segmentos)

`segmentos` é uma lista de dicionários, um por segmento. Veja
`calcular_indice_priorizacao` para as chaves aceitas e retornadas.
"""

from __future__ import annotations

import math
from typing import Any

# Pesos do IP técnico (somam 1.0).
# Pavimento (IRI + DEF) domina; VMDA modula. Cliente quer condição como fator principal.
PESO_VMDA = 0.15  # tráfego / importância operacional
PESO_IRI = 0.50   # condição funcional (irregularidade longitudinal)
PESO_DEF = 0.35   # condição estrutural (deflexão / FWD)

# Pesos da priorização final (técnico x econômico).
PESO_TECNICO = 0.60
PESO_ECONOMICO = 0.40

# Faixas de classificação textual conforme a PRIORIZAÇÃO INVERTIDA (0..10).
# Escala invertida: MENOR valor = MAIS crítico (cliente lê "1 a 10 onde 1 é o top").
# Limites inteiros para casar com o valor arredondado exibido na UI.
_FAIXAS_PRIORIDADE: tuple[tuple[float, str], ...] = (
    (3, "Prioridade Crítica"),
    (5, "Prioridade Alta"),
    (7, "Prioridade Média"),
)


def classificar_prioridade(valor: float) -> str:
    """Converte o índice de priorização invertida (0..10, menor = pior) na classificação."""
    for limite, rotulo in _FAIXAS_PRIORIDADE:
        if valor <= limite:
            return rotulo
    return "Prioridade Baixa"


def _valor_valido(valor: Any) -> float | None:
    """Converte para float; retorna None se nulo, não numérico, NaN ou infinito."""
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if math.isnan(numero) or math.isinf(numero):
        return None
    return numero


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def _normalizar_linear(valor: float | None, minimo: float, maximo: float) -> float:
    """Normalização linear (v - min)/(max - min), fixada em [0, 1].

    Retorna 0 (neutro) para valor ausente ou quando max == min.
    """
    if valor is None or maximo == minimo:
        return 0.0
    return min(1.0, max(0.0, (valor - minimo) / (maximo - minimo)))


def _normalizar_log(valor: float | None, minimo: float, maximo: float) -> float:
    """Normalização logarítmica, fixada em [0, 1].

        (LOG(v) - LOG(min)) / (LOG(max) - LOG(min))

    Retorna 0 (neutro) para valor/min/max não positivos ou quando max == min.
    """
    if valor is None or valor <= 0 or minimo <= 0 or maximo <= 0 or maximo == minimo:
        return 0.0
    n = (math.log(valor) - math.log(minimo)) / (math.log(maximo) - math.log(minimo))
    return min(1.0, max(0.0, n))


def _min_max(valores: list[float]) -> tuple[float, float]:
    return (min(valores), max(valores)) if valores else (0.0, 0.0)


def calcular_indice_priorizacao(segmentos: list[dict]) -> list[dict]:
    """Calcula a priorização por SEGMENTO e agrega no SNV pelo PIOR segmento.

    Antes a priorização era calculada por SNV usando médias — o que diluía "ilhas
    críticas" em SNVs longos com condição mista. Agora cada segmento tem seu próprio
    IPT/IPE/Priorização, e o SNV herda o valor do segmento mais crítico
    (menor priorização na escala invertida).

    Entrada — lista de dicionários, um por SEGMENTO, com as chaves:

        rodovia, snv, extensao_km, vmda, iri, deflexao (ou "fwd"), custo

    Saída — uma entrada por SNV, ordenada da maior para a menor criticidade,
    refletindo o **pior segmento** do SNV.
    """
    if not segmentos:
        return []

    # --- mínimo/máximo GLOBAIS sobre os valores por segmento ---
    vmda_seg = [v for s in segmentos if (v := _valor_valido(s.get("vmda"))) is not None]
    iri_seg = [v for s in segmentos if (v := _valor_valido(s.get("iri"))) is not None]
    def_seg = [
        v
        for s in segmentos
        if (v := _valor_valido(s.get("deflexao", s.get("fwd")))) is not None
    ]
    vmda_min, vmda_max = _min_max(vmda_seg)
    iri_min, iri_max = _min_max(iri_seg)
    def_min, def_max = _min_max(def_seg)

    # --- 1ª passada: IPT e eficiência por SEGMENTO ---
    seg_records: list[dict] = []
    for s in segmentos:
        snv = str(s.get("snv"))
        vmda = _valor_valido(s.get("vmda"))
        iri = _valor_valido(s.get("iri"))
        defl = _valor_valido(s.get("deflexao", s.get("fwd")))

        vmda_n = _normalizar_log(vmda, vmda_min, vmda_max)
        iri_n = _normalizar_linear(iri, iri_min, iri_max)
        def_n = _normalizar_linear(defl, def_min, def_max)
        ip_tecnico = 10.0 * (PESO_VMDA * vmda_n + PESO_IRI * iri_n + PESO_DEF * def_n)

        ext = _valor_valido(s.get("extensao_km")) or 0.0
        custo = _valor_valido(s.get("custo")) or 0.0
        custo_km = custo / ext if ext > 0 else 0.0
        eficiencia = (ip_tecnico / custo_km * 1000) if custo_km > 0 else 0.0

        seg_records.append(
            {
                "rodovia": s.get("rodovia"),
                "snv": snv,
                "extensao_km": ext,
                "custo": custo,
                "vmda": vmda or 0.0,
                "iri": iri or 0.0,
                "deflexao": defl or 0.0,
                "vmda_n": vmda_n,
                "iri_n": iri_n,
                "def_n": def_n,
                "ip_tecnico": ip_tecnico,
                "custo_km": custo_km,
                "eficiencia": eficiencia,
            }
        )

    # --- IP econômico: normaliza a eficiência entre os SEGMENTOS (0..10) ---
    eficiencias = [r["eficiencia"] for r in seg_records]
    efic_min, efic_max = _min_max(eficiencias)
    for r in seg_records:
        ipe = (r["eficiencia"] - efic_min) / (efic_max - efic_min) * 10.0 if efic_max > efic_min else 0.0
        r["ip_economico"] = ipe
        bruta = PESO_TECNICO * r["ip_tecnico"] + PESO_ECONOMICO * ipe
        r["priorizacao_segmento"] = int(round(10.0 - bruta))

    # --- agrega no SNV pelo PIOR segmento (menor priorização) ---
    snvs: dict[str, dict] = {}
    ordem: list[str] = []
    for r in seg_records:
        snv = r["snv"]
        if snv not in snvs:
            snvs[snv] = {
                "rodovia": r["rodovia"],
                "snv": snv,
                "extensao_km": 0.0,
                "custo": 0.0,
                "pior": r,
            }
            ordem.append(snv)
        snvs[snv]["extensao_km"] += r["extensao_km"]
        snvs[snv]["custo"] += r["custo"]
        if r["priorizacao_segmento"] < snvs[snv]["pior"]["priorizacao_segmento"]:
            snvs[snv]["pior"] = r
        elif r["priorizacao_segmento"] == snvs[snv]["pior"]["priorizacao_segmento"]:
            # Empate: prefere o de maior IPT (mais técnico).
            if r["ip_tecnico"] > snvs[snv]["pior"]["ip_tecnico"]:
                snvs[snv]["pior"] = r

    # --- monta saída (uma linha por SNV, valores do pior segmento) ---
    resultado: list[dict] = []
    for snv in ordem:
        data = snvs[snv]
        pior = data["pior"]
        custo_km_total = data["custo"] / data["extensao_km"] if data["extensao_km"] > 0 else 0.0
        resultado.append(
            {
                "rodovia": data["rodovia"],
                "snv": snv,
                "extensao_km": round(data["extensao_km"], 2),
                "vmda": round(pior["vmda"], 2),
                "iri": round(pior["iri"], 4),
                "deflexao": round(pior["deflexao"], 4),
                "vmda_normalizado": round(pior["vmda_n"], 4),
                "iri_normalizado": round(pior["iri_n"], 4),
                "deflexao_normalizada": round(pior["def_n"], 4),
                "ip_tecnico": round(pior["ip_tecnico"], 4),
                "custo_km": round(custo_km_total, 2),
                "eficiencia": round(pior["eficiencia"], 6),
                "ip_economico": round(pior["ip_economico"], 4),
                "priorizacao": pior["priorizacao_segmento"],
                "classificacao": classificar_prioridade(pior["priorizacao_segmento"]),
                "ranking": 0,
            }
        )

    # --- ordena por priorização ASC (menor = mais crítico primeiro) ---
    resultado.sort(
        key=lambda r: (r["priorizacao"], -r["ip_tecnico"], -r["eficiencia"]),
    )
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao

    return resultado


# Alias com o nome solicitado na especificação (camelCase).
calcularIndicePriorizacao = calcular_indice_priorizacao


# ---------------------------------------------------------------------------
# DNIT — sem IAP, VMDA ou DEF. Usa IRI (60%) + IGG (40%) por segmento.
# ---------------------------------------------------------------------------
PESO_IRI_DNIT = 0.60
PESO_IGG_DNIT = 0.40


def calcular_indice_priorizacao_dnit(segmentos: list[dict]) -> list[dict]:
    """Versão DNIT: usa IRI e IGG no IPT (sem VMDA/DEF), mesma escala invertida.

    Cada SEGMENTO gera um IPT/IPE/Priorização; o SNV herda o pior segmento.
    Mantém a mesma shape de saída de `calcular_indice_priorizacao`.
    """
    if not segmentos:
        return []

    iri_seg = [v for s in segmentos if (v := _valor_valido(s.get("iri"))) is not None]
    igg_seg = [v for s in segmentos if (v := _valor_valido(s.get("igg"))) is not None]
    iri_min, iri_max = _min_max(iri_seg)
    igg_min, igg_max = _min_max(igg_seg)

    seg_records: list[dict] = []
    for s in segmentos:
        snv = str(s.get("snv"))
        iri = _valor_valido(s.get("iri"))
        igg = _valor_valido(s.get("igg"))
        iri_n = _normalizar_linear(iri, iri_min, iri_max)
        igg_n = _normalizar_linear(igg, igg_min, igg_max)
        ip_tecnico = 10.0 * (PESO_IRI_DNIT * iri_n + PESO_IGG_DNIT * igg_n)

        ext = _valor_valido(s.get("extensao_km")) or 0.0
        custo = _valor_valido(s.get("custo")) or 0.0
        custo_km = custo / ext if ext > 0 else 0.0
        eficiencia = (ip_tecnico / custo_km * 1000) if custo_km > 0 else 0.0

        seg_records.append(
            {
                "rodovia": s.get("rodovia"),
                "snv": snv,
                "extensao_km": ext,
                "custo": custo,
                "iri": iri or 0.0,
                "igg": igg or 0.0,
                "iri_n": iri_n,
                "igg_n": igg_n,
                "ip_tecnico": ip_tecnico,
                "custo_km": custo_km,
                "eficiencia": eficiencia,
            }
        )

    eficiencias = [r["eficiencia"] for r in seg_records]
    efic_min, efic_max = _min_max(eficiencias)
    for r in seg_records:
        ipe = (r["eficiencia"] - efic_min) / (efic_max - efic_min) * 10.0 if efic_max > efic_min else 0.0
        r["ip_economico"] = ipe
        bruta = PESO_TECNICO * r["ip_tecnico"] + PESO_ECONOMICO * ipe
        r["priorizacao_segmento"] = int(round(10.0 - bruta))

    snvs: dict[str, dict] = {}
    ordem: list[str] = []
    for r in seg_records:
        snv = r["snv"]
        if snv not in snvs:
            snvs[snv] = {
                "rodovia": r["rodovia"],
                "snv": snv,
                "extensao_km": 0.0,
                "custo": 0.0,
                "pior": r,
            }
            ordem.append(snv)
        snvs[snv]["extensao_km"] += r["extensao_km"]
        snvs[snv]["custo"] += r["custo"]
        if r["priorizacao_segmento"] < snvs[snv]["pior"]["priorizacao_segmento"]:
            snvs[snv]["pior"] = r
        elif (
            r["priorizacao_segmento"] == snvs[snv]["pior"]["priorizacao_segmento"]
            and r["ip_tecnico"] > snvs[snv]["pior"]["ip_tecnico"]
        ):
            snvs[snv]["pior"] = r

    resultado: list[dict] = []
    for snv in ordem:
        data = snvs[snv]
        pior = data["pior"]
        custo_km_total = data["custo"] / data["extensao_km"] if data["extensao_km"] > 0 else 0.0
        resultado.append(
            {
                "rodovia": data["rodovia"],
                "snv": snv,
                "extensao_km": round(data["extensao_km"], 2),
                "iri": round(pior["iri"], 4),
                "igg": round(pior["igg"], 4),
                "iri_normalizado": round(pior["iri_n"], 4),
                "igg_normalizado": round(pior["igg_n"], 4),
                "ip_tecnico": round(pior["ip_tecnico"], 4),
                "custo_km": round(custo_km_total, 2),
                "eficiencia": round(pior["eficiencia"], 6),
                "ip_economico": round(pior["ip_economico"], 4),
                "priorizacao": pior["priorizacao_segmento"],
                "classificacao": classificar_prioridade(pior["priorizacao_segmento"]),
                "ranking": 0,
            }
        )

    resultado.sort(
        key=lambda r: (r["priorizacao"], -r["ip_tecnico"], -r["eficiencia"]),
    )
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao

    return resultado
