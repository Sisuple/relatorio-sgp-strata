"""
Módulo de Índice de Priorização de Trechos Rodoviários.

Replica a metodologia da planilha de priorização usada pela engenharia. O
índice é calculado **por SNV** (trecho), agregando os segmentos do SNV.

Etapas (para cada SNV):

1) Agrega os segmentos do SNV:
   - VMDA, IRI, DEF -> média dos segmentos do SNV (MÉDIASE)
   - custo_km       -> soma dos custos / soma das extensões do SNV

2) Normaliza cada variável usando o mínimo/máximo GLOBAIS (sobre os valores por
   segmento de toda a rede):
   - VMDA -> normalização LOGARÍTMICA
       (LOG(v) - LOG(min)) / (LOG(max) - LOG(min))
   - IRI  -> normalização LINEAR  (v - min) / (max - min)
   - DEF  -> normalização LINEAR  (v - min) / (max - min)

3) IP técnico (criticidade técnica, escala 0..10):
       IPT = 10 * (0.40*VMDA_n + 0.35*IRI_n + 0.25*DEF_n)

4) IP econômico (relação prioridade/custo, escala 0..10):
       Eficiência = IPT / custo_km * 1000
       IPE = (Eficiência - efic_min) / (efic_max - efic_min) * 10
   (efic_min/efic_max são o mínimo/máximo da eficiência entre os SNVs)

5) Priorização final (mistura técnica + econômica, escala 0..10):
       PRIORIZAÇÃO = 0.60*IPT + 0.40*IPE

Ordena os SNVs pela PRIORIZAÇÃO (maior primeiro) e atribui o ranking.

Uso típico:

    ranking = calcular_indice_priorizacao(segmentos)

`segmentos` é uma lista de dicionários, um por segmento. Veja
`calcular_indice_priorizacao` para as chaves aceitas e retornadas.
"""

from __future__ import annotations

import math
from typing import Any

# Pesos do IP técnico (somam 1.0).
PESO_VMDA = 0.40  # tráfego / importância operacional
PESO_IRI = 0.35   # condição funcional (irregularidade longitudinal)
PESO_DEF = 0.25   # condição estrutural (deflexão / FWD)

# Pesos da priorização final (técnico x econômico).
PESO_TECNICO = 0.60
PESO_ECONOMICO = 0.40

# Faixas de classificação textual conforme a PRIORIZAÇÃO (0..10).
_FAIXAS_PRIORIDADE: tuple[tuple[float, str], ...] = (
    (7.5, "Prioridade Crítica"),
    (5.0, "Prioridade Alta"),
    (3.0, "Prioridade Média"),
    (0.0, "Prioridade Baixa"),
)


def classificar_prioridade(valor: float) -> str:
    """Converte o índice de priorização (0..10) na classificação textual."""
    for limite, rotulo in _FAIXAS_PRIORIDADE:
        if valor >= limite:
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
    """Calcula a priorização por SNV e devolve a lista ordenada por prioridade.

    Entrada — lista de dicionários, um por SEGMENTO, com as chaves:

        rodovia       (str)
        snv           (str)            código SNV (agrupador)
        extensao_km   (float)          extensão do segmento em km
        vmda          (float)          tráfego do segmento
        iri           (float)          condição funcional do segmento
        deflexao      (float)          condição estrutural (FWD); alias "fwd"
        custo         (float)          custo da intervenção do segmento

    Saída — NOVA lista, um item por SNV, ordenada da maior para a menor
    priorização, cada item com:

        rodovia, snv, extensao_km (total do SNV),
        vmda, iri, deflexao (médias do SNV),
        vmda_normalizado, iri_normalizado, deflexao_normalizada,
        ip_tecnico, custo_km, eficiencia, ip_economico, priorizacao,
        classificacao, ranking
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

    # --- agrega os segmentos por SNV (preservando a ordem de aparição) ---
    grupos: dict[str, dict] = {}
    ordem: list[str] = []
    for s in segmentos:
        snv = str(s.get("snv"))
        grupo = grupos.get(snv)
        if grupo is None:
            grupo = {
                "rodovia": s.get("rodovia"),
                "snv": snv,
                "vmda": [],
                "iri": [],
                "deflexao": [],
                "custo": 0.0,
                "extensao_km": 0.0,
            }
            grupos[snv] = grupo
            ordem.append(snv)

        for chave, origem in (("vmda", "vmda"), ("iri", "iri")):
            valor = _valor_valido(s.get(origem))
            if valor is not None:
                grupo[chave].append(valor)
        deflexao = _valor_valido(s.get("deflexao", s.get("fwd")))
        if deflexao is not None:
            grupo["deflexao"].append(deflexao)

        grupo["custo"] += _valor_valido(s.get("custo")) or 0.0
        grupo["extensao_km"] += _valor_valido(s.get("extensao_km")) or 0.0

    # --- IP técnico e eficiência por SNV ---
    resultado: list[dict] = []
    for snv in ordem:
        grupo = grupos[snv]
        vmda_m = _media(grupo["vmda"])
        iri_m = _media(grupo["iri"])
        def_m = _media(grupo["deflexao"])

        vmda_n = _normalizar_log(vmda_m, vmda_min, vmda_max)
        iri_n = _normalizar_linear(iri_m, iri_min, iri_max)
        def_n = _normalizar_linear(def_m, def_min, def_max)

        ip_tecnico = 10.0 * (PESO_VMDA * vmda_n + PESO_IRI * iri_n + PESO_DEF * def_n)
        custo_km = grupo["custo"] / grupo["extensao_km"] if grupo["extensao_km"] > 0 else 0.0
        # Eficiência = criticidade técnica por unidade de custo (trata custo zero).
        eficiencia = (ip_tecnico / custo_km * 1000) if custo_km > 0 else 0.0

        resultado.append(
            {
                "rodovia": grupo["rodovia"],
                "snv": snv,
                "extensao_km": round(grupo["extensao_km"], 2),
                "vmda": round(vmda_m, 2) if vmda_m is not None else 0.0,
                "iri": round(iri_m, 4) if iri_m is not None else 0.0,
                "deflexao": round(def_m, 4) if def_m is not None else 0.0,
                "vmda_normalizado": round(vmda_n, 4),
                "iri_normalizado": round(iri_n, 4),
                "deflexao_normalizada": round(def_n, 4),
                "ip_tecnico": round(ip_tecnico, 4),
                "custo_km": round(custo_km, 2),
                "eficiencia": eficiencia,  # mantido sem arredondar p/ normalizar o IPE
                "ip_economico": 0.0,
                "priorizacao": 0.0,
                "classificacao": "",
                "ranking": 0,
            }
        )

    # --- IP econômico: normaliza a eficiência entre os SNVs (0..10) ---
    eficiencias = [r["eficiencia"] for r in resultado]
    efic_min, efic_max = _min_max(eficiencias)
    for r in resultado:
        if efic_max > efic_min:
            ipe = (r["eficiencia"] - efic_min) / (efic_max - efic_min) * 10.0
        else:
            ipe = 0.0
        r["ip_economico"] = round(ipe, 4)
        r["priorizacao"] = round(PESO_TECNICO * r["ip_tecnico"] + PESO_ECONOMICO * ipe, 4)
        r["classificacao"] = classificar_prioridade(r["priorizacao"])
        r["eficiencia"] = round(r["eficiencia"], 6)

    # --- ordena por priorização (desempate: IPT, depois eficiência) e ranqueia ---
    resultado.sort(
        key=lambda r: (r["priorizacao"], r["ip_tecnico"], r["eficiencia"]),
        reverse=True,
    )
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao

    return resultado


# Alias com o nome solicitado na especificação (camelCase).
calcularIndicePriorizacao = calcular_indice_priorizacao
