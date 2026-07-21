"""Cálculo do Índice de Prioridade de Intervenção (IPI).

Este módulo é propositalmente isolado: não consulta banco, não conhece Streamlit
e não altera estado global. A ideia é permitir testar a metodologia de forma
direta antes de usar o resultado nas telas do dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class IPIParams:
    """Parâmetros configuráveis da metodologia IPI.

    k: equivalência de 1 veículo pesado em veículos leves no VMDeq.
    a/b/c: expoentes da combinação multiplicativa do dano superficial e profundo.
    gatilho_icds/gatilho_icdp: piso assimétrico do DQO; ICDP recebe peso maior.
    vmd50: volume em que a função de tráfego atinge meia exposição.
    alpha: sensibilidade do índice ao DQO.
    beta: sensibilidade do índice ao fator de tráfego.
    """

    k: float = 4.0
    a: float = 0.45
    b: float = 0.55
    c: float = 0.20
    gatilho_icds: float = 0.80
    gatilho_icdp: float = 0.88
    vmd50: float = 5000.0
    alpha: float = 1.20
    beta: float = 1.0


def _as_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser numérico.") from exc
    if pd.isna(number):
        raise ValueError(f"{name} não pode ser nulo.")
    return number


def _validate_inputs(icds: float, icdp: float, vmdl: float, vmdp: float, vmdeq_ref: float) -> None:
    if not 0 <= icds <= 5:
        raise ValueError("icds deve estar entre 0 e 5.")
    if not 0 <= icdp <= 5:
        raise ValueError("icdp deve estar entre 0 e 5.")
    if vmdl < 0:
        raise ValueError("vmdl deve ser maior ou igual a zero.")
    if vmdp < 0:
        raise ValueError("vmdp deve ser maior ou igual a zero.")
    if vmdeq_ref <= 0:
        raise ValueError("vmdeq_ref deve ser maior que zero.")


def calcular_ipi(
    icds: float,
    icdp: float,
    vmdl: float,
    vmdp: float,
    vmdeq_ref: float,
    k: float = 4.0,
    a: float = 0.45,
    b: float = 0.55,
    c: float = 0.20,
    gatilho_icds: float = 0.80,
    gatilho_icdp: float = 0.88,
    vmd50: float = 5000.0,
    alpha: float = 1.20,
    beta: float = 1.0,
) -> dict[str, float]:
    """Calcula o IPI de um trecho e devolve também a memória de cálculo.

    DDS e DDP transformam ICDS/ICDP em dano: quanto menor a condição, maior o
    dano. Como a fórmula usa denominador 4, valores abaixo de 1 saturam o dano
    em 1 para evitar dano acima de 100%. O DQO combina dano superficial e
    deformação permanente pela fórmula multiplicativa, depois aplica um gatilho
    assimétrico para não subestimar casos críticos. O VMDeq converte veículos
    pesados em equivalentes leves e o FT limita a influência do tráfego a 1
    quando o trecho já está acima da referência da malha.
    """
    icds = _as_float(icds, "icds")
    icdp = _as_float(icdp, "icdp")
    vmdl = _as_float(vmdl, "vmdl")
    vmdp = _as_float(vmdp, "vmdp")
    vmdeq_ref = _as_float(vmdeq_ref, "vmdeq_ref")
    params = IPIParams(k=k, a=a, b=b, c=c, gatilho_icds=gatilho_icds, gatilho_icdp=gatilho_icdp, vmd50=vmd50, alpha=alpha, beta=beta)
    _validate_inputs(icds, icdp, vmdl, vmdp, vmdeq_ref)

    dds = min(1.0, max(0.0, (5.0 - icds) / 4.0))
    ddp = min(1.0, max(0.0, (5.0 - icdp) / 4.0))
    dqo_base = 1.0 - ((1.0 - dds) ** params.a * (1.0 - ddp) ** params.b * (1.0 - dds * ddp) ** params.c)
    gatilho = max(params.gatilho_icds * dds, params.gatilho_icdp * ddp)
    dqo = max(dqo_base, gatilho)
    vmdeq = vmdl + params.k * vmdp
    if vmdeq <= 0:
        ft = 0.0
    else:
        exposure = vmdeq / (vmdeq + params.vmd50)
        reference = vmdeq_ref / (vmdeq_ref + params.vmd50)
        ft = min(1.0, exposure / reference)
    ipi = 100.0 * (dqo ** params.alpha) * (ft ** params.beta)

    return {
        "dds": dds,
        "ddp": ddp,
        "dqo_base": dqo_base,
        "gatilho": gatilho,
        "dqo": dqo,
        "vmdeq": vmdeq,
        "ft": ft,
        "ipi": ipi,
    }


def classificar_prioridade_ipi(ipi: float) -> str:
    """Classifica a prioridade pela escala direta do IPI: maior = mais crítico."""
    value = float(ipi)
    if value >= 70:
        return "Crítica"
    if value >= 50:
        return "Alta"
    if value >= 30:
        return "Média"
    if value >= 15:
        return "Baixa"
    return "Muito Baixa"


def calcular_ipi_lote(df: pd.DataFrame, vmdeq_ref: float | None = None, **params: Any) -> pd.DataFrame:
    """Calcula IPI para um DataFrame de trechos.

    Espera as colunas ``icds``, ``icdp``, ``vmdl`` e ``vmdp``. Se ``vmdeq_ref``
    não for informado, usa o percentil 95 do VMDeq do próprio lote.
    """
    required = {"icds", "icdp", "vmdl", "vmdp"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"DataFrame sem colunas obrigatórias: {', '.join(sorted(missing))}.")
    if df.empty:
        return df.copy()

    out = df.copy()
    for col in required:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    k = float(params.get("k", 4.0))
    out["vmdeq"] = out["vmdl"] + k * out["vmdp"]
    ref = float(vmdeq_ref) if vmdeq_ref is not None else float(out["vmdeq"].quantile(0.95))
    if ref <= 0:
        raise ValueError("vmdeq_ref calculado deve ser maior que zero.")

    records = [
        calcular_ipi(
            row.icds,
            row.icdp,
            row.vmdl,
            row.vmdp,
            ref,
            **params,
        )
        for row in out.itertuples(index=False)
    ]
    calc = pd.DataFrame(records, index=out.index)
    for col in ("dds", "ddp", "dqo_base", "gatilho", "dqo", "vmdeq", "ft", "ipi"):
        out[col] = calc[col]
    out["classe_prioridade"] = out["ipi"].map(classificar_prioridade_ipi)
    return out
