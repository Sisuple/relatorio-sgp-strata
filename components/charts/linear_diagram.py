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
    ("Excelente", "#00c2e8"),
    ("Bom", "#00a651"),
    ("Regular", "#fff200"),
    ("Mau", "#f2a51a"),
    ("Péssimo", "#d71920"),
]
_IAP_LEGEND = [
    ("Excelente", "#00c2e8"),
    ("Bom", "#00a651"),
    ("++ Regular", "#b6d7a8"),
    ("+ Regular", "#f4f1a6"),
    ("- Regular", "#fff200"),
    ("Mau", "#f2a51a"),
    ("Péssimo", "#d71920"),
]
_SOLUTION_LEGEND = [
    ("OK", "#00c2e8"),
    ("RL", "#00a651"),
    ("RL+RS", "#b6d7a8"),
    ("RL+REF", "#f4f1a6"),
    ("RPS", "#fff200"),
    ("RPS+REF", "#f2a51a"),
    ("REC", "#d71920"),
]


def _format_km(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"


def apply_km_zoom(diagram_df, *, key: str, label: str = "Zoom (km)"):
    """Renderiza um slider de range em km e devolve (df_filtrado, km_range_or_None).

    Se o df estiver vazio, não renderiza o slider e devolve (df, None).
    """
    if diagram_df is None or diagram_df.empty:
        return diagram_df, None

    full_min = float(diagram_df["km_inicial"].min())
    full_max = float(diagram_df["km_final"].max())
    slider_min = float(int(full_min))
    slider_max = float(int(full_max) + (1 if full_max > int(full_max) else 0))
    if slider_max <= slider_min:
        slider_max = slider_min + 1.0

    zoom_min, zoom_max = st.slider(
        label,
        min_value=slider_min,
        max_value=slider_max,
        value=(slider_min, slider_max),
        step=1.0,
        key=f"{key}_{slider_min:.0f}_{slider_max:.0f}",
        help="Arraste as alças para ampliar um trecho específico da rodovia.",
    )

    filtered = diagram_df[
        (diagram_df["km_final"] >= zoom_min) & (diagram_df["km_inicial"] <= zoom_max)
    ]
    return filtered, (zoom_min, zoom_max)


def _render_segment(
    row: dict,
    class_key: str,
    color_key: str,
    value_key: str,
    total_km: float,
    min_km: float,
    max_km: float,
) -> str:
    km_initial = float(row["km_inicial"])
    km_final = float(row["km_final"])
    seg_start = max(km_initial, min_km)
    seg_end = min(km_final, max_km)
    extent = max(seg_end - seg_start, 0.001)
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


def _render_row(
    label: str,
    class_key: str,
    color_key: str,
    value_key: str,
    rows: list[dict],
    total_km: float,
    min_km: float,
    max_km: float,
) -> str:
    segments = "".join(
        _render_segment(row, class_key, color_key, value_key, total_km, min_km, max_km)
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


def _linear_heading_html(title: str, subtitle: str, legend: list[tuple[str, str]]) -> str:
    return (
        '<div class="chart-heading linear-heading">'
        f'<div><h3>{html.escape(title)}</h3>'
        f'<p>{html.escape(subtitle)}</p></div>'
        f'{_render_legend(legend)}'
        '</div>'
    )


def _linear_body_html(
    diagram_df,
    rows_config: list[tuple[str, str, str, str]],
    *,
    solution_legend: list[tuple[str, str]] | None = None,
    km_range: tuple[float, float] | None = None,
) -> str:
    rows = diagram_df.to_dict("records")
    if km_range is not None:
        min_km, max_km = km_range
    else:
        min_km = float(diagram_df["km_inicial"].min())
        max_km = float(diagram_df["km_final"].max())
    total_km = max(max_km - min_km, 1)
    diagram_rows = "".join(
        _render_row(label, class_key, color_key, value_key, rows, total_km, min_km, max_km)
        for label, class_key, color_key, value_key in rows_config
    )
    footer_legend = (
        _render_legend(solution_legend, title="Solução Corretiva", class_name="linear-solution-legend")
        if solution_legend
        else ""
    )
    return f'<div class="linear-diagram">{diagram_rows}{_render_axis(min_km, max_km)}{footer_legend}</div>'


def _render_linear_card(
    diagram_df,
    *,
    title: str,
    subtitle: str,
    rows_config: list[tuple[str, str, str, str]],
    legend: list[tuple[str, str]],
    solution_legend: list[tuple[str, str]] | None = None,
    compact: bool = False,
    km_range: tuple[float, float] | None = None,
) -> None:
    if diagram_df is None or diagram_df.empty:
        message = (
            "Sem segmentos no intervalo selecionado."
            if km_range is not None
            else "Sem dados para exibir o diagrama linear."
        )
        st.info(message)
        return

    compact_class = " linear-card-compact" if compact else ""
    markup = (
        f'<section class="chart-card linear-card{compact_class}">'
        f'{_linear_heading_html(title, subtitle, legend)}'
        f'{_linear_body_html(diagram_df, rows_config, solution_legend=solution_legend, km_range=km_range)}'
        '</section>'
    )
    st.markdown(markup, unsafe_allow_html=True)


def render_iap_linear(diagram_df, *, km_range: tuple[float, float] | None = None) -> None:
    _render_linear_card(
        diagram_df,
        title="Índice de Aptidão do Pavimento e Soluções Conceptivas",
        subtitle="IAP por segmento",
        rows_config=_IAP_ROWS,
        legend=_IAP_LEGEND,
        solution_legend=_SOLUTION_LEGEND,
        compact=True,
        km_range=km_range,
    )


def render_iap_linear_zoomable(diagram_df, *, key: str, label: str = "Filtrar trecho (km)"):
    """Card do IAP com o slider de km DENTRO do próprio card.

    Renderiza tudo dentro de um container do Streamlit (estilizado como `.chart-card`
    via CSS) na ordem: cabeçalho → slider de km → barras. Devolve `(df_filtrado, km_range)`
    para que o expander de detalhes técnicos reutilize o mesmo intervalo.
    """
    with st.container(border=True):
        # Marcador usado pelo CSS (:has) para estilizar este container como chart-card.
        st.markdown('<span class="iap-zoom-marker"></span>', unsafe_allow_html=True)
        st.markdown(
            _linear_heading_html(
                "Índice de Aptidão do Pavimento e Soluções Conceptivas",
                "IAP por segmento",
                _IAP_LEGEND,
            ),
            unsafe_allow_html=True,
        )
        filtered, km_range = apply_km_zoom(diagram_df, key=key, label=label)
        if filtered is None or filtered.empty:
            st.info(
                "Sem segmentos no intervalo selecionado."
                if km_range is not None
                else "Sem dados para exibir o diagrama linear."
            )
        else:
            st.markdown(
                _linear_body_html(
                    filtered, _IAP_ROWS, solution_legend=_SOLUTION_LEGEND, km_range=km_range
                ),
                unsafe_allow_html=True,
            )
    return filtered, km_range


def render_condition_linear(diagram_df, *, km_range: tuple[float, float] | None = None) -> None:
    _render_linear_card(
        diagram_df,
        title="Diagrama Linear de Condição",
        subtitle="ICDS, ICDP e ICDE por segmento",
        rows_config=_CONDITION_ROWS,
        legend=_CONDITION_LEGEND,
        km_range=km_range,
    )
