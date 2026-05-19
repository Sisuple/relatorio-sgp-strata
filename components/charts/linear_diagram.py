from __future__ import annotations

import html

import streamlit as st


_CONDITION_ROWS = [
    ("ICDS", "classe_icds", "cor_icds", "icds"),
    ("ICDP", "classe_icdp", "cor_icdp", "icdp"),
    ("ICDE", "classe_icde", "cor_icde", "icde"),
]
_IAP_ROWS = [
    ("IAP", "classe_iap", "cor_iap", "iap"),
]
_CONDITION_LEGEND = [
    ("Excelente", "#26c6f9"),
    ("Bom", "#00a651"),
    ("Regular", "#fff200"),
    ("Mau", "#f2a51a"),
    ("Péssimo", "#d71920"),
]
_IAP_LEGEND = [
    ("Excelente", "#26c6f9"),
    ("Bom", "#00a651"),
    ("++ Regular", "#b6d7a8"),
    ("+ Regular", "#f4f1a6"),
    ("- Regular", "#fff200"),
    ("Mau", "#f2a51a"),
    ("Péssimo", "#d71920"),
]
_SOLUTION_LEGEND = [
    ("OK", "#26c6f9"),
    ("RL", "#00a651"),
    ("RL+RS", "#b6d7a8"),
    ("RL+REF", "#f4f1a6"),
    ("RPS", "#fff200"),
    ("RPS+REF", "#f2a51a"),
    ("REC", "#d71920"),
]


def _format_km(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"


def _render_segment(row: dict, class_key: str, color_key: str, value_key: str, total_km: float) -> str:
    km_initial = float(row["km_inicial"])
    km_final = float(row["km_final"])
    extent = max(float(row["extensao"]), 0.01)
    width = extent / total_km * 100
    color = html.escape(str(row[color_key]))
    klass = html.escape(str(row[class_key]))
    value = float(row[value_key])
    title = (
        f"Segmento {row['segment_id']} | km {km_initial:.2f} - {km_final:.2f} | "
        f"{klass} | {value:.2f}"
    )
    return (
        f'<span class="linear-segment" title="{html.escape(title)}" '
        f'style="width:{width:.4f}%;background:{color};"></span>'
    )


def _render_row(label: str, class_key: str, color_key: str, value_key: str, rows: list[dict], total_km: float) -> str:
    segments = "".join(
        _render_segment(row, class_key, color_key, value_key, total_km)
        for row in rows
    )
    return (
        '<div class="linear-row">'
        f'<div class="linear-row-label">{html.escape(label)}</div>'
        f'<div class="linear-track">{segments}</div>'
        '</div>'
    )


def _render_axis(min_km: float, max_km: float) -> str:
    total = max(max_km - min_km, 1)
    tick_count = 8
    ticks = []
    for index in range(tick_count + 1):
        value = min_km + total * index / tick_count
        ticks.append(
            f'<span class="linear-tick" style="left:{index / tick_count * 100:.2f}%;">'
            f'{html.escape(_format_km(value))}</span>'
        )

    return (
        '<div class="linear-axis">'
        '<span class="linear-axis-title">Km da rodovia</span>'
        f'{"".join(ticks)}'
        '</div>'
    )


def _render_legend(legend: list[tuple[str, str]], *, title: str | None = None, class_name: str = "") -> str:
    items = "".join(
        f'<span class="linear-legend-item">'
        f'<span class="linear-dot" style="background:{color};"></span>{html.escape(label)}'
        f'</span>'
        for label, color in legend
    )
    title_markup = f'<strong>{html.escape(title)}</strong>' if title else ""
    class_attr = f" {class_name}" if class_name else ""
    return f'<div class="linear-legend{class_attr}">{title_markup}{items}</div>'


def _render_linear_card(
    diagram_df,
    *,
    title: str,
    subtitle: str,
    rows_config: list[tuple[str, str, str, str]],
    legend: list[tuple[str, str]],
    solution_legend: list[tuple[str, str]] | None = None,
    compact: bool = False,
) -> None:
    if diagram_df is None or diagram_df.empty:
        st.info("Sem dados para exibir o diagrama linear.")
        return

    rows = diagram_df.to_dict("records")
    min_km = float(diagram_df["km_inicial"].min())
    max_km = float(diagram_df["km_final"].max())
    total_km = max(max_km - min_km, 1)
    diagram_rows = "".join(
        _render_row(label, class_key, color_key, value_key, rows, total_km)
        for label, class_key, color_key, value_key in rows_config
    )
    compact_class = " linear-card-compact" if compact else ""
    footer_legend = (
        _render_legend(solution_legend, title="Solução Corretiva", class_name="linear-solution-legend")
        if solution_legend
        else ""
    )

    markup = (
        f'<section class="chart-card linear-card{compact_class}">'
        '<div class="chart-heading linear-heading">'
        f'<div><h3>{html.escape(title)}</h3>'
        f'<p>{html.escape(subtitle)}</p></div>'
        f'{_render_legend(legend)}'
        '</div>'
        f'<div class="linear-diagram">{diagram_rows}{_render_axis(min_km, max_km)}{footer_legend}</div>'
        '</section>'
    )

    st.markdown(markup, unsafe_allow_html=True)


def render_linear_diagrams(diagram_df) -> None:
    _render_linear_card(
        diagram_df,
        title="Diagrama Linear de Condição",
        subtitle="ICDS, ICDP e ICDE por segmento",
        rows_config=_CONDITION_ROWS,
        legend=_CONDITION_LEGEND,
    )
    _render_linear_card(
        diagram_df,
        title="Índice de Aptidão do Pavimento e Soluções Conceptivas",
        subtitle="IAP por segmento",
        rows_config=_IAP_ROWS,
        legend=_IAP_LEGEND,
        solution_legend=_SOLUTION_LEGEND,
        compact=True,
    )
