from __future__ import annotations

import html

import streamlit as st

from core.constants import MENU_ITEMS, PAGE_SUBTITLE, PAGE_TITLE


_ICON_SVGS = {
    "grid": "<path d='M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z'/>",
    "activity": "<path d='M3 12h4l3-7 4 14 3-7h4'/>",
    "tool": "<path d='M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 0 5.4-5.4l-2.8 2.8-3-3z'/>",
    "trend": "<path d='M3 7l6 6 4-4 8 8'/>",
    "scale": "<path d='M12 3v18M5 7h14M6 7l-3 7h6zM18 7l-3 7h6z'/>",
    "shield": "<path d='M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z'/>",
    "spark": "<path d='M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4z'/>",
}


def _menu_icon(icon: str) -> str:
    path = _ICON_SVGS.get(icon, _ICON_SVGS["grid"])
    return (
        '<svg class="menu-svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def render_sidebar(active_key: str = "overview") -> None:
    items_html = []
    for item in MENU_ITEMS:
        active_class = " active" if item["key"] == active_key else ""
        items_html.append(
            f'<a class="side-item{active_class}" href="?page={html.escape(item["key"])}" target="_self">'
            f'<div class="side-icon">{_menu_icon(item["icon"])}</div>'
            '<div class="side-copy">'
            f'<div class="side-label">{html.escape(item["label"])}</div>'
            f'<div class="side-description">{html.escape(item["description"])}</div>'
            '</div>'
            '</a>'
        )

    sidebar_html = (
        '<div class="sidebar-shell">'
        '<div class="brand-row">'
        '<div class="brand-mark"><span>◉</span></div>'
        '<div>'
        f'<div class="brand-title">{html.escape(PAGE_TITLE)}</div>'
        f'<div class="brand-subtitle">{html.escape(PAGE_SUBTITLE)}</div>'
        '</div>'
        '</div>'
        f'<div class="side-menu">{"".join(items_html)}</div>'
        '</div>'
    )

    st.sidebar.markdown(sidebar_html, unsafe_allow_html=True)
