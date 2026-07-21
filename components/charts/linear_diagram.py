"""Diagrama linear da condição do pavimento (barras horizontais por km).

Desenha, ao longo do eixo quilométrico da rodovia, faixas coloridas por segmento:
uma linha por índice de condição (ICDS/ICDP/ICDE) ou a linha do IAP com a legenda
de solução corretiva. Cada segmento vira um <span> cuja LARGURA é proporcional à
extensão em km e cuja COR vem já pronta do DataFrame (colunas cor_*). Há variações
com slider de zoom em km (apply_km_zoom) e uma versão multi-sentido empilhada.
Tudo é HTML/CSS injetado; o estilo real (.linear-*) fica no CSS global do app.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st


# Configuração das linhas do diagrama: (rótulo, coluna da classe, coluna da cor,
# coluna do valor numérico) no DataFrame de segmentos. _CONDITION_ROWS = três
# índices de condição empilhados; _IAP_ROWS = uma única linha (o IAP).
_CONDITION_ROWS = [
    ("ICDS", "classe_icds", "cor_icds", "icds"),
    ("ICDP", "classe_icdp", "cor_icdp", "icdp"),
    ("ICDE", "classe_icde", "cor_icde", "icde"),
]
_IAP_ROWS = [
    ("IAP", "classe_iap", "cor_iap", "iap"),
]
# Paletas hardcoded (rótulo -> cor hex) das legendas. São a mesma paleta semântica
# de condição repetida em vários arquivos do projeto (mapas, distribuição IAP...).
# Ver README.md Parte II §11.4. Aqui servem só para desenhar a legenda; as cores
# das barras vêm prontas das colunas cor_* do DataFrame.
_CONDITION_LEGEND = [
    ("Excelente", "#00c2e8"),
    ("Bom", "#00a651"),
    ("Regular", "#fff200"),
    ("Mau", "#f2a51a"),
    ("Péssimo", "#d71920"),
]
# Escala do IAP com 7 níveis (Regular subdividido em ++ / + / -).
_IAP_LEGEND = [
    ("Excelente", "#00c2e8"),
    ("Bom", "#00a651"),
    ("++ Regular", "#b6d7a8"),
    ("+ Regular", "#f4f1a6"),
    ("- Regular", "#fff200"),
    ("Mau", "#f2a51a"),
    ("Péssimo", "#d71920"),
]
# Solução corretiva recomendada por faixa — alinhada 1:1 (por cor) com _IAP_LEGEND:
# OK↔Excelente ... REC↔Péssimo. Esse alinhamento é usado por _combined_legend_html.
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
    """Formata um km sem casas se for inteiro, senão com 1 casa (ex.: 12 / 12.5)."""
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"


def apply_km_zoom(diagram_df, *, key: str, label: str = "Zoom (km)"):
    """Renderiza um slider de range em km e devolve (df_filtrado, km_range_or_None).

    Se o df estiver vazio, não renderiza o slider e devolve (df, None).
    """
    if diagram_df is None or diagram_df.empty:
        return diagram_df, None

    # Snap dos limites para km "redondos": min piso ao inteiro, max teto ao inteiro
    # (só arredonda para cima se houver fração). Garante passos de 1 km no slider.
    full_min = float(diagram_df["km_inicial"].min())
    full_max = float(diagram_df["km_final"].max())
    slider_min = float(int(full_min))
    slider_max = float(int(full_max) + (1 if full_max > int(full_max) else 0))
    # Evita min == max (slider degenerado) quando o trecho é menor que 1 km.
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

    # Mantém todo segmento que INTERSECTA a janela [zoom_min, zoom_max] — inclui os
    # que começam antes/terminam depois; o clip visual às bordas é feito em _render_segment.
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
    """Gera o <span> de UM segmento numa linha do diagrama.

    Recorta o segmento à janela visível [min_km, max_km], calcula a largura em %
    (proporção da sua extensão sobre total_km) e usa a cor pronta de `color_key`.
    O tooltip (title=) traz id, km, classe e valor. Recebe `row` como dict e as
    chaves das colunas de classe/cor/valor.
    """
    km_initial = float(row["km_inicial"])
    km_final = float(row["km_final"])
    # Clip do segmento à janela visível (zoom): não desenha além das bordas.
    seg_start = max(km_initial, min_km)
    seg_end = min(km_final, max_km)
    # Piso mínimo de extensão para o segmento não sumir (largura > 0).
    extent = max(seg_end - seg_start, 0.001)
    width = extent / total_km * 100  # largura como % da faixa total visível
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
    """Monta UMA linha do diagrama: rótulo à esquerda + faixa de segmentos.

    Concatena os <span> de todos os `rows` (cada um via _render_segment) dentro de
    uma track. `label` é o texto do índice (ex.: "ICDS", "IAP").
    """
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
    """Desenha o eixo horizontal de km sob o diagrama.

    Distribui tick_count+1 marcas igualmente espaçadas entre min_km e max_km,
    posicionadas em % (left) para acompanhar as barras acima.
    """
    total = max(max_km - min_km, 1)
    tick_count = 8  # nº de intervalos → 9 marcas (0/8, 1/8, ..., 8/8)
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
    """Monta uma legenda de bolinhas coloridas a partir de pares (rótulo, cor).

    `title` opcional vira um <strong> antes dos itens; `class_name` adiciona uma
    classe CSS extra ao container (ex.: para a legenda de solução no rodapé).
    """
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
    """Monta o cabeçalho do card: título + subtítulo à esquerda e legenda à direita."""
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
    """Monta o corpo do diagrama: as linhas de índices + eixo + legenda de solução.

    Se `km_range` for dado, usa-o como janela (min/max) — mantendo a escala fixa
    quando há zoom; senão calcula a partir dos km do próprio DataFrame.
    `solution_legend` opcional acrescenta a legenda de solução corretiva no rodapé.
    """
    rows = diagram_df.to_dict("records")
    if km_range is not None:
        min_km, max_km = km_range  # janela do zoom: fixa a escala independente dos dados filtrados
    else:
        min_km = float(diagram_df["km_inicial"].min())
        max_km = float(diagram_df["km_final"].max())
    total_km = max(max_km - min_km, 1)  # denominador das larguras em % (nunca zero)
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
    """Renderiza um card de diagrama linear completo (cabeçalho + corpo) no Streamlit.

    Base genérica reutilizada por render_iap_linear / render_condition_linear:
    monta o <section class="chart-card linear-card"> e injeta via st.markdown.
    Se não houver dados, mostra um st.info (mensagem varia se há zoom ativo).
    `compact` adiciona a classe de card compacto; `rows_config` define quais linhas
    desenhar (_IAP_ROWS ou _CONDITION_ROWS).
    """
    if diagram_df is None or diagram_df.empty:
        # Mensagem depende se o vazio veio de um filtro de km ou da ausência de dados.
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
    """Card do diagrama linear do IAP (uma linha), com legenda de solução corretiva.

    Wrapper de _render_linear_card com os presets do IAP; `km_range` opcional fixa
    a janela de km (usado para casar com um zoom externo).
    """
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
    """Card do diagrama linear de condição: três linhas (ICDS, ICDP, ICDE).

    Wrapper de _render_linear_card com os presets de condição; `km_range` opcional
    fixa a janela de km.
    """
    _render_linear_card(
        diagram_df,
        title="Diagrama Linear de Condição",
        subtitle="ICDS, ICDP e ICDE por segmento",
        rows_config=_CONDITION_ROWS,
        legend=_CONDITION_LEGEND,
        km_range=km_range,
    )


def _combined_legend_html() -> str:
    """Legenda única: linha 'Situação' (IAP) sobre 'Solução' (corretiva), com as colunas
    alinhadas pela cor (Péssimo↔REC, etc.). Usada no diagrama linear multi-sentido."""
    def _cells(legend):
        return "".join(
            f'<span class="lcl-cell"><span class="lcl-dot" style="background:{color}"></span>{html.escape(label)}</span>'
            for label, color in legend
        )
    return (
        '<div class="linear-combined-legend"><div class="lcl-grid">'
        f'<span class="lcl-rowlabel">Situação</span>{_cells(_IAP_LEGEND)}'
        f'<span class="lcl-rowlabel">Solução</span>{_cells(_SOLUTION_LEGEND)}'
        '</div></div>'
    )


def render_iap_linear_multi(sentido_dfs, *, key: str):
    """Diagrama linear do IAP para VÁRIOS sentidos/cenários: UM slider de km
    compartilhado, UMA barra por sentido (empilhadas, com rótulo) e UMA legenda
    combinada (Situação + Solução) no fim. Devolve o `km_range` p/ os detalhes técnicos.

    sentido_dfs: lista de (rótulo, linear_diagram_df).
    """
    valid = [(lbl, df) for lbl, df in sentido_dfs if df is not None and not df.empty]
    if not valid:
        st.info("Sem dados para o diagrama linear.")
        return None
    multi = len(valid) > 1
    ref = pd.concat([df for _, df in valid], ignore_index=True)  # range de km combinado
    with st.container(border=True):
        st.markdown('<span class="iap-zoom-marker"></span>', unsafe_allow_html=True)
        st.markdown(
            _linear_heading_html(
                "Índice de Aptidão do Pavimento e Soluções Conceptivas",
                "IAP por segmento",
                [],  # legenda única e centralizada no fim do card
            ),
            unsafe_allow_html=True,
        )
        # Slider único sobre o range combinado; a janela escolhida vale para todos os sentidos.
        _, km_range = apply_km_zoom(ref, key=key, label="Filtrar trecho (km)")
        for label, df in valid:
            # Filtra cada sentido pela mesma janela (interseção com [km_range]).
            filtered = df[(df["km_final"] >= km_range[0]) & (df["km_inicial"] <= km_range[1])]
            if multi:  # só rotula cada barra quando há mais de um sentido
                st.markdown(
                    f'<div class="linear-scenario-label">{html.escape(str(label))}</div>',
                    unsafe_allow_html=True,
                )
            if filtered is None or filtered.empty:
                st.info("Sem segmentos no intervalo selecionado.")
                continue
            st.markdown(
                _linear_body_html(filtered, _IAP_ROWS, solution_legend=None, km_range=km_range),
                unsafe_allow_html=True,
            )
        st.markdown(_combined_legend_html(), unsafe_allow_html=True)
    return km_range
