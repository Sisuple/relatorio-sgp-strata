"""Card de métrica (KPI) reutilizável da UI.

Renderiza um cartão compacto com título, ícone, valor em destaque e subtítulo,
via HTML/CSS injetado no Streamlit. O estilo real (classes .metric-card etc.)
vive no CSS global do app; aqui só se monta a marcação.
"""
from __future__ import annotations

import html

import streamlit as st


def render_metric_card(card: dict) -> None:
    """Renderiza um card de métrica a partir de um dict.

    Recebe `card` com as chaves opcionais: title, value, subtitle,
    tone (variante de cor, default "cyan") e icon. Todos os valores são
    escapados com html.escape antes de irem para o HTML (unsafe_allow_html),
    evitando injeção quando vêm de dados dinâmicos.
    """
    title = html.escape(str(card.get("title", "")))
    value = html.escape(str(card.get("value", "")))
    subtitle = html.escape(str(card.get("subtitle", "")))
    tone = html.escape(str(card.get("tone", "cyan")))
    icon = html.escape(str(card.get("icon", "")))

    st.markdown(
        f"""
        <div class="metric-card tone-{tone}">
            <div class="metric-card-top">
                <div class="metric-title">{title}</div>
                <div class="metric-icon">{icon}</div>
            </div>
            <div class="metric-value">{value}</div>
            <div class="metric-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
