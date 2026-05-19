from __future__ import annotations

import html

import streamlit as st


def render_metric_card(card: dict) -> None:
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
