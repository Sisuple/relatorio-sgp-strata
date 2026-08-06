"""Donut (rosca) de distribuição do IAP por classe de condição.

Desenha um gráfico de rosca via CSS `conic-gradient` (sem lib de charting): cada
classe vira uma fatia proporcional ao seu percentual e o valor médio fica no
centro. Os percentuais aparecem no próprio anel (leitura direta) e também na
legenda, que é a única fonte para fatias pequenas demais para receber rótulo.
Os rótulos são posicionados em duas colunas e afastados entre si por
`_spread_labels`, para nunca se sobreporem.
Genérico o bastante para reusar em outras métricas (IRI/IGG) trocando os textos.
Tudo é HTML/CSS injetado no Streamlit; o estilo (.iap-*) vive no CSS global.
"""
from __future__ import annotations

import html
import math

import streamlit as st


def _build_conic_gradient(distribution_df) -> str:
    """Constrói o valor CSS de um conic-gradient a partir da distribuição.

    Percorre as classes acumulando um cursor 0→100% e emite, para cada fatia,
    "<cor> <início>% <fim>%". `distribution_df` precisa das colunas 'percentual'
    e 'color'. Os percentuais são normalizados pelo total (evita não fechar 100%).
    """
    total = float(distribution_df["percentual"].sum()) or 1.0  # evita divisão por zero
    cursor = 0.0  # ponto angular corrente, em % (0..100)
    stops = []
    for row in distribution_df.to_dict("records"):
        percent = float(row["percentual"]) / total * 100
        start = cursor
        cursor += percent
        # Cada stop define a faixa exata da fatia; bordas coincidentes = corte nítido.
        stops.append(f"{row['color']} {start:.2f}% {cursor:.2f}%")
    return ", ".join(stops)


# Geometria do anel (ver CSS .iap-donut): disco de 190px, faixa colorida até r=95.
_DONUT_CENTER_PX = 95.0
_DONUT_LABEL_RADIUS_PX = 108.0   # logo fora do anel: 13px de folga, ainda "colado"
_DONUT_LABEL_MIN_PERCENT = 3.0   # abaixo disso o rótulo polui; fica só na legenda
_DONUT_LABEL_MIN_GAP_PX = 14.0   # folga vertical mínima entre rótulos do mesmo lado
_DONUT_LABEL_SIDE_SIN = 0.35     # |sin| abaixo disso = topo/base, texto centrado


def _nudge_overlaps(labels: list[dict]) -> None:
    """Rede de segurança: separa verticalmente rótulos quase colados (in-place).

    Só o Y é ajustado, e apenas o necessário para respeitar o gap mínimo — o X
    continua vindo do ângulo da fatia, que é o que mantém cada rótulo junto do seu
    setor. Com poucas fatias nada é movido; com muitas, o deslocamento é pequeno.
    """
    if len(labels) < 2:
        return
    labels.sort(key=lambda item: item["top"])
    for previous, current in zip(labels, labels[1:]):
        folga = current["top"] - previous["top"]
        if folga < _DONUT_LABEL_MIN_GAP_PX:
            current["top"] = previous["top"] + _DONUT_LABEL_MIN_GAP_PX


def _donut_percent_labels(distribution_df) -> str:
    """Rótulos de % logo FORA do anel, na posição angular da própria fatia.

    Cada rótulo fica a 13px da borda do anel, no ângulo médio do seu setor — é a
    proximidade que faz a referência visual, sem precisar de linha-guia. As duas
    tentativas anteriores falharam por motivos opostos: em colunas fixas à
    esquerda/direita, o rótulo de uma fatia no topo aparecia longe dela; escrito
    dentro da faixa colorida, poluía o anel.

    A ancoragem acompanha a posição: fatias à direita crescem para a direita, à
    esquerda para a esquerda, e as de topo/base ficam centradas. Fatias abaixo de
    `_DONUT_LABEL_MIN_PERCENT` ficam apenas na legenda, que traz todos os valores.
    """
    total = float(distribution_df["percentual"].sum()) or 1.0
    cursor = 0.0  # posição angular acumulada, em % (0..100)
    por_lado: dict[str, list[dict]] = {"left": [], "right": []}

    for row in distribution_df.to_dict("records"):
        percent = float(row["percentual"])
        share = percent / total * 100
        if percent < _DONUT_LABEL_MIN_PERCENT:
            cursor += share
            continue

        # Ângulo do MEIO da fatia; *3.6 converte % (0..100) em graus (0..360).
        middle_angle = math.radians((cursor + share / 2) * 3.6)
        cursor += share
        # sin/-cos partem do TOPO (0°) girando no sentido horário, casando com a
        # origem do conic-gradient que desenha o anel.
        seno = math.sin(middle_angle)
        if abs(seno) < _DONUT_LABEL_SIDE_SIN:
            ancora = "center"
        else:
            ancora = "right" if seno > 0 else "left"
        por_lado["right" if seno >= 0 else "left"].append(
            {
                "left": _DONUT_CENTER_PX + seno * _DONUT_LABEL_RADIUS_PX,
                "top": _DONUT_CENTER_PX - math.cos(middle_angle) * _DONUT_LABEL_RADIUS_PX,
                "percent": percent,
                "ancora": ancora,
            }
        )

    spans: list[str] = []
    for itens in por_lado.values():
        _nudge_overlaps(itens)
        for item in itens:
            spans.append(
                f'<span class="iap-slice-label is-{item["ancora"]}" '
                f'style="left:{item["left"]:.1f}px;top:{item["top"]:.1f}px;">'
                f'{item["percent"]:.1f}%</span>'
            )
    return "".join(spans)


def _legend_item(row: dict) -> str:
    """Monta uma linha da legenda (bolinha de cor + classe + percentual) do donut."""
    label = html.escape(str(row["classe"]))
    percent = float(row["percentual"])
    color = html.escape(str(row["color"]))
    return f"""
    <div class="iap-legend-item">
        <span class="iap-dot" style="background:{color}"></span>
        <span class="iap-label">{label}</span>
        <span class="iap-percent">{percent:.1f}%</span>
    </div>
    """


def render_iap_distribution(
    distribution_df,
    average_iap: float,
    *,
    title: str = "Distribuição IAP",
    subtitle: str = "Sentido horário · zona de alerta e crítica destacadas",
    center_label: str = "IAP MÉDIO",
    value_fmt: str = "{:.2f}",
) -> None:
    """Donut de distribuição por classe. Padrão = IAP; passe title/center_label/value_fmt
    para reusar em outras métricas (ex.: IRI, IGG na matriz DNIT)."""
    if distribution_df is None or distribution_df.empty:
        st.info(f"Sem distribuição de {center_label.replace(' MÉDIO', '')} para exibir.")
        return

    gradient = _build_conic_gradient(distribution_df)
    percent_labels = _donut_percent_labels(distribution_df)
    records = distribution_df.to_dict("records")
    # Divide as classes em duas colunas de legenda (esquerda/direita); a metade
    # ímpar sobra para a coluna da esquerda (arredondamento para cima).
    midpoint = (len(records) + 1) // 2
    left_items = "".join(_legend_item(row) for row in records[:midpoint])
    right_items = "".join(_legend_item(row) for row in records[midpoint:])

    st.markdown(
        f"""
        <section class="chart-card iap-card">
            <div class="chart-heading">
                <h3>{html.escape(title)}</h3>
                <p>{html.escape(subtitle)}</p>
            </div>
            <div class="iap-body">
                <div class="iap-donut-wrap">
                    <div class="iap-donut" style="background: conic-gradient({gradient});">
                        {percent_labels}
                        <div class="iap-donut-center">
                            <strong>{value_fmt.format(average_iap)}</strong>
                            <span>{html.escape(center_label)}</span>
                        </div>
                    </div>
                </div>
                <div class="iap-legend iap-legend-left">{left_items}</div>
                <div class="iap-legend iap-legend-right">{right_items}</div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
