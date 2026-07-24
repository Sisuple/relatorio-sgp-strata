"""Serviço de Pavimentação (composição IRI / ATR / IGG por classe).

Cada índice vem de uma view MySQL própria — mesma fonte do relatório Power BI
de referência:

- `view_iri_69`: `rodovia` solta + `dados` JSON (`dados.extensao`,
  `dados.classe_iri` — já vem classificado, não precisa recalcular).
- `view_fwd_71` (índice ATR): `rodovia`, `atr`, `km_inicial`, `km_final`
  soltos (sem JSON). Classe não vem pronta — recalculada aqui via os mesmos
  limiares do Power BI (`atr <= 10` Bom, `<= 15` Regular, `> 15` Ruim).
- `view_igg_79`: `rodovia`/`km_inicial` soltos + `dados` JSON
  (`dados.igg`, `dados.sentido_trafego`). Nem extensão nem classe vêm
  prontas: extensão é o `km_inicial` do próximo levantamento dentro do mesmo
  grupo rodovia+sentido (igual ao km_final da Geotecnia, mas aqui o Power BI
  usa 0 — não branco — quando não há próximo, réplica exata da fórmula
  original); classe usa os limiares `igg <= 40` Bom, `<= 80` Regular, `> 80`
  Ruim.

Composição = % da extensão total (km) da rodovia em cada classe — não é
contagem de linhas, é ponderado por km de cada trecho. Cacheado via
services.cache, mesmo padrão de services/traffic_service.py.
"""
from __future__ import annotations

import json

import pandas as pd

from services.cache import cached
from src.database import MySQLConnection

CLASS_ORDER = ["Bom", "Regular", "Ruim"]


def _parse_json(valor):
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except Exception:
            return {}
    if isinstance(valor, dict):
        return valor
    return {}


def _filter_by_km_range(
    df: pd.DataFrame, km_range: tuple[float, float] | None,
    km_inicial_col: str = "km_inicial", km_final_col: str = "km_final",
) -> pd.DataFrame:
    """Recorta `df` pro intervalo [km_range[0], km_range[1]] (mantém qualquer
    trecho que INTERSECTE a janela — mesma regra do slider de zoom já usado
    na Geotecnia/Tráfego). `km_final_col` pode ter NaN (último trecho de um
    grupo, sem próximo levantamento) — nesse caso trata como largura zero
    (usa o próprio km_inicial)."""
    if df.empty or km_range is None:
        return df
    km_final_efetivo = df[km_final_col].fillna(df[km_inicial_col])
    return df[(km_final_efetivo >= km_range[0]) & (df[km_inicial_col] <= km_range[1])]


def _composition_from_extensao(df: pd.DataFrame, classe_col: str, extensao_col: str) -> pd.DataFrame:
    """Agrega extensão por classe e converte em % do total — formato comum
    às 3 composições (classe, extensao, percentual), na ordem Bom/Regular/Ruim."""
    if df.empty:
        return pd.DataFrame(columns=["classe", "extensao", "percentual"])
    agrupado = df.groupby(classe_col, as_index=False)[extensao_col].sum()
    agrupado = agrupado.rename(columns={classe_col: "classe", extensao_col: "extensao"})
    total = float(agrupado["extensao"].sum()) or 1.0
    agrupado["percentual"] = agrupado["extensao"] / total * 100
    agrupado["classe"] = pd.Categorical(agrupado["classe"], categories=CLASS_ORDER, ordered=True)
    return agrupado.sort_values("classe").dropna(subset=["classe"])


@cached(ttl=600)
def get_pavimentacao_roads() -> list[str]:
    """Rodovias disponíveis (a partir de view_iri_69, o índice principal da tela)."""
    engine = MySQLConnection().get_engine()
    df = pd.read_sql("SELECT DISTINCT rodovia FROM view_iri_69", engine)
    if df.empty:
        return []
    return sorted(df["rodovia"].dropna().astype(str).unique(), key=lambda c: (len(c), c))


@cached(ttl=600)
def get_iri_composition(rodovia: str, km_range: tuple[float, float] | None = None) -> pd.DataFrame:
    """Composição do IRI (% da extensão por classe Bom/Regular/Ruim), com
    filtro opcional de trecho (km_range) — o mesmo slider que corta os
    gráficos de linha também corta as composições.

    `extensao` já vem pronta como coluna solta (não precisa recalcular, ao
    contrário do ATR/IGG). Classe não vem pronta — calculada aqui a partir de
    `dados.iri_medio`: <=2,7 Bom, <=3,5 Regular, >3,5 Ruim.
    """
    engine = MySQLConnection().get_engine()
    df = pd.read_sql(
        "SELECT km_inicial, km_final, extensao, dados FROM view_iri_69 WHERE rodovia = %(rodovia)s",
        engine, params={"rodovia": rodovia},
    )
    if df.empty:
        return pd.DataFrame(columns=["classe", "extensao", "percentual"])

    df["km_inicial"] = pd.to_numeric(df["km_inicial"], errors="coerce")
    df["km_final"] = pd.to_numeric(df["km_final"], errors="coerce")
    # extensao vem em METROS nessa view (ex.: 20.0 pra um trecho de 13.10 a
    # 13.12 km) — as outras duas composições já calculam em km, converte aqui
    # pra ficar na mesma unidade.
    df["extensao"] = pd.to_numeric(df["extensao"], errors="coerce").fillna(0.0) / 1000.0
    parsed = df["dados"].apply(_parse_json)
    iri_medio = pd.to_numeric(parsed.apply(lambda d: d.get("iri_medio")), errors="coerce")

    def _classe(iri):
        if pd.isna(iri):
            return None
        if iri <= 2.7:
            return "Bom"
        if iri <= 3.5:
            return "Regular"
        return "Ruim"

    df["classe_iri"] = iri_medio.apply(_classe)
    df = _filter_by_km_range(df, km_range)
    return _composition_from_extensao(df, "classe_iri", "extensao")


@cached(ttl=600)
def get_iri_series(rodovia: str) -> pd.DataFrame:
    """Série linha-a-linha do IRI (não agregada) — pros gráficos IRI ×
    extensão (Crescente/Decrescente), diferente de get_iri_composition (que
    agrega em % por classe). Uma linha por levantamento, com km_inicial,
    km_final, sentido, faixa e o iri_medio bruto."""
    engine = MySQLConnection().get_engine()
    df = pd.read_sql(
        "SELECT km_inicial, km_final, dados FROM view_iri_69 WHERE rodovia = %(rodovia)s",
        engine, params={"rodovia": rodovia},
    )
    if df.empty:
        return pd.DataFrame(columns=["km_inicial", "km_final", "sentido_trafego", "faixa", "iri_medio"])

    parsed = df["dados"].apply(_parse_json)
    df["sentido_trafego"] = parsed.apply(lambda d: d.get("sentido_trafego"))
    df["faixa"] = parsed.apply(lambda d: d.get("faixa"))
    df["iri_medio"] = pd.to_numeric(parsed.apply(lambda d: d.get("iri_medio")), errors="coerce")
    df["km_inicial"] = pd.to_numeric(df["km_inicial"], errors="coerce")
    df["km_final"] = pd.to_numeric(df["km_final"], errors="coerce")
    return df[["km_inicial", "km_final", "sentido_trafego", "faixa", "iri_medio"]].dropna(subset=["km_inicial"])


def _parse_signed_decimal(serie: pd.Series) -> pd.Series:
    """`fl_tre`/`fl_tri` vêm como texto — o Power Query original tira o sinal
    de '-' (artefato de digitação, não é valor negativo de verdade) antes de
    converter pra número. Aqui: remove '-' e faz parse do que sobrar."""
    limpo = serie.astype(str).str.replace("-", "", regex=False)
    return pd.to_numeric(limpo, errors="coerce")


def _fwd_raw(rodovia: str) -> pd.DataFrame:
    """Carga bruta do levantamento FWD (view_fwd_71) — fonte tanto do ATR
    quanto do d0. Calcula `atr` (média de `dados.fl_tre`/`dados.fl_tri`),
    `d0` (`dados.d0`) e `km_final` (km_inicial do próximo levantamento dentro
    do mesmo grupo rodovia+sentido+faixa — igual à Geotecnia; fica NaN quando
    não há próximo). Compartilhado entre get_atr_composition/get_atr_series
    e get_d0_series."""
    engine = MySQLConnection().get_engine()
    df = pd.read_sql(
        "SELECT rodovia, km_inicial, dados FROM view_fwd_71 WHERE rodovia = %(rodovia)s",
        engine, params={"rodovia": rodovia},
    )
    if df.empty:
        return df

    parsed = df["dados"].apply(_parse_json)
    df["fl_tre"] = _parse_signed_decimal(parsed.apply(lambda d: d.get("fl_tre")))
    df["fl_tri"] = _parse_signed_decimal(parsed.apply(lambda d: d.get("fl_tri")))
    df["atr"] = (df["fl_tre"] + df["fl_tri"]) / 2
    df["d0"] = pd.to_numeric(parsed.apply(lambda d: d.get("d0")), errors="coerce")
    df["sentido_trafego"] = parsed.apply(lambda d: d.get("sentido_trafego"))
    df["faixa"] = parsed.apply(lambda d: d.get("faixa"))
    df["km_inicial"] = pd.to_numeric(df["km_inicial"], errors="coerce")

    df = df.sort_values(["sentido_trafego", "faixa", "km_inicial"]).reset_index(drop=True)
    df["km_final"] = df.groupby(["sentido_trafego", "faixa"], dropna=False)["km_inicial"].shift(-1)
    df["extensao"] = (df["km_final"] - df["km_inicial"]).fillna(0.0).clip(lower=0.0)
    return df


@cached(ttl=600)
def get_atr_composition(rodovia: str, km_range: tuple[float, float] | None = None) -> pd.DataFrame:
    """Composição do ATR (% da extensão por classe Bom/Regular/Ruim), com
    filtro opcional de trecho (km_range).

    Classe (a mesma usada na rosca): atr<=10 Bom, 10<atr<=15 Regular,
    atr>15 Ruim. Atenção: essa classe é DIFERENTE das faixas de fundo do
    gráfico de linha (0-7/7-10/10-15) — são dois artefatos distintos do
    Power BI original (a medida "Classe ATR" e as bandas fixas do Deneb),
    replicados aqui exatamente como vieram.
    """
    df = _fwd_raw(rodovia)
    if df.empty:
        return pd.DataFrame(columns=["classe", "extensao", "percentual"])

    def _classe(atr):
        if pd.isna(atr):
            return None
        if atr <= 10:
            return "Bom"
        if atr <= 15:
            return "Regular"
        return "Ruim"

    df["classe_atr"] = df["atr"].apply(_classe)
    df = _filter_by_km_range(df, km_range)
    return _composition_from_extensao(df, "classe_atr", "extensao")


@cached(ttl=600)
def get_atr_series(rodovia: str) -> pd.DataFrame:
    """Série linha-a-linha do ATR (não agregada) — pro gráfico ATR ×
    extensão (Crescente/Decrescente)."""
    df = _fwd_raw(rodovia)
    if df.empty:
        return pd.DataFrame(columns=["km_inicial", "km_final", "sentido_trafego", "faixa", "atr"])
    return df[["km_inicial", "km_final", "sentido_trafego", "faixa", "atr"]]


@cached(ttl=600)
def get_d0_series(rodovia: str) -> pd.DataFrame:
    """Série linha-a-linha do d0 (deflexão) — mesma view do ATR (view_fwd_71),
    campo `dados.d0`."""
    df = _fwd_raw(rodovia)
    if df.empty:
        return pd.DataFrame(columns=["km_inicial", "km_final", "sentido_trafego", "faixa", "d0"])
    return df[["km_inicial", "km_final", "sentido_trafego", "faixa", "d0"]]


@cached(ttl=600)
def get_igg_composition(rodovia: str, km_range: tuple[float, float] | None = None) -> pd.DataFrame:
    """Composição do IGG (% da extensão por classe Bom/Regular/Ruim), com
    filtro opcional de trecho (km_range).

    Nem extensão nem classe vêm prontas: extensão = km_inicial do próximo
    levantamento dentro do mesmo grupo rodovia+sentido (0 quando não há
    próximo — igual à fórmula original, que usa 0 em vez de branco); classe
    usa igg<=40 Bom, <=80 Regular, >80 Ruim.
    """
    engine = MySQLConnection().get_engine()
    df = pd.read_sql(
        "SELECT km_inicial, dados FROM view_igg_79 WHERE rodovia = %(rodovia)s",
        engine, params={"rodovia": rodovia},
    )
    if df.empty:
        return pd.DataFrame(columns=["classe", "extensao", "percentual"])

    parsed = df["dados"].apply(_parse_json)
    df["igg"] = pd.to_numeric(parsed.apply(lambda d: d.get("igg")), errors="coerce")
    df["sentido_trafego"] = parsed.apply(lambda d: d.get("sentido_trafego"))
    df["km_inicial"] = pd.to_numeric(df["km_inicial"], errors="coerce")

    df = df.sort_values(["sentido_trafego", "km_inicial"]).reset_index(drop=True)
    df["km_final"] = df.groupby(["sentido_trafego"], dropna=False)["km_inicial"].shift(-1)
    df["extensao"] = (df["km_final"] - df["km_inicial"]).fillna(0.0).clip(lower=0.0)

    def _classe(igg):
        if pd.isna(igg):
            return None
        if igg <= 40:
            return "Bom"
        if igg <= 80:
            return "Regular"
        return "Ruim"

    df["classe_igg"] = df["igg"].apply(_classe)
    df = _filter_by_km_range(df, km_range)
    return _composition_from_extensao(df, "classe_igg", "extensao")
