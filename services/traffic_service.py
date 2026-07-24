"""Serviço de Tráfego (VMDA e projeção de crescimento).

Lê as views `view_vmda_67` (volume por levantamento) e `view_taxa_68` (taxa de
crescimento anual por trecho/tipo de veículo) — as MESMAS views já usadas pelo
cálculo do IPI (ver services/ipi.py). Cacheado via services.cache (Redis com
fallback local em memória).
"""
from __future__ import annotations

import json

import pandas as pd

from services.cache import cached
from src.database import MySQLConnection

# Colunas de veículo comercial (2 a 9 eixos) já expandidas do JSON `dados`.
VEHICLE_COLUMNS = [f"dados.{n}eixos" for n in range(2, 10)]
# Ordem canônica dos tipos de veículo (comerciais por nº de eixos + passeio).
VEHICLE_ORDER = [f"{n}eixos" for n in range(2, 10)] + ["Passeio"]

_DROP_COLUMNS = [
    "id", "levantamento_importacao_id", "uf_id", "data_levantamento",
    "geojson", "geometria", "created_at", "updated_at",
]


def _parse_json(valor):
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except Exception:
            return {}
    if isinstance(valor, dict):
        return valor
    return {}


def _expand_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Expande a coluna JSON `dados` em colunas `dados.<campo>`."""
    expandido = pd.json_normalize(df["dados"].apply(_parse_json)).add_prefix("dados.")
    return pd.concat([df.drop(columns=["dados"]), expandido], axis=1)


@cached(ttl=600)
def get_vmda_wide() -> pd.DataFrame:
    """VMDA por levantamento (1 linha por trecho/ano-base), colunas de eixo já numéricas."""
    engine = MySQLConnection().get_engine()
    df = pd.read_sql("SELECT * FROM view_vmda_67", engine)
    df = df.drop(columns=_DROP_COLUMNS, errors="ignore")
    df = _expand_dados(df)

    colunas_numericas = VEHICLE_COLUMNS + ["dados.passeio", "dados.vmda_total"]
    for coluna in colunas_numericas:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce").round(0).astype("Int64")

    return df.drop_duplicates()


@cached(ttl=600)
def get_vmda_long() -> pd.DataFrame:
    """VMDA em formato longo: 1 linha por trecho × tipo de veículo."""
    df = get_vmda_wide().copy()
    if df.empty:
        return df

    colunas_veiculos = ["dados.passeio"] + VEHICLE_COLUMNS
    df_long = df.melt(
        id_vars=[
            "rodovia", "trecho", "km_inicial", "km_final", "extensao",
            "dados.ano_base", "dados.vmda_total", "dados.segmento_trafego",
        ],
        value_vars=colunas_veiculos,
        var_name="tipo veiculo",
        value_name="volume",
    )
    df_long["tipo veiculo"] = (
        df_long["tipo veiculo"]
        .str.replace("dados.", "", regex=False)
        .str.replace("passeio", "Passeio", regex=False)
    )
    df_long["volume"] = pd.to_numeric(df_long["volume"], errors="coerce").fillna(0)
    return df_long


@cached(ttl=600)
def get_taxa_long() -> pd.DataFrame:
    """Taxa de crescimento anual por trecho × tipo de veículo, em formato longo."""
    engine = MySQLConnection().get_engine()
    df = pd.read_sql("SELECT * FROM view_taxa_68", engine)
    df = df.drop(columns=_DROP_COLUMNS, errors="ignore")
    df = _expand_dados(df)

    colunas_taxa = VEHICLE_COLUMNS + ["dados.passeio"]
    for coluna in colunas_taxa:
        if coluna not in df.columns:
            continue
        df[coluna] = df[coluna].astype(str).str.replace(",", ".", regex=False)
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df_long = df.melt(
        id_vars=[
            "rodovia", "trecho", "km_inicial", "km_final", "extensao",
            "dados.ano_taxa", "dados.segmento_trafego",
        ],
        value_vars=colunas_taxa,
        var_name="tipo veiculo",
        value_name="taxa",
    )
    df_long["tipo veiculo"] = (
        df_long["tipo veiculo"]
        .str.replace("dados.", "", regex=False)
        .str.replace("passeio", "Passeio", regex=False)
    )
    df_long["dados.ano_taxa"] = pd.to_numeric(df_long["dados.ano_taxa"], errors="coerce").astype("Int64")
    df_long["trecho_km"] = (
        df_long["dados.segmento_trafego"].astype(str)
        + " - " + df_long["km_inicial"].astype(str) + "km - "
        + df_long["km_final"].astype(str) + "km"
    )
    return df_long
