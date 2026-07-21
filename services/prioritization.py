"""
Módulo de Índice de Priorização de Trechos Rodoviários.

Calcula a criticidade **por segmento** e o SNV herda o valor do segmento mais
crítico (PIOR segmento define o SNV). Isso evita o efeito de "ilha crítica
diluída" quando um SNV longo tem alguns segmentos catastróficos misturados
com muitos trechos em condição regular.

Etapas Paragon (para cada SEGMENTO):

1) Calcula DDS e DDP a partir de ICDS e ICDP.
2) Calcula DQO pela regra multiplicativa e pelo gatilho assimétrico.
3) Calcula VMDeq com VMDL + 4 * VMDP.
4) Calcula FT pela curva saturante de tráfego.
5) Calcula IPI em escala 0..100.

Por SNV, herda o MAIOR IPI entre seus segmentos (= o mais crítico).

Ordena os SNVs pelo IPI em ordem decrescente e atribui o ranking.

Uso típico:

    ranking = calcular_indice_priorizacao(segmentos)

`segmentos` é uma lista de dicionários, um por segmento. Veja
`calcular_indice_priorizacao` para as chaves aceitas e retornadas.

Ref.: README.md Parte II §13 (documentação completa da metodologia de priorização).
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from services.ipi import calcular_ipi_lote, classificar_prioridade_ipi

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


def _classificar_prioridade_ipi_dashboard(ipi: float) -> str:
    """Adapta a classe direta do IPI ao texto já usado nos cards/tabelas."""
    classe = classificar_prioridade_ipi(ipi)
    if classe == "Muito Baixa":
        return "Prioridade Muito Baixa"
    return f"Prioridade {classe}"


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


def _normalizar_linear(valor: float | None, minimo: float, maximo: float) -> float:
    """Normalização linear (v - min)/(max - min), fixada em [0, 1].

    Retorna 0 (neutro) para valor ausente ou quando max == min.
    """
    if valor is None or maximo == minimo:
        return 0.0
    return min(1.0, max(0.0, (valor - minimo) / (maximo - minimo)))

def _min_max(valores: list[float]) -> tuple[float, float]:
    """Devolve (mínimo, máximo) da lista; (0.0, 0.0) quando vazia."""
    return (min(valores), max(valores)) if valores else (0.0, 0.0)


def calcular_indice_priorizacao(segmentos: list[dict]) -> list[dict]:
    """Calcula a priorização Paragon pelo IPI e agrega no SNV pelo pior segmento.

    O IPI substitui o IPT antigo. A escala técnica é direta (maior IPI = mais
    crítico). A fila é ordenada do maior IPI para o menor IPI.

    Entrada — lista de dicionários, um por SEGMENTO, com as chaves:

        rodovia, snv, extensao_km, vmdl, vmdp, icds, icdp, custo

    Saída — uma entrada por SNV, ordenada da maior para a menor criticidade,
    refletindo o **pior segmento** do SNV (maior IPI).
    """
    if not segmentos:
        return []

    base = pd.DataFrame(segmentos)
    if base.empty:
        return []
    for col in ("icds", "icdp", "vmdl", "vmdp"):
        base[col] = pd.to_numeric(base[col], errors="coerce") if col in base.columns else pd.NA
    valid = base.dropna(subset=["icds", "icdp", "vmdl", "vmdp"]).copy()
    valid = valid[
        valid["icds"].between(0, 5)
        & valid["icdp"].between(0, 5)
        & (valid["vmdl"] >= 0)
        & (valid["vmdp"] >= 0)
    ].copy()
    if valid.empty:
        return []
    ipi_df = calcular_ipi_lote(valid[["icds", "icdp", "vmdl", "vmdp"]])
    valid = valid.reset_index(drop=True)
    ipi_df = ipi_df.reset_index(drop=True)

    seg_records: list[dict] = []
    for idx, s in valid.iterrows():
        calc = ipi_df.loc[idx]
        ext = _valor_valido(s.get("extensao_km")) or 0.0
        custo = _valor_valido(s.get("custo")) or 0.0
        custo_km = custo / ext if ext > 0 else 0.0
        ipi = float(calc["ipi"])
        eficiencia = (ipi / custo_km * 1000) if custo_km > 0 else 0.0
        seg_records.append(
            {
                "rodovia": s.get("rodovia"),
                "snv": str(s.get("snv")),
                "extensao_km": ext,
                "custo": custo,
                "vmda": float(s.get("vmda") or (float(s.get("vmdl") or 0.0) + float(s.get("vmdp") or 0.0))),
                "vmdl": float(s.get("vmdl") or 0.0),
                "vmdp": float(s.get("vmdp") or 0.0),
                "vmdeq": float(calc["vmdeq"]),
                "icds": float(s.get("icds") or 0.0),
                "icdp": float(s.get("icdp") or 0.0),
                "dds": float(calc["dds"]),
                "ddp": float(calc["ddp"]),
                "dqo_base": float(calc["dqo_base"]),
                "gatilho": float(calc["gatilho"]),
                "dqo": float(calc["dqo"]),
                "ft": float(calc["ft"]),
                "ip_tecnico": ipi,
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

    # --- agrega no SNV pelo PIOR segmento (MAIOR IPI = mais crítico) ---
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
        if r["ip_tecnico"] > snvs[snv]["pior"]["ip_tecnico"]:
            snvs[snv]["pior"] = r

    # --- monta saída (uma linha por SNV, valores do pior segmento) ---
    resultado: list[dict] = []
    for snv in ordem:
        data = snvs[snv]
        pior = data["pior"]
        custo_km_total = data["custo"] / data["extensao_km"] if data["extensao_km"] > 0 else 0.0
        ipi = round(pior["ip_tecnico"], 4)
        resultado.append(
            {
                "rodovia": data["rodovia"],
                "snv": snv,
                "extensao_km": round(data["extensao_km"], 2),
                "vmda": round(pior["vmda"], 2),
                "vmdl": round(pior["vmdl"], 2),
                "vmdp": round(pior["vmdp"], 2),
                "vmdeq": round(pior["vmdeq"], 2),
                "icds": round(pior["icds"], 4),
                "icdp": round(pior["icdp"], 4),
                "dds": round(pior["dds"], 4),
                "ddp": round(pior["ddp"], 4),
                "dqo_base": round(pior["dqo_base"], 4),
                "gatilho": round(pior["gatilho"], 4),
                "dqo": round(pior["dqo"], 4),
                "ft": round(pior["ft"], 4),
                "ipi": ipi,
                "ip_tecnico": ipi,
                "custo_km": round(custo_km_total, 2),
                "eficiencia": round(pior["eficiencia"], 6),
                "ip_economico": round(pior["ip_economico"], 4),
                # Mantido como alias interno para telas antigas, sem reescala 1..10.
                "priorizacao": ipi,
                "classificacao": _classificar_prioridade_ipi_dashboard(pior["ip_tecnico"]),
                "ranking": 0,
            }
        )

    # --- ordena por IPI DESC (maior = mais crítico primeiro) ---
    resultado.sort(key=lambda r: (-r["ip_tecnico"], -r["eficiencia"]))
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao

    return resultado


# Alias com o nome solicitado na especificação (camelCase).
calcularIndicePriorizacao = calcular_indice_priorizacao


def calcular_indice_priorizacao_segmento(segmentos: list[dict]) -> list[dict]:
    """Priorização POR SEGMENTO (NÃO agrega no SNV), usando o IPI.

    Entrada — lista de dicts por SEGMENTO com: id, vmdl, vmdp, icds, icdp, extensao_km, custo.
    Saída — uma entrada por segmento (chave `id`), ordenada do mais crítico ao menos.
    """
    if not segmentos:
        return []

    base = pd.DataFrame(segmentos)
    if base.empty:
        return []
    for col in ("icds", "icdp", "vmdl", "vmdp"):
        base[col] = pd.to_numeric(base[col], errors="coerce") if col in base.columns else pd.NA
    valid = base.dropna(subset=["icds", "icdp", "vmdl", "vmdp"]).copy()
    valid = valid[
        valid["icds"].between(0, 5)
        & valid["icdp"].between(0, 5)
        & (valid["vmdl"] >= 0)
        & (valid["vmdp"] >= 0)
    ].copy()
    if valid.empty:
        return []
    ipi_df = calcular_ipi_lote(valid[["icds", "icdp", "vmdl", "vmdp"]])
    valid = valid.reset_index(drop=True)
    ipi_df = ipi_df.reset_index(drop=True)

    recs: list[dict] = []
    for idx, s in valid.iterrows():
        calc = ipi_df.loc[idx]
        ip_tecnico = float(calc["ipi"])
        ext = _valor_valido(s.get("extensao_km")) or 0.0
        custo = _valor_valido(s.get("custo")) or 0.0
        custo_km = custo / ext if ext > 0 else 0.0
        eficiencia = (ip_tecnico / custo_km * 1000) if custo_km > 0 else 0.0
        recs.append(
            {
                "id": s.get("id"),
                "vmda": float(s.get("vmda") or (float(s.get("vmdl") or 0.0) + float(s.get("vmdp") or 0.0))),
                "vmdl": float(s.get("vmdl") or 0.0),
                "vmdp": float(s.get("vmdp") or 0.0),
                "vmdeq": float(calc["vmdeq"]),
                "icds": float(s.get("icds") or 0.0),
                "icdp": float(s.get("icdp") or 0.0),
                "dds": float(calc["dds"]),
                "ddp": float(calc["ddp"]),
                "dqo_base": float(calc["dqo_base"]),
                "gatilho": float(calc["gatilho"]),
                "dqo": float(calc["dqo"]),
                "ft": float(calc["ft"]),
                "ip_tecnico": ip_tecnico,
                "custo_km": custo_km,
                "eficiencia": eficiencia,
            }
        )

    efs = [r["eficiencia"] for r in recs]
    efic_min, efic_max = _min_max(efs)
    for r in recs:
        r["ip_economico"] = (
            (r["eficiencia"] - efic_min) / (efic_max - efic_min) * 10.0
            if efic_max > efic_min else 0.0
        )

    resultado: list[dict] = []
    for r in recs:
        ipi = round(r["ip_tecnico"], 4)
        resultado.append(
            {
                "id": r["id"],
                "vmda": round(r["vmda"], 2),
                "vmdl": round(r["vmdl"], 2),
                "vmdp": round(r["vmdp"], 2),
                "vmdeq": round(r["vmdeq"], 2),
                "icds": round(r["icds"], 4),
                "icdp": round(r["icdp"], 4),
                "dds": round(r["dds"], 4),
                "ddp": round(r["ddp"], 4),
                "dqo_base": round(r["dqo_base"], 4),
                "gatilho": round(r["gatilho"], 4),
                "dqo": round(r["dqo"], 4),
                "ft": round(r["ft"], 4),
                "ipi": ipi,
                "ip_tecnico": ipi,
                "custo_km": round(r["custo_km"], 2),
                "eficiencia": round(r["eficiencia"], 6),
                "ip_economico": round(r["ip_economico"], 4),
                # Mantido como alias interno para telas antigas, sem reescala 1..10.
                "priorizacao": ipi,
                "classificacao": _classificar_prioridade_ipi_dashboard(r["ip_tecnico"]),
                "ranking": 0,
            }
        )

    resultado.sort(key=lambda r: (-r["ip_tecnico"], -r["eficiencia"]))
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao
    return resultado


# ---------------------------------------------------------------------------
# DNIT — adaptação da priorização antiga da Matriz Cadastrada.
# ---------------------------------------------------------------------------
PESO_VMDA_DNIT = 0.40
PESO_IRI_DNIT = 0.35
PESO_DEF_DNIT = 0.25
DNIT_MODO_TECNICO = "tecnica"
DNIT_MODO_ECONOMICO = "economica"
DNIT_MODO_COMBINADO = "combinada"


def _normalizar_log(valor: float | None, minimo: float, maximo: float) -> float:
    """Normalização logarítmica usada na priorização antiga da Matriz.

    Só calcula quando valor, mínimo e máximo são positivos. Se não houver faixa
    válida, retorna 0 para não inventar prioridade.
    """
    if valor is None or valor <= 0 or minimo <= 0 or maximo <= 0 or minimo == maximo:
        return 0.0
    den = math.log(maximo) - math.log(minimo)
    if den == 0:
        return 0.0
    return min(1.0, max(0.0, (math.log(valor) - math.log(minimo)) / den))


def _classificar_prioridade_direta(valor: float) -> str:
    """Classe para índice direto 0..100, onde maior valor = maior prioridade."""
    if valor >= 70:
        return "Prioridade Crítica"
    if valor >= 50:
        return "Prioridade Alta"
    if valor >= 30:
        return "Prioridade Média"
    return "Prioridade Baixa"


def calcular_indice_priorizacao_dnit(
    segmentos: list[dict],
    modo: str = DNIT_MODO_COMBINADO,
) -> list[dict]:
    """Prioriza a Matriz Cadastrada por IPT, IPE ou índice combinado.

    Adaptação da lógica antiga:
    - IPT = 100 * (0,40*VMDA_n + 0,35*IRI_n + 0,25*DEF_n)
    - Eficiência = IPT / custo_por_km * 1000
    - IPE = 100 * eficiência normalizada por log
    - Combinada = 0,60*IPT + 0,40*IPE

    A escala é direta: maior valor = maior prioridade.
    """
    if not segmentos:
        return []

    iri_seg = [v for s in segmentos if (v := _valor_valido(s.get("iri"))) is not None]
    vmda_seg = [v for s in segmentos if (v := _valor_valido(s.get("vmda"))) is not None and v > 0]
    def_seg = [v for s in segmentos if (v := _valor_valido(s.get("deflexao", s.get("def")))) is not None and v > 0]
    iri_min, iri_max = _min_max(iri_seg)
    vmda_min, vmda_max = _min_max(vmda_seg)
    def_min, def_max = _min_max(def_seg)

    seg_records: list[dict] = []
    for s in segmentos:
        snv = str(s.get("snv"))
        iri = _valor_valido(s.get("iri"))
        igg = _valor_valido(s.get("igg"))
        vmda = _valor_valido(s.get("vmda"))
        deflexao = _valor_valido(s.get("deflexao", s.get("def")))
        iri_n = _normalizar_log(iri, iri_min, iri_max)
        vmda_n = _normalizar_log(vmda, vmda_min, vmda_max)
        def_n = _normalizar_log(deflexao, def_min, def_max)
        ip_tecnico = 100.0 * (
            PESO_VMDA_DNIT * vmda_n
            + PESO_IRI_DNIT * iri_n
            + PESO_DEF_DNIT * def_n
        )

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
                "vmda": vmda or 0.0,
                "deflexao": deflexao or 0.0,
                "iri_n": iri_n,
                "vmda_n": vmda_n,
                "def_n": def_n,
                "ip_tecnico": ip_tecnico,
                "custo_km": custo_km,
                "eficiencia": eficiencia,
            }
        )

    eficiencias = [r["eficiencia"] for r in seg_records if r["eficiencia"] > 0]
    efic_min, efic_max = _min_max(eficiencias)
    modo_normalizado = str(modo or DNIT_MODO_COMBINADO).strip().lower()
    if modo_normalizado not in {DNIT_MODO_TECNICO, DNIT_MODO_ECONOMICO, DNIT_MODO_COMBINADO}:
        modo_normalizado = DNIT_MODO_COMBINADO
    for r in seg_records:
        ipe = 100.0 * _normalizar_log(r["eficiencia"], efic_min, efic_max)
        r["ip_economico"] = ipe
        combinado = PESO_TECNICO * r["ip_tecnico"] + PESO_ECONOMICO * ipe
        if modo_normalizado == DNIT_MODO_TECNICO:
            score = r["ip_tecnico"]
        elif modo_normalizado == DNIT_MODO_ECONOMICO:
            score = ipe
        else:
            score = combinado
        r["ip_combinado"] = combinado
        r["priorizacao_segmento"] = score

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
        # Pior/mais prioritário = maior índice na escala direta.
        if r["priorizacao_segmento"] > snvs[snv]["pior"]["priorizacao_segmento"]:
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
                "vmda": round(pior["vmda"], 2),
                "deflexao": round(pior["deflexao"], 4),
                "iri_normalizado": round(pior["iri_n"], 4),
                "vmda_normalizado": round(pior["vmda_n"], 4),
                "def_normalizado": round(pior["def_n"], 4),
                "ip_tecnico": round(pior["ip_tecnico"], 4),
                "custo_km": round(custo_km_total, 2),
                "eficiencia": round(pior["eficiencia"], 6),
                "ip_economico": round(pior["ip_economico"], 4),
                "ip_combinado": round(pior["ip_combinado"], 4),
                "priorizacao": round(pior["priorizacao_segmento"], 4),
                "classificacao": _classificar_prioridade_direta(pior["priorizacao_segmento"]),
                "ranking": 0,
            }
        )

    resultado.sort(
        key=lambda r: (-r["priorizacao"], -r["ip_tecnico"], -r["eficiencia"]),
    )
    for posicao, item in enumerate(resultado, start=1):
        item["ranking"] = posicao

    return resultado
