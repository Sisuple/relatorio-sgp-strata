"""Menu lateral (sidebar) do relatório.

Monta a barra lateral com a marca (título de core.constants) e a lista
de navegação a partir de MENU_ITEMS. Cada item vira um link `?page=<key>` que
recarrega a página no mesmo alvo (navegação por query param, sem JS). A marcação
é injetada via st.sidebar.markdown; o visual fica no CSS global (.sidebar-shell,
.side-item, .side-item.active, etc.).
"""
from __future__ import annotations

import html

import streamlit as st

from core.constants import MENU_ITEMS, PAGE_TITLE


# Ícones do menu como fragmentos de <path> SVG, indexados pela chave "icon" de
# cada MENU_ITEMS. Só o traçado interno — o <svg> em volta é montado em _menu_icon.
_ICON_SVGS = {
    "grid": "<path d='M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z'/>",
    "activity": "<path d='M3 12h4l3-7 4 14 3-7h4'/>",
    "tool": "<path d='M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 0 5.4-5.4l-2.8 2.8-3-3z'/>",
    "compare": "<path d='M7 7h12M15 3l4 4-4 4M17 17H5M9 13l-4 4 4 4'/>",
    "trend": "<path d='M3 7l6 6 4-4 8 8'/>",
    "scale": "<path d='M12 3v18M5 7h14M6 7l-3 7h6zM18 7l-3 7h6z'/>",
    "shield": "<path d='M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z'/>",
    "spark": "<path d='M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4z'/>",
    "search": "<circle cx='10' cy='10' r='6'/><path d='M15 15l6 6'/>",
    "dollar": "<path d='M12 2v20'/><path d='M17 6.5c0-1.9-2.2-3-5-3s-5 1.3-5 3 2.2 3 5 3 5 1.1 5 3-2.2 3-5 3-5-1.1-5-3'/>",
    "truck": "<path d='M2 16V7a1 1 0 0 1 1-1h9v10H2z'/><path d='M12 10h4l4 3.2V16h-8z'/><circle cx='6.5' cy='18' r='1.6'/><circle cx='16.5' cy='18' r='1.6'/>",
    "road": "<path d='M8 21L10 3M16 21L14 3'/><path d='M12 4v3M12 10.5v3M12 17v3'/>",
    "layers": "<path d='M12 3l9 5-9 5-9-5 9-5z'/><path d='M3 13l9 5 9-5'/><path d='M3 17l9 5 9-5'/>",
}


def _menu_icon(icon: str) -> str:
    """Envolve o <path> do ícone `icon` num <svg> pronto para o menu.

    Busca o traçado em _ICON_SVGS (caindo no ícone "grid" se a chave não existir)
    e devolve o markup <svg> completo, estilizado por CSS (stroke=currentColor).
    """
    path = _ICON_SVGS.get(icon, _ICON_SVGS["grid"])
    return (
        '<svg class="menu-svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def render_sidebar(active_key: str = "overview") -> None:
    """Renderiza a sidebar inteira (marca + menu de navegação).

    `active_key` é a chave (MENU_ITEMS[i]["key"]) da página atual: o item
    correspondente recebe a classe .active para ficar destacado. Cada item é um
    link `?page=<key>` com target=_self (recarrega na mesma aba). Rótulos e
    descrições são escapados antes de entrarem no HTML.
    """
    current_theme = str(st.session_state.get("dashboard_theme", "dark"))
    items_html = []
    cta_html = []
    last_group = "__unset__"
    for item in MENU_ITEMS:
        group = item.get("group")
        # Itens sem group (ex.: IAGON) não entram na lista de navegação: viram
        # um card de destaque próprio, renderizado fora do .side-menu.
        if group is None:
            active_class = " active" if item["key"] == active_key else ""
            href = f'?page={html.escape(item["key"])}&theme={html.escape(current_theme)}'
            cta_html.append(
                f'<a class="side-cta{active_class}" href="{href}" target="_self">'
                f'<div class="side-cta-icon">{_menu_icon(item["icon"])}</div>'
                '<div class="side-copy">'
                f'<div class="side-cta-label">{html.escape(item["label"])}</div>'
                f'<div class="side-cta-description">{html.escape(item["description"])}</div>'
                '</div>'
                '</a>'
            )
            continue
        if group != last_group:
            items_html.append(f'<div class="side-group-label">{html.escape(group)}</div>')
        last_group = group
        # Destaca o item cuja key bate com a página ativa.
        active_class = " active" if item["key"] == active_key else ""
        href = f'?page={html.escape(item["key"])}&theme={html.escape(current_theme)}'
        items_html.append(
            f'<a class="side-item{active_class}" href="{href}" target="_self">'
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
        '<div class="brand-title">'
        '<span class="brand-title-tick brand-title-tick-l"><i></i><i></i></span>'
        f'{html.escape(PAGE_TITLE)}'
        '<span class="brand-title-tick brand-title-tick-r"><i></i><i></i></span>'
        '</div>'
        '</div>'
        f'<div class="side-menu">{"".join(items_html)}</div>'
        '<div class="side-footer">'
        f'<div class="side-cta-row">{"".join(cta_html)}</div>'
        '</div>'
        '</div>'
    )

    st.sidebar.markdown(sidebar_html, unsafe_allow_html=True)
