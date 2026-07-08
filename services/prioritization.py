"""
Módulo de Índice de Priorização de Trechos Rodoviários.

Calcula a criticidade **por segmento** e o SNV herda o valor do segmento mais
crítico (PIOR segmento define o SNV). Isso evita o efeito de "ilha crítica
diluída" quando um SNV longo tem alguns segmentos catastróficos misturados
com muitos trechos em condição regular.

Etapas (para cada SEGMENTO):

1) Normaliza VMDA, ICDS e ICDP usando o mínimo/máximo GLOBAIS dos segmentos:
   - VMDA -> normalização LOGARÍTMICA
   - ICDS -> normalização LINEAR
   - ICDP -> normalização LINEAR

2) IPT = NÍVEL DE PRIORIDADE (escala 0..10, MENOR = mais prioritário):
       IPT = 10 * (0.50*(1 - VMDA_n) + 0.30*ICDS_n + 0.20*ICDP_n)
   O VMDA é inversamente proporcional à prioridade (mais tráfego -> mais
   prioritário), por isso entra como (1 - VMDA_n); ICDS/ICDP são diretos.

3) IP econômico (auxiliar, escala 0..10) — NÃO entra no nível de prioridade:
       Eficiência = (10 - IPT) / custo_km * 1000   (criticidade por custo)
       IPE = (Eficiência - efic_min) / (efic_max - efic_min) * 10

4) Por SNV, herda o MENOR IPT entre seus segmentos (= o mais crítico).

5) Nível de prioridade = RE-NORMALIZA o IPT (do pior segmento) de cada SNV entre
   os SNVs (min-max → [0,9] e soma 1) → menor IPT = 1, maior IPT = 10.

Ordena os SNVs pela PRIORIZAÇÃO (menor primeiro) e atribui o ranking.

Uso típico:

    ranking = calcular_indice_priorizacao(segmentos)

`segmentos` é uma lista de dicionários, um por segmento. Veja
`calcular_indice_priorizacao` para as chaves aceitas e retornadas.

Ref.: README.md Parte II §13 (documentação completa da metodologia de priorização).
"""

from __future__ import annotations

import math
from typing import Any

# Pesos do IPT — Índice de Priorização Técnica (Paragon). Somam 1.0.
# Metodologia do cliente: o IPT é o próprio nível de prioridade (0..10, menor =
# mais prioritário). VMDA é INVERSAMENTE proporcional à prioridade (entra como
# 1 - R_VMDA); ICDS/ICDP são diretamente proporcionais.
PESO_VMDA = 0.50  # tráfego / importância operacional (log, invertido)
PESO_ICDS = 0.30  # condição de superfície
PESO_ICDP = 0.20  # condição de profundidade

# Pesos da priorização final (técnico x econômico) — usados SÓ na versão DNIT.
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
    """Média aritmética simples; retorna None se a lista estiver vazia."""
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
    """Devolve (mínimo, máximo) da lista; (0.0, 0.0) quando vazia."""
    return (min(valores), max(valores)) if valores else (0.0, 0.0)


def calcular_indice_priorizacao(segmentos: list[dict]) -> list[dict]:
    """Calcula a priorização por SEGMENTO e agrega no SNV pelo PIOR segmento.

    Antes a priorização era calculada por SNV usando médias — o que diluía "ilhas
    críticas" em SNVs longos com condição mista. Agora cada segmento tem seu próprio
    IPT/IPE/Priorização, e o SNV herda o valor do segmento mais crítico
    (menor priorização na escala invertida).

    Entrada — lista de dicionários, um por SEGMENTO, com as chaves:

        rodovia, snv, extensao_km, vmda, icds, icdp, custo

    Saída — uma entrada por SNV, ordenada da maior para a menor criticidade,
    refletindo o **pior segmento** do SNV (menor IPT).
    """
    if not segmentos:
        return []

    # --- mínimo/máximo GLOBAIS sobre os valores por segmento ---
    vmda_seg = [v for s in segmentos if (v := _valor_valido(s.get("vmda"))) is not None]
    icds_seg = [v for s in segmentos if (v := _valor_valido(s.get("icds"))) is not None]
    icdp_seg = [v for s in segmentos if (v := _valor_valido(s.get("icdp"))) is not None]
    vmda_min, vmda_max = _min_max(vmda_seg)
    icds_min, icds_max = _min_max(icds_seg)
    icdp_min, icdp_max = _min_max(icdp_seg)

    # --- 1ª passada: IPT (nível de prioridade) e eficiência por SEGMENTO ---
    seg_records: list[dict] = []
    for s in segmentos:
        snv = str(s.get("snv"))
        vmda = _valor_valido(s.get("vmda"))
        icds = _valor_valido(s.get("icds"))
        icdp = _valor_valido(s.get("icdp"))

        # R ∈ [0,1] (min-max global). VMDA log; ICDS/ICDP lineares.
        vmda_n = _normalizar_log(vmda, vmda_min, vmda_max)
        icds_n = _normalizar_linear(icds, icds_min, icds_max)
        icdp_n = _normalizar_linear(icdp, icdp_min, icdp_max)
        # IPT = nível de prioridade (0..10, MENOR = mais prioritário). VMDA é
        # inversamente proporcional -> (1 - R_VMDA); ICDS/ICDP são diretos.
        ip_tecnico = 10.0 * (
            PESO_VMDA * (1.0 - vmda_n) + PESO_ICDS * icds_n + PESO_ICDP * icdp_n
        )

        ext = _valor_valido(s.get("extensao_km")) or 0.0
        custo = _valor_valido(s.get("custo")) or 0.0
        custo_km = custo / ext if ext > 0 else 0.0
        # Eficiência econômica (auxiliar): criticidade (10 - IPT) por custo/km.
        # Mais crítico e mais barato -> mais eficiente de atacar.
        eficiencia = ((10.0 - ip_tecnico) / custo_km * 1000) if custo_km > 0 else 0.0

        seg_records.append(
            {
                "rodovia": s.get("rodovia"),
                "snv": snv,
                "extensao_km": ext,
                "custo": custo,
                "vmda": vmda or 0.0,
                "icds": icds or 0.0,
                "icdp": icdp or 0.0,
                "vmda_n": vmda_n,
                "icds_n": icds_n,
                "icdp_n": icdp_n,
                "ip_tecnico": ip_tecnico,
                "custo_km": custo_km,
                "eficiencia": eficiencia,
            }
        )

    # --- IP econômico: normaliza a eficiência entre os SEGMENTOS (0..10) ---
    eficiencias = [r["eficiencia"] for r in seg_records]
    efic_min, efic_max = _min_max(eficiencias)
    for r in seg_records:
        r["ip_economico"] = (
            (r["eficiencia"] - efic_min) / (efic_max - efic_min) * 10.0
            if efic_max > efic_min else 0.0
        )

    # --- agrega no SNV pelo PIOR segmento (MENOR IPT = mais crítico) ---
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
        if r["ip_tecnico"] < snvs[snv]["pior"]["ip_tecnico"]:
            snvs[snv]["pior"] = r

    # --- nível de prioridade 1..10: RE-NORMALIZA o IPT do pior segmento de cada SNV
    # (min-max ENTRE os SNVs) p/ [0,9] e soma 1 → menor IPT = 1, maior IPT = 10. ---
    pior_ipts = [snvs[s]["pior"]["ip_tecnico"] for s in ordem]
    ipt_min, ipt_max = _min_max(pior_ipts)

    def _nivel(ipt: float) -> int:
        n = (ipt - ipt_min) / (ipt_max - ipt_min) * 9.0 + 1.0 if ipt_max > ipt_min else 1.0
        return max(1, min(10, int(round(n))))

    # --- monta saída (uma linha por SNV, valores do pior segmento) ---
    resultado: list[dict] = []
    for snv in ordem:
        data = snvs[snv]
        pior = data["pior"]
        custo_km_total = data["custo"] / data["extensao_km"] if data["extensao_km"] > 0 else 0.0
        nivel = _nivel(pior["ip_tecnico"])
        resultado.append(
            {
                "rodovia": data["rodovia"],
                "snv": snv,
                "extensao_km": round(data["extensao_km"], 2),
                "vmda": round(pior["vmda"], 2),
                "icds": round(pior["icds"], 4),
                "icdp": round(pior["icdp"], 4),
                "vmda_normalizado": round(pior["vmda_n"], 4),
                "icds_normalizado": round(pior["icds_n"], 4),
                "icdp_normalizado": round(pior["icdp_n"], 4),
                # mín/máx GLOBAIS (p/ a memória de cálculo na UI).
                "vmda_min": round(vmda_min, 2), "vmda_max": round(vmda_max, 2),
                "icds_min": round(icds_min, 4), "icds_max": round(icds_max, 4),
                "icdp_min": round(icdp_min, 4), "icdp_max": round(icdp_max, 4),
                "ip_tecnico": round(pior["ip_tecnico"], 4),
                # mín/máx do IPT entre SNVs (p/ a re-normalização 1..10 na memória).
                "ipt_min": round(ipt_min, 4), "ipt_max": round(ipt_max, 4),
                "custo_km": round(custo_km_total, 2),
                "eficiencia": round(pior["eficiencia"], 6),
                "ip_economico": round(pior["ip_economico"], 4),
                "priorizacao": nivel,
                "classificacao": classificar_prioridade(nivel),
                "ranking": 0,
            }
        )

    # --- ordena por priorização ASC e IPT ASC (menor = mais crítico primeiro) ---
    resultado.sort(
        key=lambda r: (r["priorizacao"], r["ip_tecnico"], -r["eficiencia"]),
    )
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao

    return resultado


# Alias com o nome solicitado na especificação (camelCase).
calcularIndicePriorizacao = calcular_indice_priorizacao


def calcular_indice_priorizacao_segmento(segmentos: list[dict]) -> list[dict]:
    """Priorização POR SEGMENTO (NÃO agrega no SNV). Cada segmento tem seu próprio
    IPT e nível de prioridade 1..10 (re-normalização min-max do IPT ENTRE os segmentos).

    Mesma fórmula da versão por SNV: IPT = 10·(0,5·(1−R_VMDA) + 0,3·R_ICDS + 0,2·R_ICDP),
    R_VMDA log e ICDS/ICDP lineares (min-max global). Nível = round((IPT−mín)/(máx−mín)·9+1).

    Entrada — lista de dicts por SEGMENTO com: id, vmda, icds, icdp, extensao_km, custo.
    Saída — uma entrada por segmento (chave `id`), ordenada do mais crítico ao menos.
    """
    if not segmentos:
        return []

    vmda_seg = [v for s in segmentos if (v := _valor_valido(s.get("vmda"))) is not None]
    icds_seg = [v for s in segmentos if (v := _valor_valido(s.get("icds"))) is not None]
    icdp_seg = [v for s in segmentos if (v := _valor_valido(s.get("icdp"))) is not None]
    vmda_min, vmda_max = _min_max(vmda_seg)
    icds_min, icds_max = _min_max(icds_seg)
    icdp_min, icdp_max = _min_max(icdp_seg)

    recs: list[dict] = []
    for s in segmentos:
        vmda = _valor_valido(s.get("vmda"))
        icds = _valor_valido(s.get("icds"))
        icdp = _valor_valido(s.get("icdp"))
        vmda_n = _normalizar_log(vmda, vmda_min, vmda_max)
        icds_n = _normalizar_linear(icds, icds_min, icds_max)
        icdp_n = _normalizar_linear(icdp, icdp_min, icdp_max)
        ip_tecnico = 10.0 * (
            PESO_VMDA * (1.0 - vmda_n) + PESO_ICDS * icds_n + PESO_ICDP * icdp_n
        )
        ext = _valor_valido(s.get("extensao_km")) or 0.0
        custo = _valor_valido(s.get("custo")) or 0.0
        custo_km = custo / ext if ext > 0 else 0.0
        eficiencia = ((10.0 - ip_tecnico) / custo_km * 1000) if custo_km > 0 else 0.0
        recs.append(
            {
                "id": s.get("id"),
                "vmda": vmda or 0.0, "icds": icds or 0.0, "icdp": icdp or 0.0,
                "vmda_n": vmda_n, "icds_n": icds_n, "icdp_n": icdp_n,
                "ip_tecnico": ip_tecnico, "custo_km": custo_km, "eficiencia": eficiencia,
            }
        )

    efs = [r["eficiencia"] for r in recs]
    efic_min, efic_max = _min_max(efs)
    for r in recs:
        r["ip_economico"] = (
            (r["eficiencia"] - efic_min) / (efic_max - efic_min) * 10.0
            if efic_max > efic_min else 0.0
        )

    ipts = [r["ip_tecnico"] for r in recs]
    ipt_min, ipt_max = _min_max(ipts)

    def _nivel(ipt: float) -> int:
        n = (ipt - ipt_min) / (ipt_max - ipt_min) * 9.0 + 1.0 if ipt_max > ipt_min else 1.0
        return max(1, min(10, int(round(n))))

    resultado: list[dict] = []
    for r in recs:
        nivel = _nivel(r["ip_tecnico"])
        resultado.append(
            {
                "id": r["id"],
                "vmda": round(r["vmda"], 2), "icds": round(r["icds"], 4), "icdp": round(r["icdp"], 4),
                "vmda_normalizado": round(r["vmda_n"], 4),
                "icds_normalizado": round(r["icds_n"], 4),
                "icdp_normalizado": round(r["icdp_n"], 4),
                "vmda_min": round(vmda_min, 2), "vmda_max": round(vmda_max, 2),
                "icds_min": round(icds_min, 4), "icds_max": round(icds_max, 4),
                "icdp_min": round(icdp_min, 4), "icdp_max": round(icdp_max, 4),
                "ip_tecnico": round(r["ip_tecnico"], 4),
                "ipt_min": round(ipt_min, 4), "ipt_max": round(ipt_max, 4),
                "custo_km": round(r["custo_km"], 2),
                "eficiencia": round(r["eficiencia"], 6),
                "ip_economico": round(r["ip_economico"], 4),
                "priorizacao": nivel,
                "classificacao": classificar_prioridade(nivel),
                "ranking": 0,
            }
        )

    resultado.sort(key=lambda r: (r["priorizacao"], r["ip_tecnico"], -r["eficiencia"]))
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao
    return resultado


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
        # IPT DNIT (0..10): IRI e IGG são ambos LINEARES e DIRETOS (pior condição
        # -> maior IPT). Diferente do Paragon, aqui não há termo invertido.
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
        # Nota bruta = técnico (IPT, 60%) + econômico (IPE, 40%); a priorização
        # do segmento INVERTE essa nota (10 - bruta) para a escala 0..10 onde
        # MENOR = mais crítico (mesma leitura de classificar_prioridade).
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
        # Pior segmento = menor priorização; em empate, o de maior IPT (pior
        # condição técnica) — o SNV herda esse segmento.
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
