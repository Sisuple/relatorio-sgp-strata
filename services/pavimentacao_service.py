"""Serviço de Pavimentação (composição IRI / ATR / IGG por classe).

Cada índice vem de uma view MySQL própria, com o valor dentro do JSON `dados`:

- `view_iri_69` — `dados.iri_medio`; limiares `<= 2,7` Bom, `<= 3,5` Regular,
  acima Ruim. É a única das três com `km_final` preenchido, então o trecho de
  cada leitura é explícito.
- `view_fwd_71` — ATR = média de `dados.fl_tre`/`dados.fl_tri`; limiares
  `<= 10` Bom, `<= 15` Regular, acima Ruim. Também é a fonte do d0.
- `view_igg_79` — `dados.igg`; limiares `<= 40` Bom, `<= 80` Regular, acima Ruim.

FWD e IGG são leituras PONTUAIS (sem `km_final`): o trecho de cada leitura vai
até a leitura seguinte do mesmo sentido/faixa/ciclo, limitado a
`MAX_READING_GAP_KM` para uma lacuna entre trechos da rodovia não virar
pavimento medido.

Composição = km de pista em cada classe, não contagem de leituras. Como as views
guardam VÁRIOS levantamentos do mesmo trecho (um por ano, mais os ciclos de
"Implantação" de trechos ainda não construídos), somar linha a linha conta o
mesmo km mais de uma vez — por isso `get_condition_compositions` trabalha com
união e subtração de intervalos, e não com `groupby().sum()`. Cacheado via
services.cache, mesmo padrão de services/traffic_service.py.
"""
from __future__ import annotations

import json
import unicodedata

import pandas as pd

from services.cache import cached
from src.database import MySQLConnection

CLASS_ORDER = ["Bom", "Regular", "Ruim"]
# Fatia dos km que existem na base comum mas não têm leitura DESTE índice. Só
# aparece nas composições normalizadas (ver `get_condition_compositions`), que
# obrigam os 3 donuts a fechar no mesmo total de km.
NO_DATA_CLASS = "Sem dado"
COMPOSITION_CLASS_ORDER = CLASS_ORDER + [NO_DATA_CLASS]

# Lacuna máxima entre duas leituras consecutivas que ainda conta como pavimento
# medido (km). FWD e IGG são leituras pontuais sem `km_final`: a extensão sai da
# distância até a leitura seguinte, e sem teto o vão de 44,5 km entre os trechos
# IV e V da BR-055 entrava como um segmento só, inflando o total em 33%.
MAX_READING_GAP_KM = 0.05

# Ciclos de levantamento cujo nome indica trecho a ser construído (duplicação,
# faixa adicional) em vez de medição de campo. `levantamento_ciclos` guarda
# "1° ANO_2025_Ciclo 1" e "2° ANO_2026_Ciclo 1" para os reais e
# "Implantação 2027/2028/…" para os projetados — e todas as importações foram
# feitas em 2026, então o ano do dado vem do ciclo, não de uma medição.
_PROJECTION_CYCLE_TOKEN = "implanta"


def _parse_json(valor):
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except Exception:
            return {}
    if isinstance(valor, dict):
        return valor
    return {}


# ---------------------------------------------------------------------------
# Intervalos de km — a composição é medida em km de pista, não em nº de leituras,
# e as views trazem leituras que se sobrepõem (dois levantamentos do mesmo trecho).
# Somar linha por linha conta o mesmo km duas vezes; por isso tudo aqui trabalha
# com união/subtração de intervalos.
# ---------------------------------------------------------------------------


def _merge_intervals(intervalos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """União de intervalos, já ordenada e sem sobreposição."""
    limpos = sorted((lo, hi) for lo, hi in intervalos if hi > lo)
    if not limpos:
        return []
    saida = [list(limpos[0])]
    for lo, hi in limpos[1:]:
        if lo <= saida[-1][1]:
            saida[-1][1] = max(saida[-1][1], hi)
        else:
            saida.append([lo, hi])
    return [(lo, hi) for lo, hi in saida]


def _subtract_intervals(
    base: list[tuple[float, float]], remover: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """`base` menos `remover` (os dois já unidos)."""
    if not remover:
        return list(base)
    saida: list[tuple[float, float]] = []
    for lo, hi in base:
        restos = [(lo, hi)]
        for rlo, rhi in remover:
            if rhi <= lo or rlo >= hi:
                continue
            novos = []
            for plo, phi in restos:
                if rhi <= plo or rlo >= phi:
                    novos.append((plo, phi))
                    continue
                if plo < rlo:
                    novos.append((plo, rlo))
                if rhi < phi:
                    novos.append((rhi, phi))
            restos = novos
        saida.extend(restos)
    return _merge_intervals(saida)


def _total_km(intervalos: list[tuple[float, float]]) -> float:
    return sum(hi - lo for lo, hi in intervalos)


@cached(ttl=600)
def _survey_cycles() -> dict[int, dict]:
    """Ciclos de levantamento: `{ciclo_id: {nome, ano, projecao}}`.

    `projecao=True` para os ciclos de "Implantação" — trecho que ainda vai ser
    construído, não medição de campo. O ano sai de `data_inicial` do ciclo, que é
    o ano a que o dado se refere; `levantamento_importacoes.ano` é sempre 2026
    (quando tudo foi importado) e não serve para distinguir.
    """
    engine = MySQLConnection().get_engine()
    df = pd.read_sql("SELECT id, nome, data_inicial FROM levantamento_ciclos", engine)
    if df.empty:
        return {}
    ciclos: dict[int, dict] = {}
    for _, row in df.iterrows():
        nome = str(row.get("nome") or "")
        ano = pd.to_datetime(row.get("data_inicial"), errors="coerce")
        ciclos[int(row["id"])] = {
            "nome": nome,
            "ano": int(ano.year) if pd.notna(ano) else None,
            "projecao": _PROJECTION_CYCLE_TOKEN in _strip_accents(nome).lower(),
        }
    return ciclos


def _strip_accents(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()


@cached(ttl=600)
def get_survey_years(rodovia: str) -> list[int]:
    """Anos de levantamento REAL disponíveis para a rodovia, do mais novo ao mais antigo.

    Só ciclos de medição — os de "Implantação" (2027–2032) ficam fora: são trechos
    projetados, e misturá-los com medição duplicava km e falseava a composição.
    """
    ciclos = _survey_cycles()
    reais = {cid for cid, c in ciclos.items() if not c["projecao"]}
    if not reais:
        return []
    engine = MySQLConnection().get_engine()
    marcadores = ", ".join(f"%(c{i})s" for i in range(len(reais)))
    params = {f"c{i}": cid for i, cid in enumerate(sorted(reais))}
    params["rodovia"] = rodovia
    anos: set[int] = set()
    for view in ("view_iri_69", "view_fwd_71", "view_igg_79"):
        df = pd.read_sql(
            f"""SELECT DISTINCT i.levantamento_ciclo_id AS ciclo
                FROM {view} v
                JOIN levantamento_importacoes i ON i.id = v.levantamento_importacao_id
                WHERE v.rodovia = %(rodovia)s
                  AND i.levantamento_ciclo_id IN ({marcadores})""",
            engine, params=params,
        )
        for cid in df["ciclo"].dropna().astype(int):
            ano = ciclos.get(int(cid), {}).get("ano")
            if ano:
                anos.add(int(ano))
    return sorted(anos, reverse=True)


@cached(ttl=600)
def get_pavimentacao_roads() -> list[str]:
    """Rodovias disponíveis (a partir de view_iri_69, o índice principal da tela)."""
    engine = MySQLConnection().get_engine()
    df = pd.read_sql("SELECT DISTINCT rodovia FROM view_iri_69", engine)
    if df.empty:
        return []
    return sorted(df["rodovia"].dropna().astype(str).unique(), key=lambda c: (len(c), c))


# ---------------------------------------------------------------------------
# Composições normalizadas dos 3 donuts (IRI / ATR / IGG)
# ---------------------------------------------------------------------------

# Cada índice: view, campo do JSON com o valor, e os limiares de classe.
_CONDITION_SOURCES = {
    "IRI": {
        "view": "view_iri_69",
        # iri_medio vem do JSON; a view também traz km_final, então o trecho de
        # cada leitura é explícito e não precisa ser inferido.
        "campo": "iri_medio",
        "tem_km_final": True,
        "classes": ((2.7, "Bom"), (3.5, "Regular"), (None, "Ruim")),
    },
    "ATR": {
        "view": "view_fwd_71",
        # ATR = média de fl_tre/fl_tri (tratado em `_atr_from_json`).
        "campo": None,
        "tem_km_final": False,
        "classes": ((10.0, "Bom"), (15.0, "Regular"), (None, "Ruim")),
    },
    "IGG": {
        "view": "view_igg_79",
        "campo": "igg",
        "tem_km_final": False,
        "classes": ((40.0, "Bom"), (80.0, "Regular"), (None, "Ruim")),
    },
}


def _classificar(valor: float, classes) -> str | None:
    if pd.isna(valor):
        return None
    for limite, nome in classes:
        if limite is None or valor <= limite:
            return nome
    return None


def _atr_from_json(parsed: pd.Series) -> pd.Series:
    fl_tre = _parse_signed_decimal(parsed.apply(lambda d: d.get("fl_tre")))
    fl_tri = _parse_signed_decimal(parsed.apply(lambda d: d.get("fl_tri")))
    return (fl_tre + fl_tri) / 2


@cached(ttl=600)
def _condition_readings(indice: str, rodovia: str) -> pd.DataFrame:
    """Leituras de um índice com trecho, sentido, faixa, ano e classe.

    Devolve uma linha por leitura com `km_lo`/`km_hi` já normalizados (no sentido
    decrescente a view grava `km_final < km_inicial`, o que zerava toda a extensão)
    e apenas ciclos de levantamento REAL — os de "Implantação" ficam fora.

    Para IRI o trecho é o `km_final` da própria view. Para ATR e IGG, que são
    leituras pontuais sem `km_final`, o trecho vai da leitura até a seguinte do
    MESMO sentido, faixa e ciclo, limitado a `MAX_READING_GAP_KM` — sem esse teto
    a lacuna entre dois trechos da rodovia virava pavimento medido.
    """
    fonte = _CONDITION_SOURCES[indice]
    ciclos = _survey_cycles()
    reais = sorted(cid for cid, c in ciclos.items() if not c["projecao"])
    vazio = pd.DataFrame(columns=["km_lo", "km_hi", "sentido", "faixa", "ano", "classe"])
    if not reais:
        return vazio

    marcadores = ", ".join(f"%(c{i})s" for i in range(len(reais)))
    params = {f"c{i}": cid for i, cid in enumerate(reais)}
    params["rodovia"] = rodovia
    engine = MySQLConnection().get_engine()
    df = pd.read_sql(
        f"""SELECT v.km_inicial, v.km_final, v.dados,
                   i.levantamento_ciclo_id AS ciclo
            FROM {fonte['view']} v
            JOIN levantamento_importacoes i ON i.id = v.levantamento_importacao_id
            WHERE v.rodovia = %(rodovia)s
              AND i.levantamento_ciclo_id IN ({marcadores})""",
        engine, params=params,
    )
    if df.empty:
        return vazio

    parsed = df["dados"].apply(_parse_json)
    df["sentido"] = parsed.apply(lambda d: str(d.get("sentido_trafego") or "").strip().lower())
    df["faixa"] = parsed.apply(lambda d: str(d.get("faixa") or "").strip())
    valores = _atr_from_json(parsed) if indice == "ATR" else pd.to_numeric(
        parsed.apply(lambda d: d.get(fonte["campo"])), errors="coerce"
    )
    df["classe"] = valores.apply(lambda v: _classificar(v, fonte["classes"]))
    df["ano"] = df["ciclo"].map(lambda cid: (ciclos.get(int(cid)) or {}).get("ano"))
    df["km_inicial"] = pd.to_numeric(df["km_inicial"], errors="coerce")
    df = df.dropna(subset=["km_inicial", "ano"])
    if df.empty:
        return vazio

    if fonte["tem_km_final"]:
        km_final = pd.to_numeric(df["km_final"], errors="coerce")
        df["km_lo"] = pd.concat([df["km_inicial"], km_final], axis=1).min(axis=1)
        df["km_hi"] = pd.concat([df["km_inicial"], km_final], axis=1).max(axis=1)
    else:
        df = df.sort_values(["ciclo", "sentido", "faixa", "km_inicial"])
        proximo = df.groupby(["ciclo", "sentido", "faixa"], dropna=False)["km_inicial"].shift(-1)
        largura = (proximo - df["km_inicial"]).clip(lower=0.0, upper=MAX_READING_GAP_KM)
        # Última leitura de cada grupo não tem próxima: usa o passo típico do
        # grupo para ela não desaparecer do total.
        largura = largura.fillna(MAX_READING_GAP_KM)
        df["km_lo"] = df["km_inicial"]
        df["km_hi"] = df["km_inicial"] + largura

    df["ano"] = df["ano"].astype(int)
    return df[["km_lo", "km_hi", "sentido", "faixa", "ano", "classe"]].reset_index(drop=True)


def get_condition_sentidos_faixas(rodovia: str) -> tuple[list[str], list[str]]:
    """Sentidos e faixas com leitura para a rodovia — alimenta os slicers dos donuts."""
    sentidos: set[str] = set()
    faixas: set[str] = set()
    for indice in _CONDITION_SOURCES:
        df = _condition_readings(indice, rodovia)
        if df.empty:
            continue
        sentidos.update(v for v in df["sentido"].dropna().unique() if v)
        faixas.update(v for v in df["faixa"].dropna().unique() if v)
    ordem_sentido = {"crescente": 0, "decrescente": 1}
    return (
        sorted(sentidos, key=lambda s: (ordem_sentido.get(s, 9), s)),
        sorted(faixas, key=lambda f: (len(f), f)),
    )


def _claimed_by_class(df: pd.DataFrame, ano: int | None) -> dict[str, list[tuple[float, float]]]:
    """km de cada classe, sem contar o mesmo km duas vezes.

    Com `ano=None` vale a leitura MAIS RECENTE de cada km: percorre os anos do mais
    novo para o mais antigo e cada um só fica com o km que os mais novos não
    cobriram. Com um ano explícito, só aquele levantamento entra.
    """
    if df.empty:
        return {}
    anos = sorted(df["ano"].unique(), reverse=True) if ano is None else [ano]
    ja_usado: list[tuple[float, float]] = []
    por_classe: dict[str, list[tuple[float, float]]] = {}
    for ano_atual in anos:
        do_ano = df[df["ano"] == ano_atual]
        if do_ano.empty:
            continue
        # Dentro do mesmo ano, classe mais severa primeiro: onde duas leituras se
        # sobrepõem, o trecho fica com a pior condição (critério conservador).
        for classe in reversed(CLASS_ORDER):
            trechos = do_ano[do_ano["classe"] == classe]
            if trechos.empty:
                continue
            novos = _subtract_intervals(
                _merge_intervals(list(zip(trechos["km_lo"], trechos["km_hi"]))), ja_usado
            )
            if not novos:
                continue
            por_classe[classe] = _merge_intervals(por_classe.get(classe, []) + novos)
            ja_usado = _merge_intervals(ja_usado + novos)
    return por_classe


@cached(ttl=600)
def get_condition_compositions(
    rodovia: str,
    km_range: tuple[float, float] | None = None,
    sentido: str | None = None,
    faixa: str | None = None,
    ano: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Composição de IRI, ATR e IGG sobre a MESMA base de km.

    Os três donuts precisavam fechar no mesmo total (pedido do cliente, 08/2026) e
    não fechavam: cada índice tem cobertura de levantamento própria, e a soma linha
    a linha ainda contava o mesmo km em dois levantamentos diferentes.

    Aqui a base é a UNIÃO do km que os três cobrem no recorte, e o que falta em um
    índice entra como `Sem dado`. Assim o total é idêntico nos três e a diferença
    de cobertura fica visível em vez de escondida numa divergência de km.

    `sentido`/`faixa`/`ano` são os slicers dos donuts; `ano=None` usa a leitura
    mais recente de cada km. Devolve `{indice: DataFrame(classe, extensao, percentual)}`.
    """
    por_indice: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for indice in _CONDITION_SOURCES:
        df = _condition_readings(indice, rodovia)
        if not df.empty:
            if sentido:
                df = df[df["sentido"] == sentido]
            if faixa:
                df = df[df["faixa"] == faixa]
            if km_range is not None:
                df = df[(df["km_hi"] >= km_range[0]) & (df["km_lo"] <= km_range[1])]
        por_indice[indice] = _claimed_by_class(df, ano)

    # Base comum: tudo que qualquer um dos três mediu no recorte.
    base = _merge_intervals(
        [iv for classes in por_indice.values() for ivs in classes.values() for iv in ivs]
    )
    if km_range is not None:
        base = _subtract_intervals(base, [(-1e9, km_range[0]), (km_range[1], 1e9)])
    base_km = _total_km(base)

    saida: dict[str, pd.DataFrame] = {}
    for indice, classes in por_indice.items():
        linhas = []
        medido = 0.0
        for classe in CLASS_ORDER:
            ivs = classes.get(classe) or []
            if km_range is not None and ivs:
                ivs = _subtract_intervals(ivs, [(-1e9, km_range[0]), (km_range[1], 1e9)])
            km = _total_km(ivs)
            medido += km
            if km > 0:
                linhas.append({"classe": classe, "extensao": km})
        # "Sem dado" por DIFERENÇA da base, não medindo os intervalos que faltam:
        # somar/subtrair intervalos deixa resíduo de centímetros e os 3 donuts
        # fechavam com 10 m de diferença entre si. Por diferença o total é
        # exatamente `base_km` nos três, que é o ponto de toda esta função.
        sem_dado = max(base_km - medido, 0.0)
        # O corte é pelo PERCENTUAL visível, não por km: a legenda mostra uma casa
        # decimal, então qualquer coisa abaixo de 0,05% apareceria como "Sem dado
        # 0,0%" — uma fatia que não dá para ver e não informa nada. Descartar o km
        # faria o donut fechar abaixo da base e voltar a divergir dos outros dois,
        # então o resíduo entra na maior classe, onde é imperceptível.
        visivel = base_km > 0 and (sem_dado / base_km * 100) >= 0.05
        if visivel:
            linhas.append({"classe": NO_DATA_CLASS, "extensao": sem_dado})
        elif sem_dado > 0 and linhas:
            maior = max(linhas, key=lambda linha: linha["extensao"])
            maior["extensao"] += sem_dado
        df_out = pd.DataFrame(linhas, columns=["classe", "extensao"])
        total = base_km or 1.0
        df_out["percentual"] = df_out["extensao"] / total * 100
        df_out["classe"] = pd.Categorical(
            df_out["classe"], categories=COMPOSITION_CLASS_ORDER, ordered=True
        )
        saida[indice] = df_out.sort_values("classe").reset_index(drop=True)
    return saida


@cached(ttl=600)
def get_iri_series(rodovia: str) -> pd.DataFrame:
    """Série linha-a-linha do IRI (não agregada) — pros gráficos IRI ×
    extensão (Crescente/Decrescente), diferente de `get_condition_compositions`
    (que agrega em % por classe). Uma linha por levantamento, com km_inicial,
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
    não há próximo). Compartilhado entre get_atr_series e get_d0_series."""
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


# As três `get_*_composition` viveram aqui até 08/2026. Foram substituídas por
# `get_condition_compositions`, que resolve o que elas não davam conta:
#
# - somavam TODOS os levantamentos, contando o mesmo km em 2025 e 2026 (o IRI da
#   BR-055 dava 281 km num trecho de 134) e ainda incluíam os ciclos de
#   "Implantação" de 2027 a 2032, que são trecho projetado, não medição;
# - a do IGG agrupava a extensão só por sentido, sem a faixa: com 3 faixas no
#   mesmo km, 26.885 de 40.283 leituras ficavam com extensão zero;
# - a do IRI usava a coluna `extensao` da view, que se sobrepõe entre leituras;
# - nenhuma normalizava o sentido decrescente, onde a view grava
#   `km_final < km_inicial` e toda subtração dava negativo;
# - FWD e IGG transformavam a lacuna de 44,5 km entre os trechos IV e V da
#   BR-055 num único segmento medido.
