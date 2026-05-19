from __future__ import annotations

import html
import math

import streamlit as st


def _build_conic_gradient(distribution_df) -> str:
    total = float(distribution_df["percentual"].sum()) or 1.0
    cursor = 0.0
    stops = []
    for row in distribution_df.to_dict("records"):
        percent = float(row["percentual"]) / total * 100
        start = cursor
        cursor += percent
        stops.append(f"{row['color']} {start:.2f}% {cursor:.2f}%")
    return ", ".join(stops)


def _donut_percent_labels(distribution_df) -> str:
    total = float(distribution_df["percentual"].sum()) or 1.0
    cursor = 0.0
    labels = []
    donut_center_px = 95
    label_radius_px = 116

    for row in distribution_df.to_dict("records"):
        percent = float(row["percentual"])
        normalized_percent = percent / total * 100
        middle_angle = (cursor + normalized_percent / 2) * 3.6
        cursor += normalized_percent
        angle_rad = math.radians(middle_angle)
        label_left = donut_center_px + math.sin(angle_rad) * label_radius_px
        label_top = donut_center_px - math.cos(angle_rad) * label_radius_px

        labels.append(
            f'<span class="iap-slice-label" '
            f'style="left:{label_left:.1f}px;top:{label_top:.1f}px;">'
            f'{percent:.1f}%</span>'
        )

    return "".join(labels)


def _legend_item(row: dict) -> str:
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


def render_iap_distribution(distribution_df, average_iap: float) -> None:
    if distribution_df is None or distribution_df.empty:
        st.info("Sem distribuição de IAP para exibir.")
        return

    gradient = _build_conic_gradient(distribution_df)
    percent_labels = _donut_percent_labels(distribution_df)
    records = distribution_df.to_dict("records")
    midpoint = (len(records) + 1) // 2
    left_items = "".join(_legend_item(row) for row in records[:midpoint])
    right_items = "".join(_legend_item(row) for row in records[midpoint:])

    st.markdown(
        f"""
        <section class="chart-card iap-card">
            <div class="chart-heading">
                <h3>Distribuição IAP</h3>
                <p>Sentido horário · zona de alerta e crítica destacadas</p>
            </div>
            <div class="iap-body">
                <div class="iap-donut-wrap">
                    <div class="iap-donut" style="background: conic-gradient({gradient});">
                        {percent_labels}
                        <div class="iap-donut-center">
                            <strong>{average_iap:.2f}</strong>
                            <span>IAP MÉDIO</span>
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
