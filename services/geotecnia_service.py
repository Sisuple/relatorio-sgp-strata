"""Serviço de Geotecnia (estrutura do pavimento por camada).

Lê a view `view_est_estrutura` (MySQL) — mesma fonte usada pelo relatório
Power BI de referência. A view expõe a maior parte dos campos dentro de uma
coluna JSON `dados` (mesmo padrão de `view_vmda_67`/`view_taxa_68`, ver
services/traffic_service.py), da qual usamos `sentido_trafego`, `faixa` e as
4 espessuras medidas (`espessura_base`, `espessura_reforco`,
`espessura_subbase`, `espessura_revestimento`).

`km_final` NÃO vem pronto da view: o modelo original (Power Query) descarta o
`km_final` bruto e recalcula como o `km_inicial` do próximo levantamento
dentro do mesmo grupo rodovia+sentido+faixa (ordenado por km_inicial) — o
último trecho de cada grupo fica sem km_final (segmento "Xkm - km"). Aqui
replicamos isso com groupby+shift.

O Subleito não é medido: é um preenchimento visual igual ao usado no Power
BI original, `MAX(soma_camadas) - soma_camadas(linha)`, calculado aqui só
dentro da rodovia selecionada (não globalmente entre todas as rodovias).
Cacheado via services.cache (Redis com fallback local em memória), mesmo
padrão de services/traffic_service.py.
"""
from __future__ import annotations

import json

import pandas as pd

from services.cache import cached
from src.database import MySQLConnection

# Ordem estrutural das camadas, de baixo pra cima (bottom-up no gráfico).
LAYER_ORDER = ["subleito", "reforco", "subbase", "base", "revestimento"]

_DADOS_KEYS = [
    "faixa", "sentido_trafego",
    "espessura_base", "espessura_reforco", "espessura_subbase", "espessura_revestimento",
    # Material de cada camada (texto, ex.: "GRANULAR"/"CBUQ") — só pro tooltip
    # do gráfico, não entra na conta de espessura.
    "base", "subbase", "revestimento",
]
_ESPESSURA_COLUMNS = [
    "dados.espessura_base", "dados.espessura_reforco",
    "dados.espessura_subbase", "dados.espessura_revestimento",
]
_GROUP_KEYS = ["rodovia", "dados.sentido_trafego", "dados.faixa"]


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
    """Expande a coluna JSON `dados` em colunas `dados.<campo>` (só as chaves
    usadas por este gráfico — ver _DADOS_KEYS)."""
    parsed = df["dados"].apply(_parse_json)
    expandido = pd.json_normalize(parsed.apply(lambda d: {k: d.get(k) for k in _DADOS_KEYS})).add_prefix("dados.")
    return pd.concat([df.drop(columns=["dados"]), expandido], axis=1)


@cached(ttl=600)
def get_pavement_structure_roads() -> list[str]:
    """Rodovias com levantamento estrutural (view_est_estrutura) disponível."""
    engine = MySQLConnection().get_engine()
    df = pd.read_sql("SELECT DISTINCT rodovia FROM view_est_estrutura", engine)
    if df.empty:
        return []
    return sorted(df["rodovia"].dropna().astype(str).unique(), key=lambda c: (len(c), c))


@cached(ttl=600)
def get_pavement_structure(rodovia: str) -> pd.DataFrame:
    """Espessura de cada camada por trecho/sentido, já com o Subleito calculado.

    Uma linha por trecho (km_inicial/km_final) × sentido_trafego, com colunas
    `subleito`, `reforco`, `subbase`, `base`, `revestimento` (nessa ordem
    estrutural) prontas pra empilhar num gráfico, mais `segmento` (rótulo
    "Xkm - Ykm") e `sentido_trafego`.
    """
    engine = MySQLConnection().get_engine()
    df = pd.read_sql(
        "SELECT rodovia, km_inicial, dados FROM view_est_estrutura WHERE rodovia = %(rodovia)s",
        engine,
        params={"rodovia": rodovia},
    )
    if df.empty:
        return df

    df = _expand_dados(df)
    df["km_inicial"] = pd.to_numeric(df["km_inicial"], errors="coerce")

    for coluna in _ESPESSURA_COLUMNS:
        df[coluna] = pd.to_numeric(
            df[coluna].astype(str).str.replace(",", ".", regex=False), errors="coerce"
        ).fillna(0.0)

    # km_final não vem pronto: é o km_inicial do próximo trecho dentro do
    # mesmo grupo rodovia+sentido+faixa (ordenado por km_inicial) — o último
    # trecho de cada grupo fica sem km_final (replica o Power Query original).
    df = df.sort_values(_GROUP_KEYS + ["km_inicial"]).reset_index(drop=True)
    df["km_final"] = df.groupby(_GROUP_KEYS, dropna=False)["km_inicial"].shift(-1)

    df["reforco"] = df["dados.espessura_reforco"]
    df["subbase"] = df["dados.espessura_subbase"]
    df["base"] = df["dados.espessura_base"]
    df["revestimento"] = df["dados.espessura_revestimento"]
    df["soma_camadas"] = df["reforco"] + df["subbase"] + df["base"] + df["revestimento"]

    # Preenchimento visual (não é uma espessura medida): iguala a altura total
    # de todas as barras à maior soma_camadas encontrada nesta rodovia.
    maior_soma = float(df["soma_camadas"].max())
    df["subleito"] = (maior_soma - df["soma_camadas"]).clip(lower=0.0)

    def _fmt_km(v: float) -> str:
        # O levantamento pode vir bem fino (amostras a cada ~20m em algumas
        # rodovias) — arredondar pro km inteiro faria vários trechos reais
        # diferentes mostrarem o mesmo rótulo (ex.: "0km - 0km" repetido).
        # Mantém casas decimais só quando precisa (2 casas, sem zero à toa).
        if pd.isna(v):
            return ""
        v = round(float(v), 2)
        if v == int(v):
            return str(int(v))
        return f"{v:.2f}".rstrip("0").rstrip(".")

    df["segmento"] = df["km_inicial"].apply(_fmt_km) + "km - " + df["km_final"].apply(_fmt_km) + "km"
    df["sentido_trafego"] = df["dados.sentido_trafego"]
    df["extensao"] = df["km_final"] - df["km_inicial"]

    # Material de cada camada (texto), pro tooltip — "" quando a view não trouxer.
    df["material_base"] = df["dados.base"].fillna("").astype(str)
    df["material_subbase"] = df["dados.subbase"].fillna("").astype(str)
    df["material_revestimento"] = df["dados.revestimento"].fillna("").astype(str)

    cols = [
        "rodovia", "km_inicial", "km_final", "extensao", "segmento", "sentido_trafego", "soma_camadas",
        "material_base", "material_subbase", "material_revestimento", *LAYER_ORDER,
    ]
    return df[cols]
