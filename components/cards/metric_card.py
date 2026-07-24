"""Card de métrica (KPI) reutilizável da UI.

Renderiza um cartão compacto com título, ícone, valor em destaque e subtítulo,
via HTML/CSS injetado no Streamlit. O estilo real (classes .metric-card etc.)
vive no CSS global do app; aqui só se monta a marcação.
"""
from __future__ import annotations

import html

import streamlit as st

# Ícones em SVG (stroke uniforme, sem preenchimento) para os cards de métrica.
# Substituem glifos/emoji avulsos por um conjunto visual único e consistente.
_ICON_ATTRS = 'viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
_METRIC_ICONS: dict[str, str] = {
    "money": f'<svg {_ICON_ATTRS}><rect x="3" y="7" width="18" height="10" rx="2"/><circle cx="12" cy="12" r="2.2"/><path d="M6.5 9.2V9M17.5 9.2V9M6.5 15v-.2M17.5 15v-.2"/></svg>',
    "trend-up": f'<svg {_ICON_ATTRS}><path d="M4 16l5-5 3 3 6.5-7"/><path d="M14 6.5h4.5V11"/></svg>',
    "ruler": f'<svg {_ICON_ATTRS}><rect x="4" y="9" width="16" height="6" rx="1"/><path d="M8 9v2.4M12 9v3M16 9v2.4"/></svg>',
    "alert-triangle": f'<svg {_ICON_ATTRS}><path d="M12 4.2 21 19H3z"/><path d="M12 10v4"/><circle cx="12" cy="16.8" r="0.55" fill="currentColor"/></svg>',
    "list": f'<svg {_ICON_ATTRS}><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
    "check-circle": f'<svg {_ICON_ATTRS}><circle cx="12" cy="12" r="8.5"/><path d="M8.2 12.4l2.6 2.6L16 9.4"/></svg>',
    "activity": f'<svg {_ICON_ATTRS}><path d="M3 12h4l2-7 4 14 2-7h6"/></svg>',
    "grid": f'<svg {_ICON_ATTRS}><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg>',
    "target": f'<svg {_ICON_ATTRS}><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="0.7" fill="currentColor"/></svg>',
    "flag": f'<svg {_ICON_ATTRS}><path d="M6 4v16"/><path d="M6 5h12l-3 4 3 4H6"/></svg>',
    "bar-chart": f'<svg {_ICON_ATTRS}><path d="M4 20V11M10 20V4M16 20v-6"/></svg>',
    "calendar": f'<svg {_ICON_ATTRS}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>',
    "car": f'<svg {_ICON_ATTRS}><path d="M4 16l1.4-4.8A2 2 0 0 1 7.3 10h9.4a2 2 0 0 1 1.9 1.2L20 16"/><rect x="3" y="16" width="18" height="4" rx="1.4"/><circle cx="7.5" cy="20" r="1.3"/><circle cx="16.5" cy="20" r="1.3"/></svg>',
    "truck": f'<svg {_ICON_ATTRS}><rect x="2.5" y="8" width="11" height="8.5" rx="1"/><path d="M13.5 11h4l3.5 3.3V16.5h-7.5"/><circle cx="6.5" cy="18.3" r="1.5"/><circle cx="17" cy="18.3" r="1.5"/></svg>',
}


def render_metric_card(card: dict) -> None:
    """Renderiza um card de métrica a partir de um dict.

    Recebe `card` com as chaves opcionais: title, value, subtitle,
    tone (variante de cor, default "cyan"), icon, details e class_name. Todos os valores são
    escapados com html.escape antes de irem para o HTML (unsafe_allow_html),
    evitando injeção quando vêm de dados dinâmicos.
    """
    title = html.escape(str(card.get("title", "")))
    value = html.escape(str(card.get("value", "")))
    subtitle = html.escape(str(card.get("subtitle", "")))
    tone = html.escape(str(card.get("tone", "cyan")))
    icon_key = str(card.get("icon", ""))
    icon = _METRIC_ICONS.get(icon_key, html.escape(icon_key))
    class_name = html.escape(str(card.get("class_name", "")).strip())
    card_classes = f"metric-card tone-{tone}"
    if class_name:
        card_classes += f" {class_name}"
    detail_items = []
    for detail in card.get("details", []) or []:
        label = html.escape(str(detail.get("label", "")))
        detail_value = html.escape(str(detail.get("value", "")))
        detail_tone = html.escape(str(detail.get("tone", "muted")))
        detail_items.append(
            f'<span class="metric-detail-pill metric-detail-{detail_tone}">'
            f'<span>{label}</span><strong>{detail_value}</strong></span>'
        )
    details_html = f'<div class="metric-details">{"".join(detail_items)}</div>' if detail_items else ""

    st.markdown(
        f"""
        <div class="{card_classes}">
            <div class="metric-card-top">
                <div class="metric-title">{title}</div>
                <div class="metric-icon">{icon}</div>
            </div>
            <div class="metric-value">{value}</div>
            <div class="metric-subtitle">{subtitle}</div>
            {details_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
