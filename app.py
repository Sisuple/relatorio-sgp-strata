from __future__ import annotations

import streamlit as st

from components.cards.metric_card import render_metric_card
from components.charts.iap_distribution import render_iap_distribution
from components.charts.linear_diagram import render_linear_diagrams
from components.layout.sidebar import render_sidebar
from components.maps.overview_map import render_overview_map
from services.overview_service import get_available_roads, get_available_scenarios, get_overview_data


st.set_page_config(
    page_title="DNIT · Pavimentos",
    page_icon="●",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg: #061018;
                --sidebar: #081923;
                --surface: #0b1d28;
                --surface-2: #0d2633;
                --border: #1c3442;
                --muted: #92a1ad;
                --text: #f4f7fb;
                --cyan: #00c2e8;
                --green: #22c55e;
                --red: #ff314a;
                --orange: #ff8a00;
                --yellow: #facc15;
            }

            #MainMenu, footer, header[data-testid="stHeader"] { display: none; }
            [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--text); }
            [data-testid="stMain"] { background: var(--bg); }
            [data-testid="stSidebar"] { background: var(--sidebar); border-right: 1px solid var(--border); width: 252px !important; }
            [data-testid="stSidebar"] > div:first-child { padding: 0; }
            [data-testid="stSidebarContent"] { padding: 0 !important; }
            .block-container { max-width: 1220px; padding: 1.1rem 1.55rem 3rem; }

            .sidebar-shell { min-height: 100vh; background: var(--sidebar); }
            .brand-row { height: 86px; display: flex; align-items: center; gap: 12px; padding: 0 12px; border-bottom: 1px solid rgba(148,163,184,.12); }
            .brand-mark { width: 38px; height: 38px; border-radius: 13px; display: grid; place-items: center; color: #001018; background: linear-gradient(135deg, #00c2e8, #0ea5b7); box-shadow: 0 14px 28px rgba(0,194,232,.2); font-size: 15px; font-weight: 900; }
            .brand-title { font-size: 13px; font-weight: 800; color: var(--text); letter-spacing: .01em; }
            .brand-subtitle { font-size: 11px; color: var(--muted); margin-top: 2px; }
            .side-menu { padding: 14px 8px 0; }
            .side-item { display: grid; grid-template-columns: 24px 1fr; gap: 10px; align-items: center; min-height: 48px; padding: 7px 10px; margin-bottom: 8px; border-radius: 8px; color: #95a4af; }
            .side-item.active { background: #063f4c; color: #00c2e8; }
            .side-icon { display: grid; place-items: center; }
            .menu-svg { width: 16px; height: 16px; }
            .side-label { font-size: 13px; line-height: 1.1; color: inherit; font-weight: 800; }
            .side-description { font-size: 10px; line-height: 1.2; color: #83929e; margin-top: 3px; }
            .side-item.active .side-description { color: #75b8c5; }

            .top-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin: 4px 0 12px; }
            .eyebrow { margin: 0 0 2px; color: #8c9ba7; font-size: 10px; font-weight: 800; letter-spacing: .16em; }
            .page-title { margin: 0; color: var(--text); font-size: 17px; font-weight: 850; letter-spacing: 0; }
            .top-actions { display: flex; align-items: center; gap: 12px; justify-content: flex-end; }
            .filter-label { min-height: 14px; margin: 0 0 5px; color: #8c9ba7; font-size: 10px; font-weight: 850; letter-spacing: .13em; text-transform: uppercase; }
            .status-pill { display: inline-flex; align-items: center; gap: 9px; min-height: 30px; padding: 0 13px; border-radius: 14px; border: 1px solid #244257; background: #0b1a23; color: #a4b2bd; font-size: 12px; white-space: nowrap; }
            .status-dot { width: 6px; height: 6px; border-radius: 999px; background: var(--green); box-shadow: 0 0 12px rgba(34,197,94,.72); }
            .status-pill strong { color: var(--text); font-weight: 700; }

            div[data-testid="stSelectbox"] { min-width: 315px; }
            div[data-testid="stSelectbox"] label { display: none; }
            div[data-baseweb="select"] > div { min-height: 32px; background: #0b1a23; border-color: #244257; border-radius: 14px; color: var(--text); box-shadow: none; }
            div[data-baseweb="select"] span { color: var(--text); font-size: 12px; font-weight: 700; }
            div[data-baseweb="popover"] { background: #0b1d28; }
            div[data-testid="column"] div[data-testid="stSelectbox"] { min-width: 0; }

            .metric-card { height: 170px; border-radius: 14px; background: linear-gradient(180deg, rgba(13,38,51,.95), rgba(8,20,29,.98)); border: 1px solid rgba(148,163,184,.22); padding: 19px 20px; box-shadow: 0 18px 40px rgba(0,0,0,.22); position: relative; overflow: hidden; }
            .metric-card:before { content: ""; position: absolute; inset: 0; opacity: .18; background: radial-gradient(circle at 72% 8%, currentColor, transparent 38%); }
            .metric-card * { position: relative; }
            .metric-card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
            .metric-title { color: #a7b4bf; font-size: 12px; letter-spacing: .14em; font-weight: 800; text-transform: uppercase; line-height: 1.35; }
            .metric-icon { width: 30px; height: 30px; border-radius: 10px; display: grid; place-items: center; background: rgba(0,0,0,.24); color: currentColor; font-size: 19px; font-weight: 800; }
            .metric-value { color: var(--text); font-size: 31px; line-height: 1.08; font-weight: 850; margin-top: 8px; letter-spacing: 0; }
            .metric-subtitle { color: #9aa8b3; font-size: 12px; line-height: 1.35; margin-top: 8px; max-width: 142px; }
            .tone-green { color: var(--green); border-color: rgba(34,197,94,.55); }
            .tone-red { color: var(--red); border-color: rgba(255,49,74,.58); }
            .tone-cyan { color: var(--cyan); border-color: rgba(0,194,232,.28); }
            .tone-orange { color: var(--orange); border-color: rgba(255,138,0,.58); }
            .tone-yellow { color: var(--yellow); border-color: rgba(250,204,21,.22); }

            .element-container:has(.metric-card) { height: 100%; }
            iframe { border-radius: 14px; }

            .chart-card { margin-top: 14px; min-height: 436px; border-radius: 14px; border: 1px solid #1d3848; background: #0b1d28; box-shadow: 0 18px 44px rgba(0,0,0,.24); padding: 20px 20px 18px; }
            .chart-heading h3 { margin: 0; color: var(--text); font-size: 15px; font-weight: 850; }
            .chart-heading p { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
            .iap-body { height: 345px; display: grid; grid-template-columns: 1fr 260px 1fr; gap: 28px; align-items: end; }
            .iap-donut-wrap { grid-column: 2; align-self: center; display: grid; place-items: center; overflow: visible; }
            .iap-donut { width: 190px; height: 190px; border-radius: 50%; position: relative; overflow: visible; box-shadow: 0 0 34px rgba(255,49,74,.18); }
            .iap-donut:after { content: ""; position: absolute; inset: 36px; background: #0b1d28; border-radius: 50%; box-shadow: inset 0 0 0 1px rgba(255,255,255,.05); }
            .iap-slice-label { position: absolute; z-index: 4; transform: translate(-50%, -50%); color: #e5edf3; font-size: 11px; line-height: 1; font-weight: 850; text-align: center; white-space: nowrap; pointer-events: none; text-shadow: 0 1px 3px rgba(0,0,0,.65); }
            .iap-donut-center { position: absolute; inset: 48px; z-index: 2; display: grid; place-items: center; align-content: center; color: var(--text); }
            .iap-donut-center strong { display: block; font-size: 25px; line-height: 1; font-weight: 850; }
            .iap-donut-center span { display: block; margin-top: 7px; color: #9aa8b3; font-size: 10px; letter-spacing: .08em; font-weight: 800; }
            .iap-legend { align-self: end; display: grid; gap: 10px; padding-bottom: 4px; }
            .iap-legend-left { grid-column: 1; }
            .iap-legend-right { grid-column: 3; }
            .iap-legend-item { display: grid; grid-template-columns: 10px 1fr auto; align-items: center; gap: 8px; min-height: 15px; color: var(--text); font-size: 12px; }
            .iap-dot { width: 10px; height: 10px; border-radius: 999px; }
            .iap-percent { color: #8f9eaa; }
            .linear-card { min-height: 264px; }
            .linear-card-compact { min-height: 176px; }
            .linear-card-compact .linear-diagram { margin-top: 20px; }
            .linear-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
            .linear-diagram { margin-top: 28px; display: grid; gap: 12px; }
            .linear-row { display: grid; grid-template-columns: 48px 1fr; align-items: center; gap: 12px; }
            .linear-row-label { color: var(--text); font-size: 12px; font-weight: 850; text-align: right; }
            .linear-track { height: 17px; display: flex; overflow: hidden; border-radius: 2px; background: rgba(148,163,184,.16); box-shadow: inset 0 0 0 1px rgba(255,255,255,.04); }
            .linear-segment { display: block; min-width: 1px; height: 100%; border-right: 1px solid rgba(6,16,24,.42); }
            .linear-segment:hover { filter: brightness(1.12); }
            .linear-axis { position: relative; height: 38px; margin-left: 60px; border-top: 1px solid rgba(148,163,184,.2); }
            .linear-axis-title { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); color: var(--text); font-size: 11px; font-weight: 850; }
            .linear-tick { position: absolute; top: 6px; transform: translateX(-50%); color: #8f9eaa; font-size: 10px; }
            .linear-tick:before { content: ""; position: absolute; top: -7px; left: 50%; width: 1px; height: 5px; background: rgba(148,163,184,.38); }
            .linear-legend { display: flex; align-items: center; justify-content: flex-end; gap: 11px; flex-wrap: wrap; max-width: 520px; }
            .linear-legend strong { color: var(--text); font-size: 11px; font-weight: 850; margin-right: 2px; }
            .linear-solution-legend { justify-self: end; margin-top: -4px; padding-top: 4px; max-width: none; }
            .linear-legend-item { display: inline-flex; align-items: center; gap: 5px; color: #cbd5dd; font-size: 11px; font-weight: 700; white-space: nowrap; }
            .linear-dot { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }

            @media (max-width: 980px) {
                .block-container { padding-left: 1rem; padding-right: 1rem; }
                .top-row, .top-actions { flex-wrap: wrap; }
                div[data-testid="stSelectbox"] { min-width: 100%; }
                .iap-body { grid-template-columns: 1fr; height: auto; }
                .iap-donut-wrap, .iap-legend-left, .iap-legend-right { grid-column: 1; }
                .linear-heading { display: grid; }
                .linear-row { grid-template-columns: 40px 1fr; }
                .linear-axis { margin-left: 52px; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _filter_label(label: str) -> None:
    st.markdown(f'<div class="filter-label">{label}</div>', unsafe_allow_html=True)


def render_top_bar(selected_road: str) -> tuple[str, str, str | None]:
    left, right = st.columns([0.82, 1.92], gap="large")
    with right:
        diagnosis_col, road_col, scenario_col = st.columns([0.8, 0.8, 1.35], gap="small")
        with diagnosis_col:
            _filter_label("Diagnóstico")
            diagnosis = st.selectbox(
                "Diagnóstico",
                ["Diagnóstico Paragon", "Diagnóstico DNIT"],
                label_visibility="collapsed",
            )
        with road_col:
            _filter_label("Rodovias")
            roads = get_available_roads()
            selected_road = st.selectbox(
                "Rodovia",
                roads,
                index=roads.index(selected_road) if selected_road in roads else 0,
                label_visibility="collapsed",
            )

            scenarios = get_available_scenarios(selected_road)
        with scenario_col:
            _filter_label("Cenários")
            scenario_keys = [scenario["key"] for scenario in scenarios]
            scenario_labels = {scenario["key"]: scenario["label"] for scenario in scenarios}
            scenario_key = st.selectbox(
                "Cenário",
                scenario_keys,
                format_func=lambda key: scenario_labels.get(key, key),
                label_visibility="collapsed",
            ) if scenario_keys else None

    with left:
        st.markdown(
            f"""
            <div class="top-copy">
                <p class="eyebrow">RELATÓRIOS</p>
                <h1 class="page-title">{diagnosis}</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return diagnosis, selected_road, scenario_key


def render_metric_cards(cards: list[dict]) -> None:
    columns = st.columns(len(cards), gap="medium")
    for column, card in zip(columns, cards):
        with column:
            render_metric_card(card)


def main() -> None:
    inject_css()
    render_sidebar(active_key="overview")

    default_road = get_available_roads()[0]
    diagnosis, selected_road, scenario_key = render_top_bar(default_road)

    if diagnosis == "Diagnóstico DNIT":
        st.info("Diagnóstico DNIT será montado na próxima etapa com os indicadores próprios do DNIT.")
        return

    data = get_overview_data(selected_road, scenario_key=scenario_key)
    metrics = data["metrics"]

    render_metric_cards(data["cards"])
    st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
    render_overview_map(data["segments"], metrics["extension_km"])
    render_iap_distribution(data["distribution"], metrics["iap_average"])
    render_linear_diagrams(data["linear_diagram"])


if __name__ == "__main__":
    main()
