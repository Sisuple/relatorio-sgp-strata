"""Donut (rosca) de distribuição do IAP por classe de condição.

Desenha um gráfico de rosca via CSS `conic-gradient` (sem lib de charting): cada
classe vira uma fatia proporcional ao seu percentual, os rótulos de % são
posicionados por trigonometria em volta do anel, e o valor médio fica no centro.
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


def _donut_percent_labels(distribution_df) -> str:
    """Posiciona os rótulos de % ao redor do anel do donut (por trigonometria).

    Para cada fatia calcula o ÂNGULO DO MEIO e projeta o rótulo num raio fixo em
    torno do centro. Devolve <span> absolutamente posicionados (left/top em px).
    """
    total = float(distribution_df["percentual"].sum()) or 1.0
    cursor = 0.0  # posição angular acumulada, em % (0..100)
    labels = []
    donut_center_px = 95   # centro do donut em px (metade do tamanho do elemento)
    label_radius_px = 108  # raio onde os rótulos são colocados (fora do anel)
    min_visible_percent = 3.0  # fatias muito pequenas ficam só na legenda

    for row in distribution_df.to_dict("records"):
        percent = float(row["percentual"])
        if percent < min_visible_percent:
            cursor += percent / total * 100
            continue
        normalized_percent = percent / total * 100
        # Ângulo do MEIO da fatia; *3.6 converte % (0..100) em graus (0..360).
        middle_angle = (cursor + normalized_percent / 2) * 3.6
        cursor += normalized_percent
        angle_rad = math.radians(middle_angle)
        # sin/-cos posicionam a partir do TOPO (0°) girando no sentido horário,
        # casando com a origem do conic-gradient. left usa +sin, top usa -cos.
        label_left = donut_center_px + math.sin(angle_rad) * label_radius_px
        label_top = donut_center_px - math.cos(angle_rad) * label_radius_px

        labels.append(
            f'<span class="iap-slice-label" '
            f'style="left:{label_left:.1f}px;top:{label_top:.1f}px;">'
            f'{percent:.1f}%</span>'
        )

    return "".join(labels)


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
