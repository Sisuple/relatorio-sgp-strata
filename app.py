"""Aplicação Streamlit do Relatório SGP Strata (camada de apresentação).

Este arquivo é o ponto de entrada e o roteador da UI. `main()` lê o parâmetro
`?page=` da URL e monta a tela correspondente da jornada de decisão executiva:

    Visão geral → Diagnóstico → Soluções → Cenário econômico → Projeção
       (rede)      (condição)    (o que fazer)  (quanto custa)   (evolução)

Cada trilha metodológica tem seu par de telas: as funções `_render_*` cobrem a
metodologia **Paragon** e as `_render_dnit_*` cobrem a **Matriz Cadastrada (DNIT)**.
O roteamento entre as duas é decidido pelo "Tipo de Matriz" escolhido na top bar.

Papel deste módulo: concentrar as REGRAS DE APRESENTAÇÃO e boa parte das regras de
negócio hardcoded (cores, custos paramétricos, estratégias, mapeamentos código→nome,
pesos de priorização). Os dados técnicos já vêm processados pelas camadas `services/`
e `components/`. As regras hardcoded aqui estão catalogadas no README.md Parte II
(§11 Terminologia/Cores, §12 Limiares, §13 Priorização, §14 Custos/Econômico/Famílias).

Fora do escopo desta documentação: o assistente IAGON (funções `_iagon_*` e
`_render_iagon_page`/`_render_screen_iagon`), que é o chat de IA embutido nas telas.
"""
from __future__ import annotations

import html
import json
import math
import re
from datetime import date
from functools import lru_cache
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from components.cards.metric_card import render_metric_card
from components.charts.iap_distribution import render_iap_distribution
from components.charts.linear_diagram import (
    render_condition_linear,
    render_iap_linear_multi,
    render_iap_linear_zoomable,
)
from components.layout.sidebar import render_sidebar
from components.maps.overview_map import render_overview_map, _CLASS_COLORS as _MAP_CLASS_COLORS
from components.maps.dnit_map import render_dnit_map
from services.overview_service import (
    get_available_roads,
    get_available_scenarios,
    get_available_years,
    get_scenario_label,
    get_dnit_economic_data,
    get_dnit_iri_projection,
    get_dnit_overview_data,
    get_dnit_projection_schedule,
    get_dnit_solutions_data,
    get_dnit_available_roads,
    get_overview_data,
    get_projection_data,
    get_solutions_data,
    ensure_fresh_data,
    IAP_META,
    _DNIT_GROUP_COLORS,
    _DNIT_ORDER,
    _IAP_CLASS_ORDER,
    _dnit_solution_group,
    _normalize_road_code,
)
from services.prioritization import (
    calcular_indice_priorizacao,
    calcular_indice_priorizacao_dnit,
    calcular_indice_priorizacao_segmento,
    classificar_prioridade,
)
from services.cache import cached
from services.work_plan_pdf import build_work_plan_pdf
from services import iagon


st.set_page_config(
    page_title="IAGON · Pavimentos",
    page_icon="●",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_css() -> None:
    """Injeta o tema visual (CSS) global do painel.

    Define as variáveis de cor (fundo escuro, superfícies, bordas) e estiliza os
    componentes Streamlit para o visual executivo do relatório. Só aparência.
    """
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

            /* Anti-flicker: previne o flash branco do iframe + overlay do "Running…". */
            iframe { background: var(--bg) !important; color-scheme: dark; }
            [data-testid="stMain"] iframe[title="streamlit_components.v1.html"] {
                background: var(--bg) !important;
            }
            /* Esconde o spinner global do Streamlit que escurece tudo durante re-renders. */
            [data-testid="stStatusWidget"] { display: none !important; }
            /* Suaviza a transição de opacidade de qualquer container que re-renderiza. */
            [data-testid="stMain"] > .stMainBlockContainer { transition: opacity .15s ease; }
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
            .side-item { display: grid; grid-template-columns: 24px 1fr; gap: 10px; align-items: center; min-height: 48px; padding: 7px 10px; margin-bottom: 8px; border-radius: 8px; color: #95a4af; text-decoration: none; }
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
            .filter-placeholder { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%; min-height: 32px; padding: 0 13px; border-radius: 14px; border: 1px solid #244257; background: #0b1a23; color: #8fa0ac; font-size: 12px; font-weight: 700; line-height: 1; box-sizing: border-box; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; box-shadow: none; }
            .filter-placeholder-text { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
            .filter-placeholder-caret { color: #5f7280; font-size: 11px; flex: none; }

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
            /* Card do IAP com o slider de km embutido: estiliza SOMENTE o container do slider como
               .chart-card. Usa combinador de filho direto (> ... > :first-child) para NÃO casar com
               o border-wrapper da página inteira (que conteria o marcador como descendente profundo). */
            div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div:first-child .iap-zoom-marker) { margin-top: 14px; border-radius: 14px; border: 1px solid #1d3848; background: #0b1d28; box-shadow: 0 18px 44px rgba(0,0,0,.24); padding: 18px 20px 16px; }
            .iap-zoom-marker { display: none; }
            /* Compacta o espaçamento do slider e alinha sua largura à faixa de barras: recua o
               conteúdo interno em 60px (rótulo "IAP" 48px + gap 12px, igual ao .linear-axis) via
               padding-left + box-sizing, mantendo a borda direita dentro do card (sem estourar). */
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.iap-zoom-marker) div[data-testid="stSlider"] { padding-top: 2px; padding-left: 60px; box-sizing: border-box; }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.iap-zoom-marker) .linear-diagram { margin-top: 6px; }
            @media (max-width: 760px) {
              div[data-testid="stVerticalBlockBorderWrapper"]:has(.iap-zoom-marker) div[data-testid="stSlider"] { padding-left: 52px; }
            }
            /* Painel IAGON por tela — botão estilizado, alinhado à direita (sem position:fixed,
               que quebrava o layout/scroll do Streamlit). */
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.iagon-fab-mark) {
                border: none !important; background: transparent !important; box-shadow: none !important; padding: 0 !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.iagon-fab-mark) > div[data-testid="stVerticalBlock"] {
                align-items: flex-end;
            }
            .iagon-fab-mark { display: none; }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.iagon-fab-mark) [data-testid="stPopover"] button {
                border-radius: 999px !important; border: none !important;
                background: linear-gradient(135deg,#00c2e8,#0a6ee0) !important; color: #04121a !important;
                font-weight: 850 !important; padding: 11px 20px !important; box-shadow: 0 12px 30px rgba(0,194,232,.45) !important;
            }
            .iagon-cv-head { font-size: 15px; color: #f4f7fb; }
            .iagon-cv-sub { font-size: 12px; color: #92a1ad; margin: 2px 0 10px; }
            .iagon-cv-filtro { font-size: 12.5px; color: #cbd5dd; background: rgba(7,17,25,.55); border: 1px solid rgba(148,163,184,.2); border-radius: 10px; padding: 10px 12px; margin-bottom: 6px; line-height: 1.5; }
            .iagon-cv-q { font-size: 12.5px; color: #8fd3ff; font-weight: 700; margin: 12px 0 4px; }
            .chart-heading:not(.linear-heading) { display: grid; gap: 6px; margin-bottom: 18px; }
            .chart-heading h3 { margin: 0; color: var(--text); font-size: 15px; font-weight: 850; }
            .chart-heading p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
            .iap-body { height: 345px; display: grid; grid-template-columns: 1fr 260px 1fr; gap: 28px; align-items: end; padding-top: 10px; }
            .iap-donut-wrap { grid-column: 2; align-self: center; display: grid; place-items: center; overflow: visible; }
            .iap-donut { width: 190px; height: 190px; border-radius: 50%; position: relative; overflow: visible; box-shadow: 0 0 34px rgba(255,49,74,.18); }
            .iap-donut:after { content: ""; position: absolute; inset: 36px; background: #0b1d28; border-radius: 50%; box-shadow: inset 0 0 0 1px rgba(255,255,255,.05); }
            .iap-slice-label { position: absolute; z-index: 4; transform: translate(-50%, -50%); color: #e5edf3; font-size: 11px; line-height: 1; font-weight: 850; text-align: center; white-space: nowrap; pointer-events: none; text-shadow: 0 1px 3px rgba(0,0,0,.65); }
            .iap-donut-center { position: absolute; inset: 48px; z-index: 2; display: grid; place-items: center; align-content: center; color: var(--text); }
            .iap-donut-center strong { display: block; font-size: 25px; line-height: 1; font-weight: 850; }
            .iap-donut-center span { display: block; margin-top: 7px; color: #9aa8b3; font-size: 10px; letter-spacing: .08em; font-weight: 800; }
            .iap-legend { align-self: end; display: grid; gap: 10px; padding-bottom: 4px; width: max-content; max-width: 100%; }
            .iap-legend-left { grid-column: 1; justify-self: start; }
            .iap-legend-right { grid-column: 3; justify-self: end; }
            .iap-legend-item { display: inline-grid; grid-template-columns: 10px auto auto; align-items: center; justify-content: start; gap: 8px; min-height: 15px; color: var(--text); font-size: 12px; }
            .iap-dot { width: 10px; height: 10px; border-radius: 999px; }
            .iap-label, .iap-percent { white-space: nowrap; }
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
            /* Legenda combinada (Situação sobre Solução, colunas pareadas pela cor) — diagrama multi-sentido. */
            .linear-combined-legend { display: flex; justify-content: center; margin-top: 22px; }
            .lcl-grid { display: inline-grid; grid-template-columns: auto repeat(7, auto); gap: 9px 16px; align-items: center; }
            .lcl-rowlabel { color: #9aa8b3; font-size: 11px; font-weight: 850; text-align: right; padding-right: 4px; }
            .lcl-cell { display: inline-flex; align-items: center; gap: 6px; color: #cbd5dd; font-size: 11px; font-weight: 700; white-space: nowrap; }
            .lcl-dot { width: 11px; height: 11px; border-radius: 2px; display: inline-block; }
            .solution-card { margin-top: 16px; border-radius: 14px; border: 1px solid #1d3848; background: #0b1d28; box-shadow: 0 18px 44px rgba(0,0,0,.24); overflow: hidden; }
            .solution-card-head { padding: 20px 20px 18px; border-bottom: 1px solid rgba(148,163,184,.1); }
            .solution-card-head h3 { margin: 0; color: var(--text); font-size: 15px; font-weight: 850; }
            .solution-card-head p { margin: 6px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
            .solution-table-wrap { overflow-x: auto; }
            .solution-table { width: 100%; border-collapse: collapse; min-width: 920px; }
            .solution-table th { padding: 11px 14px; color: #8f9eaa; background: rgba(18,39,52,.72); font-size: 10px; letter-spacing: .11em; text-transform: uppercase; text-align: left; white-space: nowrap; }
            .solution-table td { padding: 12px 14px; border-top: 1px solid rgba(148,163,184,.08); color: #dce6ed; font-size: 13px; white-space: nowrap; }
            .solution-table tr:hover td { background: rgba(0,194,232,.04); }
            .solution-table .mono { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 12px; }
            .solution-table .muted { color: #9aa8b3; }
            .net-road-link { color: #e8f1f8; font-weight: 750; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; }
            .net-road-link:hover { color: #00c2e8; text-decoration: underline; }
            .net-rank-dot { width: 9px; height: 9px; border-radius: 999px; display: inline-block; flex: none; }
            /* Ranking das rodovias como gráfico de barras horizontais. */
            .net-rank-body { padding: 18px 20px 22px; }
            .net-rank-legend { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-top: 10px; color: #9aa8b3; font-size: 11px; line-height: 1.45; }
            .net-rank-legend-item { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
            .net-rank-legend-sw { width: 12px; height: 12px; border-radius: 999px; display: inline-block; box-shadow: inset 0 0 0 1px rgba(255,255,255,.08); }
            .net-rank-legend-sw.interv { background: linear-gradient(90deg, #ffb11c, #f08f12); }
            .net-rank-legend-sw.ok { background: linear-gradient(90deg, #3f86ad, #296b8f); }
            .net-rank-legend-note { color: #7f909c; }
            .net-rank-row { display: grid; grid-template-columns: 190px 1fr 64px; grid-template-rows: auto auto; align-items: center; column-gap: 16px; row-gap: 6px; margin: 0; padding: 12px 0 14px; border-bottom: 1px solid rgba(148,163,184,.08); transition: background .15s ease, border-color .15s ease, box-shadow .15s ease; border-radius: 12px; }
            .net-rank-row:last-child { border-bottom: none; padding-bottom: 4px; }
            .net-rank-row:hover { background: rgba(9,30,42,.42); }
            .net-rank-row.active { background: rgba(9,30,42,.22); box-shadow: inset 0 0 0 1px rgba(0,194,232,.14); }
            .net-rank-name { grid-row: 1 / span 2; align-self: start; color: #e8f1f8; font-size: 13px; font-weight: 800; text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-top: 3px; }
            .net-rank-name:hover { color: #00c2e8; }
            .net-rank-row.active .net-rank-name { color: #5fd4ff; }
            .net-rank-track { height: 18px; border-radius: 999px; background: #172a37; overflow: hidden; box-shadow: inset 0 0 0 1px rgba(255,255,255,.08), inset 0 1px 8px rgba(0,0,0,.28); position: relative; }
            .net-rank-bar { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #3f86ad, #296b8f); position: relative; overflow: hidden; box-shadow: inset 0 0 0 1px rgba(255,255,255,.05); }   /* extensão total / parte OK */
            .net-rank-interv { position: absolute; left: 0; top: 0; height: 100%; background: linear-gradient(90deg, #ffb11c, #f08f12); border-radius: 999px; display: flex; align-items: center; justify-content: flex-end; min-width: 2px; }
            .net-rank-interv-label { padding: 0 8px; color: #08202b; font-size: 10px; font-weight: 900; letter-spacing: .02em; white-space: nowrap; text-shadow: none; }
            .net-rank-val { color: #f2f7fb; font-size: 13px; font-weight: 850; text-align: right; white-space: nowrap; }
            .net-rank-extra { grid-column: 2 / span 2; color: #8f9eaa; font-size: 11px; line-height: 1.35; }
            @media (max-width: 920px) {
                .net-rank-row { grid-template-columns: minmax(0, 1fr) 70px; grid-template-rows: auto auto auto; row-gap: 7px; padding: 12px 0 15px; }
                .net-rank-name { grid-column: 1 / span 2; grid-row: 1; white-space: normal; }
                .net-rank-track { grid-column: 1; grid-row: 2; }
                .net-rank-val { grid-column: 2; grid-row: 2; }
                .net-rank-extra { grid-column: 1 / span 2; grid-row: 3; }
            }
            .iagon-hero { display: flex; gap: 14px; align-items: center; margin: 4px 0 16px; padding: 18px 20px; border-radius: 16px; border: 1px solid #1d3848; background: linear-gradient(120deg, rgba(0,194,232,.10), rgba(11,29,40,.45)); }
            .iagon-avatar { width: 46px; height: 46px; flex: none; display: grid; place-items: center; border-radius: 14px; background: linear-gradient(135deg, #00c2e8, #0a6ee0); color: #04121a; font-size: 22px; font-weight: 800; box-shadow: 0 10px 28px rgba(0,194,232,.35); }
            .iagon-hero h3 { margin: 0; color: var(--text); font-size: 16px; font-weight: 850; }
            .iagon-hero p { margin: 4px 0 0; color: var(--muted); font-size: 12.5px; max-width: 760px; line-height: 1.5; }
            .iagon-suggest-label { color: #8f9eaa; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 800; margin: 8px 0 8px; }
            .segment-table { min-width: 720px; width: 100%; border-collapse: collapse; background: rgba(6,16,24,.42); border: 1px solid rgba(148,163,184,.16); border-radius: 8px; overflow: hidden; }
            .segment-table th { padding: 8px 10px; background: rgba(6,16,24,.52); color: #8f9eaa; font-size: 9px; letter-spacing: .1em; text-transform: uppercase; }
            .segment-table td { padding: 8px 10px; border-top: 1px solid rgba(148,163,184,.08); font-size: 11px; }
            .solution-chip-cell { border-radius: 6px; font-weight: 850; text-align: center; }
            .solution-table td.detail-toggle-cell { text-align: center; white-space: nowrap; }
            .detail-toggle { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; padding: 5px 12px; border-radius: 999px; border: 1px solid #244257; background: #0b1a23; color: var(--cyan); font-size: 11px; font-weight: 800; white-space: nowrap; user-select: none; transition: background .15s, border-color .15s; }
            .detail-toggle:hover { background: #06303a; border-color: #00c2e8; }
            .detail-toggle .caret { font-size: 9px; line-height: 1; transition: transform .15s ease; }
            .detail-row td.detail-cell { padding: 0 !important; border-top: 0 !important; background: rgba(6,16,24,.4); }
            .detail-checkbox { position: absolute; width: 0; height: 0; opacity: 0; pointer-events: none; }
            .detail-content { display: none; padding: 14px 18px 18px; }
            .detail-checkbox:checked ~ .detail-content { display: block; }
            .detail-summary { color: #9aa8b3; font-size: 11px; font-weight: 700; margin-bottom: 10px; }
            .snv-strip-wrap { margin: 2px 0 18px; }
            .snv-strip { display: flex; height: 28px; border-radius: 6px; overflow: hidden; box-shadow: inset 0 0 0 1px rgba(255,255,255,.05); }
            .snv-strip-seg { height: 100%; min-width: 1px; border-right: 1px solid rgba(6,16,24,.5); transition: filter .15s; }
            .snv-strip-seg:hover { filter: brightness(1.15); }
            .snv-strip-axis { display: flex; justify-content: space-between; color: #8f9eaa; font-size: 10px; margin-top: 5px; }
            .snv-strip-legend { display: flex; flex-wrap: wrap; gap: 5px 14px; margin-top: 9px; }
            .snv-strip-leg { display: inline-flex; align-items: center; gap: 6px; color: #cbd5dd; font-size: 11px; font-weight: 700; }
            .snv-strip-leg .dot { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }
            .snv-cost-bars { display: grid; gap: 8px; margin-top: 4px; }
            .snv-cost-row { display: grid; grid-template-columns: minmax(120px, 220px) 1fr minmax(120px, auto); align-items: center; gap: 12px; }
            .snv-cost-lbl { color: #dce6ed; font-size: 12px; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .snv-cost-track { height: 16px; background: rgba(148,163,184,.12); border-radius: 4px; overflow: hidden; }
            .snv-cost-bar { display: block; height: 100%; border-radius: 4px; min-width: 2px; }
            .snv-cost-val { color: #9aa8b3; font-size: 11px; white-space: nowrap; }
            .proj-chart { margin-top: 18px; }
            .proj-legend { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 14px; padding-top: 13px; border-top: 1px solid rgba(148,163,184,.12); }
            .proj-leg { display: inline-flex; align-items: center; gap: 8px; color: #cbd5dd; font-size: 12px; font-weight: 700; }
            .proj-leg .sw { width: 16px; height: 4px; border-radius: 2px; display: inline-block; }
            .proj-leg .sw-dash { border-top: 2px dashed #ff314a; height: 0; width: 16px; }
            .alert-list { margin-top: 18px; display: grid; gap: 8px; }
            .alert-item { display: grid; grid-template-columns: 10px 1fr; align-items: center; gap: 12px; padding: 11px 14px; border-radius: 10px; border: 1px solid #1d3848; background: #0b1d28; color: #dce6ed; font-size: 13px; }
            .alert-item .alert-dot { width: 9px; height: 9px; border-radius: 999px; }
            .alert-critico { border-color: rgba(255,49,74,.5); }
            .alert-critico .alert-dot { background: #ff314a; box-shadow: 0 0 10px rgba(255,49,74,.6); }
            .alert-atencao { border-color: rgba(255,138,0,.45); }
            .alert-atencao .alert-dot { background: #ff8a00; }
            .alert-ok .alert-dot { background: #22c55e; }
            .alert-more { color: #8f9eaa; font-size: 12px; padding: 4px 2px; }
            .sol-chip { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 800; margin: 2px 5px 2px 0; white-space: nowrap; }
            .cp-headline { margin-top: 14px; font-size: 13px; color: #cbd5dd; line-height: 1.5; }
            .cp-headline strong { color: var(--text); }
            .cp-chart { display: flex; align-items: flex-end; gap: 6px; margin-top: 18px; height: 232px; }
            .cp-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
            .cp-bar { width: 100%; max-width: 38px; height: 200px; display: flex; flex-direction: column; border-radius: 4px; overflow: hidden; box-shadow: inset 0 0 0 1px rgba(0,0,0,.25); }
            .cp-seg { width: 100%; }
            .cp-seg:hover { filter: brightness(1.15); }
            .cp-year { margin-top: 8px; font-size: 10px; color: #8f9eaa; }
            .cp-legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 16px; padding-top: 12px; border-top: 1px solid rgba(148,163,184,.12); }
            .cp-leg { display: inline-flex; align-items: center; gap: 7px; color: #cbd5dd; font-size: 12px; font-weight: 700; }
            .cp-sw { width: 13px; height: 13px; border-radius: 3px; display: inline-block; }
            tr.snv-row:has(+ tr.detail-row .detail-checkbox:checked) .detail-toggle { background: #06303a; border-color: #00c2e8; }
            tr.snv-row:has(+ tr.detail-row .detail-checkbox:checked) .detail-toggle .caret { transform: rotate(90deg); }
            div[data-testid="stPopover"] button {
                min-height: 38px;
                border-radius: 10px;
                border: 1px solid #38bdf8;
                background: rgba(0,194,232,.10);
                color: var(--cyan);
                font-size: 12px;
                font-weight: 850;
            }
            .iap-pill { display: inline-flex; align-items: center; gap: 8px; }
            .iap-pill-dot { width: 9px; height: 9px; border-radius: 999px; display: inline-block; }
            .solution-distribution { margin-top: 16px; border-radius: 14px; border: 1px solid #1d3848; background: #0b1d28; padding: 20px 20px 24px; box-shadow: 0 18px 44px rgba(0,0,0,.18); overflow: hidden; }
            .solution-distribution-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
            .solution-distribution-title { display: flex; align-items: center; gap: 10px; }
            .solution-distribution-icon { width: 32px; height: 32px; border-radius: 12px; display: grid; place-items: center; background: #00c2e8; color: #031019; font-weight: 900; }
            .solution-distribution h3 { margin: 0; color: var(--text); font-size: 15px; font-weight: 850; }
            .solution-distribution p { margin: 6px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
            .solution-distribution-meta { display: flex; align-items: center; gap: 16px; color: #8f9eaa; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }
            .solution-distribution-meta strong { color: var(--text); letter-spacing: 0; }
            .solution-distribution-meta .accent { color: var(--cyan); }
            .solution-bars { height: 270px; display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 8px; }
            .solution-y-axis { position: relative; height: 188px; margin-top: 18px; border-right: 1px solid rgba(148,163,184,.14); }
            .solution-y-tick { position: absolute; right: 10px; transform: translateY(50%); color: #8f9eaa; font-size: 11px; }
            .solution-chart-area { position: relative; padding-top: 18px; overflow-x: auto; overflow-y: visible; scrollbar-width: thin; scrollbar-color: rgba(148,163,184,.5) rgba(148,163,184,.12); }
            /* Barra de rolagem SEMPRE visível (no macOS o overlay fica oculto e o gráfico parece estourar). */
            .solution-chart-area::-webkit-scrollbar { height: 10px; }
            .solution-chart-area::-webkit-scrollbar-track { background: rgba(148,163,184,.10); border-radius: 6px; }
            .solution-chart-area::-webkit-scrollbar-thumb { background: rgba(148,163,184,.45); border-radius: 6px; }
            .solution-chart-area::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,.72); }
            .solution-chart-plot { height: 188px; border-bottom: 2px solid rgba(148,163,184,.34); background: repeating-linear-gradient(to top, transparent 0, transparent 48px, rgba(148,163,184,.10) 49px, transparent 50px); }
            .solution-bar-grid { height: 188px; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(156px, 1fr); align-items: end; gap: 26px; padding: 0 16px; min-width: 100%; }
            .solution-bar-item { height: 188px; display: grid; align-items: end; justify-items: center; min-width: 156px; }
            .solution-bar { width: min(100%, 118px); min-height: 3px; border-radius: 5px 5px 0 0; position: relative; box-shadow: 0 10px 22px rgba(0,0,0,.18); }
            .solution-bar-value { position: absolute; top: -30px; left: 50%; transform: translateX(-50%); color: #f4f7fb; font-size: 11px; font-weight: 850; white-space: nowrap; text-align: center; line-height: 1.15; }
            .solution-bar-value span { display: block; color: #9aa8b3; font-size: 10px; font-weight: 750; margin-top: 2px; }
            .solution-label-grid { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(156px, 1fr); gap: 26px; padding: 9px 16px 0; min-width: 100%; justify-items: center; }
            .solution-bar-label { color: #9aa8b3; font-size: 11px; text-align: center; white-space: normal; line-height: 1.25; min-width: 156px; max-width: 156px; }
            .solution-panel { margin-top: 16px; border-radius: 14px; border: 1px solid #1d3848; background: #0b1d28; padding: 20px; box-shadow: 0 18px 44px rgba(0,0,0,.18); }
            .solution-panel-title { margin: 0; color: var(--text); font-size: 15px; font-weight: 850; }
            .solution-panel-subtitle { margin: 6px 0 20px; color: var(--muted); font-size: 12px; line-height: 1.45; }
            .solution-panel-spacer { height: 12px; }
            .solution-filter-label { margin: 0 0 6px; color: #8f9eaa; font-size: 10px; letter-spacing: .11em; text-transform: uppercase; font-weight: 850; }
            div[data-testid="stMultiSelect"] label,
            div[data-testid="stSlider"] label { display: none; }
            div[data-baseweb="tag"] { background: rgba(0,194,232,.14); color: var(--text); }
            .pagination-summary { color: #9aa8b3; font-size: 12px; padding-top: 28px; text-align: right; }
            div[data-testid="stNumberInput"] label { display: none; }
            div[data-testid="stNumberInput"] input,
            div[data-testid="stSelectbox"] input { color: var(--text); }
            div[data-testid="stDownloadButton"] button {
                min-height: 40px;
                border-radius: 10px;
                border: 1px solid #244257;
                background: #0b1a23;
                color: var(--text);
                font-size: 12px;
                font-weight: 800;
            }
            .economic-panel { margin-top: 16px; border-radius: 14px; border: 1px solid #1d3848; background: #0b1d28; padding: 20px; box-shadow: 0 18px 44px rgba(0,0,0,.18); }
            .economic-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
            .economic-title { display: flex; align-items: center; gap: 10px; }
            .economic-icon { width: 32px; height: 32px; border-radius: 12px; display: grid; place-items: center; background: #00c2e8; color: #031019; font-weight: 900; }
            .economic-head h3 { margin: 0; color: var(--text); font-size: 15px; font-weight: 850; }
            .economic-head p { margin: 6px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
            .economic-note { color: #9aa8b3; font-size: 11px; line-height: 1.45; border: 1px solid rgba(148,163,184,.14); background: rgba(6,16,24,.36); border-radius: 10px; padding: 10px 12px; margin-top: 16px; }
            .economic-control-value { color: var(--cyan); text-align: right; font-size: 12px; font-weight: 850; margin-top: -20px; margin-bottom: 6px; }
            .economic-chart { display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: 10px; min-height: 276px; }
            .economic-y-axis { position: relative; height: 210px; margin-top: 28px; border-right: 1px solid rgba(148,163,184,.14); }
            .economic-y-tick { position: absolute; right: 10px; transform: translateY(50%); color: #8f9eaa; font-size: 11px; }
            .economic-plot { position: relative; height: 210px; margin-top: 28px; border-bottom: 2px solid rgba(148,163,184,.34); background: repeating-linear-gradient(to top, transparent 0, transparent 51px, rgba(148,163,184,.10) 52px, transparent 53px); overflow: visible; }
            .economic-bars { position: absolute; inset: 0 16px; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(82px, 1fr); align-items: end; gap: 18px; }
            .economic-bar-item { height: 210px; display: grid; align-items: end; justify-items: center; }
            .economic-bar { width: 54px; min-height: 3px; border-radius: 5px 5px 0 0; background: #ff7a00; opacity: .72; position: relative; }
            .economic-bar span { position: absolute; top: -24px; left: 50%; transform: translateX(-50%); color: #f4f7fb; font-size: 10px; font-weight: 850; white-space: nowrap; text-shadow: 0 1px 3px rgba(0,0,0,.72); }
            .economic-line { position: absolute; left: 0; right: 0; height: 2px; background: #00c2e8; opacity: .62; }
            .economic-labels { margin: 8px 16px 0; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(82px, 1fr); gap: 18px; color: #8f9eaa; font-size: 11px; text-align: center; }
            .economic-legend { display: flex; justify-content: center; gap: 16px; color: #cbd5dd; font-size: 11px; margin-top: 16px; flex-wrap: wrap; }
            /* Rolagem horizontal DENTRO do card (muitos anos) com barra sempre visível. */
            .economic-scroll { overflow-x: auto; overflow-y: hidden; padding-bottom: 10px; scrollbar-width: thin; scrollbar-color: rgba(148,163,184,.5) rgba(148,163,184,.12); }
            .economic-scroll::-webkit-scrollbar { height: 10px; }
            .economic-scroll::-webkit-scrollbar-track { background: rgba(148,163,184,.10); border-radius: 6px; }
            .economic-scroll::-webkit-scrollbar-thumb { background: rgba(148,163,184,.45); border-radius: 6px; }
            .economic-scroll::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,.72); }
            .economic-scroll .economic-plot { min-width: max-content; }
            .economic-scroll .economic-bars { position: static; inset: auto; height: 210px; padding: 0 16px; }
            .economic-scroll .economic-labels { min-width: max-content; }
            .economic-legend span { display: inline-flex; align-items: center; gap: 6px; }
            .economic-legend i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
            .priority-dot { width: 8px; height: 8px; border-radius: 999px; display: inline-block; margin-right: 7px; }

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


# ═══════════════════════════════════════════════════════════════════════════
# Helpers de UI, navegação e top bar (seletores Rodovia / Tipo de Matriz / Cenário)
# ═══════════════════════════════════════════════════════════════════════════

def _filter_label(label: str) -> None:
    """Renderiza o rótulo pequeno acima de um filtro da top bar."""
    st.markdown(f'<div class="filter-label">{label}</div>', unsafe_allow_html=True)


def _preselect_road_from_url(roads: list[str]) -> None:
    """Drill-down da Visão geral: aplica ?road=<código> uma vez no seletor (key topbar_road)."""
    nav = st.query_params.get("road")
    if not nav:
        return
    match = next((r for r in roads if _normalize_road_code(r) == _normalize_road_code(nav)), None)
    if match and st.session_state.get("_nav_road_applied") != nav:
        st.session_state["topbar_road"] = match
        st.session_state["_nav_road_applied"] = nav


def _sync_selected_road(selected_road: str | None) -> None:
    """Compartilha a rodovia escolhida entre a Visão geral e as demais telas."""
    if not selected_road:
        return
    st.session_state["topbar_road"] = selected_road
    st.query_params["road"] = _normalize_road_code(selected_road) or selected_road


# "Tipo de Matriz" substitui o antigo seletor "Diagnóstico" (eram o mesmo eixo).
# Cada tipo de matriz mapeia para o diagnóstico/pipeline interno correspondente.
_DIAGNOSIS_TO_MATRIX = {
    "Diagnóstico Paragon": "Paragon",
    "Diagnóstico DNIT": "Matriz Cadastrada",
    "Comparativo Paragon × DNIT": "Comparativo Paragon × DNIT",
}
_MATRIX_TO_DIAGNOSIS = {v: k for k, v in _DIAGNOSIS_TO_MATRIX.items()}


def _short_scenario_label(s: dict | None) -> str:
    """Rótulo CURTO do cenário: '<sentido> · <segmentação>' (ex.: 'CR e DE · SH'),
    em vez do nome longo do banco. Robusto aos dois formatos de `cenario`."""
    if not s:
        return ""
    cen = s.get("cenario") or ""
    segm = re.search(r"\((SH|Fixa|\d+\s*km)\)", cen, re.I)
    seg = segm.group(1) if segm else (s.get("segment_type_label") or "")
    low = cen.lower()
    # Ordem importa: 'cr e de' antes; 'decrescente' antes de 'crescente'
    # (pois "deCRESCENTE" contém "crescente").
    if "cr e de" in low or "cr/de" in low or "ambas" in low:
        sent = "CR e DE"
    elif "decrescente" in low:
        sent = "DECRESCENTE"
    elif "crescente" in low:
        sent = "CRESCENTE"
    elif "todos" in low:
        sent = "TODOS"
    else:
        sent = ""
    # Sentidos isolados exibidos como pista simples (LE/LD), conforme padrão do usuário.
    if sent == "DECRESCENTE":
        return "Pista simples - LE"
    if sent == "CRESCENTE":
        return "Pista simples - LD"
    parts = [p for p in (sent, seg) if p]
    return " · ".join(parts) if parts else (cen or str(s.get("key", "")))


def _network_scenario_label(s: dict | None) -> str:
    """Rótulo do cenário na Visão geral, removendo dados já cobertos por outros filtros.

    Exemplo:
    - "BR-364 (SH) - DECRESCENTE - MATRIZ PARAGON - GATILHO IQO"
    - vira "SH - DECRESCENTE - GATILHO IQO"
    """
    if not s:
        return ""
    cen = str(s.get("cenario") or "").strip()
    if not cen:
        return str(s.get("key", ""))

    low = cen.lower()
    parts: list[str] = []

    segm = re.search(r"\((SH|Fixa|\d+\s*km)\)", cen, re.I)
    if segm:
        parts.append(segm.group(1).strip())
    elif "segmentos homog" in low:
        parts.append("SH")
    elif re.search(r"\bfixa\b", low):
        parts.append("Fixa")

    if "cr e de" in low or "cr/de" in low or "ambas" in low:
        parts.append("CR e DE")
    elif "decrescente" in low:
        parts.append("DECRESCENTE")
    elif "crescente" in low:
        parts.append("CRESCENTE")
    elif "pista: todos" in low or re.search(r"\btodos\b", low):
        parts.append("TODOS")

    gatilho = re.search(r"(GATILHO\s+[A-Z0-9._/-]+)", cen, re.I)
    if gatilho:
        parts.append(gatilho.group(1).upper())

    if parts:
        deduped: list[str] = []
        seen: set[str] = set()
        for part in parts:
            key = part.strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(part.strip())
        return " - ".join(deduped)

    raw_parts = [p.strip() for p in re.split(r"\s+-\s+", cen) if p.strip()]
    filtered = []
    for part in raw_parts:
        plow = part.lower()
        if "matriz paragon" in plow or "matriz revitaliza" in plow or "método de análise" in plow:
            continue
        if plow.startswith("rodovia:"):
            continue
        if re.match(r"^BR-\d+(?:[_-][A-Za-z0-9]+)?(?:\s*\(.+\))?$", part, re.I):
            continue
        filtered.append(part)
    return " - ".join(filtered) if filtered else cen


def render_top_bar(
    selected_road: str,
    *,
    page_title: str = "Diagnóstico Paragon",
    show_diagnosis: bool = True,
    keep_title: bool = False,
    show_filters: bool = True,
    show_scenario: bool = True,
    multi_scenario: bool = False,
    diagnosis_options: list[str] | None = None,
) -> tuple[str, str | None, str | None]:
    """Monta a barra superior (título + seletores) comum a todas as telas.

    Renderiza os filtros de Rodovia, Tipo de Matriz e Cenário conforme os flags
    recebidos, e devolve `(diagnóstico, rodovia, chave_cenário)` — o diagnóstico
    (Paragon / DNIT / Comparativo) é o que decide qual pipeline `main()` chama.
    """
    options = diagnosis_options or ["Diagnóstico Paragon", "Diagnóstico DNIT"]
    # "Tipo de Matriz" é o seletor único; cada opção mapeia para um diagnóstico interno
    # (Paragon ↔ intervencoes_iap, Matriz Cadastrada ↔ intervencoes_dnit/pipeline DNIT).
    matrix_options = [_DIAGNOSIS_TO_MATRIX.get(o, o) for o in options]
    left, right = st.columns([0.82, 1.92], gap="large")
    selected_out: str | None = selected_road
    scenario_key: str | None = None
    diagnosis = page_title

    def _matrix_selectbox() -> str:
        # Selectbox de "Tipo de Matriz" (Paragon / Matriz Cadastrada / Comparativo).
        # Evita exceção do Streamlit quando o valor salvo (ex.: Comparativo) não existe
        # nas opções desta página.
        if st.session_state.get("topbar_matrix_type") not in matrix_options:
            st.session_state.pop("topbar_matrix_type", None)
        choice = st.selectbox(
            "Tipo de Matriz",
            matrix_options,
            key="topbar_matrix_type",
            label_visibility="collapsed",
        )
        return choice

    with right:
        if not show_filters:
            # Modo rede (Visão geral): só o seletor Tipo de Matriz, sem rodovia/cenário.
            if show_diagnosis:
                matriz_col, _spacer = st.columns([0.8, 2.15], gap="small")
                with matriz_col:
                    _filter_label("Tipo de Matriz")
                    matrix_choice = _matrix_selectbox()
                    diagnosis = _MATRIX_TO_DIAGNOSIS.get(matrix_choice, matrix_choice)
            selected_out = None
        else:
            road_col, matriz_col, scenario_col = st.columns([0.8, 0.85, 1.35], gap="small")

            with road_col:
                _filter_label("Rodovias")
                roads = get_available_roads()
                _preselect_road_from_url(roads)
                selected_out = st.selectbox(
                    "Rodovia",
                    roads,
                    key="topbar_road",
                    label_visibility="collapsed",
                )
            with matriz_col:
                _filter_label("Tipo de Matriz")
                matrix_choice = _matrix_selectbox()
            diagnosis = _MATRIX_TO_DIAGNOSIS.get(matrix_choice, matrix_choice)
            # Para listar cenários: Comparativo não tem matriz própria → usa Paragon (oculto).
            matrix_type = matrix_choice if matrix_choice in ("Paragon", "Matriz Cadastrada") else "Paragon"
            if show_scenario:
                scenarios = get_available_scenarios(selected_out, matrix_type)
                with scenario_col:
                    # Comparativo não usa o seletor de Cenários (cada metodologia tem o seu).
                    if diagnosis == "Comparativo Paragon × DNIT":
                        _filter_label("Cenários")
                        st.markdown(
                            '<div class="status-pill" style="margin-top:2px">Auto · Paragon (SH) + DNIT Revitaliza</div>',
                            unsafe_allow_html=True,
                        )
                        scenario_key = None
                    else:
                        _filter_label("Cenários")
                        scenario_keys = [s["key"] for s in scenarios]
                        scen_by_key = {s["key"]: s for s in scenarios}
                        _fmt = lambda k: _short_scenario_label(scen_by_key.get(k))
                        if multi_scenario and scenario_keys:
                            # Campo ÚNICO de cenários (multi): a 1ª seleção dirige os cards;
                            # a lista alimenta o comparativo abaixo (sem 2º campo).
                            sel = st.multiselect(
                                "Cenários",
                                scenario_keys,
                                default=[scenario_keys[0]],
                                format_func=_fmt,
                                key=f"topbar_scen_{selected_out}_{matrix_type}",
                                label_visibility="collapsed",
                            )
                            st.session_state["_topbar_selected_scenarios"] = sel
                            scenario_key = sel[0] if sel else None
                        else:
                            scenario_key = st.selectbox(
                                "Cenário",
                                scenario_keys,
                                format_func=_fmt,
                                label_visibility="collapsed",
                            ) if scenario_keys else None
            else:
                scenario_key = None

    with left:
        st.markdown(
            f"""
            <div class="top-copy">
                <p class="eyebrow">RELATÓRIOS</p>
                <h1 class="page-title">{page_title if (keep_title or not show_diagnosis) else diagnosis}</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return diagnosis, selected_out, scenario_key


def _network_scenario_token(road: str, scenario_key: str) -> str:
    code = _normalize_road_code(road) or str(road)
    return f"{code}::{scenario_key}"


def _parse_network_scenario_token(token: str) -> tuple[str | None, str | None]:
    if not token or "::" not in str(token):
        return None, None
    road_code, scenario_key = str(token).split("::", 1)
    return road_code or None, scenario_key or None


def _network_filter_roads(selected_roads: list[str] | None, diagnosis: str) -> list[str]:
    if selected_roads:
        return selected_roads
    return get_dnit_available_roads() if diagnosis == "Diagnóstico DNIT" else get_available_roads()


def _collect_network_scenario_options(roads: list[str], matrix_type: str) -> list[dict]:
    options: list[dict] = []
    multi_road = len(roads) > 1
    for road in roads:
        for scenario in get_available_scenarios(road, matrix_type):
            short_label = _network_scenario_label(scenario) or str(scenario.get("key", ""))
            display_label = f"{road} - {short_label}" if multi_road else short_label
            options.append(
                {
                    "token": _network_scenario_token(road, str(scenario["key"])),
                    "road": road,
                    "road_code": _normalize_road_code(road),
                    "scenario_key": str(scenario["key"]),
                    "display_label": display_label,
                    "short_label": short_label,
                }
            )
    options.sort(key=lambda item: (str(item["road"]), str(item["display_label"])))
    return options


def _collect_network_year_options(
    roads: list[str],
    matrix_type: str,
    selected_scenario_tokens: list[str] | None,
) -> list[int]:
    years: set[int] = set()
    if selected_scenario_tokens:
        for token in selected_scenario_tokens:
            road_code, scenario_key = _parse_network_scenario_token(token)
            road = next((item for item in roads if _normalize_road_code(item) == road_code), None)
            if not road:
                continue
            years.update(get_available_years(road, matrix_type, scenario_key))
    else:
        for road in roads:
            years.update(get_available_years(road, matrix_type, None))
    return sorted(years)


def render_network_top_bar() -> tuple[str, list[str], list[str], list[int]]:
    """Barra superior da Visão geral com seleção múltipla de rodovia, cenário e ano."""
    options = ["Diagnóstico Paragon", "Diagnóstico DNIT"]
    matrix_options = [_DIAGNOSIS_TO_MATRIX.get(o, o) for o in options]
    left, right = st.columns([0.82, 2.25], gap="large")
    diagnosis = "Visão geral"
    selected_roads: list[str] = []
    selected_scenarios: list[str] = []
    selected_years: list[int] = []

    with right:
        road_col, matriz_col, scenario_col, year_col = st.columns([1.0, 0.9, 1.45, 0.75], gap="small")

        with road_col:
            _filter_label("Rodovia")
            road_options = get_available_roads()
            selected_roads = st.multiselect(
                "Rodovia",
                road_options,
                key="topbar_network_road",
                placeholder="Todas as rodovias",
                label_visibility="collapsed",
            )
            _sync_selected_road(selected_roads[0] if len(selected_roads) == 1 else None)

        with matriz_col:
            _filter_label("Tipo de Matriz")
            if st.session_state.get("topbar_network_matrix_type") not in matrix_options:
                st.session_state.pop("topbar_network_matrix_type", None)
            matrix_choice = st.selectbox(
                "Tipo de Matriz",
                matrix_options,
                key="topbar_network_matrix_type",
                label_visibility="collapsed",
            )
            diagnosis = _MATRIX_TO_DIAGNOSIS.get(matrix_choice, matrix_choice)

        matrix_type = matrix_choice if matrix_choice in ("Paragon", "Matriz Cadastrada") else "Paragon"
        effective_roads = _network_filter_roads(selected_roads, diagnosis)
        scenario_options = _collect_network_scenario_options(effective_roads, matrix_type)
        valid_scenario_tokens = {item["token"] for item in scenario_options}
        if st.session_state.get("topbar_network_scenario_values"):
            st.session_state["topbar_network_scenario_values"] = [
                token for token in st.session_state["topbar_network_scenario_values"]
                if token in valid_scenario_tokens
            ]

        with scenario_col:
            _filter_label("Cenário")
            selected_scenarios = st.multiselect(
                    "Cenário",
                    [item["token"] for item in scenario_options],
                    key="topbar_network_scenario_values",
                    format_func=lambda token: next(
                        (item["display_label"] for item in scenario_options if item["token"] == token),
                        str(token),
                    ),
                    placeholder="Todos os cenários",
                    label_visibility="collapsed",
                )
        year_options = _collect_network_year_options(effective_roads, matrix_type, selected_scenarios)
        if st.session_state.get("topbar_network_year_values"):
            st.session_state["topbar_network_year_values"] = [
                year for year in st.session_state["topbar_network_year_values"]
                if year in year_options
            ]
        with year_col:
            _filter_label("Ano")
            selected_years = st.multiselect(
                    "Ano",
                    year_options,
                    key="topbar_network_year_values",
                    placeholder="Todos os anos",
                    label_visibility="collapsed",
                )

    with left:
        st.markdown(
            """
            <div class="top-copy">
                <p class="eyebrow">RELATÓRIOS</p>
                <h1 class="page-title">Visão geral</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return diagnosis, selected_roads, selected_scenarios, selected_years


def render_diagnosis_top_bar(default_road: str) -> tuple[str, str, str | None, int | None]:
    """Barra superior do Diagnóstico com a mesma lógica visual da Visão geral.

    Usa select único para cenário e adiciona filtro de ano.
    """
    options = ["Diagnóstico Paragon", "Diagnóstico DNIT"]
    matrix_options = [_DIAGNOSIS_TO_MATRIX.get(o, o) for o in options]
    left, right = st.columns([0.82, 2.25], gap="large")
    selected_road = default_road
    scenario_key: str | None = None
    selected_year: int | None = None
    diagnosis = "Diagnóstico Paragon"

    with right:
        road_col, matriz_col, scenario_col, year_col = st.columns([1.0, 0.9, 1.45, 0.75], gap="small")

        def _placeholder(text: str) -> None:
            st.markdown(
                '<div class="filter-placeholder">'
                f'<span class="filter-placeholder-text">{html.escape(text)}</span>'
                '<span class="filter-placeholder-caret">▾</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        with road_col:
            _filter_label("Rodovia")
            roads = get_available_roads()
            _preselect_road_from_url(roads)
            selected_road = st.selectbox(
                "Rodovia",
                roads,
                key="topbar_road",
                label_visibility="collapsed",
            )

        with matriz_col:
            _filter_label("Tipo de Matriz")
            if st.session_state.get("topbar_matrix_type") not in matrix_options:
                st.session_state.pop("topbar_matrix_type", None)
            matrix_choice = st.selectbox(
                "Tipo de Matriz",
                matrix_options,
                key="topbar_matrix_type",
                label_visibility="collapsed",
            )
            diagnosis = _MATRIX_TO_DIAGNOSIS.get(matrix_choice, matrix_choice)

        matrix_type = matrix_choice if matrix_choice in ("Paragon", "Matriz Cadastrada") else "Paragon"
        scenarios = get_available_scenarios(selected_road, matrix_type)
        with scenario_col:
            _filter_label("Cenário")
            if scenarios:
                scenario_keys = [s["key"] for s in scenarios]
                scen_by_key = {s["key"]: s for s in scenarios}
                scenario_key = st.selectbox(
                    "Cenário",
                    scenario_keys,
                    key=f"topbar_diag_scenario_{selected_road}_{matrix_type}",
                    format_func=lambda k: _network_scenario_label(scen_by_key.get(k)),
                    label_visibility="collapsed",
                )
            else:
                _placeholder("Sem cenários para a rodovia")

        years = get_available_years(selected_road, matrix_type, scenario_key)
        with year_col:
            _filter_label("Ano")
            if years:
                selected_year = st.selectbox(
                    "Ano",
                    years,
                    key=f"topbar_diag_year_{selected_road}_{matrix_type}_{scenario_key or 'default'}",
                    label_visibility="collapsed",
                )
            else:
                _placeholder("Sem anos")

    with left:
        st.markdown(
            """
            <div class="top-copy">
                <p class="eyebrow">RELATÓRIOS</p>
                <h1 class="page-title">Diagnóstico</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return diagnosis, selected_road, scenario_key, selected_year


def render_solution_top_bar(default_road: str) -> tuple[str, str, str | None, int | None]:
    """Barra superior da tela Soluções com cenário em seleção única.

    Mantém a mesma leitura visual das outras telas, mas trabalha só com os filtros
    mestres desta página: rodovia e cenário.
    """
    options = ["Diagnóstico Paragon", "Diagnóstico DNIT"]
    matrix_options = [_DIAGNOSIS_TO_MATRIX.get(o, o) for o in options]
    left, right = st.columns([0.82, 2.25], gap="large")
    selected_road = default_road
    scenario_key: str | None = None
    selected_year: int | None = None
    diagnosis = "Diagnóstico Paragon"

    with right:
        road_col, matriz_col, scenario_col, year_col = st.columns([1.0, 0.9, 1.45, 0.75], gap="small")

        def _placeholder(text: str) -> None:
            st.markdown(
                '<div class="filter-placeholder">'
                f'<span class="filter-placeholder-text">{html.escape(text)}</span>'
                '<span class="filter-placeholder-caret">▾</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        with road_col:
            _filter_label("Rodovia")
            roads = get_available_roads()
            _preselect_road_from_url(roads)
            selected_road = st.selectbox(
                "Rodovia",
                roads,
                key="topbar_solution_road",
                label_visibility="collapsed",
            )
            _sync_selected_road(selected_road)

        with matriz_col:
            _filter_label("Tipo de Matriz")
            if st.session_state.get("topbar_solution_matrix_type") not in matrix_options:
                st.session_state.pop("topbar_solution_matrix_type", None)
            matrix_choice = st.selectbox(
                "Tipo de Matriz",
                matrix_options,
                key="topbar_solution_matrix_type",
                label_visibility="collapsed",
            )
            diagnosis = _MATRIX_TO_DIAGNOSIS.get(matrix_choice, matrix_choice)

        matrix_type = matrix_choice if matrix_choice in ("Paragon", "Matriz Cadastrada") else "Paragon"
        scenarios = get_available_scenarios(selected_road, matrix_type)
        with scenario_col:
            _filter_label("Cenário")
            if scenarios:
                scenario_keys = [s["key"] for s in scenarios]
                scen_by_key = {s["key"]: s for s in scenarios}
                scenario_key = st.selectbox(
                    "Cenário",
                    scenario_keys,
                    key=f"topbar_solution_scenario_{selected_road}_{matrix_type}",
                    format_func=lambda k: _network_scenario_label(scen_by_key.get(k)),
                    label_visibility="collapsed",
                )
            else:
                _placeholder("Sem cenários para a rodovia")

        years = get_available_years(selected_road, matrix_type, scenario_key)
        with year_col:
            _filter_label("Ano")
            if years:
                selected_year = st.selectbox(
                    "Ano",
                    years,
                    key=f"topbar_solution_year_{selected_road}_{matrix_type}_{scenario_key or 'default'}",
                    label_visibility="collapsed",
                )
            else:
                _placeholder("Sem anos")

    with left:
        st.markdown(
            """
            <div class="top-copy">
                <p class="eyebrow">RELATÓRIOS</p>
                <h1 class="page-title">Soluções</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return diagnosis, selected_road, scenario_key, selected_year


def render_metric_cards(cards: list[dict]) -> None:
    """Renderiza uma linha de cards de métrica (KPIs) lado a lado."""
    columns = st.columns(len(cards), gap="medium")
    for column, card in zip(columns, cards):
        with column:
            render_metric_card(card)


def _format_km(value: float) -> str:
    """Formata quilometragem com 2 casas e vírgula decimal (padrão pt-BR)."""
    return f"{value:.2f}".replace(".", ",")


def _filter_caption(label: str) -> None:
    """Renderiza o rótulo pequeno de um filtro na página de Soluções."""
    st.markdown(f'<div class="solution-filter-label">{html.escape(label)}</div>', unsafe_allow_html=True)


def _diagnosis_km_range_from_state(diagram_df: pd.DataFrame | None, key: str) -> tuple[float, float] | None:
    """Lê do estado atual a faixa de km escolhida no diagrama, se existir."""
    if diagram_df is None or diagram_df.empty:
        return None
    full_min = float(diagram_df["km_inicial"].min())
    full_max = float(diagram_df["km_final"].max())
    slider_min = float(int(full_min))
    slider_max = float(int(full_max) + (1 if full_max > int(full_max) else 0))
    if slider_max <= slider_min:
        slider_max = slider_min + 1.0
    slider_key = f"{key}_{slider_min:.0f}_{slider_max:.0f}"
    value = st.session_state.get(slider_key)
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return float(value[0]), float(value[1])
    return slider_min, slider_max


def _filter_by_km_range(df: pd.DataFrame | None, km_range: tuple[float, float] | None) -> pd.DataFrame:
    if df is None or df.empty or km_range is None:
        return df.copy() if df is not None else pd.DataFrame()
    return df[(df["km_final"] >= km_range[0]) & (df["km_inicial"] <= km_range[1])].copy()


def _filter_by_iap_class(
    df: pd.DataFrame | None,
    selected_class: str | None,
    *,
    class_col: str = "classe_iap",
) -> pd.DataFrame:
    if df is None or df.empty or not selected_class or selected_class == "Todas":
        return df.copy() if df is not None else pd.DataFrame()
    if class_col not in df.columns:
        return df.copy()
    return df[df[class_col].astype(str) == selected_class].copy()


def _build_distribution_from_linear(diagram_df: pd.DataFrame | None) -> pd.DataFrame:
    if diagram_df is None or diagram_df.empty:
        return pd.DataFrame()
    work = diagram_df.copy()
    grouped = (
        work.groupby(["classe_iap", "cor_iap"], as_index=False)["extensao"]
        .sum()
        .rename(columns={"classe_iap": "classe", "cor_iap": "color", "extensao": "km"})
    )
    total_km = float(grouped["km"].sum()) or 1.0
    grouped["percentual"] = grouped["km"].astype(float) / total_km * 100
    grouped["_ord"] = grouped["classe"].apply(
        lambda value: _IAP_CLASS_ORDER.index(value) if value in _IAP_CLASS_ORDER else 99
    )
    return grouped.sort_values("_ord")[["classe", "km", "percentual", "color"]].reset_index(drop=True)


def _weighted_metric_from_segments(
    segments_df: pd.DataFrame | None,
    value_col: str,
    fallback: float,
) -> float:
    if segments_df is None or segments_df.empty or value_col not in segments_df.columns:
        return fallback
    ext = (segments_df["km_final"].astype(float) - segments_df["km_inicial"].astype(float)).clip(lower=0)
    total_ext = float(ext.sum())
    if total_ext <= 0:
        return fallback
    values = pd.to_numeric(segments_df[value_col], errors="coerce").fillna(0.0)
    return float((values * ext).sum() / total_ext)


def _weighted_iap_from_linear(diagram_df: pd.DataFrame | None, fallback: float) -> float:
    if diagram_df is None or diagram_df.empty:
        return fallback
    total_ext = float(diagram_df["extensao"].astype(float).sum())
    if total_ext <= 0:
        return fallback
    return float((diagram_df["iap"].astype(float) * diagram_df["extensao"].astype(float)).sum() / total_ext)


def _render_diagnosis_iap_class_filter(
    distribution_df: pd.DataFrame,
    *,
    key: str,
    class_order: list[str] | None = None,
) -> str:
    class_order = class_order or _IAP_CLASS_ORDER
    options = ["Todas"]
    if distribution_df is not None and not distribution_df.empty:
        options.extend(
            [cls for cls in class_order if cls in set(distribution_df["classe"].astype(str))]
        )
    current = st.session_state.get(key, "Todas")
    if current not in options:
        st.session_state[key] = "Todas"
    return st.radio(
        "Faixa do gráfico",
        options,
        key=key,
        horizontal=True,
        label_visibility="collapsed",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Página: SOLUÇÕES (Paragon) — "o que fazer" (matriz de priorização + distribuição)
# ═══════════════════════════════════════════════════════════════════════════

def _render_solution_filters(table_df):
    """Renderiza os filtros da tela de Soluções (SRE, Conceito IAP, Tipo de solução)
    e devolve a tabela já filtrada pelas seleções do usuário."""
    if table_df is None or table_df.empty:
        return table_df

    sre_options = sorted(str(value) for value in table_df["SNV"].dropna().unique())
    # Ordem canônica dos conceitos IAP, do melhor ao pior (ver README §11 / §12.1).
    iap_class_order = ["Excelente", "Bom", "++ Regular", "+ Regular", "- Regular", "Mau", "Péssimo"]
    iap_options = [
        label
        for label in iap_class_order
        if label in set(table_df["_classe_iap"].dropna().astype(str))
    ]
    solution_options = sorted(
        str(value)
        for value in table_df["Solução recomendada"].dropna().unique()
        if str(value) != "Sem intervenção"
    )

    first_row = st.columns([1, 1, 1], gap="medium")
    with first_row[0]:
        _filter_caption("SRE")
        selected_sre = st.multiselect(
            "SRE",
            sre_options,
            placeholder="Todos os SREs",
            label_visibility="collapsed",
        )
    with first_row[1]:
        _filter_caption("Conceito IAP")
        selected_iap_classes = st.multiselect(
            "Conceito IAP",
            iap_options,
            placeholder="Todos os conceitos",
            label_visibility="collapsed",
        )
    with first_row[2]:
        _filter_caption("Tipo de solução")
        selected_solutions = st.multiselect(
            "Tipo de solução",
            solution_options,
            placeholder="Todas as soluções",
            label_visibility="collapsed",
        )

    filtered = table_df.copy()
    if selected_sre:
        filtered = filtered[filtered["SNV"].astype(str).isin(selected_sre)]
    if selected_iap_classes:
        filtered = filtered[filtered["_classe_iap"].astype(str).isin(selected_iap_classes)]
    if selected_solutions:
        filtered = filtered[filtered["Solução recomendada"].astype(str).isin(selected_solutions)]

    return filtered


def _render_solution_filter_panel(table_df):
    """Alias fino para `_render_solution_filters` (mantido por compatibilidade)."""
    return _render_solution_filters(table_df)


def _solution_table_to_excel(table_df) -> bytes:
    """Serializa a matriz de priorização Paragon num .xlsx estilizado (bytes)."""
    export_columns = [
        "SNV",
        "Km Inicial",
        "Km Final",
        "Extensão",
        "IAP",
        "IRI",
        "IGG",
        "Solução recomendada",
    ]
    output = BytesIO()
    export_df = table_df[export_columns].copy()
    with st.spinner("Preparando Excel..."):
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Matriz")
            workbook = writer.book
            worksheet = writer.sheets["Matriz"]
            header_format = workbook.add_format(
                {"bold": True, "bg_color": "#0b1d28", "font_color": "#ffffff", "border": 1}
            )
            number_format = workbook.add_format({"num_format": "0.00"})
            for col_index, column in enumerate(export_df.columns):
                worksheet.write(0, col_index, column, header_format)
                width = max(12, min(42, int(export_df[column].astype(str).str.len().max() or 12) + 2))
                worksheet.set_column(col_index, col_index, width)
            for column in ["Km Inicial", "Km Final", "Extensão", "IAP", "IRI", "IGG"]:
                col_index = export_df.columns.get_loc(column)
                worksheet.set_column(col_index, col_index, 12, number_format)
    return output.getvalue()


def _render_export_button(table_df) -> None:
    """Botão de download da matriz Paragon em Excel (oculto se não houver dados)."""
    if table_df is None or table_df.empty:
        return

    st.download_button(
        "Exportar Excel",
        data=_solution_table_to_excel(table_df),
        file_name="matriz_priorizacao_paragon.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )


def _solution_color(label: str) -> str:
    """Cor (hex) de uma solução Paragon a partir do NOME exibido.

    REGRA HARDCODED (README §11.4): a cor é decidida por SUBSTRING do rótulo, na
    ordem abaixo (mais específico primeiro). É frágil — renomear uma solução pode
    quebrar a cor silenciosamente. A paleta é a mesma dos conceitos IAP e está
    repetida em ≥4 arquivos (overview_service/overview_map/linear_diagram).
    """
    normalized = label.lower()
    if "sem intervenção" in normalized or "monitor" in normalized:
        return "#9fb9d9"  # OK / monitorar — cinza-azulado
    if "reconstrução" in normalized or "reconstrucao" in normalized:
        return "#d71920"  # REC — Péssimo (vermelho)
    if "fresagem" in normalized and "reforço" in normalized:
        return "#f2a51a"  # RPS+REF — Mau (laranja)
    if "fresagem" in normalized:
        return "#fff200"  # RPS — - Regular (amarelo)
    if "reparo localizado" in normalized and "reforço" in normalized:
        return "#f4f1a6"  # RL+REF — + Regular
    if "microrrevestimento" in normalized and "reparo localizado" in normalized:
        return "#b6d7a8"  # RL+RS — ++ Regular
    if "microrrevestimento" in normalized:
        return "#b6d7a8"
    # RL+RS — rótulo Paragon agora exibido como "Recarga Superficial".
    if "recarga superficial" in normalized:
        return "#b6d7a8"
    if "reparo localizado" in normalized or normalized.startswith("rl"):
        return "#00a651"  # RL — Bom (verde)
    if "reforço" in normalized:
        return "#f4f1a6"
    return "#00a651"  # fallback: verde (Bom)


def _render_solution_distribution(
    table_df,
    total_km: float | None = None,
    plan_cost_mi: float | None = None,
    *,
    group_col: str = "Solução recomendada",
    subtitle: str = "Engenharia aplicada · catálogo paramétrico Paragon",
    color_fn=None,
) -> None:
    """Gráfico de barras (HTML) com a distribuição de km por tipo de solução na rede."""
    if table_df is None or table_df.empty:
        return

    color_fn = color_fn or _solution_color
    grouped = (
        table_df.groupby(group_col, as_index=False)["Extensão"]
        .sum()
        .sort_values("Extensão", ascending=False)
    )
    total_extension = float(total_km or table_df["Extensão"].sum() or 0)
    if total_extension <= 0:
        return

    max_percent = max(float(grouped["Extensão"].max()) / total_extension * 100, 1)
    axis_max = _axis_max_10(max_percent)
    ticks = _axis_ticks_10(axis_max)

    tick_markup = "".join(
        f'<span class="solution-y-tick" style="bottom:{tick / axis_max * 100:.2f}%;">{tick:.0f}</span>'
        for tick in ticks
    )

    bars = []
    labels = []
    for row in grouped.to_dict("records"):
        label = str(row[group_col])
        km = float(row["Extensão"])
        percent = km / total_extension * 100
        height = max(percent / axis_max * 100, 2)
        color = color_fn(label)
        bars.append(
            '<div class="solution-bar-item">'
            f'<div class="solution-bar" style="height:{height:.2f}%;background:{color};">'
            f'<span class="solution-bar-value">{percent:.1f}%<span>{km:.1f} km</span></span>'
            '</div>'
            '</div>'
        )
        labels.append(f'<div class="solution-bar-label">{html.escape(label)}</div>')

    cost_markup = (
        f'<span>Custo <strong class="accent">R$ {plan_cost_mi:.1f} mi</strong></span>'
        if plan_cost_mi is not None
        else ""
    )
    markup = (
        '<div class="solution-distribution">'
        '<div class="solution-distribution-head">'
        '<div class="solution-distribution-title">'
        '<div class="solution-distribution-icon">≋</div>'
        '<div><h3>Distribuição de soluções na rede</h3>'
        f'<p>{html.escape(subtitle)}</p></div>'
        '</div>'
        '<div class="solution-distribution-meta">'
        f'<span>Total · <strong>{total_extension:.1f} km</strong></span>'
        f'{cost_markup}'
        '</div>'
        '</div>'
        '<div class="solution-bars">'
        f'<div class="solution-y-axis">{tick_markup}</div>'
        '<div class="solution-chart-area">'
        '<div class="solution-chart-plot">'
        f'<div class="solution-bar-grid">{"".join(bars)}</div>'
        '</div>'
        f'<div class="solution-label-grid">{"".join(labels)}</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.markdown(markup, unsafe_allow_html=True)


def _solutions_sentido_keys(road, topbar_key, widget_key="sol_scen", matrix_type="Paragon"):
    """Multiselect de cenários (sentidos). Devolve (keys, labels).
    Default = CRESCENTE + DECRESCENTE se existirem; senão o cenário do topo."""
    scenarios = get_available_scenarios(road, matrix_type)
    labels = {s["key"]: s["cenario"] for s in scenarios}
    by_key = {s["key"]: s for s in scenarios}
    keys = [s["key"] for s in scenarios]
    if not keys:
        return ([topbar_key] if topbar_key else []), labels
    cr = next((k for k in keys if "crescente" in labels[k].lower()
               and "decrescente" not in labels[k].lower()), None)
    de = next((k for k in keys if "decrescente" in labels[k].lower()), None)
    default = [k for k in (cr, de) if k] or ([topbar_key] if topbar_key in keys else keys[:1])
    _filter_caption("Cenários (sentidos) — selecione um ou mais")
    selected = st.multiselect(
        "Cenários (sentidos)", keys, default=default,
        format_func=lambda k: _short_scenario_label(by_key.get(k)),  # nome curto (igual às outras telas)
        key=f"{widget_key}_{road}", label_visibility="collapsed",
    )
    return (selected or default), labels


def _combined_solution_data(road, keys, labels):
    """Tabela e segmentos combinados de vários cenários, com coluna/atributo de
    Sentido e os segmentos deslocados (uma camada por sentido) para o mapa."""
    tables, segs = [], []
    n = len(keys)
    for i, k in enumerate(keys):
        d = get_solutions_data(road, scenario_key=k)
        t, s = d.get("table"), d.get("segments")
        sent = _sentido_faixa(labels.get(k, k))
        if t is not None and not t.empty:
            t = t.copy()
            t["Sentido"] = sent
            tables.append(t)
        if s is not None and not s.empty:
            s = s.copy()
            s["offset_side"] = (i - (n - 1) / 2.0)  # lado p/ offset por pixel (zoom-aware) no mapa
            s["sentido"] = sent
            segs.append(s)
    return (
        pd.concat(tables, ignore_index=True) if tables else None,
        pd.concat(segs, ignore_index=True) if segs else None,
    )


def _sentido_bar_bg(color: str, idx: int) -> str:
    """Fundo da barra mantendo a COR DA SOLUÇÃO; o sentido é distinguido por padrão:
    1º sentido sólido, demais com listras diagonais (vãos transparentes)."""
    if idx <= 0:
        return color
    angle = 45 if idx % 2 == 1 else -45
    return (
        f"repeating-linear-gradient({angle}deg, {color} 0, {color} 5px, "
        "transparent 5px, transparent 10px)"
    )


def _render_solution_distribution_by_sentido(table_df) -> None:
    """Distribuição de soluções com BARRAS POR SENTIDO (um gráfico só: para cada
    solução, uma barra por sentido)."""
    if table_df is None or table_df.empty or "Sentido" not in table_df.columns:
        _render_solution_distribution(table_df)
        return
    g = table_df.groupby(["Solução recomendada", "Sentido"], as_index=False)["Extensão"].sum()
    solucoes = list(
        g.groupby("Solução recomendada")["Extensão"].sum().sort_values(ascending=False).index
    )
    sentidos = list(dict.fromkeys(table_df["Sentido"].tolist()))
    sent_idx = {s: i for i, s in enumerate(sentidos)}
    pivot = {sol: {} for sol in solucoes}
    for r in g.to_dict("records"):
        pivot[r["Solução recomendada"]][r["Sentido"]] = float(r["Extensão"])
    max_km = max((max(d.values()) for d in pivot.values() if d), default=1.0) or 1.0
    axis_max = _axis_max_headroom(max_km)
    ticks = _axis_ticks_10(axis_max)
    tick_markup = "".join(
        f'<span class="solution-y-tick" style="bottom:{t / axis_max * 100:.2f}%;">{t:.0f}</span>'
        for t in ticks
    )
    groups, labels = [], []
    for sol in solucoes:
        col = _solution_color(sol)
        bars = ""
        for sent in sentidos:
            km = pivot[sol].get(sent, 0.0)
            h = max(km / axis_max * 100, 1.5) if km > 0 else 0.0
            bars += (
                f'<div class="solution-bar" style="height:{h:.2f}%;'
                f'background:{_sentido_bar_bg(col, sent_idx[sent])};'
                'min-width:22px;width:auto;flex:0 0 auto">'
                f'<span class="solution-bar-value">{km:.1f}<span>km</span></span></div>'
            )
        groups.append(
            '<div class="solution-bar-item" style="display:flex;gap:8px;'
            f'align-items:flex-end;justify-content:center">{bars}</div>'
        )
        labels.append(f'<div class="solution-bar-label">{html.escape(str(sol))}</div>')
    legend = "".join(
        '<span style="display:inline-flex;align-items:center;gap:6px;font-size:12px;'
        f'color:#cbd5df;margin:0 14px 0 0"><span style="width:12px;height:12px;border-radius:3px;'
        f'background:{_sentido_bar_bg("#cbd5df", sent_idx[s])};display:inline-block"></span>'
        f'{html.escape(s)}</span>'
        for s in sentidos
    )
    markup = (
        '<div class="solution-distribution">'
        '<div class="solution-distribution-head">'
        '<div class="solution-distribution-title">'
        '<div class="solution-distribution-icon">≋</div>'
        '<div><h3>Distribuição de soluções por sentido</h3>'
        '<p>Extensão (km) de cada solução, por sentido</p></div>'
        '</div>'
        f'<div class="solution-distribution-meta">{legend}</div>'
        '</div>'
        '<div class="solution-bars">'
        f'<div class="solution-y-axis">{tick_markup}</div>'
        '<div class="solution-chart-area">'
        '<div class="solution-chart-plot">'
        f'<div class="solution-bar-grid">{"".join(groups)}</div>'
        '</div>'
        f'<div class="solution-label-grid">{"".join(labels)}</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.markdown(markup, unsafe_allow_html=True)


def _render_solutions_table(table_df) -> None:
    """Renderiza a tabela HTML da Matriz de Paragon (um trecho por linha, com pill de IAP)."""
    if table_df is None or table_df.empty:
        st.info("Sem trechos para exibir na matriz.")
        return

    has_sentido = "Sentido" in table_df.columns
    # Ordena por sentido e, dentro de cada sentido, por km crescente (início, fim).
    table_df = table_df.assign(
        _ki=table_df["Km Inicial"].astype(float),
        _kf=table_df["Km Final"].astype(float),
    ).sort_values(
        (["Sentido"] if has_sentido else []) + ["_ki", "_kf"], kind="stable"
    )
    rows_markup = []
    for index, row in enumerate(table_df.to_dict("records"), start=1):
        iap_color = html.escape(str(row.get("_cor_iap", "#fff200")))
        iap_class = html.escape(str(row.get("_classe_iap", "")))
        sentido_td = (
            f"<td>{html.escape(str(row.get('Sentido', '')))}</td>" if has_sentido else ""
        )
        rows_markup.append(
            "<tr>"
            f"<td class='muted'>{index}</td>"
            f"<td class='mono'>{html.escape(str(row['SNV']))}</td>"
            + sentido_td +
            f"<td>{_format_km(float(row['Km Inicial']))}</td>"
            f"<td>{_format_km(float(row['Km Final']))}</td>"
            f"<td>{_format_km(float(row['Extensão']))} km</td>"
            f"<td><span class='iap-pill'><span class='iap-pill-dot' style='background:{iap_color}'></span>{float(row['IAP']):.2f} <span class='muted'>{iap_class}</span></span></td>"
            f"<td>{html.escape(str(row['Solução recomendada']))}</td>"
            "</tr>"
        )

    st.markdown(
        """
        <section class="solution-card">
          <div class="solution-card-head">
            <h3>Matriz de Paragon</h3>
            <p>""" + str(len(table_df)) + """ trechos encontrados conforme filtros aplicados</p>
          </div>
          <div class="solution-table-wrap">
            <table class="solution-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>SRE</th>""" + ("<th>Sentido</th>" if has_sentido else "") + """
                  <th>Km Inicial</th>
                  <th>Km Final</th>
                  <th>Extensão</th>
                  <th>IAP</th>
                  <th>Solução recomendada</th>
                </tr>
              </thead>
              <tbody>
        """
        + "".join(rows_markup)
        + """
              </tbody>
            </table>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_solution_table_controls(filtered_table, *, export_fn=None):
    """Controles da tabela de soluções: botão de exportação + paginação.
    Devolve (tabela_completa_filtrada, página_atual) para renderização."""
    export_fn = export_fn or _render_export_button
    st.markdown('<div class="solution-panel-spacer"></div>', unsafe_allow_html=True)
    action_col, page_size_col, page_col, summary_col = st.columns([0.72, 0.62, 0.45, 1.35], gap="medium")
    with action_col:
        _filter_caption("Exportação")
        export_fn(filtered_table)

    if filtered_table is None or filtered_table.empty:
        with summary_col:
            st.markdown(
                '<div class="pagination-summary">Nenhum registro encontrado para os filtros aplicados.</div>',
                unsafe_allow_html=True,
            )
        return filtered_table, filtered_table

    total_rows = len(filtered_table)
    page_size_options = [25, 50, 100, "Todos"]
    with page_size_col:
        _filter_caption("Registros por página")
        page_size = st.selectbox(
            "Registros por página",
            page_size_options,
            index=0,
            label_visibility="collapsed",
        )

    if page_size == "Todos":
        with summary_col:
            st.markdown(
                f'<div class="pagination-summary">Exibindo todos os {total_rows} registros filtrados.</div>',
                unsafe_allow_html=True,
            )
        return filtered_table, filtered_table.reset_index(drop=True)

    total_pages = max(1, (total_rows + int(page_size) - 1) // int(page_size))
    with page_col:
        _filter_caption("Página")
        page_number = st.number_input(
            "Página",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            label_visibility="collapsed",
        )

    start = (int(page_number) - 1) * int(page_size)
    end = min(start + int(page_size), total_rows)
    with summary_col:
        st.markdown(
            f'<div class="pagination-summary">Exibindo {start + 1}-{end} de {total_rows} registros filtrados.</div>',
            unsafe_allow_html=True,
        )

    return filtered_table, filtered_table.iloc[start:end].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════
# Página: SOLUÇÕES (DNIT / Matriz Cadastrada) — versão _dnit_* da tela de soluções
# ═══════════════════════════════════════════════════════════════════════════

def _dnit_group_color(label: str) -> str:
    """Cor do grupo de solução DNIT (paleta `_DNIT_GROUP_COLORS`; fallback cinza)."""
    return _DNIT_GROUP_COLORS.get(str(label), "#9fb9d9")


def _dnit_core_color(label: str) -> str:
    """Cor da barra pela severidade do núcleo da solução (Micro=verde, FR5+CBUQ=laranja, REC=vermelho)."""
    return _DNIT_GROUP_COLORS.get(_dnit_solution_group([str(label)]), "#9fb9d9")


def _render_dnit_solution_filters(table_df, zona_order):
    """Filtros da tela de Soluções DNIT (SRE, Faixa IRI, Tipo de solução) e devolve
    a tabela filtrada. `zona_order` fixa a ordem das faixas de IRI (ver README §12.4)."""
    if table_df is None or table_df.empty:
        return table_df

    sre_options = sorted(str(v) for v in table_df["SNV"].dropna().unique())
    faixa_present = set(table_df["Faixa"].dropna().astype(str))
    faixa_options = [z for z in zona_order if z in faixa_present]
    solucao_options = sorted(str(v) for v in table_df["Solução núcleo"].dropna().unique())

    first_row = st.columns([1, 1, 1], gap="medium")
    with first_row[0]:
        _filter_caption("SRE")
        selected_sre = st.multiselect(
            "SRE", sre_options, placeholder="Todos os SREs", label_visibility="collapsed"
        )
    with first_row[1]:
        _filter_caption("Faixa IRI (matriz)")
        selected_faixa = st.multiselect(
            "Faixa IRI", faixa_options, placeholder="Todas as faixas", label_visibility="collapsed"
        )
    with first_row[2]:
        _filter_caption("Tipo de solução")
        selected_solucao = st.multiselect(
            "Tipo de solução", solucao_options, placeholder="Todas as soluções", label_visibility="collapsed"
        )

    filtered = table_df.copy()
    if selected_sre:
        filtered = filtered[filtered["SNV"].astype(str).isin(selected_sre)]
    if selected_faixa:
        filtered = filtered[filtered["Faixa"].astype(str).isin(selected_faixa)]
    if selected_solucao:
        filtered = filtered[filtered["Solução núcleo"].astype(str).isin(selected_solucao)]
    return filtered


def _dnit_solution_table_to_excel(table_df) -> bytes:
    """Serializa a matriz Revitaliza DNIT/RO num .xlsx estilizado (bytes)."""
    export_columns = [
        "SNV", "Km Inicial", "Km Final", "Extensão",
        "IRI", "IGG", "Faixa", "Solução recomendada",
    ]
    output = BytesIO()
    export_df = table_df[export_columns].copy()
    with st.spinner("Preparando Excel..."):
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Soluções DNIT")
            workbook = writer.book
            worksheet = writer.sheets["Soluções DNIT"]
            header_format = workbook.add_format(
                {"bold": True, "bg_color": "#0b1d28", "font_color": "#ffffff", "border": 1}
            )
            number_format = workbook.add_format({"num_format": "0.00"})
            for col_index, column in enumerate(export_df.columns):
                worksheet.write(0, col_index, column, header_format)
                width = max(12, min(48, int(export_df[column].astype(str).str.len().max() or 12) + 2))
                worksheet.set_column(col_index, col_index, width)
            for column in ["Km Inicial", "Km Final", "Extensão", "IRI", "IGG"]:
                col_index = export_df.columns.get_loc(column)
                worksheet.set_column(col_index, col_index, 12, number_format)
    return output.getvalue()


def _render_dnit_export_button(table_df) -> None:
    """Botão de download da matriz DNIT em Excel (oculto se não houver dados)."""
    if table_df is None or table_df.empty:
        return
    st.download_button(
        "Exportar Excel",
        data=_dnit_solution_table_to_excel(table_df),
        file_name="solucoes_dnit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )


def _render_dnit_solutions_table(table_df) -> None:
    """Renderiza a tabela HTML da Matriz Revitaliza DNIT/RO (um trecho por linha)."""
    if table_df is None or table_df.empty:
        st.info("Sem trechos para exibir na matriz DNIT.")
        return

    rows_markup = []
    for index, row in enumerate(table_df.to_dict("records"), start=1):
        faixa_color = html.escape(str(row.get("_zona_color", "#fff200")))
        faixa = html.escape(str(row.get("Faixa", "")))
        rows_markup.append(
            "<tr>"
            f"<td class='muted'>{index}</td>"
            f"<td class='mono'>{html.escape(str(row['SNV']))}</td>"
            f"<td>{_format_km(float(row['Km Inicial']))}</td>"
            f"<td>{_format_km(float(row['Km Final']))}</td>"
            f"<td>{_format_km(float(row['Extensão']))} km</td>"
            f"<td><span class='iap-pill'><span class='iap-pill-dot' style='background:{faixa_color}'></span>{faixa}</span></td>"
            f"<td>{float(row['IRI']):.2f}</td>"
            f"<td>{float(row['IGG']):.2f}</td>"
            f"<td style='white-space:normal;min-width:260px'>{html.escape(str(row['Solução recomendada']))}</td>"
            "</tr>"
        )

    st.markdown(
        """
        <section class="solution-card">
          <div class="solution-card-head">
            <h3>Matriz Revitaliza DNIT/RO</h3>
            <p>""" + str(len(table_df)) + """ trechos encontrados conforme filtros aplicados</p>
          </div>
          <div class="solution-table-wrap">
            <table class="solution-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>SRE</th>
                  <th>Km Inicial</th>
                  <th>Km Final</th>
                  <th>Extensão</th>
                  <th>Faixa IRI</th>
                  <th>IRI</th>
                  <th>IGG</th>
                  <th>Solução recomendada</th>
                </tr>
              </thead>
              <tbody>
        """
        + "".join(rows_markup)
        + """
              </tbody>
            </table>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_dnit_solutions_page(road, scenario_key) -> None:
    """Monta a página inteira de Soluções DNIT: mapa + distribuição + tabela paginada.
    Só rodovias processadas com a Matriz Revitaliza DNIT/RO têm esses dados; as demais
    caem no diagnóstico Paragon (mensagem informativa ao usuário)."""
    data = get_dnit_solutions_data(road, scenario_key=scenario_key)
    if not data or not data.get("available") or data.get("table") is None or data["table"].empty:
        disponiveis = get_dnit_available_roads()
        if disponiveis:
            quais = ", ".join(f"**{r}**" for r in disponiveis)
            st.info(
                f"Esta rodovia não foi processada com a **Matriz Revitaliza DNIT/RO**. "
                f"No banco, {quais} possui(em) esse cálculo; as demais usam o diagnóstico **Paragon**."
            )
        else:
            st.info("Nenhuma rodovia foi processada com a **Matriz Revitaliza DNIT/RO** ainda.")
        return

    st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
    filtered_table = _render_dnit_solution_filters(data["table"], data["zona_order"])
    filtered_segments = _filter_map_segments(data["segments"], filtered_table)
    render_dnit_map(filtered_segments, zona_colors=data["zona_colors"], zona_order=data["zona_order"])
    nucleo_iri_color = {
        str(nucleo): sub["_zona_color"].mode().iloc[0]
        for nucleo, sub in filtered_table.groupby("Solução núcleo")
        if "_zona_color" in sub.columns and not sub["_zona_color"].mode().empty
    } if filtered_table is not None and not filtered_table.empty else {}
    _render_solution_distribution(
        filtered_table,
        group_col="Solução núcleo",
        subtitle="Soluções aplicadas · Matriz Revitaliza DNIT/RO (gravadas no banco)",
        color_fn=lambda label: nucleo_iri_color.get(str(label), "#9fb9d9"),
    )
    _, paginated_table = _render_solution_table_controls(filtered_table, export_fn=_render_dnit_export_button)
    _render_dnit_solutions_table(paginated_table)


# ═══════════════════════════════════════════════════════════════════════════
# Página: CENÁRIO ECONÔMICO — "quanto custa" (custos, orçamento, simulação, mapa)
# Regras hardcoded desta seção catalogadas no README §14.
# ═══════════════════════════════════════════════════════════════════════════

# Custo paramétrico por km, por CÓDIGO de solução (README §14.1). É apenas FALLBACK:
# só é usado quando o trecho não tem orçamento real gravado no banco. R$/km.
_ECONOMIC_SOLUTION_COST_KM = {
    "OK": 0,
    "RL": 180_000,
    "RL+RS": 280_000,
    "RL+REF": 420_000,
    "RPS": 680_000,
    "RPS+REF": 920_000,
    "REC": 1_250_000,
    "Sem intervenção": 0,
}

# Ordem de prioridade das soluções por ESTRATÉGIA (menor número = atendido primeiro
# quando o orçamento é escasso). Na prática a UI expõe só "Balanceada"; Corretiva
# (prioriza reconstruir o pior) e Preventiva (prioriza barato/muitos km) existem mas
# não estão expostas (README §14.2).
_ECONOMIC_STRATEGY_ORDER = {
    "Corretiva": {"REC": 1, "RPS+REF": 2, "RPS": 3, "RL+REF": 4, "RL+RS": 5, "RL": 6, "OK": 7},
    "Preventiva": {"RL": 1, "RL+RS": 2, "RL+REF": 3, "RPS": 4, "RPS+REF": 5, "REC": 6, "OK": 7},
    "Balanceada": {"REC": 1, "RPS": 2, "RL+RS": 3, "RPS+REF": 4, "RL+REF": 5, "RL": 6, "OK": 7},
}
# Ano-base do cenário econômico: o horizonte cobre [_ECONOMIC_BASE_YEAR, _ECONOMIC_BASE_YEAR + horizonte - 1].
_ECONOMIC_BASE_YEAR = 2026
# Horizonte padrão (anos) — usado no slider do cenário econômico E no custo da Visão geral,
# pra os dois mostrarem a mesma necessidade por rodovia.
_ECONOMIC_DEFAULT_HORIZON = 8


def _limit_budget_to_horizon(budget_items, horizon: int):
    """Restringe a programação à janela do horizonte: do PRIMEIRO ano programado
    (não de um ano-base fixo) até +horizonte-1. Assim horizonte 1 = 1º ano da matriz,
    horizonte N = os N primeiros anos (sem janela vazia / off-by-one)."""
    if budget_items is None or budget_items.empty or "Ano" not in budget_items:
        return budget_items

    years = pd.to_numeric(budget_items["Ano"], errors="coerce")
    base = int(years.min())  # 1º ano com programação (ex.: 2027)
    max_year = base + int(horizon) - 1
    return budget_items[(years >= base) & (years <= max_year)].copy()


def _format_money(value: float) -> str:
    """Formata reais de forma compacta (mi / mil / R$) para KPIs e cards."""
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi"
    if value >= 1_000:
        return f"R$ {value / 1_000:.0f} mil"
    return f"R$ {value:.0f}"


def _format_money_chart(value: float) -> str:
    """Como `_format_money`, mas com 1 casa em 'mil' e '0' explícito, p/ rótulos de gráfico."""
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi"
    if value >= 1_000:
        return f"R$ {value / 1_000:.1f} mil"
    if value > 0:
        return f"R$ {value:.0f}"
    return "R$ 0"


def _axis_max_10(value: float) -> int:
    """Arredonda o topo do eixo para o próximo múltiplo de 10 (mínimo 10)."""
    return max(10, ((int(value) + 9) // 10) * 10)


def _axis_ticks_10(axis_max: int) -> list[int]:
    """Ticks do eixo Y de 10 em 10, do topo até 0 (para os gráficos HTML)."""
    return list(range(int(axis_max), -1, -10))


def _axis_max_headroom(value: float) -> int:
    """Como _axis_max_10, mas com folga acima da maior barra para o rótulo
    (que fica em cima da barra) não ser cortado no topo do gráfico."""
    return _axis_max_10(value * 1.18)


def _economic_work_table(table_df) -> pd.DataFrame:
    """Prepara a tabela base do cenário econômico atribuindo custo a cada trecho.

    Prioriza o custo REAL do banco ("Custo estimado"); quando ausente, cai no custo
    paramétrico por km (`_ECONOMIC_SOLUTION_COST_KM`, README §14.1). A coluna
    "Custo origem" marca a proveniência: Banco / Paramétrico / Sem custo.
    """
    if table_df is None or table_df.empty:
        return pd.DataFrame()

    df = table_df.copy()
    df["_solucao_codigo"] = df.get("_solucao_codigo", "Sem intervenção").fillna("Sem intervenção").astype(str)
    df["Custo banco"] = pd.to_numeric(df.get("Custo estimado", 0), errors="coerce").fillna(0.0)
    df["Custo econômico"] = df["Custo banco"]

    # Sem custo no banco → aplica o fallback paramétrico (R$/km × extensão).
    missing_cost = df["Custo econômico"] <= 0
    fallback_cost = df["_solucao_codigo"].map(_ECONOMIC_SOLUTION_COST_KM).fillna(0) * df["Extensão"].astype(float)
    df.loc[missing_cost, "Custo econômico"] = fallback_cost.loc[missing_cost]
    df["Custo origem"] = "Banco"
    df.loc[missing_cost & (df["Custo econômico"] > 0), "Custo origem"] = "Paramétrico"
    df.loc[df["Custo econômico"] <= 0, "Custo origem"] = "Sem custo"
    return df


def _prioridade_por_snv(df: pd.DataFrame) -> dict[str, dict]:
    """Calcula a priorização por SNV (IPT = nível de prioridade) por segmento.

    Segmentos classificados como "Excelente" são excluídos do cálculo — só entram no
    ranking trechos que precisam de intervenção. Metodologia (cliente): o IPT é o
    próprio nível de prioridade (1 = maior … 10 = menor), com
    IPT = 10·(0,5·(1 − R_VMDA) + 0,3·R_ICDS + 0,2·R_ICDP), R_VMDA log e ICDS/ICDP
    lineares (min-max global). Menor IPT = mais crítico.
    """
    if df is None or df.empty:
        return {}

    if "_classe_iap" in df.columns:
        df = df[df["_classe_iap"].astype(str) != "Excelente"]
        if df.empty:
            return {}

    has_sent = "Sentido" in df.columns
    segmentos = [
        {
            "rodovia": row.get("Rodovia", ""),
            # Chave por (SNV, Sentido) quando há sentido → priorização/IPT/IPE
            # independentes por sentido (senão CR e DE ficariam idênticos).
            "snv": (f"{row.get('SNV')}␟{row.get('Sentido')}" if has_sent else str(row.get("SNV"))),
            "extensao_km": row.get("Extensão"),
            "vmda": row.get("VMDA"),
            "icds": row.get("ICDS"),
            "icdp": row.get("ICDP"),
            "custo": row.get("Custo econômico"),
        }
        for _, row in df.iterrows()
    ]
    return {item["snv"]: item for item in calcular_indice_priorizacao(segmentos)}


def _prioridade_por_segmento(df: pd.DataFrame) -> dict:
    """Por _segment_id → priorização/IPT calculados POR SEGMENTO (sem agregar no SNV).
    Segmentos 'Excelente' são excluídos do cálculo (não precisam de intervenção)."""
    if df is None or df.empty or "_segment_id" not in df.columns:
        return {}
    work = df
    if "_classe_iap" in df.columns:
        work = df[df["_classe_iap"].astype(str) != "Excelente"]
        if work.empty:
            return {}
    segmentos = [
        {
            "id": int(row.get("_segment_id")),
            "vmda": row.get("VMDA"),
            "icds": row.get("ICDS"),
            "icdp": row.get("ICDP"),
            "extensao_km": row.get("Extensão"),
            "custo": row.get("Custo econômico"),
        }
        for _, row in work.iterrows()
    ]
    return {item["id"]: item for item in calcular_indice_priorizacao_segmento(segmentos)}


def _aplicar_indice_priorizacao(df: pd.DataFrame) -> pd.DataFrame:
    """Anexa IPT/IPE/PRIORIZAÇÃO calculados POR SEGMENTO aos segmentos e ordena."""
    if df is None or df.empty or "_segment_id" not in df.columns:
        return df

    prio = _prioridade_por_segmento(df)
    df = df.copy()
    sid = df["_segment_id"]
    df["IPT"] = sid.map(lambda i: prio.get(int(i), {}).get("ip_tecnico", 0.0) if pd.notna(i) else 0.0)
    df["IPE"] = sid.map(lambda i: prio.get(int(i), {}).get("ip_economico", 0.0) if pd.notna(i) else 0.0)
    # Segmentos sem entrada no ranking (Excelente / sem intervenção) ficam com 10.0.
    df["Priorização"] = sid.map(lambda i: prio.get(int(i), {}).get("priorizacao", 10.0) if pd.notna(i) else 10.0)
    df["Classe prioridade"] = sid.map(lambda i: prio.get(int(i), {}).get("classificacao", "Prioridade Baixa") if pd.notna(i) else "Prioridade Baixa")
    df["_rank"] = sid.map(lambda i: prio.get(int(i), {}).get("ranking", len(prio) + 1) if pd.notna(i) else len(prio) + 1)

    df = df.sort_values(["_rank", "Km Inicial"]).reset_index(drop=True)
    df["Prioridade"] = df["_rank"]
    return df


def _simulate_economic_scenario(table_df, annual_budget_mi: int, horizon: int, strategy: str) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Simula a execução das obras dentro de um orçamento anual e horizonte.

    Ordena os trechos por priorização e vai "gastando" o orçamento ano a ano: cada
    trecho vira Executa / Backlog / Sem intervenção. Devolve
    `(métricas, tabela_por_trecho, tabela_anual)` — a tabela anual traz km executado,
    backlog e IAP médio projetado por ano. Constantes hardcoded no README §14.2.
    """
    df = _economic_work_table(table_df)
    if df.empty:
        return {}, df, pd.DataFrame()

    df = _aplicar_indice_priorizacao(df)

    annual_budget = float(annual_budget_mi) * 1_000_000
    total_budget = annual_budget * int(horizon)
    remaining_total = total_budget
    statuses = []
    execution_years = []

    for _, row in df.iterrows():
        cost = float(row["Custo econômico"])
        if cost <= 0:
            statuses.append("Sem intervenção")
            execution_years.append("")
        elif cost <= remaining_total:
            statuses.append("Executa")
            # Ano previsto = ano-base 2026 (_ECONOMIC_BASE_YEAR, README §14.2) + nº de
            # orçamentos anuais já consumidos, limitado ao fim do horizonte.
            execution_year = int((total_budget - remaining_total) // annual_budget) + 2026 if annual_budget else 2026
            execution_years.append(str(min(execution_year, 2025 + int(horizon))))
            remaining_total -= cost
        else:
            statuses.append("Backlog")
            execution_years.append("")

    df["Status"] = statuses
    df["Ano previsto"] = execution_years

    annual_rows = []
    pending = df[(df["Custo econômico"] > 0)].copy()
    executed_ids: set[int] = set()
    cumulative_cost = 0.0
    current_iap = float((df["IAP"] * df["Extensão"]).sum() / df["Extensão"].sum()) if df["Extensão"].sum() else 0

    for offset in range(int(horizon)):
        year = 2026 + offset
        year_budget = annual_budget
        year_km = 0.0
        for idx, row in pending.iterrows():
            if idx in executed_ids:
                continue
            cost = float(row["Custo econômico"])
            if cost <= year_budget:
                executed_ids.add(idx)
                year_budget -= cost
                year_km += float(row["Extensão"])
                cumulative_cost += cost

        remaining_df = pending.loc[[idx for idx in pending.index if idx not in executed_ids]]
        executed_df = pending.loc[list(executed_ids)] if executed_ids else pending.iloc[0:0]
        if not executed_df.empty and df["Extensão"].sum():
            adjusted_iap = df["IAP"].copy()
            # Trecho executado assume IAP "pós-obra": clip inferior em 4,1 (Excelente).
            # É premissa hardcoded (README §14.2), não vem do banco.
            adjusted_iap.loc[executed_df.index] = adjusted_iap.loc[executed_df.index].clip(lower=4.1)
            current_iap = float((adjusted_iap * df["Extensão"]).sum() / df["Extensão"].sum())

        annual_rows.append(
            {
                "Ano": year,
                "Km executado": year_km,
                "Backlog km": float(remaining_df["Extensão"].sum()),
                "Custo acumulado": cumulative_cost,
                "IAP médio": current_iap,
            }
        )

    need_df = df[df["Custo econômico"] > 0]
    executed = df[df["Status"] == "Executa"]
    backlog = df[df["Status"] == "Backlog"]
    total_need = float(need_df["Custo econômico"].sum())
    executed_cost = float(executed["Custo econômico"].sum())
    metrics = {
        "total_need": total_need,
        "total_budget": total_budget,
        "deficit": max(total_need - total_budget, 0.0),
        "executed_km": float(executed["Extensão"].sum()),
        "backlog_km": float(backlog["Extensão"].sum()),
        "iap_final": float(annual_rows[-1]["IAP médio"]) if annual_rows else 0,
        # Custo evitado = 35% do custo executado (premissa hardcoded, README §14.2):
        # intervir cedo evitaria reconstrução futura mais cara.
        "cost_avoided": executed_cost * 0.35,
        "uses_parametric_cost": bool((df["Custo origem"] == "Paramétrico").any()),
    }
    return metrics, df, pd.DataFrame(annual_rows)


def _necessidade_total(table_df, budget_items, horizon: int) -> float:
    """Custo total para tratar a rede (necessidade), respeitando o horizonte.

    Usa o orçamento do banco quando disponível; senão, o custo econômico dos
    segmentos. Independe do orçamento anual — serve de valor padrão do slider.
    """
    bi = _limit_budget_to_horizon(budget_items, horizon)
    if bi is not None and not bi.empty:
        return float(bi["Custo"].sum())
    work = _economic_work_table(table_df)
    return float(work["Custo econômico"].sum()) if not work.empty else 0.0


def _budget_items_for_year(budget_items: pd.DataFrame | None, year: int | None) -> pd.DataFrame | None:
    """Restringe o orçamento ao ano selecionado, quando houver coluna `Ano`."""
    if year is None or budget_items is None or budget_items.empty or "Ano" not in budget_items.columns:
        return budget_items
    years = pd.to_numeric(budget_items["Ano"], errors="coerce")
    return budget_items.loc[years == int(year)].copy()


def _render_economic_controls(table_df, budget_items, total_snv: int, scenario_key: str) -> tuple[int, int, int]:
    """Sliders do cenário econômico: orçamento anual, horizonte e nível de prioridade.
    Devolve `(orçamento_mi, horizonte_anos, prioridade_máx)`. O default do orçamento é
    a necessidade total (cobre 100%) e o horizonte default é o total programado no banco."""
    budget_col, horizon_col, prio_col = st.columns([1, 1, 1], gap="medium")

    # Horizonte TOTAL da análise (ano-base até o último ano programado) — é o default
    # e o máximo do slider (não fixo em 8/20). O gestor pode reduzir a partir do total.
    _anos = (
        pd.to_numeric(budget_items["Ano"], errors="coerce").dropna()
        if (budget_items is not None and not budget_items.empty and "Ano" in budget_items)
        else None
    )
    full_h = max(1, int(_anos.max()) - int(_anos.min()) + 1) if (_anos is not None and not _anos.empty) else _ECONOMIC_DEFAULT_HORIZON

    # Horizonte primeiro: a necessidade total (default do orçamento) depende dele.
    with horizon_col:
        _filter_caption("Horizonte")
        horizon = st.slider(
            "Horizonte", 1, max(full_h, 2), full_h, 1,
            key=f"horizon_{scenario_key}",
            label_visibility="collapsed",
        )
        st.markdown(f'<div class="economic-control-value">{horizon} anos</div>', unsafe_allow_html=True)

    # Default do orçamento = necessidade total (garante cobrir tudo). O máximo é
    # estável (necessidade sem limite de horizonte) para o estado do slider não
    # estourar ao mudar o horizonte.
    # teto (ceil) em milhões — garante que o default cobre 100% da necessidade
    need_mi = max(1, int(-(-_necessidade_total(table_df, budget_items, horizon) // 1_000_000)))
    budget_max = max(50, int(-(-_necessidade_total(table_df, budget_items, 9999) // 1_000_000)))
    with budget_col:
        _filter_caption("Orçamento anual")
        annual_budget = st.slider(
            "Orçamento anual", 1, budget_max, need_mi, 1,
            key=f"budget_{scenario_key}",
            label_visibility="collapsed",
        )
        st.markdown(f'<div class="economic-control-value">{_format_money(annual_budget * 1_000_000)}</div>', unsafe_allow_html=True)

    # Filtro de nível de prioridade: mantém SNVs com priorização (invertida) ≤ X.
    # Escala 1..10, default 10 = todos. 1 = só o(s) mais crítico(s).
    with prio_col:
        _filter_caption("Nível de prioridade")
        prio_max = st.slider(
            "Nível de prioridade", 1, 10, 10, 1,
            key=f"prio_{scenario_key}",
            label_visibility="collapsed",
            help="1 = atender só o mais crítico; 10 = atender todos.",
        )
        rotulo = "Todos" if prio_max >= 10 else f"Nível ≤ {prio_max}"
        st.markdown(f'<div class="economic-control-value">{rotulo}</div>', unsafe_allow_html=True)

    return annual_budget, horizon, prio_max


def _render_cost_by_solution(table_df: pd.DataFrame) -> None:
    """Gráfico de barras (HTML) do custo (% do total) consumido por tipo de solução."""
    if table_df is None or table_df.empty:
        return

    cost_df = table_df[table_df["Custo econômico"] > 0].copy()
    if cost_df.empty:
        return

    grouped = (
        cost_df.groupby("Solução recomendada", as_index=False)
        .agg({"Custo econômico": "sum", "Extensão": "sum"})
        .sort_values("Custo econômico", ascending=False)
    )
    total_cost = float(grouped["Custo econômico"].sum())
    total_km = float(grouped["Extensão"].sum())
    max_percent = max(float(grouped["Custo econômico"].max()) / total_cost * 100, 1)
    axis_max = _axis_max_10(max_percent)
    ticks = _axis_ticks_10(axis_max)
    tick_markup = "".join(
        f'<span class="solution-y-tick" style="bottom:{tick / axis_max * 100:.2f}%;">{tick:.0f}</span>'
        for tick in ticks
    )
    bars = []
    labels = []
    for row in grouped.to_dict("records"):
        label = str(row["Solução recomendada"])
        cost = float(row["Custo econômico"])
        km = float(row["Extensão"])
        percent = cost / total_cost * 100
        height = max(percent / axis_max * 100, 2)
        bars.append(
            '<div class="solution-bar-item">'
            f'<div class="solution-bar" style="height:{height:.2f}%;background:{_solution_color(label)};">'
            f'<span class="solution-bar-value">{percent:.1f}%<span>{_format_money(cost)} · {km:.1f} km</span></span>'
            '</div></div>'
        )
        labels.append(f'<div class="solution-bar-label">{html.escape(label)}</div>')

    st.markdown(
        '<div class="solution-distribution">'
        '<div class="solution-distribution-head">'
        '<div class="solution-distribution-title"><div class="solution-distribution-icon">$</div>'
        '<div><h3>Custos por solução</h3><p>Onde o orçamento é consumido por tipo de intervenção</p></div></div>'
        f'<div class="solution-distribution-meta"><span>Total · <strong>{_format_money(total_cost)}</strong></span><span>Trecho · <strong>{total_km:.1f} km</strong></span></div>'
        '</div>'
        '<div class="solution-bars">'
        f'<div class="solution-y-axis">{tick_markup}</div>'
        '<div class="solution-chart-area"><div class="solution-chart-plot">'
        f'<div class="solution-bar-grid">{"".join(bars)}</div></div>'
        f'<div class="solution-label-grid">{"".join(labels)}</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _grouped_bars_html(groups, sentidos, height_of, label_of, color_of, axis_max):
    """Monta (ticks, grupos, labels, legenda) de barras agrupadas por sentido:
    cor pelo grupo (solução/ano), sentido distinguido por listras (1º sólido)."""
    sent_idx = {s: i for i, s in enumerate(sentidos)}
    ticks = _axis_ticks_10(axis_max)
    tick_markup = "".join(
        f'<span class="solution-y-tick" style="bottom:{t / axis_max * 100:.2f}%;">{t:.0f}</span>'
        for t in ticks
    )
    ghtml, lhtml = [], []
    for g in groups:
        col = color_of(g)
        bars = ""
        for s in sentidos:
            v = height_of(g, s)
            h = max(v / axis_max * 100, 1.5) if v > 0 else 0.0
            bars += (
                f'<div class="solution-bar" style="height:{h:.2f}%;'
                f'background:{_sentido_bar_bg(col, sent_idx[s])};width:56px;min-width:56px;flex:0 0 auto">'
                '<span class="solution-bar-value" style="font-size:9px;line-height:1.12;letter-spacing:-.2px">'
                f'{label_of(g, s)}</span></div>'
            )
        ghtml.append(
            '<div class="solution-bar-item" style="display:flex;gap:16px;'
            f'align-items:flex-end;justify-content:center">{bars}</div>'
        )
        lhtml.append(f'<div class="solution-bar-label">{html.escape(str(g))}</div>')
    legend = "".join(
        '<span style="display:inline-flex;align-items:center;gap:6px;font-size:12px;'
        f'color:#cbd5df;margin:0 14px 0 0"><span style="width:12px;height:12px;border-radius:3px;'
        f'background:{_sentido_bar_bg("#cbd5df", sent_idx[s])};display:inline-block"></span>'
        f'{html.escape(s)}</span>'
        for s in sentidos
    )
    return tick_markup, "".join(ghtml), "".join(lhtml), legend


def _grouped_bars_card(icon, title, subtitle, meta_html, tick, groups_html, labels_html):
    """Envolve as barras agrupadas de `_grouped_bars_html` no card HTML padrão."""
    return (
        '<div class="solution-distribution"><div class="solution-distribution-head">'
        f'<div class="solution-distribution-title"><div class="solution-distribution-icon">{icon}</div>'
        f'<div><h3>{title}</h3><p>{subtitle}</p></div></div>'
        f'<div class="solution-distribution-meta">{meta_html}</div></div>'
        '<div class="solution-bars">'
        f'<div class="solution-y-axis">{tick}</div>'
        '<div class="solution-chart-area"><div class="solution-chart-plot">'
        f'<div class="solution-bar-grid">{groups_html}</div></div>'
        f'<div class="solution-label-grid">{labels_html}</div></div></div></div>'
    )


def _render_budget_cost_by_year_sentido(budget_items: pd.DataFrame) -> None:
    """Custo por ano da programação orçamentária, com barras agrupadas por sentido."""
    g = budget_items.groupby(["Ano", "Sentido"], as_index=False)["Custo"].sum()
    anos = sorted(g["Ano"].unique())
    sentidos = list(dict.fromkeys(budget_items["Sentido"].tolist()))
    total_cost = float(g["Custo"].sum())
    pivot = {(int(r["Ano"]), r["Sentido"]): float(r["Custo"]) for r in g.to_dict("records")}
    mi_of = lambda ano, sent: pivot.get((int(ano), sent), 0.0) / 1_000_000
    axis_max = _axis_max_headroom(max((mi_of(a, s) for a in anos for s in sentidos), default=1.0) or 1.0)
    tick, gh, lh, legend = _grouped_bars_html(
        [int(a) for a in anos],
        sentidos,
        mi_of,
        lambda ano, sent: _format_money_chart(pivot.get((int(ano), sent), 0.0)),
        lambda ano: "#9aa0a6",
        axis_max,
    )
    meta = f'<span>Total · <strong>{_format_money(total_cost)}</strong></span>{legend}'
    st.markdown(
        _grouped_bars_card("$", "Custo por ano", "Programação orçamentária por sentido", meta, tick, gh, lh),
        unsafe_allow_html=True,
    )


def _render_budget_cost_by_solution_sentido(budget_items: pd.DataFrame, color_fn) -> None:
    """Custo (% do total) por solução, com barras agrupadas por sentido."""
    g = budget_items.groupby(["Solução", "Sentido"], as_index=False).agg({"Custo": "sum", "Extensão": "sum"})
    solucoes = list(g.groupby("Solução")["Custo"].sum().sort_values(ascending=False).index)
    sentidos = list(dict.fromkeys(budget_items["Sentido"].tolist()))
    total_cost = float(g["Custo"].sum()) or 1.0
    pivot = {(r["Solução"], r["Sentido"]): (float(r["Custo"]), float(r["Extensão"])) for r in g.to_dict("records")}
    pct_of = lambda sol, sent: pivot.get((sol, sent), (0.0, 0.0))[0] / total_cost * 100
    axis_max = _axis_max_headroom(max((pct_of(s, se) for s in solucoes for se in sentidos), default=1.0) or 1.0)

    def label_of(sol, sent):
        cost, _km = pivot.get((sol, sent), (0.0, 0.0))
        return f"{pct_of(sol, sent):.1f}%<span>{_format_money(cost)}</span>"

    tick, gh, lh, legend = _grouped_bars_html(solucoes, sentidos, pct_of, label_of, color_fn, axis_max)
    total_km = float(budget_items.drop_duplicates(["_budget_id", "_segment_id"])["Extensão"].sum())
    meta = (
        f'<span>Total · <strong>{_format_money(total_cost)}</strong></span>'
        f'<span>Trecho · <strong>{total_km:.1f} km</strong></span>{legend}'
    )
    st.markdown(
        _grouped_bars_card("$", "Custos por solução", "Itens do orçamento por sentido", meta, tick, gh, lh),
        unsafe_allow_html=True,
    )


def _render_budget_cost_by_year(budget_items: pd.DataFrame) -> None:
    """Gráfico de custo por ano da programação. Se houver >1 sentido, delega à versão
    agrupada por sentido; senão, barras simples por ano."""
    if budget_items is None or budget_items.empty:
        return
    if "Sentido" in budget_items.columns and budget_items["Sentido"].nunique() > 1:
        _render_budget_cost_by_year_sentido(budget_items)
        return

    grouped = budget_items.groupby("Ano", as_index=False)["Custo"].sum().sort_values("Ano")
    total_cost = float(grouped["Custo"].sum())
    max_cost = max(float(grouped["Custo"].max()), 1)
    axis_max = _axis_max_10(max_cost / 1_000_000)
    ticks = _axis_ticks_10(axis_max)
    tick_markup = "".join(
        f'<span class="economic-y-tick" style="bottom:{tick / axis_max * 100:.2f}%;">{tick:.0f}</span>'
        for tick in ticks
    )
    bars = []
    labels = []
    for row in grouped.to_dict("records"):
        cost_mi = float(row["Custo"]) / 1_000_000
        height = max(cost_mi / axis_max * 100, 2 if cost_mi > 0 else 0)
        value_label = _format_money_chart(float(row["Custo"]))
        bars.append(
            '<div class="economic-bar-item">'
            f'<div class="economic-bar" style="height:{height:.2f}%;background:#9aa0a6;opacity:.95;"><span>{value_label}</span></div>'
            '</div>'
        )
        labels.append(f'<div>{int(row["Ano"])}</div>')

    st.markdown(
        '<section class="economic-panel">'
        '<div class="economic-head">'
        '<div class="economic-title"><div class="economic-icon">$</div>'
        '<div><h3>Custo por ano</h3><p>Programação orçamentária cadastrada no banco</p></div></div>'
        f'<div class="solution-distribution-meta"><span>Total · <strong>{_format_money(total_cost)}</strong></span></div>'
        '</div>'
        '<div class="economic-chart">'
        f'<div class="economic-y-axis">{tick_markup}</div>'
        '<div class="economic-scroll">'
        '<div class="economic-plot">'
        f'<div class="economic-bars">{"".join(bars)}</div>'
        '</div>'
        f'<div class="economic-labels">{"".join(labels)}</div>'
        '</div>'
        '</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def _render_budget_cost_by_solution(budget_items: pd.DataFrame, *, color_fn=None) -> None:
    """Custo (% do total) por solução com base nos ITENS do orçamento do banco
    (não só a solução final do IAP). Delega à versão por sentido quando há >1 sentido."""
    if budget_items is None or budget_items.empty:
        return

    color_fn = color_fn or _solution_color
    if "Sentido" in budget_items.columns and budget_items["Sentido"].nunique() > 1:
        _render_budget_cost_by_solution_sentido(budget_items, color_fn)
        return
    grouped = (
        budget_items.groupby("Solução", as_index=False)
        .agg({"Custo": "sum", "Extensão": "sum"})
        .sort_values("Custo", ascending=False)
    )
    total_cost = float(grouped["Custo"].sum())
    total_km = float(budget_items.drop_duplicates(["_budget_id", "_segment_id"])["Extensão"].sum())
    max_percent = max(float(grouped["Custo"].max()) / total_cost * 100, 1)
    axis_max = _axis_max_10(max_percent)
    ticks = _axis_ticks_10(axis_max)
    tick_markup = "".join(
        f'<span class="solution-y-tick" style="bottom:{tick / axis_max * 100:.2f}%;">{tick:.0f}</span>'
        for tick in ticks
    )

    bars = []
    labels = []
    for row in grouped.to_dict("records"):
        label = str(row["Solução"])
        cost = float(row["Custo"])
        km = float(row["Extensão"])
        percent = cost / total_cost * 100
        height = max(percent / axis_max * 100, 2)
        color = color_fn(label)
        bars.append(
            '<div class="solution-bar-item">'
            f'<div class="solution-bar" style="height:{height:.2f}%;background:{color};">'
            f'<span class="solution-bar-value">{percent:.1f}%<span>{_format_money(cost)} · {km:.1f} km</span></span>'
            '</div></div>'
        )
        labels.append(f'<div class="solution-bar-label">{html.escape(label)}</div>')

    st.markdown(
        '<div class="solution-distribution">'
        '<div class="solution-distribution-head">'
        '<div class="solution-distribution-title"><div class="solution-distribution-icon">$</div>'
        '<div><h3>Custos por solução</h3><p>Itens detalhados do orçamento, não apenas a solução final do IAP</p></div></div>'
        f'<div class="solution-distribution-meta"><span>Total · <strong>{_format_money(total_cost)}</strong></span><span>Trecho · <strong>{total_km:.1f} km</strong></span></div>'
        '</div>'
        '<div class="solution-bars">'
        f'<div class="solution-y-axis">{tick_markup}</div>'
        '<div class="solution-chart-area"><div class="solution-chart-plot">'
        f'<div class="solution-bar-grid">{"".join(bars)}</div></div>'
        f'<div class="solution-label-grid">{"".join(labels)}</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _group_priority_by_snv(table_df: pd.DataFrame) -> pd.DataFrame:
    """Consolida os segmentos por SNV (ou SNV+Sentido) numa tabela de prioridade.
    O SNV herda o segmento mais crítico (Prioridade = min) e reordena 1..N."""
    if table_df is None or table_df.empty:
        return pd.DataFrame()

    agg = {
        "Prioridade": "min",
        "Km Inicial": "min",
        "Km Final": "max",
        "Extensão": "sum",
        "IAP": "mean",
        "Custo econômico": "sum",
        "Solução recomendada": lambda values: " + ".join(dict.fromkeys(str(value) for value in values if str(value).strip())),
    }
    for col in ("IPT", "IPE", "Priorização"):
        if col in table_df.columns:
            agg[col] = "max"  # constantes por (SNV, sentido) — "max" só extrai o valor

    keys = ["SNV", "Sentido"] if "Sentido" in table_df.columns else ["SNV"]
    grouped = (
        table_df.groupby(keys, as_index=False)
        .agg(agg)
        .sort_values(["Prioridade", "IAP", "Km Inicial"], ascending=[True, True, True])
        .reset_index(drop=True)
    )
    for col in ("IPT", "IPE", "Priorização"):
        if col not in grouped.columns:
            grouped[col] = 0.0
        grouped[col] = grouped[col].fillna(0.0)
    grouped["Classe prioridade"] = grouped["Priorização"].map(classificar_prioridade)
    grouped["Prioridade"] = range(1, len(grouped) + 1)
    return grouped


def _group_budget_by_snv(budget_items: pd.DataFrame, priority_table: pd.DataFrame) -> pd.DataFrame:
    """Consolida a programação do banco por SNV (custo/extensão) e casa com a
    prioridade calculada. Fallback: se não há orçamento, usa `_group_priority_by_snv`."""
    if budget_items is None or budget_items.empty:
        return _group_priority_by_snv(priority_table)

    keys = ["SNV", "Sentido"] if "Sentido" in budget_items.columns else ["SNV"]
    cost_by_snv = (
        budget_items.groupby(keys, as_index=False)
        .agg(
            {
                "Custo": "sum",
                "Km Inicial": "min",
                "Km Final": "max",
                "Solução": lambda values: " + ".join(dict.fromkeys(str(value) for value in values if str(value).strip())),
            }
        )
        .rename(columns={"Custo": "Custo econômico", "Solução": "Solução recomendada"})
    )
    extension_by_snv = (
        budget_items.drop_duplicates(keys + ["_segment_id"])
        .groupby(keys, as_index=False)["Extensão"]
        .sum()
    )
    grouped = cost_by_snv.merge(extension_by_snv, on=keys, how="left")

    priority = _group_priority_by_snv(priority_table)
    if not priority.empty:
        merge_keys = (
            ["SNV", "Sentido"]
            if ("Sentido" in grouped.columns and "Sentido" in priority.columns)
            else ["SNV"]
        )
        grouped = grouped.merge(
            priority[merge_keys + ["Prioridade", "IAP", "IPT", "IPE", "Priorização"]],
            on=merge_keys,
            how="left",
        )
    else:
        grouped["Prioridade"] = range(1, len(grouped) + 1)
        grouped["IAP"] = 0
        grouped["IPT"] = 0.0
        grouped["IPE"] = 0.0
        grouped["Priorização"] = 0.0

    grouped["Prioridade"] = grouped["Prioridade"].fillna(len(grouped) + 1).astype(int)
    grouped["IAP"] = grouped["IAP"].fillna(0)
    for col in ("IPT", "IPE", "Priorização"):
        grouped[col] = grouped[col].fillna(0.0)
    grouped["Classe prioridade"] = grouped["Priorização"].map(classificar_prioridade)
    grouped = grouped.sort_values(["Prioridade", "IAP", "Km Inicial"], ascending=[True, True, True]).reset_index(drop=True)
    grouped["Prioridade"] = range(1, len(grouped) + 1)
    return grouped


def _select_snv_attended_by_budget(snv_table: pd.DataFrame, annual_budget_mi: int) -> pd.DataFrame:
    """Seleciona os SNVs atendidos por um orçamento, em ordem estrita de prioridade
    (para no 1º trecho que não couber). Versão por SNV inteiro; a por segmento é
    `_segment_attendance`."""
    if snv_table is None or snv_table.empty:
        return pd.DataFrame()

    remaining = float(annual_budget_mi) * 1_000_000
    attended_rows = []
    # Atende em ordem ESTRITA de prioridade: percorre do mais prioritário ao
    # menos e para no primeiro trecho que não couber — assim nada abaixo do
    # corte de prioridade é atendido na frente de um trecho mais prioritário.
    for row in snv_table.to_dict("records"):
        cost = float(row.get("Custo econômico", 0) or 0)
        if cost > remaining:
            break
        row["Orçamento restante"] = remaining - cost
        attended_rows.append(row)
        remaining -= cost

    return pd.DataFrame(attended_rows)


def _segment_cost_frame(
    budget_items: pd.DataFrame | None,
    priority_table: pd.DataFrame | None,
    keys: list[str],
) -> pd.DataFrame | None:
    """Tabela de custo+extensão POR SEGMENTO para o atendimento por orçamento.

    Prefere o `budget_items` (programação do banco, recortada ao horizonte). Quando
    ele está vazio — caso do horizonte de 1 ano, em que a janela do banco fica fora
    do intervalo (ano-base × dados) — usa a `priority_table` (segmentos priorizados
    com o custo econômico de uma intervenção). Sem nenhuma das duas, devolve None.
    """
    if (
        budget_items is not None and not budget_items.empty
        and {"_segment_id", "Extensão", "Custo"}.issubset(budget_items.columns)
        and all(k in budget_items.columns for k in keys)
    ):
        df, cost_col = budget_items, "Custo"
    elif (
        priority_table is not None and not priority_table.empty
        and {"_segment_id", "Extensão", "Custo econômico"}.issubset(priority_table.columns)
        and all(k in priority_table.columns for k in keys)
    ):
        df, cost_col = priority_table, "Custo econômico"
    else:
        return None

    agg = {"_custo": (cost_col, "sum"), "_ext": ("Extensão", "first")}
    if "Km Inicial" in df.columns:
        agg["_km_ini"] = ("Km Inicial", "min")
    seg = df.groupby(keys + ["_segment_id"], as_index=False).agg(**agg)
    if "_km_ini" not in seg.columns:
        seg["_km_ini"] = 0.0
    # Só segmentos que precisam de intervenção (custo > 0) entram na carteira.
    return seg[seg["_custo"] > 0].copy()


def _segment_attendance(
    snv_table: pd.DataFrame,
    budget_items: pd.DataFrame | None,
    annual_budget_mi: int,
    priority_table: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, float, set]:
    """Atende SEGMENTO a segmento, em ordem estrita de prioridade do SNV.

    A versão por SNV inteiro (`_select_snv_attended_by_budget`) dava `break` no
    primeiro SNV que não coubesse — quando o trecho mais prioritário sozinho já
    estourava o orçamento, retornava 0 km mesmo a cobertura indicando >0% (ver
    "Cenário econômico"). Aqui o corte é por segmento: um SNV pode ser
    parcialmente atendido, então os km atendidos ficam coerentes com a cobertura
    e nunca zeram com orçamento > 0. A ordem de prioridade continua estrita —
    segmentos de um SNV menos prioritário só entram depois de esgotados os mais
    prioritários.

    Retorna (attended_snv_table, attended_km, attended_segment_ids):
      - attended_snv_table: uma linha por SNV com ≥1 segmento financiado;
        `Extensão` e `Custo econômico` refletem apenas a porção atendida.
      - attended_segment_ids: `_segment_id` efetivamente financiados (mapa/PDF).
    """
    if snv_table is None or snv_table.empty:
        return pd.DataFrame(), 0.0, set()

    keys = ["SNV", "Sentido"] if "Sentido" in snv_table.columns else ["SNV"]

    seg = _segment_cost_frame(budget_items, priority_table, keys)
    # Sem dados por segmento (ex.: custo paramétrico) → cai no SNV inteiro.
    if seg is None or seg.empty:
        attended = _select_snv_attended_by_budget(snv_table, annual_budget_mi)
        km = float(attended["Extensão"].sum()) if not attended.empty else 0.0
        return attended, km, set()

    budget = float(annual_budget_mi) * 1_000_000

    # Ordem de prioridade herdada do SNV (snv_table já vem ordenada por prioridade).
    # Segmentos cujo SNV não está no escopo (filtro de nível) ficam de fora.
    order = {tuple(str(r[k]) for k in keys): i for i, r in enumerate(snv_table.to_dict("records"))}
    seg["_ord"] = seg.apply(lambda r: order.get(tuple(str(r[k]) for k in keys)), axis=1)
    seg = seg[seg["_ord"].notna()].sort_values(["_ord", "_km_ini"]).reset_index(drop=True)

    remaining = budget
    attended_ids: set = set()
    att_ext: dict = {}
    att_cost: dict = {}
    for r in seg.to_dict("records"):
        cost = float(r["_custo"] or 0)
        if cost > remaining:
            break
        remaining -= cost
        attended_ids.add(int(r["_segment_id"]))
        gk = tuple(str(r[k]) for k in keys)
        att_ext[gk] = att_ext.get(gk, 0.0) + float(r["_ext"] or 0)
        att_cost[gk] = att_cost.get(gk, 0.0) + cost

    if not attended_ids:
        return pd.DataFrame(), 0.0, set()

    # Tabela por SNV com a PORÇÃO atendida, preservando colunas de exibição.
    attended_rows = []
    for r in snv_table.to_dict("records"):
        gk = tuple(str(r[k]) for k in keys)
        if gk not in att_ext:
            continue
        row = dict(r)
        row["Extensão"] = att_ext[gk]
        row["Custo econômico"] = att_cost[gk]
        attended_rows.append(row)

    return pd.DataFrame(attended_rows), float(sum(att_ext.values())), attended_ids


def _segment_priority_table(prioritized_table: pd.DataFrame, budget_items: pd.DataFrame | None) -> pd.DataFrame:
    """Tabela POR SEGMENTO (uma linha por _segment_id) com o custo REAL do orçamento.
    Só segmentos que recebem intervenção (custo > 0), ordenados por prioridade."""
    if prioritized_table is None or prioritized_table.empty or "_segment_id" not in prioritized_table.columns:
        return pd.DataFrame()
    df = prioritized_table.copy()
    # Custo real por segmento (soma da programação do orçamento); fallback p/ Custo econômico.
    if budget_items is not None and not budget_items.empty and "_segment_id" in budget_items.columns:
        real = (
            budget_items.groupby("_segment_id", as_index=False)["Custo"].sum()
            .rename(columns={"Custo": "_custo_real"})
        )
        df = df.merge(real, on="_segment_id", how="left")
        usa_real = df["_custo_real"].notna() & (df["_custo_real"] > 0)
        df["Custo econômico"] = df["_custo_real"].where(usa_real, df["Custo econômico"])
        df = df.drop(columns=["_custo_real"])
    df = df[df["Custo econômico"] > 0].copy()
    df = df.sort_values(["Prioridade", "Km Inicial"]).reset_index(drop=True)
    df["Prioridade"] = range(1, len(df) + 1)
    return df


def _segment_attendance_seg(seg_table: pd.DataFrame, annual_budget_mi: int) -> tuple[pd.DataFrame, float, set]:
    """Atende SEGMENTO a segmento em ordem estrita de prioridade até esgotar o orçamento.
    Retorna (segmentos_atendidos, km_atendido, ids_atendidos)."""
    if seg_table is None or seg_table.empty:
        return pd.DataFrame(), 0.0, set()
    remaining = float(annual_budget_mi) * 1_000_000
    rows, km, ids = [], 0.0, set()
    for r in seg_table.to_dict("records"):
        cost = float(r.get("Custo econômico", 0) or 0)
        if cost <= 0:
            continue
        if cost > remaining:
            break
        remaining -= cost
        ids.add(int(r["_segment_id"]))
        rows.append(r)
        km += float(r.get("Extensão", 0) or 0)
    return pd.DataFrame(rows), km, ids


def _solution_text_color(color: str) -> str:
    """Escolhe texto claro/escuro conforme o fundo da cor da solução (contraste).
    Fundos escuros (vermelho/verde/laranja) → texto claro; demais → texto escuro."""
    return "#f4f7fb" if color.lower() in {"#d71920", "#00a651", "#f2a51a"} else "#061018"


def _consolidar_trechos_por_solucao(segments: pd.DataFrame) -> pd.DataFrame:
    """Funde segmentos contíguos de mesma solução e ano numa única linha.

    Evita repetir a mesma solução km a km com o mesmo custo (ex.: fresagem a
    R$ 677 mil/km): soma extensão e custo e estende o intervalo de km. Trechos
    com lacuna ou de solução/ano diferentes permanecem separados.
    """
    if segments is None or segments.empty:
        return segments

    ordenado = segments.sort_values(
        ["Solução recomendada", "Ano", "Km Inicial"]
    ).reset_index(drop=True)

    grupos: list[dict] = []
    atual: dict | None = None
    for row in ordenado.to_dict("records"):
        contiguo = (
            atual is not None
            and str(row.get("Solução recomendada")) == str(atual["Solução recomendada"])
            and str(row.get("Ano", "")) == str(atual["Ano"])
            and abs(float(row["Km Inicial"]) - float(atual["Km Final"])) < 0.011
        )
        if contiguo:
            atual["Km Final"] = float(row["Km Final"])
            atual["Extensão"] += float(row.get("Extensão", 0) or 0)
            atual["Custo econômico"] += float(row.get("Custo econômico", 0) or 0)
            atual["Segmentos"] += 1
        else:
            atual = {
                "Km Inicial": float(row["Km Inicial"]),
                "Km Final": float(row["Km Final"]),
                "Extensão": float(row.get("Extensão", 0) or 0),
                "Solução recomendada": row.get("Solução recomendada"),
                "Custo econômico": float(row.get("Custo econômico", 0) or 0),
                "Ano": row.get("Ano", ""),
                "Segmentos": 1,
            }
            grupos.append(atual)

    return pd.DataFrame(grupos).sort_values(["Ano", "Km Inicial"]).reset_index(drop=True)


def _snv_segments_table(snv: str, budget_items: pd.DataFrame | None, priority_table: pd.DataFrame | None) -> pd.DataFrame:
    """Segmentos de um SNV consolidados por solução/ano. Prefere o orçamento do banco;
    na ausência, usa a tabela priorizada."""
    segments = pd.DataFrame()
    if budget_items is not None and not budget_items.empty:
        source = budget_items[budget_items["SNV"].astype(str) == str(snv)].copy()
        if not source.empty:
            segments = (
                source.groupby(["_segment_id", "Km Inicial", "Km Final", "Extensão", "Solução"], as_index=False)
                .agg({"Custo": "sum", "Ano": "min"})
                .sort_values(["Ano", "Km Inicial", "Solução"])
                .rename(columns={"Solução": "Solução recomendada", "Custo": "Custo econômico"})
            )

    if segments.empty and priority_table is not None and not priority_table.empty:
        source = priority_table[priority_table["SNV"].astype(str) == str(snv)].copy()
        if not source.empty:
            segments = (
                source.groupby(["Km Inicial", "Km Final", "Extensão", "Solução recomendada"], as_index=False)
                .agg({"Custo econômico": "sum"})
                .sort_values(["Km Inicial", "Solução recomendada"])
            )
            segments["Ano"] = ""

    # Consolida trechos contíguos da mesma solução/ano para não repetir custo por km.
    return _consolidar_trechos_por_solucao(segments)


def _segment_details_markup(segments: pd.DataFrame) -> str:
    """Tabela HTML (popover) com os trechos de um SNV: km, solução (chip colorido),
    custo e ano."""
    if segments is None or segments.empty:
        return '<span class="muted">Sem trechos</span>'

    detail_rows = []
    for item in segments.to_dict("records"):
        solution = str(item.get("Solução recomendada", ""))
        color = _solution_color(solution)
        text_color = _solution_text_color(color)
        year = item.get("Ano", "")
        detail_rows.append(
            "<tr>"
            f"<td>{_format_km(float(item['Km Inicial']))}</td>"
            f"<td>{_format_km(float(item['Km Final']))}</td>"
            f"<td>{_format_km(float(item['Extensão']))} km</td>"
            f"<td class='solution-chip-cell' style='background:{color};color:{text_color};'>{html.escape(solution)}</td>"
            f"<td>{_format_money(float(item.get('Custo econômico', 0) or 0))}</td>"
            f"<td>{html.escape(str(year)) if year else '-'}</td>"
            "</tr>"
        )

    return (
        '<div class="segment-popover">'
        '<table class="segment-table">'
        '<thead><tr><th>Km Inicial</th><th>Km Final</th><th>Extensão</th><th>Solução</th><th>Custo</th><th>Ano</th></tr></thead>'
        f'<tbody>{"".join(detail_rows)}</tbody>'
        '</table>'
        '</div>'
    )


def _snv_strip_and_costs(snv: str, budget_items, priority_table):
    """Dados do detalhe do trecho: faixa por km (solução dominante) + custo/solução.

    Retorna (faixa, custos, total_km, total_cost), onde:
      - faixa: blocos contíguos {km_ini, km_fim, ext, solucao, custo} ao longo do km
        (em cada km, a solução de maior custo — a intervenção principal);
      - custos: {solucao, custo, km} somados por solução (todos os itens do orçamento).
    """
    # FAIXA: solução final (IAP) por km, da tabela priorizada (uma por segmento),
    # consolidando trechos contíguos de mesma solução -> blocos limpos, igual ao mapa.
    faixa: list[dict] = []
    if priority_table is not None and not priority_table.empty:
        seg = priority_table[priority_table["SNV"].astype(str) == str(snv)]
        if not seg.empty:
            seg_df = (
                seg.groupby(["Km Inicial", "Km Final", "Extensão", "Solução recomendada"], as_index=False)
                ["Custo econômico"].sum()
            )
            seg_df["Ano"] = ""
            consol = _consolidar_trechos_por_solucao(seg_df)
            faixa = [
                {
                    "km_ini": float(r["Km Inicial"]),
                    "km_fim": float(r["Km Final"]),
                    "ext": float(r["Extensão"]),
                    "solucao": str(r["Solução recomendada"]),
                    "custo": float(r.get("Custo econômico", 0) or 0),
                }
                for r in consol.to_dict("records")
            ]

    # CUSTOS: por solução, do orçamento (todos os itens, multi-ano).
    custos: list[dict] = []
    if budget_items is not None and not budget_items.empty:
        src = budget_items[budget_items["SNV"].astype(str) == str(snv)]
        if not src.empty:
            by_sol = src.groupby("Solução", as_index=False)["Custo"].sum()
            km_sol = (
                src.drop_duplicates(["_segment_id", "Solução"])
                .groupby("Solução", as_index=False)["Extensão"].sum()
            )
            cdf = by_sol.merge(km_sol, on="Solução", how="left").sort_values("Custo", ascending=False)
            custos = [
                {"solucao": str(r["Solução"]), "custo": float(r["Custo"]), "km": float(r.get("Extensão") or 0)}
                for r in cdf.to_dict("records")
            ]
    # Sem orçamento detalhado: usa o custo da solução final por km (da faixa).
    if not custos and faixa:
        agreg: dict[str, dict] = {}
        for b in faixa:
            item = agreg.setdefault(b["solucao"], {"solucao": b["solucao"], "custo": 0.0, "km": 0.0})
            item["custo"] += b["custo"]
            item["km"] += b["ext"]
        custos = sorted(agreg.values(), key=lambda c: c["custo"], reverse=True)

    if not faixa and not custos:
        return [], [], 0.0, 0.0

    total_km = sum(b["ext"] for b in faixa)
    total_cost = sum(c["custo"] for c in custos) if custos else sum(b["custo"] for b in faixa)
    return faixa, custos, total_km, total_cost


def _snv_detail_chart_markup(snv: str, budget_items, priority_table) -> str:
    """Detalhe do trecho: solução por FAIXA DE KM (onde exatamente cada solução é
    aplicada) + custo por solução."""
    faixa, custos, total_km, total_cost = _snv_strip_and_costs(snv, budget_items, priority_table)
    if not custos and not faixa:
        return '<span class="muted">Sem trechos</span>'

    head = ('font-size:11px;font-weight:800;letter-spacing:.04em;color:#9aa8b3;'
            'text-transform:uppercase;margin:12px 0 4px')
    parts: list[str] = []
    # Exibe o nome da solução com "/" no lugar de "+" (cor usa o nome original).
    _sol = lambda s: html.escape(str(s).replace(" + ", " / "))

    # 1) Solução aplicada ao longo do km — só faixas COM intervenção (km exato).
    _SEM_INTERV = {"sem intervenção", "ok", "", "nan", "none"}
    _tem = lambda b: str(b["solucao"]).strip().lower() not in _SEM_INTERV
    blocos = sorted(faixa, key=lambda b: b["km_ini"])
    interv = [b for b in blocos if _tem(b)]
    if interv:
        km_ini = blocos[0]["km_ini"]
        km_fim = max(b["km_fim"] for b in blocos)
        span = max(km_fim - km_ini, 0.001)
        # Barra posicional: intervenções coloridas; trechos sem intervenção = lacuna.
        segs = "".join(
            (
                f'<span style="flex:0 0 {(b["km_fim"] - b["km_ini"]) / span * 100:.3f}%;'
                f'background:{_solution_color(b["solucao"])}" '
                f'title="km {_format_km(b["km_ini"])} – {_format_km(b["km_fim"])} · {_sol(b["solucao"])}"></span>'
                if _tem(b)
                else f'<span style="flex:0 0 {(b["km_fim"] - b["km_ini"]) / span * 100:.3f}%;background:transparent"></span>'
            )
            for b in blocos
        )
        linhas = "".join(
            '<div style="display:flex;align-items:center;gap:8px;font-size:12px;padding:4px 0;'
            'border-bottom:1px solid rgba(148,163,184,.08)">'
            f'<span style="width:9px;height:9px;border-radius:999px;flex:none;background:{_solution_color(b["solucao"])}"></span>'
            f'<span style="color:#e5edf3;font-weight:700;min-width:150px">km {_format_km(b["km_ini"])} – {_format_km(b["km_fim"])}</span>'
            f'<span style="color:#cbd5dd;flex:1">{_sol(b["solucao"])}</span>'
            f'<span style="color:#8f9eaa">{_format_km(b["ext"])} km</span>'
            '</div>'
            for b in interv
        )
        parts.append(
            f'<div style="{head};margin-top:2px">Solução aplicada ao longo do km</div>'
            '<div style="display:flex;height:18px;border-radius:6px;overflow:hidden;'
            f'border:1px solid rgba(148,163,184,.2)">{segs}</div>'
            '<div style="display:flex;justify-content:space-between;font-size:10px;'
            f'color:#8f9eaa;margin-top:3px"><span>km {_format_km(km_ini)}</span>'
            f'<span>km {_format_km(km_fim)}</span></div>'
            f'<div style="margin-top:8px">{linhas}</div>'
        )

    # 2) Custo por solução (barras, como antes).
    if custos:
        max_cost = max((c["custo"] for c in custos), default=1.0) or 1.0
        barras = "".join(
            f'<div class="snv-cost-row">'
            f'<span class="snv-cost-lbl">{_sol(c["solucao"])}</span>'
            f'<span class="snv-cost-track"><span class="snv-cost-bar" style="width:{c["custo"] / max_cost * 100:.2f}%;'
            f'background:{_solution_color(c["solucao"])}"></span></span>'
            f'<span class="snv-cost-val">{_format_money(c["custo"])} · Extensão: {_format_km(c["km"])} km</span>'
            f'</div>'
            for c in custos
        )
        parts.append(f'<div style="{head}">Custo por solução</div><div class="snv-cost-bars">{barras}</div>')

    return "".join(parts)


def _segment_detail_markup(row: dict, budget_items) -> str:
    """Detalhe de UM segmento: km, solução(ões) aplicada(s) e custo por solução."""
    _sol = lambda s: html.escape(str(s).replace(" + ", " / "))
    km_ini = float(row.get("Km Inicial", 0) or 0)
    km_fim = float(row.get("Km Final", 0) or 0)
    sol = str(row.get("Solução recomendada", "") or "")
    parts = [
        f'<div style="font-size:13px;color:#e5edf3;margin:2px 0 6px">'
        f'<b>km {_format_km(km_ini)} – {_format_km(km_fim)}</b> · {_sol(sol)}</div>'
    ]
    sid = row.get("_segment_id")
    if (
        sid is not None and budget_items is not None and not budget_items.empty
        and "_segment_id" in budget_items.columns
    ):
        src = budget_items[budget_items["_segment_id"] == int(sid)]
        if not src.empty:
            # Por ANO + solução, em ordem cronológica (deixa claro o que é manutenção futura).
            has_ano = "Ano" in src.columns
            gcols = ["Ano", "Solução"] if has_ano else ["Solução"]
            by = src.groupby(gcols, as_index=False)["Custo"].sum()
            by = by.sort_values(["Ano", "Custo"], ascending=[True, False]) if has_ano else by.sort_values("Custo", ascending=False)
            mx = max(float(by["Custo"].max()), 1.0)
            bars = "".join(
                '<div class="snv-cost-row">'
                + (
                    f'<span class="snv-cost-lbl"><b style="color:#9fb0bd">{int(r2["Ano"])}</b> · {_sol(r2["Solução"])}</span>'
                    if has_ano else f'<span class="snv-cost-lbl">{_sol(r2["Solução"])}</span>'
                )
                + f'<span class="snv-cost-track"><span class="snv-cost-bar" style="width:{float(r2["Custo"]) / mx * 100:.1f}%;'
                f'background:{_solution_color(r2["Solução"])}"></span></span>'
                f'<span class="snv-cost-val">{_format_money(float(r2["Custo"]))}</span>'
                '</div>'
                for r2 in by.to_dict("records")
            )
            parts.append(
                '<div style="font-size:10px;letter-spacing:.05em;color:#8f9eaa;'
                'text-transform:uppercase;margin:6px 0 2px">Programação por ano</div>'
                f'<div class="snv-cost-bars">{bars}</div>'
            )
    return "".join(parts)


def _render_solution_segments_map(segments_df, budget_items: pd.DataFrame, selected_snv: str) -> None:
    """Mapa Leaflet (imagem de satélite Esri) dos segmentos de um SRE, coloridos pela
    solução dominante do orçamento. Renderizado via `components.html` embutido."""
    if segments_df is None or segments_df.empty:
        st.info("Sem geometria para exibir no mapa.")
        return

    map_segments = segments_df[segments_df["sre"].astype(str) == str(selected_snv)].copy()
    if map_segments.empty:
        st.info("Sem trechos georreferenciados para este SRE.")
        return

    if budget_items is not None and not budget_items.empty:
        dominant = (
            budget_items[budget_items["SNV"].astype(str) == str(selected_snv)]
            .groupby(["_segment_id", "Solução"], as_index=False)["Custo"]
            .sum()
            .sort_values(["_segment_id", "Custo"], ascending=[True, False])
            .drop_duplicates("_segment_id")
            .rename(columns={"_segment_id": "segment_id"})
        )
        map_segments = map_segments.merge(dominant[["segment_id", "Solução"]], on="segment_id", how="left")
    else:
        map_segments["Solução"] = map_segments.get("classe_iap", "")

    payload = []
    for row in map_segments.to_dict("records"):
        solution = str(row.get("Solução") or row.get("classe_iap") or "")
        payload.append(
            {
                "segment_id": int(row["segment_id"]),
                "sre": str(row.get("sre", selected_snv)),
                "km_inicial": float(row["km_inicial"]),
                "km_final": float(row["km_final"]),
                "solution": solution,
                "color": _solution_color(solution),
                "paths": row["paths"],
            }
        )

    payload_json = json.dumps(payload, ensure_ascii=False)
    map_html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
          html, body {{ margin:0; padding:0; background:#061018; }}
          #map {{ height: 360px; width: 100%; border-radius: 12px; overflow: hidden; border: 1px solid #1d3848; }}
          .leaflet-control-container .leaflet-top, .leaflet-control-container .leaflet-bottom {{ display:none; }}
        </style>
      </head>
      <body>
        <div id="map"></div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
          const segments = {payload_json};
          const map = L.map('map', {{ zoomControl:false, attributionControl:false, scrollWheelZoom:true }});
          L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 22, maxNativeZoom: 17, attribution: 'Tiles &copy; Esri' }}).addTo(map);
          L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 22, maxNativeZoom: 17 }}).addTo(map);
          L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 22, maxNativeZoom: 17 }}).addTo(map);
          const points = [];
          const fmt = (value) => Number(value).toFixed(2);
          segments.forEach((segment) => {{
            segment.paths.forEach((path) => {{
              const coords = path.map((coord) => [Number(coord[0]), Number(coord[1])]);
              coords.forEach((coord) => points.push(coord));
              L.polyline(coords, {{
                color: segment.color,
                weight: 7,
                opacity: .96,
                lineCap: 'round',
                lineJoin: 'round'
              }}).addTo(map).bindTooltip(
                'SRE ' + segment.sre + ' · km ' + fmt(segment.km_inicial) + ' - ' + fmt(segment.km_final) + ' · ' + segment.solution
              );
            }});
          }});
          if (points.length) map.fitBounds(L.latLngBounds(points), {{ padding: [24, 24] }});
        </script>
      </body>
    </html>
    """
    components.html(map_html, height=372, scrolling=False)


# Cor da CLASSE de prioridade (README §13.2: faixas Crítica/Alta/Média/Baixa do IPT).
# Mesma paleta semáforo (vermelho→amarelo→cinza) usada nas telas.
_PRIORITY_CLASS_COLORS = {
    "Prioridade Crítica": "#d71920",
    "Prioridade Alta": "#f2a51a",
    "Prioridade Média": "#fff200",
    "Prioridade Baixa": "#7f909c",
}


def _priority_class_color(classe: str) -> str:
    """Cor da classe de prioridade (fallback cinza para classe desconhecida)."""
    return _PRIORITY_CLASS_COLORS.get(str(classe or ""), "#7f909c")


def _priority_memory_markup(m: dict) -> str:
    """Memória de cálculo do nível de prioridade (IPT) de um SNV: fórmulas + valores."""
    if not m:
        return '<span class="muted">Memória de cálculo indisponível para este trecho.</span>'
    vmda = float(m.get("vmda") or 0.0)
    icds = float(m.get("icds") or 0.0)
    icdp = float(m.get("icdp") or 0.0)
    rv = float(m.get("vmda_normalizado") or 0.0)
    rs = float(m.get("icds_normalizado") or 0.0)
    rp = float(m.get("icdp_normalizado") or 0.0)
    vmin = float(m.get("vmda_min") or 0.0); vmax = float(m.get("vmda_max") or 0.0)
    smin = float(m.get("icds_min") or 0.0); smax = float(m.get("icds_max") or 0.0)
    pmin = float(m.get("icdp_min") or 0.0); pmax = float(m.get("icdp_max") or 0.0)
    ipt = float(m.get("ip_tecnico") or 0.0)
    iptmin = float(m.get("ipt_min") or 0.0); iptmax = float(m.get("ipt_max") or 0.0)
    prio = int(round(float(m.get("priorizacao") or 0)))

    head = ('font-size:11px;font-weight:800;letter-spacing:.04em;color:#9aa8b3;'
            'text-transform:uppercase;margin:2px 0 4px')
    th = 'text-align:left;color:#8f9eaa;font-size:10px;text-transform:uppercase;padding:4px 10px;font-weight:700'
    td = 'padding:5px 10px;border-top:1px solid rgba(148,163,184,.10);color:#cbd5dd'
    fcss = 'font-family:monospace;font-size:13px;color:#e5edf3;margin:3px 0'
    rows = (
        '<tr>'
        f'<td style="{td};color:#e5edf3;font-weight:700">R<sub>VMDA</sub> (log)</td>'
        f'<td style="{td}">{vmda:,.0f}</td>'
        f'<td style="{td};font-family:monospace">(ln&nbsp;{vmda:,.0f} − ln&nbsp;{vmin:,.0f}) / (ln&nbsp;{vmax:,.0f} − ln&nbsp;{vmin:,.0f})</td>'
        f'<td style="{td};color:#fff;font-weight:800">{rv:.3f}</td>'
        '</tr>'
        '<tr>'
        f'<td style="{td};color:#e5edf3;font-weight:700">R<sub>ICDS</sub></td>'
        f'<td style="{td}">{icds:.2f}</td>'
        f'<td style="{td};font-family:monospace">({icds:.2f} − {smin:.2f}) / ({smax:.2f} − {smin:.2f})</td>'
        f'<td style="{td};color:#fff;font-weight:800">{rs:.3f}</td>'
        '</tr>'
        '<tr>'
        f'<td style="{td};color:#e5edf3;font-weight:700">R<sub>ICDP</sub></td>'
        f'<td style="{td}">{icdp:.2f}</td>'
        f'<td style="{td};font-family:monospace">({icdp:.2f} − {pmin:.2f}) / ({pmax:.2f} − {pmin:.2f})</td>'
        f'<td style="{td};color:#fff;font-weight:800">{rp:.3f}</td>'
        '</tr>'
    )
    return (
        f'<div style="{head}">Nível de prioridade — memória de cálculo</div>'
        '<div style="font-size:12px;color:#8f9eaa;margin-bottom:8px">Escala 1 (mais crítico) … 10 (menos crítico). '
        'Normalização min–máx global (R ∈ [0,1]); valores do segmento mais crítico do SNV. '
        'O VMDA é inverso (mais tráfego → mais prioritário).</div>'
        '<table style="border-collapse:collapse;width:100%;font-size:12px">'
        f'<tr><th style="{th}">Variável</th><th style="{th}">Valor</th>'
        f'<th style="{th}">Normalização</th><th style="{th}">R</th></tr>{rows}</table>'
        f'<div style="{fcss};margin-top:10px">IPT = 10 × (0,5·(1 − R<sub>VMDA</sub>) + 0,3·R<sub>ICDS</sub> + 0,2·R<sub>ICDP</sub>)</div>'
        f'<div style="{fcss}">&nbsp;&nbsp;&nbsp;&nbsp;= 10 × (0,5·(1 − {rv:.3f}) + 0,3·{rs:.3f} + 0,2·{rp:.3f}) = <b>{ipt:.2f}</b></div>'
        f'<div style="{fcss};margin-top:8px">Nível de prioridade = round( (IPT − IPT<sub>mín</sub>) / (IPT<sub>máx</sub> − IPT<sub>mín</sub>) × 9 + 1 )</div>'
        f'<div style="{fcss}">&nbsp;&nbsp;&nbsp;&nbsp;= round( ({ipt:.2f} − {iptmin:.2f}) / ({iptmax:.2f} − {iptmin:.2f}) × 9 + 1 ) = <b style="color:#00c2e8">{prio}</b></div>'
        '<div style="font-size:11px;color:#8f9eaa;margin-top:6px">O IPT é re-normalizado entre os trechos (min–máx) para a escala 1 (mais crítico) … 10 (menos crítico).</div>'
    )


def _render_economic_priority_table(
    snv_table: pd.DataFrame,
    attended_snv_table: pd.DataFrame | None = None,
    annual_budget_mi: int | None = None,
    budget_items: pd.DataFrame | None = None,
    priority_table: pd.DataFrame | None = None,
    segments_df=None,
    prio_memory: dict | None = None,
) -> None:
    """Tabela executiva de priorização do cenário econômico (a "fila" de trechos).

    Duas visões: só os segmentos atendidos pelo orçamento anual, ou todos os
    priorizados. Cada linha expande a memória de cálculo do IPT e o detalhe de custos.
    """
    if snv_table is None or snv_table.empty:
        return

    mode_col, sort_col, summary_col = st.columns([0.9, 0.7, 1.4], gap="medium")
    with mode_col:
        _filter_caption("Visualização")
        view_mode = st.selectbox(
            "Visualização da tabela",
            ["Segmentos atendidos pelo orçamento", "Todos os segmentos"],
            label_visibility="collapsed",
        )
    with sort_col:
        _filter_caption("Ordenar por")
        sort_by = st.selectbox(
            "Ordenar por", ["Km inicial", "Prioridade"], label_visibility="collapsed",
        )

    if view_mode == "Segmentos atendidos pelo orçamento":
        view = attended_snv_table.copy() if attended_snv_table is not None else pd.DataFrame()
        title = "Segmentos atendidos pelo orçamento anual"
        subtitle = f"Carteira inicial considerando {_format_money((annual_budget_mi or 0) * 1_000_000)} disponíveis no ano"
    else:
        view = snv_table.copy()
        title = "Fila executiva de aplicação do orçamento"
        subtitle = "Segmentos priorizados conforme o cenário selecionado"

    total_seg = int(len(view))
    with summary_col:
        if view.empty:
            st.markdown('<div class="pagination-summary">Nenhum segmento cabe no orçamento anual selecionado.</div>', unsafe_allow_html=True)
        else:
            extra = "" if total_seg <= 400 else " · exibindo os primeiros 400"
            st.markdown(
                f'<div class="pagination-summary">Exibindo {total_seg} segmentos · {_format_km(float(view["Extensão"].sum()))} km · {_format_money(float(view["Custo econômico"].sum()))}{extra}</div>',
                unsafe_allow_html=True,
            )

    if view.empty:
        return

    # Ordenação: km inicial (default) ou prioridade.
    if sort_by == "Prioridade" and "Prioridade" in view.columns:
        view = view.sort_values("Prioridade")
    else:
        _sc = (["Sentido"] if "Sentido" in view.columns else []) + ["Km Inicial", "Km Final"]
        view = view.sort_values([c for c in _sc if c in view.columns], kind="stable")
    view = view.head(400).reset_index(drop=True)
    has_sentido = "Sentido" in view.columns
    rows_markup = []
    cspan = 12 if has_sentido else 11
    _mem = prio_memory or {}
    for index, row in enumerate(view.to_dict("records"), start=1):
        snv = str(row["SNV"])
        seg_id = row.get("_segment_id")
        toggle_id = f"snv-detail-{index}"
        prio_id = f"snv-prio-{index}"
        detail_chart = _segment_detail_markup(row, budget_items)
        sentido = str(row.get("Sentido", ""))
        sentido_td = f"<td>{html.escape(sentido)}</td>" if has_sentido else ""
        # Memória de cálculo do nível de prioridade do SEGMENTO (clique no valor).
        mem = _mem.get(int(seg_id)) if (seg_id is not None and pd.notna(seg_id)) else {}
        mem_markup = _priority_memory_markup(mem or {})
        rows_markup.append(
            "<tr class='snv-row'>"
            f"<td class='muted'>{int(row['Prioridade'])}</td>"
            f"<td class='mono'>{html.escape(snv)}</td>"
            + sentido_td +
            f"<td>{_format_km(float(row['Km Inicial']))}</td>"
            f"<td>{_format_km(float(row['Km Final']))}</td>"
            f"<td>{_format_km(float(row['Extensão']))} km</td>"
            f"<td>{float(row['IAP']):.2f}</td>"
            f"<td>{float(row.get('IPT', 0) or 0):.2f}</td>"
            f"<td>{float(row.get('IPE', 0) or 0):.2f}</td>"
            f"<td><label for='{prio_id}' style='cursor:pointer;display:inline-flex' title='Ver memória de cálculo'>"
            f"<span class='iap-pill'><span class='iap-pill-dot' style='background:{_priority_class_color(row.get('Classe prioridade'))}'></span>{int(round(float(row.get('Priorização', 0) or 0)))}</span>"
            "</label></td>"
            f"<td>{_format_money(float(row['Custo econômico']))}</td>"
            "<td class='detail-toggle-cell'>"
            f"<label class='detail-toggle' for='{toggle_id}'><span class='caret'>▸</span>Ver soluções</label>"
            "</td>"
            "</tr>"
            "<tr class='detail-row'>"
            f"<td class='detail-cell' colspan='{cspan}'>"
            f"<input type='checkbox' id='{prio_id}' class='detail-checkbox'>"
            f"<div class='detail-content'>{mem_markup}</div>"
            "</td>"
            "</tr>"
            "<tr class='detail-row'>"
            f"<td class='detail-cell' colspan='{cspan}'>"
            f"<input type='checkbox' id='{toggle_id}' class='detail-checkbox'>"
            f"<div class='detail-content'>{detail_chart}</div>"
            "</td>"
            "</tr>"
        )

    st.markdown(
        """
        <section class="solution-card">
          <div class="solution-card-head">
            <h3>""" + title + """</h3>
            <p>""" + subtitle + """</p>
          </div>
          <div class="solution-table-wrap">
            <table class="solution-table">
              <thead>
                <tr>
                  <th>Prior.</th>
                  <th>SRE</th>""" + ("<th>Sentido</th>" if has_sentido else "") + """
                  <th>Km Inicial</th>
                  <th>Km Final</th>
                  <th>Extensão</th>
                  <th>IAP</th>
                  <th>IPT</th>
                  <th>IPE</th>
                  <th>Priorização</th>
                  <th>Custo</th>
                  <th>Soluções</th>
                </tr>
              </thead>
              <tbody>
        """
        + "".join(rows_markup)
        + """
              </tbody>
            </table>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _attended_segment_ids(segments_df, attended_snv_table) -> set:
    """IDs dos segmentos pertencentes aos SNVs atendidos (casados pelo código SRE)."""
    if segments_df is None or segments_df.empty or "sre" not in segments_df:
        return set()
    attended_snvs = (
        set(attended_snv_table["SNV"].astype(str))
        if attended_snv_table is not None and not attended_snv_table.empty
        else set()
    )
    if not attended_snvs:
        return set()
    return set(segments_df[segments_df["sre"].astype(str).isin(attended_snvs)]["segment_id"].astype(int))


def _render_economic_scenario_map(segments_df, attended_snv_table, annual_budget: int, attended_km: float, attended_ids: set | None = None) -> None:
    """Mostra no mapa quais trechos o orçamento anual consegue atender (cinza = fora)."""
    if segments_df is None or segments_df.empty or "sre" not in segments_df:
        return

    if attended_ids is None:
        attended_ids = _attended_segment_ids(segments_df, attended_snv_table)
    total_km = float((segments_df["km_final"] - segments_df["km_inicial"]).clip(lower=0).sum())

    st.markdown(
        '<section class="solution-distribution" style="padding-bottom:16px">'
        '<div class="solution-distribution-head" style="margin-bottom:0">'
        '<div class="solution-distribution-title"><div class="solution-distribution-icon">◎</div>'
        '<div><h3>Cenário no mapa</h3><p>Trechos atendidos pelo orçamento anual · cinza = fora do orçamento</p></div></div>'
        f'<div class="solution-distribution-meta"><span>Atendido · <strong>{attended_km:.1f} km</strong></span>'
        f'<span>Orçamento · <strong class="accent">{_format_money(annual_budget * 1_000_000)}/ano</strong></span></div>'
        '</div></section>',
        unsafe_allow_html=True,
    )
    render_overview_map(
        segments_df,
        total_km,
        attended_ids=attended_ids,
        legend_foot='<span class="legend-line" style="background:#46586a"></span>Cinza · trecho fora do orçamento anual',
        color_by="solucao",
    )


def _render_economic_page(
    table_df,
    budget_items=None,
    segments_df=None,
    scenario_key: str = "",
    road: str = "",
    scenario_label: str = "",
) -> None:
    """Monta a página inteira de Cenário econômico (visão do gestor).

    Fluxo: lê os sliders (orçamento/horizonte/prioridade) → roda a simulação →
    aplica o filtro de nível de prioridade por segmento → renderiza KPIs, mapa do
    que cabe no orçamento, custos por ano/solução, tabela executiva e botão do
    plano de trabalho. Ao final publica o contexto para o assistente IAGON da tela.
    """
    total_snv = 0
    if table_df is not None and not table_df.empty:
        total_snv = int(table_df["SNV"].dropna().astype(str).nunique()) if "SNV" in table_df else int(len(table_df))

    annual_budget, horizon, prio_max = _render_economic_controls(table_df, budget_items, total_snv, scenario_key)
    budget_items = _limit_budget_to_horizon(budget_items, horizon)
    metrics, prioritized_table, annual_df = _simulate_economic_scenario(table_df, annual_budget, horizon, "Balanceada")
    if not metrics:
        st.info("Sem dados de intervenção para montar o cenário econômico.")
        return

    # Memória de cálculo da prioridade POR SEGMENTO (mesma base do _simulate).
    prio_memory = _prioridade_por_segmento(_economic_work_table(table_df))

    # Tabela POR SEGMENTO (uma linha por segmento), ordenada por prioridade, custo real.
    seg_table = _segment_priority_table(prioritized_table, budget_items)
    # Filtro de nível de prioridade — agora POR SEGMENTO.
    if prio_max < 10 and "Priorização" in seg_table.columns:
        seg_table = seg_table[seg_table["Priorização"] <= prio_max].reset_index(drop=True)
        seg_table["Prioridade"] = range(1, len(seg_table) + 1)
    top_segments = {int(x) for x in seg_table["_segment_id"]} if not seg_table.empty else set()

    # Restringe orçamento, prioritized_table e mapa ao escopo prioritário (por segmento).
    if budget_items is not None and not budget_items.empty:
        budget_items = budget_items[budget_items["_segment_id"].isin(top_segments)].copy()
    if prioritized_table is not None and not prioritized_table.empty:
        prioritized_table = prioritized_table[prioritized_table["_segment_id"].isin(top_segments)].copy()
    # Mapa segue a tabela: só os segmentos dentro do nível de prioridade.
    if segments_df is not None and not segments_df.empty and "segment_id" in segments_df.columns:
        segments_df = segments_df[segments_df["segment_id"].isin(top_segments)].copy()

    if budget_items is not None and not budget_items.empty:
        total_need = float(budget_items["Custo"].sum())
    else:
        total_need = float(seg_table["Custo econômico"].sum()) if not seg_table.empty else 0.0
    metrics["total_need"] = total_need
    metrics["deficit"] = max(total_need - metrics["total_budget"], 0.0)

    scope_snv = int(len(seg_table))  # nº de segmentos no escopo prioritário
    scope_km = float(seg_table["Extensão"].sum()) if not seg_table.empty else 0.0
    annual_coverage = min((annual_budget * 1_000_000) / total_need * 100, 100) if total_need else 0
    # `attended_snv_table` agora guarda os SEGMENTOS atendidos (uma linha por segmento).
    attended_snv_table, attended_km, attended_ids = _segment_attendance_seg(seg_table, annual_budget)

    render_metric_cards(
        [
            {
                "title": "NECESSIDADE TOTAL",
                "value": _format_money(metrics["total_need"]),
                "subtitle": "Custo estimado para tratar a rede",
                "tone": "cyan",
                "icon": "$",
            },
            {
                "title": "COBERTURA ANUAL",
                "value": f"{annual_coverage:.1f}%",
                "subtitle": f"{_format_money(annual_budget * 1_000_000)} cobre da necessidade",
                "tone": "green",
                "icon": "↗",
            },
            {
                "title": "TRECHOS ATENDIDOS",
                "value": f"{attended_km:.1f} / {scope_km:.1f} km",
                "subtitle": "Km de segmentos cobertos pelo orçamento",
                "tone": "orange",
                "icon": "#",
            },
            {
                "title": "ORÇAMENTO FALTANTE",
                "value": _format_money(max(total_need - annual_budget * 1_000_000, 0.0)),
                "subtitle": (
                    "Necessidade já coberta pelo orçamento"
                    if annual_budget * 1_000_000 >= total_need
                    else "Adicional para cobrir 100% da necessidade"
                ),
                "tone": "yellow",
                "icon": "△",
            },
        ]
    )
    _render_economic_scenario_map(segments_df, attended_snv_table, annual_budget, attended_km, attended_ids)
    if budget_items is not None and not budget_items.empty:
        _render_budget_cost_by_year(budget_items)
        _render_budget_cost_by_solution(budget_items)
    else:
        _render_cost_by_solution(prioritized_table)
    _render_economic_priority_table(
        seg_table,
        attended_snv_table,
        annual_budget,
        budget_items,
        prioritized_table,
        prio_memory=prio_memory,
    )

    if metrics["uses_parametric_cost"] and (budget_items is None or budget_items.empty):
        st.markdown(
            '<div class="economic-note">Observação: este cenário usa custo do banco quando disponível. Para trechos sem orçamento no JSON de soluções, foi aplicado custo paramétrico provisório por km para permitir simulação gerencial.</div>',
            unsafe_allow_html=True,
        )

    _render_work_plan_button(
        scenario_key=scenario_key,
        road=road,
        scenario_label=scenario_label,
        annual_budget=annual_budget,
        horizon=horizon,
        top_label="Todos" if prio_max >= 10 else f"Nível ≤ {prio_max}",
        metrics=metrics,
        annual_coverage=annual_coverage,
        attended_snv_table=attended_snv_table,
        scope_snv=scope_snv,
        attended_km=attended_km,
        budget_items=budget_items,
        segments_df=segments_df,
        priority_table=prioritized_table,
        attended_ids=attended_ids,
    )

    # IAGON desta tela (Cenário econômico — orçamento × cobertura).
    _nivel = "Todos" if prio_max >= 10 else f"≤ {prio_max}"
    _eco_dados = (
        f"Necessidade total (todos os anos do programa): {_format_money(metrics.get('total_need', 0))}\n"
        f"Orçamento anual selecionado: {_format_money(annual_budget * 1_000_000)} · "
        f"Horizonte: {horizon} ano(s) · Nível de prioridade: {_nivel}\n"
        f"Cobertura anual: {annual_coverage:.1f}% · "
        f"Trechos atendidos: {attended_km:.1f} de {scope_km:.1f} km ({scope_snv} segmentos no escopo)\n"
        f"Orçamento faltante p/ cobrir 100%: {_format_money(max(metrics.get('total_need', 0) - annual_budget * 1_000_000, 0))}\n"
        "Use estes números para montar uma resposta executiva ao gestor (o que dá pra fazer com o "
        "orçamento, o que priorizar primeiro, quanto falta)."
    )
    if attended_snv_table is not None and not attended_snv_table.empty:
        _att = attended_snv_table.sort_values("Prioridade").head(15)
        _eco_dados += "\n\nSegmentos ATENDIDOS pelo orçamento (ordem de prioridade):\n" + "\n".join(
            f"- {int(r['Prioridade'])}º {r['SNV']} km {_format_km(float(r['Km Inicial']))}–{_format_km(float(r['Km Final']))} · "
            f"{float(r['Extensão']):.2f} km · nível {int(round(float(r['Priorização'])))} · "
            f"{str(r['Solução recomendada']).replace(' + ', ' / ')} · {_format_money(float(r['Custo econômico']))}"
            for _, r in _att.iterrows())
    if annual_df is not None and not annual_df.empty and "Ano" in annual_df.columns:
        _eco_dados += "\n\nProgramação ano a ano (km executado no ano · custo acumulado · IAP médio projetado):\n" + "\n".join(
            f"- Ano {int(r['Ano'])}: {float(r.get('Km executado', 0) or 0):.1f} km · "
            f"{_format_money(float(r.get('Custo acumulado', 0) or 0))} acumulado · IAP {float(r.get('IAP médio', 0) or 0):.2f}"
            for _, r in annual_df.head(12).iterrows())
    _render_screen_iagon(
        "cenario", f"Cenário econômico · {road}",
        f"<b>Rodovia:</b> {road} &nbsp;·&nbsp; <b>Cenário:</b> {html.escape(str(scenario_label))} &nbsp;·&nbsp; "
        f"<b>Orçamento:</b> {_format_money(annual_budget * 1_000_000)}/ano &nbsp;·&nbsp; "
        f"<b>Horizonte:</b> {horizon}a &nbsp;·&nbsp; <b>Prioridade:</b> {_nivel}",
        _screen_ctx("Cenário econômico (orçamento × cobertura)",
                    {"Rodovia": road, "Cenário": scenario_label,
                     "Orçamento anual": _format_money(annual_budget * 1_000_000),
                     "Horizonte": f"{horizon}a", "Nível de prioridade": _nivel},
                    _eco_dados),
        sugestoes=["Análise para o gestor", "O que faço no 1º ano?", "Quanto falta p/ 100%?"],
    )


def _combined_economic_data(road, keys, labels):
    """Combina tabela/orçamento/segmentos de vários cenários (sentidos) para o
    módulo econômico: a simulação roda sobre os dois juntos (necessidade total =
    soma) e `per_sentido` traz a necessidade de cada um para o comparativo."""
    tables, budgets, segs, per_sentido = [], [], [], []
    n = len(keys)
    for i, k in enumerate(keys):
        d = get_solutions_data(road, scenario_key=k)
        t, b, s = d.get("table"), d.get("budget_items"), d.get("segments")
        sent = _sentido_faixa(labels.get(k, k))
        # Necessidade do PROGRAMA COMPLETO por sentido (todos os anos) — bate com a
        # NECESSIDADE TOTAL (horizonte default = total da análise). 9999 = sem corte.
        per_sentido.append(
            {"sentido": sent, "need": _necessidade_total(t, b, 9999)}
        )
        if t is not None and not t.empty:
            t = t.copy()
            t["Sentido"] = sent
            tables.append(t)
        if b is not None and not b.empty:
            b = b.copy()
            b["Sentido"] = sent
            budgets.append(b)
        if s is not None and not s.empty:
            s = s.copy()
            s["offset_side"] = (i - (n - 1) / 2.0)  # lado p/ offset por pixel (zoom-aware) no mapa
            s["sentido"] = sent
            segs.append(s)
    return {
        "table": pd.concat(tables, ignore_index=True) if tables else None,
        "budget_items": pd.concat(budgets, ignore_index=True) if budgets else None,
        "segments": pd.concat(segs, ignore_index=True) if segs else None,
        "per_sentido": per_sentido,
    }


def _render_economic_comparison(per_sentido) -> None:
    """Cards comparando a necessidade total de cada sentido + o total combinado."""
    if not per_sentido:
        return
    total = sum(p["need"] for p in per_sentido)
    cells = ""
    for p in per_sentido:
        pct = (p["need"] / total * 100) if total else 0.0
        cells += (
            "<div style='flex:1;min-width:170px;background:rgba(7,17,25,.5);"
            "border:1px solid rgba(148,163,184,.18);border-radius:12px;padding:14px 16px'>"
            "<div style='font-size:11px;letter-spacing:.08em;color:#9aa8b3;"
            f"text-transform:uppercase'>{html.escape(p['sentido'])}</div>"
            "<div style='font-size:22px;font-weight:800;color:#e6edf2;margin-top:4px'>"
            f"{_format_money(p['need'])}</div>"
            f"<div style='font-size:12px;color:#7f909c'>{pct:.0f}% do total</div></div>"
        )
    # O total combinado é redundante com o card NECESSIDADE TOTAL abaixo — não repetimos.
    st.markdown(
        "<div style='margin:6px 0 16px'>"
        "<div style='font-weight:700;color:#cbd5df;margin-bottom:8px'>"
        "⚖️ Necessidade total por sentido</div>"
        f"<div style='display:flex;gap:12px;flex-wrap:wrap'>{cells}</div></div>",
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Cenário Econômico DNIT
# ----------------------------------------------------------------------------
def _aplicar_indice_priorizacao_dnit(df: pd.DataFrame) -> pd.DataFrame:
    """Versão DNIT do priorização — IRI 60% + IGG 40% (sem IAP/VMDA/DEF)."""
    if df is None or df.empty:
        return df
    has_sent = "Sentido" in df.columns
    segmentos = [
        {
            "rodovia": row.get("Rodovia", ""),
            "snv": (f"{row.get('SNV')}␟{row.get('Sentido')}" if has_sent else str(row.get("SNV"))),
            "extensao_km": row.get("Extensão"),
            "iri": row.get("IRI"),
            "igg": row.get("IGG"),
            "custo": row.get("Custo econômico"),
        }
        for _, row in df.iterrows()
    ]
    prio = {item["snv"]: item for item in calcular_indice_priorizacao_dnit(segmentos)}
    snv = (
        df["SNV"].astype(str) + "␟" + df["Sentido"].astype(str)
        if has_sent else df["SNV"].astype(str)
    )
    df = df.copy()
    df["IPT"] = snv.map(lambda s: prio.get(s, {}).get("ip_tecnico", 0.0))
    df["IPE"] = snv.map(lambda s: prio.get(s, {}).get("ip_economico", 0.0))
    df["Priorização"] = snv.map(lambda s: prio.get(s, {}).get("priorizacao", 10.0))
    df["Classe prioridade"] = snv.map(lambda s: prio.get(s, {}).get("classificacao", "Prioridade Baixa"))
    df["_rank"] = snv.map(lambda s: prio.get(s, {}).get("ranking", len(prio) + 1))
    df = df.sort_values(["_rank", "Km Inicial"]).reset_index(drop=True)
    df["Prioridade"] = df["_rank"]
    return df


def _render_dnit_economic_controls(total_need: float, scenario_key: str) -> tuple[int, int, int]:
    """Mesmo layout do controle Paragon, mas com defaults compatíveis com DNIT."""
    budget_col, horizon_col, prio_col = st.columns([1, 1, 1], gap="medium")

    with horizon_col:
        _filter_caption("Horizonte")
        horizon = st.slider(
            "Horizonte", 1, 30, 10, 1,
            key=f"dnit_horizon_{scenario_key}",
            label_visibility="collapsed",
        )
        st.markdown(f'<div class="economic-control-value">{horizon} anos</div>', unsafe_allow_html=True)

    need_mi = max(1, int(-(-total_need // 1_000_000)))
    budget_max = max(50, need_mi * 2)
    with budget_col:
        _filter_caption("Orçamento anual")
        annual_budget = st.slider(
            "Orçamento anual", 1, budget_max, need_mi, 1,
            key=f"dnit_budget_{scenario_key}",
            label_visibility="collapsed",
        )
        st.markdown(f'<div class="economic-control-value">{_format_money(annual_budget * 1_000_000)}</div>', unsafe_allow_html=True)

    with prio_col:
        _filter_caption("Nível de prioridade")
        prio_max = st.slider(
            "Nível de prioridade", 1, 10, 10, 1,
            key=f"dnit_prio_{scenario_key}",
            label_visibility="collapsed",
            help="1 = atender só o mais crítico; 10 = atender todos.",
        )
        rotulo = "Todos" if prio_max >= 10 else f"Nível ≤ {prio_max}"
        st.markdown(f'<div class="economic-control-value">{rotulo}</div>', unsafe_allow_html=True)

    return annual_budget, horizon, prio_max


def _combined_dnit_economic_data(road, keys, labels):
    """Combina os dados econômicos DNIT de vários cenários (sentidos): a simulação
    roda sobre os dois juntos (necessidade total = soma) e `per_sentido` traz a
    necessidade de cada um para o comparativo. Segmentos deslocados (2 camadas)."""
    tables, budgets, segs, per_sentido = [], [], [], []
    n = len(keys)
    zona_colors = zona_order = ano_base = None
    for i, k in enumerate(keys):
        d = get_dnit_economic_data(road, scenario_key=k)
        if not d.get("available"):
            continue
        t, b, s = d.get("table"), d.get("budget_items"), d.get("segments")
        sent = _sentido_faixa(labels.get(k, k))
        need = float(t["Custo estimado"].sum()) if t is not None and not t.empty else 0.0
        per_sentido.append({"sentido": sent, "need": need})
        zona_colors = zona_colors or d.get("zona_colors")
        zona_order = zona_order or d.get("zona_order")
        ano_base = ano_base or d.get("ano_base")
        if t is not None and not t.empty:
            t = t.copy()
            t["Sentido"] = sent
            tables.append(t)
        if b is not None and not b.empty:
            b = b.copy()
            b["Sentido"] = sent
            budgets.append(b)
        if s is not None and not s.empty:
            s = s.copy()
            s["offset_side"] = (i - (n - 1) / 2.0)  # lado p/ offset por pixel (zoom-aware) no mapa
            s["sentido"] = sent
            segs.append(s)
    return {
        "available": bool(tables),
        "table": pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(),
        "budget_items": pd.concat(budgets, ignore_index=True) if budgets else pd.DataFrame(),
        "segments": pd.concat(segs, ignore_index=True) if segs else pd.DataFrame(),
        "per_sentido": per_sentido,
        "zona_colors": zona_colors,
        "zona_order": zona_order,
        "ano_base": ano_base,
    }


def _render_dnit_economic_page(road: str, scenario_key: str) -> None:
    """Cenário econômico DNIT — usa orçamentos gravados em analise_gerencial_orcamentos
    e priorização IRI+IGG. Espelha estrutura visual do Paragon."""
    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    _dnit_keys, _dnit_labels = _solutions_sentido_keys(
        road, scenario_key, widget_key="dnit_eco_scen", matrix_type="Matriz Cadastrada"
    )
    _dnit_multi = len(_dnit_keys) >= 2
    if _dnit_multi:
        data = _combined_dnit_economic_data(road, _dnit_keys, _dnit_labels)
    else:
        _dkey = _dnit_keys[0] if _dnit_keys else scenario_key
        data = get_dnit_economic_data(road, _dkey)
    if not data.get("available") or data.get("table") is None or data["table"].empty:
        disponiveis = get_dnit_available_roads()
        if disponiveis:
            quais = ", ".join(f"**{r}**" for r in disponiveis)
            st.info(
                f"Esta rodovia não foi processada com a **Matriz Revitaliza DNIT/RO**. "
                f"No banco, {quais} possui(em) esse cálculo; as demais usam **Paragon**."
            )
        else:
            st.info("Nenhuma rodovia foi processada com a **Matriz Revitaliza DNIT/RO** ainda.")
        return

    if _dnit_multi:
        _render_economic_comparison(data["per_sentido"])

    table = data["table"].copy()
    segments_df = data["segments"]
    budget_items = data["budget_items"]
    total_need = float(table["Custo estimado"].sum())

    annual_budget, horizon, prio_max = _render_dnit_economic_controls(total_need, scenario_key)

    # Limita budget_items ao horizonte selecionado a partir do ano-base.
    ano_base = int(data.get("ano_base") or 2027)
    horizon_max = ano_base + horizon - 1
    if budget_items is not None and not budget_items.empty:
        budget_items = budget_items[
            (budget_items["Ano"] >= ano_base) & (budget_items["Ano"] <= horizon_max)
        ].copy()

    # Recalcula total_need considerando o horizonte recortado.
    if budget_items is not None and not budget_items.empty:
        custo_seg = budget_items.groupby("_segment_id")["Custo"].sum().to_dict()
        table["Custo estimado"] = table["_segment_id"].astype(int).map(custo_seg).fillna(0.0)
        total_need = float(budget_items["Custo"].sum())

    # Priorização DNIT por segmento (SNV herda o pior).
    work = table.copy()
    work["Custo econômico"] = work["Custo estimado"].astype(float)
    work = _aplicar_indice_priorizacao_dnit(work)

    # Agrega por SNV (× Sentido quando há) pra construir snv_budget_table.
    _dnit_gkeys = ["SNV", "Sentido"] if "Sentido" in work.columns else ["SNV"]
    snv_budget_table = (
        work.groupby(_dnit_gkeys, as_index=False)
        .agg({
            "Prioridade": "min",
            "Priorização": "max",
            "Classe prioridade": "first",
            "Km Inicial": "min",
            "Km Final": "max",
            "Extensão": "sum",
            "IRI": "mean",
            "IGG": "mean",
            "IPT": "max",
            "IPE": "max",
            "Custo econômico": "sum",
            "Solução recomendada": lambda v: " + ".join(dict.fromkeys(str(x) for x in v if str(x).strip())),
        })
        .sort_values("Prioridade")
        .reset_index(drop=True)
    )
    snv_budget_table["Prioridade"] = range(1, len(snv_budget_table) + 1)

    # Filtro por nível de prioridade.
    if prio_max < 10:
        snv_budget_table = snv_budget_table[snv_budget_table["Priorização"] <= prio_max].reset_index(drop=True)

    top_snvs = set(snv_budget_table["SNV"].astype(str))
    if budget_items is not None and not budget_items.empty:
        budget_items = budget_items[budget_items["SNV"].astype(str).isin(top_snvs)].copy()

    scope_km = float(snv_budget_table["Extensão"].sum()) if not snv_budget_table.empty else 0.0
    attended_snv_table, attended_km, attended_ids = _segment_attendance(
        snv_budget_table, budget_items, annual_budget, work
    )
    annual_coverage = min((annual_budget * 1_000_000) / total_need * 100, 100) if total_need else 0
    faltante = max(total_need - annual_budget * 1_000_000, 0.0)

    render_metric_cards([
        {"title": "NECESSIDADE TOTAL", "value": _format_money(total_need),
         "subtitle": f"Custo no horizonte de {horizon} anos", "tone": "cyan", "icon": "$"},
        {"title": "COBERTURA ANUAL", "value": f"{annual_coverage:.1f}%",
         "subtitle": f"{_format_money(annual_budget * 1_000_000)} cobre da necessidade", "tone": "green", "icon": "↗"},
        {"title": "TRECHOS ATENDIDOS", "value": f"{attended_km:.1f} / {scope_km:.1f} km",
         "subtitle": "Km de segmentos cobertos pelo orçamento", "tone": "orange", "icon": "#"},
        {"title": "ORÇAMENTO FALTANTE", "value": _format_money(faltante),
         "subtitle": ("Necessidade já coberta pelo orçamento" if faltante == 0
                      else "Adicional para cobrir 100% da necessidade"),
         "tone": "yellow", "icon": "△"},
    ])

    # Mapa do cenário: restringe os segmentos aos SNVs que passaram pelo filtro de
    # nível de prioridade. Sem isso, o mapa ignora o slider.
    if segments_df is not None and not segments_df.empty:
        scoped_segments = segments_df[segments_df["sre"].astype(str).isin(top_snvs)].copy()
        st.markdown(
            '<section class="solution-distribution" style="padding-bottom:16px">'
            '<div class="solution-distribution-head" style="margin-bottom:0">'
            '<div class="solution-distribution-title"><div class="solution-distribution-icon">◎</div>'
            '<div><h3>Cenário no mapa</h3><p>Trechos no nível de prioridade selecionado</p></div></div>'
            f'<div class="solution-distribution-meta"><span>Atendido · <strong>{attended_km:.1f} km</strong></span>'
            f'<span>Orçamento · <strong class="accent">{_format_money(annual_budget * 1_000_000)}/ano</strong></span></div>'
            '</div></section>',
            unsafe_allow_html=True,
        )
        render_dnit_map(
            scoped_segments,
            zona_colors=data.get("zona_colors"),
            zona_order=data.get("zona_order"),
        )

    # Cor por IRI faixa dominante de cada solução (compartilhada entre gráfico e PDF).
    seg_zona_color = dict(zip(
        table["_segment_id"].astype(int),
        table["_zona_color"].astype(str),
    ))
    solucao_iri_color: dict[str, str] = {}
    if budget_items is not None and not budget_items.empty:
        joined = budget_items.copy()
        joined["_zona_color"] = joined["_segment_id"].astype(int).map(seg_zona_color)
        solucao_iri_color = {
            str(sol): sub["_zona_color"].mode().iloc[0]
            for sol, sub in joined.groupby("Solução")
            if not sub["_zona_color"].mode().empty
        }

    # Custo por ano (gráfico de barras anual a partir do budget_items).
    if budget_items is not None and not budget_items.empty:
        _render_budget_cost_by_year(budget_items)
        _render_budget_cost_by_solution(
            budget_items,
            color_fn=lambda label: solucao_iri_color.get(str(label), "#9fb9d9"),
        )

    # Tabela de SNVs com priorização DNIT.
    _render_dnit_economic_priority_table(snv_budget_table, attended_snv_table, annual_budget)

    # Botão de exportação do PDF (mesma infra do Paragon, com adaptações DNIT).
    metrics = {"total_need": total_need, "total_budget": annual_budget * horizon * 1_000_000}
    scope_snv = int(len(snv_budget_table))
    top_label = "Todos" if prio_max >= 10 else f"Nível ≤ {prio_max}"

    # PDF espera coluna "classe_iap" nos segmentos; para DNIT, usa a faixa IRI.
    pdf_segments_df = segments_df
    if segments_df is not None and not segments_df.empty and "matriz_categoria" in segments_df.columns:
        pdf_segments_df = segments_df.rename(columns={"matriz_categoria": "classe_iap"}).copy()

    zona_colors = data.get("zona_colors") or {}
    _render_work_plan_button(
        scenario_key=scenario_key,
        road=road,
        scenario_label="Matriz Revitaliza DNIT/RO",
        annual_budget=annual_budget,
        horizon=horizon,
        top_label=top_label,
        metrics=metrics,
        annual_coverage=annual_coverage,
        attended_snv_table=attended_snv_table,
        scope_snv=scope_snv,
        attended_km=attended_km,
        budget_items=budget_items,
        segments_df=pdf_segments_df,
        priority_table=work,
        class_colors=zona_colors,
        attended_ids=attended_ids,
        solution_color=lambda label: solucao_iri_color.get(str(label), "#9fb9d9"),
    )


def _render_dnit_economic_priority_table(snv_budget_table, attended_snv_table, annual_budget: int) -> None:
    """Tabela enxuta para a página DNIT — Prior. + SRE + Km + IRI/IGG + Priorização + Solução + Custo."""
    if snv_budget_table is None or snv_budget_table.empty:
        st.info("Sem SNVs no filtro atual.")
        return

    attended_sres = set(attended_snv_table["SNV"].astype(str)) if attended_snv_table is not None and not attended_snv_table.empty else set()
    has_sentido = "Sentido" in snv_budget_table.columns
    rows_html = []
    for _, row in snv_budget_table.iterrows():
        sre = str(row.get("SNV"))
        atendido = sre in attended_sres
        sentido_td = f"<td>{html.escape(str(row.get('Sentido', '')))}</td>" if has_sentido else ""
        rows_html.append(
            "<tr>"
            f"<td>{int(row['Prioridade'])}</td>"
            f"<td>{html.escape(sre)}</td>"
            + sentido_td +
            f"<td>{_format_km(float(row['Km Inicial']))}</td>"
            f"<td>{_format_km(float(row['Km Final']))}</td>"
            f"<td>{_format_km(float(row['Extensão']))} km</td>"
            f"<td>{float(row.get('IRI', 0) or 0):.2f}</td>"
            f"<td>{float(row.get('IGG', 0) or 0):.0f}</td>"
            f"<td>{float(row.get('IPT', 0) or 0):.2f}</td>"
            f"<td>{float(row.get('IPE', 0) or 0):.2f}</td>"
            f"<td><span class='iap-pill'><span class='iap-pill-dot' style='background:{_priority_class_color(row.get('Classe prioridade'))}'></span>{int(round(float(row.get('Priorização', 0) or 0)))}</span></td>"
            f"<td>{html.escape(str(row.get('Solução recomendada', '')))}</td>"
            f"<td>{_format_money(float(row['Custo econômico']))}</td>"
            f"<td>{'✓ Atendido' if atendido else '— Fora'}</td>"
            "</tr>"
        )
    st.markdown(
        f"""
        <section class="solution-distribution" style="padding-bottom:8px">
          <div class="solution-distribution-head" style="margin-bottom:8px">
            <div class="solution-distribution-title">
              <div class="solution-distribution-icon">◎</div>
              <div><h3>SNVs atendidos pelo orçamento anual</h3><p>Carteira priorizada · custo do banco (Matriz Revitaliza DNIT/RO)</p></div>
            </div>
          </div>
          <table class="solution-table">
            <thead><tr>
              <th>PRIOR.</th><th>SRE</th>{'<th>SENTIDO</th>' if has_sentido else ''}<th>KM INICIAL</th><th>KM FINAL</th><th>EXTENSÃO</th>
              <th>IRI</th><th>IGG</th><th>IPT</th><th>IPE</th><th>PRIORIZAÇÃO</th>
              <th>SOLUÇÃO RECOMENDADA</th><th>CUSTO</th><th>STATUS</th>
            </tr></thead>
            <tbody>{''.join(rows_html)}</tbody>
          </table>
        </section>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Comparativo Paragon × DNIT (dentro de Cenário Econômico)
# ----------------------------------------------------------------------------
def _compute_paragon_pipeline(road: str, annual_budget: int, horizon: int, attended_budget_mi: int | None = None) -> dict:
    """Roda o pipeline Paragon e devolve métricas + budget agregado por ano.

    `attended_budget_mi` (R$ mi) = orçamento usado em "trechos atendidos"/cobertura.
    None → 1 ano (`annual_budget`, carteira anual = tela Cenário Econômico).
    Comparativo/compare passam `annual_budget * horizon` (escopo do horizonte).
    """
    scenarios = get_available_scenarios(road)
    if not scenarios:
        return {"available": False}
    scenario_key = scenarios[0]["key"]
    data = get_solutions_data(road, scenario_key=scenario_key)
    table = data.get("table")
    budget_items = data.get("budget_items")
    if table is None or table.empty:
        return {"available": False}

    budget_items = _limit_budget_to_horizon(budget_items, horizon)
    metrics, prioritized_table, _ = _simulate_economic_scenario(
        table, annual_budget, horizon, "Balanceada"
    )
    snv_budget_table = _group_budget_by_snv(budget_items, prioritized_table)

    if budget_items is not None and not budget_items.empty:
        total_need = float(budget_items["Custo"].sum())
    else:
        total_need = float(snv_budget_table["Custo econômico"].sum()) if not snv_budget_table.empty else 0.0

    # Orçamento de "atendidos"/cobertura: o caller decide. None = 1 ano (carteira anual,
    # = tela Cenário Econômico). Comparativo/compare passam anual×horizonte (senão um SNV
    # multi-ano nunca cabe em 1 ano → gerava 0 km na Paragon).
    eff_budget_mi = attended_budget_mi if attended_budget_mi is not None else annual_budget
    attended_tbl, attended_km, _ = _segment_attendance(snv_budget_table, budget_items, eff_budget_mi, prioritized_table)
    scope_km = float(snv_budget_table["Extensão"].sum()) if not snv_budget_table.empty else 0.0

    custo_por_ano = pd.DataFrame()
    if budget_items is not None and not budget_items.empty and "Ano" in budget_items.columns:
        custo_por_ano = (
            budget_items.groupby("Ano", as_index=False)["Custo"]
            .sum()
            .sort_values("Ano")
        )

    custo_por_snv = pd.DataFrame()
    if not snv_budget_table.empty:
        custo_por_snv = snv_budget_table[["SNV", "Extensão", "Custo econômico"]].copy()
        custo_por_snv.columns = ["SNV", "Extensão", "Custo"]

    return {
        "available": True,
        "total_need": total_need,
        "annual_coverage": min((eff_budget_mi * 1_000_000) / total_need * 100, 100) if total_need else 0,
        "attended_km": attended_km,
        "scope_km": scope_km,
        "custo_por_ano": custo_por_ano,
        "custo_por_snv": custo_por_snv,
        "attended_snv": (
            [{"snv": str(r["SNV"]), "ext_km": round(float(r["Extensão"]), 2),
              "custo": float(r["Custo econômico"])}
             for r in attended_tbl.to_dict("records")]
            if attended_tbl is not None and not attended_tbl.empty else []
        ),
        "scenario_label": scenarios[0]["cenario"],
    }


def _compute_dnit_pipeline(road: str, annual_budget: int, horizon: int, attended_budget_mi: int | None = None) -> dict:
    """Roda o pipeline DNIT e devolve métricas + budget agregado por ano.

    `attended_budget_mi`: ver _compute_paragon_pipeline (None = carteira de 1 ano).
    """
    data = get_dnit_economic_data(road)
    if not data.get("available") or data["table"].empty:
        return {"available": False}

    ano_base = int(data.get("ano_base") or 2027)
    horizon_max = ano_base + horizon - 1
    budget_items = data["budget_items"]
    if budget_items is not None and not budget_items.empty:
        budget_items = budget_items[
            (budget_items["Ano"] >= ano_base) & (budget_items["Ano"] <= horizon_max)
        ].copy()

    table = data["table"].copy()
    if budget_items is not None and not budget_items.empty:
        custo_seg = budget_items.groupby("_segment_id")["Custo"].sum().to_dict()
        table["Custo estimado"] = table["_segment_id"].astype(int).map(custo_seg).fillna(0.0)
        total_need = float(budget_items["Custo"].sum())
    else:
        total_need = float(table["Custo estimado"].sum())

    work = table.copy()
    work["Custo econômico"] = work["Custo estimado"].astype(float)
    work = _aplicar_indice_priorizacao_dnit(work)

    snv_budget_table = (
        work.groupby("SNV", as_index=False)
        .agg({"Prioridade": "min", "Priorização": "max", "Classe prioridade": "first",
              "Km Inicial": "min", "Km Final": "max", "Extensão": "sum",
              "Custo econômico": "sum"})
        .sort_values("Prioridade")
        .reset_index(drop=True)
    )
    # Orçamento de "atendidos"/cobertura: o caller decide. None = 1 ano (carteira anual,
    # = tela Cenário Econômico). Comparativo/compare passam anual×horizonte (senão um SNV
    # multi-ano nunca cabe em 1 ano → gerava 0 km na Paragon).
    eff_budget_mi = attended_budget_mi if attended_budget_mi is not None else annual_budget
    attended_tbl, attended_km, _ = _segment_attendance(snv_budget_table, budget_items, eff_budget_mi, work)
    scope_km = float(snv_budget_table["Extensão"].sum()) if not snv_budget_table.empty else 0.0

    custo_por_ano = pd.DataFrame()
    if budget_items is not None and not budget_items.empty:
        custo_por_ano = (
            budget_items.groupby("Ano", as_index=False)["Custo"]
            .sum()
            .sort_values("Ano")
        )

    custo_por_snv = pd.DataFrame()
    if not snv_budget_table.empty:
        custo_por_snv = snv_budget_table[["SNV", "Extensão", "Custo econômico"]].copy()
        custo_por_snv.columns = ["SNV", "Extensão", "Custo"]

    return {
        "available": True,
        "total_need": total_need,
        "annual_coverage": min((eff_budget_mi * 1_000_000) / total_need * 100, 100) if total_need else 0,
        "attended_km": attended_km,
        "scope_km": scope_km,
        "custo_por_ano": custo_por_ano,
        "custo_por_snv": custo_por_snv,
        "attended_snv": (
            [{"snv": str(r["SNV"]), "ext_km": round(float(r["Extensão"]), 2),
              "custo": float(r["Custo econômico"])}
             for r in attended_tbl.to_dict("records")]
            if attended_tbl is not None and not attended_tbl.empty else []
        ),
        "scenario_label": "Matriz Revitaliza DNIT/RO",
    }


def _render_compare_kpi(title: str, value_p: str, value_d: str) -> None:
    """Linha de comparação Paragon × DNIT — 1 KPI lado a lado."""
    st.markdown(
        f"""
        <div class="status-pill" style="width:100%;display:grid;
             grid-template-columns:1.2fr 1fr 1fr;gap:18px;align-items:center;
             padding:14px 18px;border-radius:14px;margin-bottom:10px;
             background:#0b1d28;border-color:#244257">
          <div style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;
               color:#8f9eaa;font-weight:800">{html.escape(title)}</div>
          <div style="text-align:center">
            <div style="font-size:10px;color:#00c2e8;font-weight:800;letter-spacing:.12em">PARAGON</div>
            <div style="font-size:18px;color:#f4f7fb;font-weight:850;margin-top:2px">{value_p}</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:10px;color:#f2a51a;font-weight:800;letter-spacing:.12em">DNIT</div>
            <div style="font-size:18px;color:#f4f7fb;font-weight:850;margin-top:2px">{value_d}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_compare_anual_bars(p_df: pd.DataFrame, d_df: pd.DataFrame) -> None:
    """Barras duplas Paragon × DNIT por ano (custo em R$ mi)."""
    if (p_df is None or p_df.empty) and (d_df is None or d_df.empty):
        return
    anos = sorted(set(
        (p_df["Ano"].tolist() if p_df is not None and not p_df.empty else []) +
        (d_df["Ano"].tolist() if d_df is not None and not d_df.empty else [])
    ))
    p_by = dict(zip(p_df["Ano"], p_df["Custo"])) if p_df is not None and not p_df.empty else {}
    d_by = dict(zip(d_df["Ano"], d_df["Custo"])) if d_df is not None and not d_df.empty else {}

    valores_mi = []
    for a in anos:
        valores_mi.append(float(p_by.get(a, 0)) / 1_000_000)
        valores_mi.append(float(d_by.get(a, 0)) / 1_000_000)
    max_val = max(valores_mi) if valores_mi else 1
    axis_max = _axis_max_10(max_val)
    ticks = _axis_ticks_10(axis_max)
    tick_markup = "".join(
        f'<span class="economic-y-tick" style="bottom:{t / axis_max * 100:.2f}%;">{t:.0f}</span>'
        for t in ticks
    )

    bars = []
    labels = []
    for a in anos:
        p_mi = float(p_by.get(a, 0)) / 1_000_000
        d_mi = float(d_by.get(a, 0)) / 1_000_000
        h_p = max(p_mi / axis_max * 100, 1 if p_mi > 0 else 0)
        h_d = max(d_mi / axis_max * 100, 1 if d_mi > 0 else 0)
        bars.append(
            f'<div class="economic-bar-item" style="display:flex;gap:2px;align-items:flex-end;justify-content:center">'
            f'<div class="economic-bar" style="height:{h_p:.2f}%;background:#00c2e8;flex:1;max-width:14px" '
            f'title="Paragon · {_format_money(p_mi * 1_000_000)}"></div>'
            f'<div class="economic-bar" style="height:{h_d:.2f}%;background:#f2a51a;flex:1;max-width:14px" '
            f'title="DNIT · {_format_money(d_mi * 1_000_000)}"></div>'
            '</div>'
        )
        labels.append(f'<div>{int(a)}</div>')

    total_p = sum(p_by.values())
    total_d = sum(d_by.values())
    st.markdown(
        '<section class="economic-panel">'
        '<div class="economic-head">'
        '<div class="economic-title"><div class="economic-icon">$</div>'
        '<div><h3>Custo por ano · Paragon × DNIT</h3>'
        '<p>Programação anual em R$ mi · azul = Paragon · laranja = DNIT</p></div></div>'
        f'<div class="solution-distribution-meta">'
        f'<span>Paragon · <strong style="color:#00c2e8">{_format_money(total_p)}</strong></span>'
        f'<span>DNIT · <strong style="color:#f2a51a">{_format_money(total_d)}</strong></span>'
        '</div></div>'
        '<div class="economic-chart">'
        f'<div class="economic-y-axis">{tick_markup}</div>'
        '<div class="economic-scroll">'
        f'<div class="economic-plot"><div class="economic-bars">{"".join(bars)}</div></div>'
        f'<div class="economic-labels">{"".join(labels)}</div>'
        '</div>'
        '</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def _render_compare_diff_table(p_df: pd.DataFrame, d_df: pd.DataFrame) -> None:
    """Tabela com custo por SRE em cada metodologia + delta."""
    p_by = dict(zip(p_df["SNV"].astype(str), p_df["Custo"])) if p_df is not None and not p_df.empty else {}
    d_by = dict(zip(d_df["SNV"].astype(str), d_df["Custo"])) if d_df is not None and not d_df.empty else {}
    p_ext = dict(zip(p_df["SNV"].astype(str), p_df["Extensão"])) if p_df is not None and not p_df.empty else {}
    d_ext = dict(zip(d_df["SNV"].astype(str), d_df["Extensão"])) if d_df is not None and not d_df.empty else {}

    sres = sorted(set(p_by.keys()) | set(d_by.keys()))
    if not sres:
        return

    rows_html = []
    for sre in sres:
        cp = float(p_by.get(sre, 0))
        cd = float(d_by.get(sre, 0))
        ext_p = float(p_ext.get(sre, 0))
        ext_d = float(d_ext.get(sre, 0))
        delta = cp - cd
        delta_color = "#00a651" if delta < 0 else ("#d71920" if delta > 0 else "#8f9eaa")
        delta_arrow = "▼" if delta < 0 else ("▲" if delta > 0 else "—")
        status = ""
        if not p_by.get(sre):
            status = " <span style='color:#8f9eaa;font-size:10px'>(só DNIT)</span>"
        elif not d_by.get(sre):
            status = " <span style='color:#8f9eaa;font-size:10px'>(só Paragon)</span>"

        rows_html.append(
            "<tr>"
            f"<td class='mono'>{html.escape(sre)}{status}</td>"
            f"<td style='text-align:right'>{_format_money(cp)}</td>"
            f"<td style='text-align:right;color:#8f9eaa'>{ext_p:.1f} km</td>"
            f"<td style='text-align:right'>{_format_money(cd)}</td>"
            f"<td style='text-align:right;color:#8f9eaa'>{ext_d:.1f} km</td>"
            f"<td style='text-align:right;color:{delta_color};font-weight:800'>"
            f"{delta_arrow} {_format_money(abs(delta))}</td>"
            "</tr>"
        )
    st.markdown(
        f"""
        <section class="solution-card">
          <div class="solution-card-head">
            <h3>Custo por trecho (SRE) · Paragon × DNIT</h3>
            <p>Delta positivo (vermelho) = Paragon mais caro · negativo (verde) = DNIT mais caro</p>
          </div>
          <div class="solution-table-wrap"><table class="solution-table">
            <thead><tr>
              <th>SRE</th>
              <th style='text-align:right;color:#00c2e8'>PARAGON · R$</th>
              <th style='text-align:right;color:#00c2e8'>EXT.</th>
              <th style='text-align:right;color:#f2a51a'>DNIT · R$</th>
              <th style='text-align:right;color:#f2a51a'>EXT.</th>
              <th style='text-align:right'>DELTA (P − D)</th>
            </tr></thead>
            <tbody>{''.join(rows_html)}</tbody>
          </table></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_comparativo_page(road: str, scenario_key: str | None) -> None:
    """Página Comparativo Paragon × DNIT — usa sliders compartilhados de orçamento e horizonte."""
    if road not in set(get_dnit_available_roads()):
        st.info(
            f"A rodovia **{road}** não tem cálculo DNIT no banco. "
            f"O comparativo precisa das duas metodologias. Disponíveis: "
            f"{', '.join(f'**{r}**' for r in get_dnit_available_roads()) or '_nenhuma_'}."
        )
        return

    # Sliders compartilhados (orçamento + horizonte). Sem slider de prioridade.
    st.markdown(
        """
        <section class="economic-panel">
          <div class="economic-head">
            <div class="economic-title">
              <div class="economic-icon">≋</div>
              <div><h3>Comparativo orçamentário</h3>
                   <p>Paragon × DNIT · mesmos parâmetros aplicados às duas metodologias</p></div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    horizon_col, budget_col = st.columns([1, 1], gap="medium")
    with horizon_col:
        _filter_caption("Horizonte")
        horizon = st.slider(
            "Horizonte (anos)", 1, 30, _ECONOMIC_DEFAULT_HORIZON, 1,
            key=f"cmp_horizon_{road}",
            label_visibility="collapsed",
        )
        st.markdown(f'<div class="economic-control-value">{horizon} anos</div>', unsafe_allow_html=True)
    with budget_col:
        _filter_caption("Orçamento anual (R$ mi)")
        annual_budget = st.slider(
            "Orçamento (R$ mi)", 1, 200, 50, 1,
            key=f"cmp_budget_{road}",
            label_visibility="collapsed",
        )
        st.markdown(f'<div class="economic-control-value">{_format_money(annual_budget * 1_000_000)}</div>', unsafe_allow_html=True)

    # Pipelines paralelos.
    paragon = _compute_paragon_pipeline(road, annual_budget, horizon, attended_budget_mi=annual_budget * horizon)
    dnit = _compute_dnit_pipeline(road, annual_budget, horizon, attended_budget_mi=annual_budget * horizon)

    if not paragon.get("available") or not dnit.get("available"):
        st.info("Pipeline incompleto: uma das metodologias não retornou dados.")
        return

    st.markdown("<div style='height: 18px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:13px;letter-spacing:.12em;text-transform:uppercase;'
        'color:#8f9eaa;font-weight:850;margin-bottom:10px">RESUMO COMPARATIVO</div>',
        unsafe_allow_html=True,
    )
    _render_compare_kpi(
        "Necessidade total no horizonte",
        _format_money(paragon["total_need"]),
        _format_money(dnit["total_need"]),
    )
    _render_compare_kpi(
        f"Cobertura no horizonte ({horizon} anos × orçamento)",
        f"{paragon['annual_coverage']:.1f}%",
        f"{dnit['annual_coverage']:.1f}%",
    )
    _render_compare_kpi(
        "Trechos atendidos no horizonte (km)",
        f"{paragon['attended_km']:.1f} / {paragon['scope_km']:.1f} km",
        f"{dnit['attended_km']:.1f} / {dnit['scope_km']:.1f} km",
    )
    _render_compare_kpi(
        "Orçamento faltante no horizonte",
        _format_money(max(paragon["total_need"] - annual_budget * horizon * 1_000_000, 0)),
        _format_money(max(dnit["total_need"] - annual_budget * horizon * 1_000_000, 0)),
    )

    st.markdown("<div style='height: 18px'></div>", unsafe_allow_html=True)
    _render_compare_anual_bars(paragon["custo_por_ano"], dnit["custo_por_ano"])
    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
    _render_compare_diff_table(paragon["custo_por_snv"], dnit["custo_por_snv"])

    st.markdown(
        '<div class="economic-note" style="margin-top:14px">'
        'Observação: cada metodologia segmenta a rodovia de forma diferente. O comparativo '
        'por SRE só é direto quando o mesmo trecho existe nas duas análises. '
        '<span style="color:#00c2e8;font-weight:700">Paragon</span> usa o cenário '
        f'<em>{html.escape(paragon["scenario_label"])}</em>; '
        '<span style="color:#f2a51a;font-weight:700">DNIT</span> usa '
        f'<em>{html.escape(dnit["scenario_label"])}</em>.'
        '</div>',
        unsafe_allow_html=True,
    )

    _render_iagon_comparativo(road, paragon, dnit, annual_budget, horizon)


@st.cache_data(show_spinner=False, ttl=3600)
def _iagon_comparativo_text(
    road: str, p_total: float, d_total: float, p_cov: float, d_cov: float,
    p_att: float, d_att: float, scope: float, annual_budget: int, horizon: int,
    top_snv_lines: str,
) -> str:
    """Chama a IAGON (system prompt + memória) para interpretar o comparativo.
    Cacheado pelos números → não re-chama a API em reruns/sliders inalterados."""
    try:
        from services import iagon
    except Exception:
        return ""
    if not iagon.is_configured():
        return ""
    razao = (p_total / d_total) if d_total else 0.0
    contexto = (
        f"Rodovia: BR-{road}.\n"
        f"Comparativo: metodologia Paragon × Matriz Revitaliza DNIT (mesma rodovia, mesmos km).\n"
        f"Horizonte: {horizon} anos · Orçamento: R$ {annual_budget} mi/ano "
        f"(R$ {annual_budget * horizon} mi no horizonte).\n\n"
        f"NECESSIDADE TOTAL NO HORIZONTE: Paragon R$ {p_total / 1e6:.1f} mi · "
        f"DNIT R$ {d_total / 1e6:.1f} mi (Paragon = {razao:.1f}× o DNIT).\n"
        f"COBERTURA NO HORIZONTE com este orçamento: Paragon {p_cov:.1f}% · DNIT {d_cov:.1f}%.\n"
        f"TRECHOS ATENDIDOS NO HORIZONTE: Paragon {p_att:.1f}/{scope:.1f} km · "
        f"DNIT {d_att:.1f}/{scope:.1f} km.\n\n"
        f"CUSTO POR TRECHO (SRE) — Paragon vs DNIT (delta = Paragon − DNIT):\n{top_snv_lines}\n"
    )
    pergunta = (
        "Você é a IAGON. Com base SOMENTE nos números acima, escreva uma análise técnica "
        "e objetiva (3 a 5 frases, em português, em prosa corrida — sem listas nem markdown) "
        "do comparativo Paragon × DNIT desta rodovia, para um gestor de pavimentos: "
        "(1) a diferença de custo total e o porquê — a Paragon prescreve soluções mais pesadas "
        "(reconstrução/fresagem) e a Revitaliza DNIT intervenções mais leves sobre os mesmos km; "
        "(2) o que o orçamento informado cobre em cada metodologia; "
        "(3) feche com uma recomendação prática. Não invente números além dos fornecidos."
    )
    try:
        return iagon.analisar(contexto, pergunta)
    except Exception:
        return ""


def _render_iagon_comparativo(road: str, paragon: dict, dnit: dict, annual_budget: int, horizon: int) -> None:
    """Bloco final: interpretação do comparativo gerada pela IAGON (com memória)."""
    try:
        from services import iagon
    except Exception:
        return
    if not iagon.is_configured():
        return

    # Top trechos por delta (Paragon − DNIT), em texto, para alimentar o modelo.
    p, d = paragon.get("custo_por_snv"), dnit.get("custo_por_snv")
    linhas = ""
    if p is not None and not p.empty and d is not None and not d.empty:
        m = p.merge(d, on="SNV", suffixes=("_p", "_d"))
        if not m.empty:
            m = m.rename(columns={"Custo_p": "cp", "Custo_d": "cd", "Extensão_p": "ext"})
            m["delta"] = m["cp"] - m["cd"]
            m = m.sort_values("delta", ascending=False).head(6)
            linhas = "\n".join(
                f"- {r.SNV}: Paragon R$ {r.cp / 1e6:.1f} mi · DNIT R$ {r.cd / 1e6:.1f} mi · "
                f"{r.ext:.1f} km · delta R$ {r.delta / 1e6:+.1f} mi"
                for r in m.itertuples()
            )

    with st.spinner("IAGON analisando o comparativo…"):
        texto = _iagon_comparativo_text(
            road, float(paragon["total_need"]), float(dnit["total_need"]),
            float(paragon["annual_coverage"]), float(dnit["annual_coverage"]),
            float(paragon["attended_km"]), float(dnit["attended_km"]),
            float(paragon["scope_km"]), int(annual_budget), int(horizon), linhas,
        )
    if not texto:
        return

    corpo = html.escape(texto).replace("\n\n", "<br><br>").replace("\n", "<br>")
    st.markdown(
        '<div style="margin-top:16px;border:1px solid rgba(0,194,232,.30);border-radius:14px;'
        'background:linear-gradient(180deg,rgba(0,194,232,.07),rgba(0,194,232,.02));padding:16px 18px">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        '<div style="width:30px;height:30px;border-radius:9px;background:#00c2e8;color:#04141b;'
        'display:flex;align-items:center;justify-content:center;font-weight:900;font-size:14px">IA</div>'
        '<div style="font-weight:850;letter-spacing:.03em;color:#e8f6fb;font-size:15px">Análise da IAGON</div>'
        '<div style="font-size:11px;color:#7fb9c9;font-weight:600">· interpretação automática · '
        'confira sempre os números acima</div></div>'
        f'<div style="color:#c8d6df;font-size:14px;line-height:1.65">{corpo}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _build_service_order_detail(attended_snv_table, priority_table, attended_ids: set | None = None) -> pd.DataFrame:
    """Detalhamento por segmento p/ ordem de serviço: trechos contíguos que precisam
    de intervenção (solução final do IAP), por SNV atendido, em ordem de prioridade.

    Quando `attended_ids` é informado (corte por segmento), restringe aos segmentos
    efetivamente financiados — assim um SNV parcialmente atendido só lista a porção
    coberta pelo orçamento."""
    if (
        attended_snv_table is None
        or attended_snv_table.empty
        or priority_table is None
        or priority_table.empty
    ):
        return pd.DataFrame()

    if attended_ids and "_segment_id" in priority_table.columns:
        priority_table = priority_table[priority_table["_segment_id"].astype(int).isin(attended_ids)]
        if priority_table.empty:
            return pd.DataFrame()

    rows = []
    for snv in attended_snv_table["SNV"].astype(str).tolist():
        seg = priority_table[priority_table["SNV"].astype(str) == snv]
        if seg.empty:
            continue
        base = seg.groupby(
            ["Km Inicial", "Km Final", "Extensão", "Solução recomendada"], as_index=False
        )["Custo econômico"].sum()
        base["Ano"] = ""
        for r in _consolidar_trechos_por_solucao(base).to_dict("records"):
            solucao = str(r["Solução recomendada"]).strip()
            if solucao.lower() in {"sem intervenção", "sem intervencao", ""}:
                continue  # ordem de serviço só onde precisa de intervenção
            rows.append(
                {
                    "SNV": snv,
                    "Km Inicial": float(r["Km Inicial"]),
                    "Km Final": float(r["Km Final"]),
                    "Extensão": float(r["Extensão"]),
                    "Intervenção": solucao,
                    "Custo": float(r.get("Custo econômico", 0) or 0),
                }
            )
    return pd.DataFrame(rows)


def _render_work_plan_button(
    *,
    scenario_key: str,
    road: str,
    scenario_label: str,
    annual_budget: int,
    horizon: int,
    top_label: str,
    metrics: dict,
    annual_coverage: float,
    attended_snv_table,
    scope_snv: int,
    attended_km: float,
    budget_items,
    segments_df,
    priority_table=None,
    class_colors: dict | None = None,
    solution_color=None,
    attended_ids: set | None = None,
) -> None:
    """Botão no fim da tela: gera o PDF do plano de trabalho do cenário atual."""
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    state_key = f"wp_pdf_{scenario_key}"
    class_colors = class_colors or _MAP_CLASS_COLORS
    solution_color = solution_color or _solution_color

    if st.button("📄 Gerar plano de trabalho (PDF)", key=f"genpdf_{scenario_key}"):
        seg_records = (
            segments_df[["segment_id", "classe_iap", "paths"]].to_dict("records")
            if segments_df is not None and not segments_df.empty
            else []
        )
        # Gráficos do plano refletem só os trechos atendidos pelo orçamento.
        attended_snvs = (
            set(attended_snv_table["SNV"].astype(str))
            if attended_snv_table is not None and not attended_snv_table.empty
            else set()
        )
        plan_budget = budget_items
        if budget_items is not None and not budget_items.empty:
            if attended_ids:
                # Corte por segmento: só os segmentos efetivamente financiados.
                plan_budget = budget_items[budget_items["_segment_id"].astype(int).isin(attended_ids)].copy()
            elif attended_snvs:
                plan_budget = budget_items[budget_items["SNV"].astype(str).isin(attended_snvs)].copy()
        plan_attended_ids = (
            attended_ids if attended_ids is not None
            else _attended_segment_ids(segments_df, attended_snv_table)
        )
        with st.spinner("Gerando plano de trabalho..."):
            st.session_state[state_key] = build_work_plan_pdf(
                road=road or "Rodovia",
                scenario_label=scenario_label or "Paragon",
                generated_at=date.today().strftime("%d/%m/%Y"),
                annual_budget_mi=annual_budget,
                horizon=horizon,
                top_label=top_label,
                metrics=metrics,
                annual_coverage=annual_coverage,
                attended_snv_table=attended_snv_table,
                scope_snv=scope_snv,
                attended_km=attended_km,
                budget_items=plan_budget,
                segments=seg_records,
                attended_ids=plan_attended_ids,
                class_colors=class_colors,
                solution_color=solution_color,
                segments_detail=_build_service_order_detail(attended_snv_table, priority_table, plan_attended_ids),
            )

    if st.session_state.get(state_key):
        st.download_button(
            "⬇ Baixar plano de trabalho",
            data=st.session_state[state_key],
            file_name=f"plano_trabalho_{road.replace('/', '-') or 'cenario'}.pdf",
            mime="application/pdf",
            key=f"dlpdf_{scenario_key}",
        )


# ═══════════════════════════════════════════════════════════════════════════
# Página: PROJEÇÃO — "evolução" (curva de condição IAP/IRI ao longo dos anos)
# ═══════════════════════════════════════════════════════════════════════════

# Severidade de solução por SUBSTRING do nome (README §14.4): define qual solução
# "ganha" a cor do ano quando um trecho recebe mais de uma intervenção no mesmo ano.
# Ordem = da mais severa (índice 0, Reconstrução) para a mais leve.
_SOLUTION_SEVERITY = [
    ("reconstru", "Reconstrução"),
    ("fresagem", "Fresagem e recomposição"),
    ("reforç", "Reforço"),
    ("microrrev", "Microrrevestimento"),
    ("reparo", "Reparo localizado"),
]


def _solution_severity(nome: str) -> int:
    """Ranqueia a gravidade da solução (0 = mais severa: Reconstrução)."""
    n = str(nome).lower()
    for i, (chave, _) in enumerate(_SOLUTION_SEVERITY):
        if chave in n:
            return i
    return len(_SOLUTION_SEVERITY)


def _render_intervention_table(sre_history: dict) -> None:
    """Lista cada SNV e em quais anos terá intervenção (chips de ano coloridos pela solução mais severa)."""
    if not sre_history:
        return

    present_ranks: set[int] = set()
    rows = []
    for sre in sorted(sre_history):
        chips = []
        for h in sre_history[sre]:
            if h.get("km", 0) > 0 and h.get("solucoes"):
                # cor do chip = solução mais severa do ano (ex.: Reconstrução vence Fresagem)
                severa = min(h["solucoes"], key=_solution_severity)
                present_ranks.add(_solution_severity(severa))
                cor = _solution_color(severa)
                tip = html.escape(f"{h['year']} · {h['label']} · {_format_km(h['km'])} km", quote=True)
                chips.append(
                    f'<span class="sol-chip" style="background:{cor};color:{_chip_text_color(cor)}" title="{tip}">{h["year"]}</span>'
                )
        anos = "".join(chips) if chips else "<span class='muted'>Sem intervenção</span>"
        rows.append(
            "<tr>"
            f"<td class='mono'>{html.escape(sre)}</td>"
            f"<td>{anos}</td>"
            "</tr>"
        )

    legend = "".join(
        f'<span class="cp-leg"><span class="cp-sw" style="background:{_solution_color(rotulo)}"></span>{html.escape(rotulo)}</span>'
        for i, (_, rotulo) in enumerate(_SOLUTION_SEVERITY)
        if i in present_ranks
    )

    st.markdown(
        '<section class="solution-card">'
        '<div class="solution-card-head">'
        '<h3>Pontos de intervenção por trecho (SNV)</h3>'
        '<p>Em quais anos cada trecho da rodovia receberá obra · cor = solução mais relevante do ano</p>'
        '</div>'
        '<div class="solution-table-wrap"><table class="solution-table">'
        '<thead><tr><th>SNV</th><th>Anos com intervenção</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        f'<div class="cp-legend" style="padding:0 20px 18px">{legend}</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def _render_projection_chart(series: dict, bands: list, ymax: float, meta: float, sre: str) -> None:
    """Desenha (SVG) a curva de projeção do IAP de um trecho ao longo dos anos.

    Fundo em faixas de conceito (Excelente…Péssimo), linha de meta tracejada
    (IAP_META = 2,5, README §12.3) e marcadores azuis nos anos com intervenção.
    """
    years = series.get("years", [])
    iap = series.get("iap", [])
    interv = series.get("interv", [])
    n = len(years)
    if n == 0:
        return

    W, H = 1080, 380
    L, R, T, B = 44, 118, 18, 40   # R largo p/ rótulos das faixas de conceito
    pw, ph = W - L - R, H - T - B

    def X(i: int) -> float:
        return L + (i / (n - 1) if n > 1 else 0) * pw

    def Y(v: float) -> float:
        return T + (1 - min(float(v), ymax) / ymax) * ph

    p: list[str] = []
    # faixas de conceito (fundo)
    for b in bands:
        y_hi, y_lo = Y(b["high"]), Y(b["low"])
        p.append(f'<rect x="{L}" y="{y_hi:.1f}" width="{pw}" height="{(y_lo - y_hi):.1f}" fill="{b["color"]}" opacity="0.18"/>')
        if (y_lo - y_hi) >= 13:
            p.append(f'<text x="{L + pw + 8}" y="{(y_hi + y_lo) / 2 + 3:.1f}" fill="{b["color"]}" font-size="10" font-weight="700">{html.escape(str(b["conceito"]))}</text>')
    # grade + eixo Y
    for t in range(0, int(ymax) + 1):
        gy = Y(t)
        p.append(f'<line x1="{L}" y1="{gy:.1f}" x2="{L + pw}" y2="{gy:.1f}" stroke="rgba(148,163,184,.12)" stroke-width="1"/>')
        p.append(f'<text x="{L - 8}" y="{gy + 3:.1f}" fill="#8f9eaa" font-size="10" text-anchor="end">{t}</text>')
    # linha da meta
    my = Y(meta)
    p.append(f'<line x1="{L}" y1="{my:.1f}" x2="{L + pw}" y2="{my:.1f}" stroke="#ff314a" stroke-width="1.6" stroke-dasharray="6 4"/>')
    p.append(f'<text x="{L + 6}" y="{my - 5:.1f}" fill="#ff6b7e" font-size="10" font-weight="700">Meta 2,5</text>')
    # linha do trecho
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(iap))
    p.append(f'<polyline points="{pts}" fill="none" stroke="#f4f7fb" stroke-width="2.6"/>')
    # marcadores (azul = ano com intervenção) + área transparente p/ hover (tooltip JS)
    solucoes = series.get("solucoes") or [[] for _ in years]
    for i, v in enumerate(iap):
        tip = f"{years[i]} · IAP {v:.2f}"
        if interv[i] and i < len(solucoes) and solucoes[i]:
            tip += " · " + " + ".join(solucoes[i])
        tip = html.escape(tip, quote=True)
        if interv[i]:
            p.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="5" fill="#00c2e8" stroke="#06222b" stroke-width="1.5"/>')
        else:
            p.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="2.6" fill="#f4f7fb"/>')
        p.append(f'<circle class="pt" data-tip="{tip}" cx="{X(i):.1f}" cy="{Y(v):.1f}" r="13" fill="transparent" pointer-events="all"/>')
    # eixo X
    step = max(1, n // 12)
    for i, yr in enumerate(years):
        if i % step == 0 or i == n - 1:
            p.append(f'<text x="{X(i):.1f}" y="{T + ph + 16}" fill="#8f9eaa" font-size="10" text-anchor="middle">{yr}</text>')

    svg = (
        f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="xMidYMid meet" '
        f'style="display:block;width:100%;height:auto">{"".join(p)}</svg>'
    )

    css = (
        'html,body{margin:0;padding:0;background:#0b1d28;'
        'font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;}'
        '.card{padding:18px 20px 16px;color:#f4f7fb;}'
        '.h3{margin:0;font-size:15px;font-weight:850;}'
        '.sub{margin:3px 0 0;font-size:12px;color:#92a1ad;}'
        '.chart{margin-top:14px;}'
        '.legend{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;padding-top:12px;'
        'border-top:1px solid rgba(148,163,184,.12);}'
        '.leg{display:inline-flex;align-items:center;gap:8px;color:#cbd5dd;font-size:12px;font-weight:700;}'
        '.leg .sw{width:16px;height:4px;border-radius:2px;display:inline-block;}'
        '.leg .sw-dot{width:11px;height:11px;border-radius:999px;}'
        '.leg .sw-dash{width:16px;border-top:2px dashed #ff314a;}'
        '.pt{cursor:pointer;}'
        '#tip{position:fixed;pointer-events:none;background:rgba(7,17,25,.97);'
        'border:1px solid #244257;color:#f4f7fb;font-size:12px;font-weight:600;'
        'padding:7px 10px;border-radius:8px;opacity:0;transition:opacity .08s;'
        'white-space:nowrap;z-index:99;box-shadow:0 10px 30px rgba(0,0,0,.45);}'
    )
    js = (
        "var tip=document.getElementById('tip');"
        "document.querySelectorAll('.pt').forEach(function(el){"
        "el.addEventListener('mousemove',function(e){"
        "tip.textContent=el.getAttribute('data-tip');tip.style.opacity='1';"
        "tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY-6)+'px';});"
        "el.addEventListener('mouseleave',function(){tip.style.opacity='0';});});"
    )
    legend_inner = (
        '<span class="leg"><span class="sw" style="background:#f4f7fb"></span>Condição do trecho (IAP)</span>'
        '<span class="leg"><span class="sw sw-dot" style="background:#00c2e8"></span>Ano com intervenção</span>'
        '<span class="leg"><span class="sw sw-dash"></span>Meta mínima (2,5)</span>'
    )
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style></head><body>"
        "<div class='card'>"
        f"<div class='h3'>Projeção do trecho {html.escape(str(sre))}</div>"
        "<div class='sub'>Qualidade do pavimento (IAP) ano a ano · faixas = conceito · marcador azul = ano com intervenção</div>"
        f"<div class='chart'>{svg}</div>"
        f"<div class='legend'>{legend_inner}</div>"
        "</div><div id='tip'></div>"
        "<script>" + js + "</script></body></html>"
    )
    components.html(doc, height=540, scrolling=False)


# Faixas IRI da Matriz DNIT — bands do gráfico de projeção (cores idem ao mapa DNIT).
_DNIT_IRI_BANDS = [
    {"low": 0.0, "high": 3.0, "color": "#00a651", "conceito": "IRI ≤ 3"},
    {"low": 3.0, "high": 4.0, "color": "#fff200", "conceito": "3 < IRI ≤ 4"},
    {"low": 4.0, "high": 5.5, "color": "#f2a51a", "conceito": "4 < IRI ≤ 5,5"},
    {"low": 5.5, "high": 8.0, "color": "#d71920", "conceito": "IRI > 5,5"},
]


def _render_dnit_iri_chart(series: dict, sre: str) -> None:
    """Mesma estrutura do gráfico Paragon, mas com IRI e faixas da Matriz DNIT."""
    years = series.get("years", [])
    iri = series.get("iri", [])
    interv = series.get("interv", [])
    n = len(years)
    if n == 0:
        return

    bands = _DNIT_IRI_BANDS
    # Escala Y: cobre as bandas e o pico observado, com folga.
    ymax = max(8.0, max(iri) * 1.10 if iri else 8.0)
    meta = 3.0  # IRI ≤ 3 é a faixa "boa" — meta de manutenção.

    W, H = 1080, 380
    L, R, T, B = 44, 138, 18, 40
    pw, ph = W - L - R, H - T - B

    def X(i: int) -> float:
        return L + (i / (n - 1) if n > 1 else 0) * pw

    def Y(v: float) -> float:
        # Eixo invertido: IRI baixo (bom) fica no topo, IRI alto (ruim) embaixo.
        # Assim intervenção que reduz o IRI aparece como linha SUBINDO no gráfico.
        return T + (min(float(v), ymax) / ymax) * ph

    p: list[str] = []
    for b in bands:
        # Com eixo invertido: low (bom) -> topo da faixa; high (ruim) -> base da faixa.
        y_top = Y(b["low"])
        y_bot = Y(b["high"])
        height = max(y_bot - y_top, 0)
        p.append(f'<rect x="{L}" y="{y_top:.1f}" width="{pw}" height="{height:.1f}" fill="{b["color"]}" opacity="0.20"/>')
        if height >= 13:
            p.append(
                f'<text x="{L + pw + 8}" y="{(y_top + y_bot) / 2 + 3:.1f}" '
                f'fill="{b["color"]}" font-size="10" font-weight="700">{html.escape(str(b["conceito"]))}</text>'
            )

    # Grade + eixo Y (passo de 1).
    for t in range(0, int(ymax) + 1):
        gy = Y(t)
        p.append(f'<line x1="{L}" y1="{gy:.1f}" x2="{L + pw}" y2="{gy:.1f}" stroke="rgba(148,163,184,.12)" stroke-width="1"/>')
        p.append(f'<text x="{L - 8}" y="{gy + 3:.1f}" fill="#8f9eaa" font-size="10" text-anchor="end">{t}</text>')

    # Linha da meta (IRI ≤ 3).
    my = Y(meta)
    p.append(f'<line x1="{L}" y1="{my:.1f}" x2="{L + pw}" y2="{my:.1f}" stroke="#ff314a" stroke-width="1.6" stroke-dasharray="6 4"/>')
    p.append(f'<text x="{L + 6}" y="{my - 5:.1f}" fill="#ff6b7e" font-size="10" font-weight="700">Limite 3,0</text>')

    # Linha do trecho (IRI ao longo do tempo).
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(iri))
    p.append(f'<polyline points="{pts}" fill="none" stroke="#f4f7fb" stroke-width="2.6"/>')

    # Marcadores: azul = ano com intervenção; branco = projeção sem obra.
    for i, v in enumerate(iri):
        tip = f"{years[i]} · IRI {v:.2f}"
        if interv[i]:
            tip += " · Intervenção"
        tip = html.escape(tip, quote=True)
        if interv[i]:
            p.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="5" fill="#00c2e8" stroke="#06222b" stroke-width="1.5"/>')
        else:
            p.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="2.6" fill="#f4f7fb"/>')
        p.append(f'<circle class="pt" data-tip="{tip}" cx="{X(i):.1f}" cy="{Y(v):.1f}" r="13" fill="transparent" pointer-events="all"/>')

    # Eixo X.
    step = max(1, n // 12)
    for i, yr in enumerate(years):
        if i % step == 0 or i == n - 1:
            p.append(f'<text x="{X(i):.1f}" y="{T + ph + 16}" fill="#8f9eaa" font-size="10" text-anchor="middle">{yr}</text>')

    svg = (
        f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="xMidYMid meet" '
        f'style="display:block;width:100%;height:auto">{"".join(p)}</svg>'
    )

    css = (
        'html,body{margin:0;padding:0;background:#0b1d28;'
        'font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;}'
        '.card{padding:18px 20px 16px;color:#f4f7fb;}'
        '.h3{margin:0;font-size:15px;font-weight:850;}'
        '.sub{margin:3px 0 0;font-size:12px;color:#92a1ad;}'
        '.chart{margin-top:14px;}'
        '.legend{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;padding-top:12px;'
        'border-top:1px solid rgba(148,163,184,.12);}'
        '.leg{display:inline-flex;align-items:center;gap:8px;color:#cbd5dd;font-size:12px;font-weight:700;}'
        '.leg .sw{width:16px;height:4px;border-radius:2px;display:inline-block;}'
        '.leg .sw-dot{width:11px;height:11px;border-radius:999px;}'
        '.leg .sw-dash{width:16px;border-top:2px dashed #ff314a;}'
        '.pt{cursor:pointer;}'
        '#tip{position:fixed;pointer-events:none;background:rgba(7,17,25,.97);'
        'border:1px solid #244257;color:#f4f7fb;font-size:12px;font-weight:600;'
        'padding:7px 10px;border-radius:8px;opacity:0;transition:opacity .08s;'
        'white-space:nowrap;z-index:99;box-shadow:0 10px 30px rgba(0,0,0,.45);}'
    )
    js = (
        "var tip=document.getElementById('tip');"
        "document.querySelectorAll('.pt').forEach(function(el){"
        "el.addEventListener('mousemove',function(e){"
        "tip.textContent=el.getAttribute('data-tip');tip.style.opacity='1';"
        "tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY-6)+'px';});"
        "el.addEventListener('mouseleave',function(){tip.style.opacity='0';});});"
    )
    legend_inner = (
        '<span class="leg"><span class="sw" style="background:#f4f7fb"></span>Irregularidade do trecho (IRI)</span>'
        '<span class="leg"><span class="sw sw-dot" style="background:#00c2e8"></span>Ano com intervenção</span>'
        '<span class="leg"><span class="sw sw-dash"></span>Limite recomendado (3,0)</span>'
    )
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style></head><body>"
        "<div class='card'>"
        f"<div class='h3'>Projeção do trecho {html.escape(str(sre))}</div>"
        "<div class='sub'>IRI projetado ano a ano · faixas = Matriz DNIT · marcador azul = ano com intervenção</div>"
        f"<div class='chart'>{svg}</div>"
        f"<div class='legend'>{legend_inner}</div>"
        "</div><div id='tip'></div>"
        "<script>" + js + "</script></body></html>"
    )
    components.html(doc, height=540, scrolling=False)


def _chip_text_color(hex_color: str) -> str:
    """Texto escuro ou claro conforme a luminância da cor de fundo (legibilidade)."""
    h = str(hex_color).lstrip("#")
    if len(h) != 6:
        return "#061018"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#061018" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#f4f7fb"


def _solution_chips(solucoes: list) -> str:
    """Renderiza uma lista de soluções como chips coloridos (cor por `_solution_color`)."""
    chips = []
    for nome in solucoes:
        cor = _solution_color(str(nome))
        chips.append(
            f'<span class="sol-chip" style="background:{cor};color:{_chip_text_color(cor)}">{html.escape(str(nome))}</span>'
        )
    return "".join(chips)


def _render_projection_history(history: list, sre: str) -> None:
    """Histórico de intervenções do trecho ano a ano (o que foi feito em cada ano)."""
    if not history:
        return

    rows = [
        "<tr>"
        f"<td class='muted'>{h['year']}</td>"
        f"<td>{_solution_chips(h['solucoes'])}</td>"
        f"<td>{_format_km(float(h['km']))} km</td>"
        "</tr>"
        for h in history
        if h.get("km", 0) > 0 and h.get("solucoes")
    ]
    if not rows:
        rows = ["<tr><td class='muted' colspan='3'>Sem intervenções no horizonte.</td></tr>"]

    st.markdown(
        '<section class="solution-card">'
        '<div class="solution-card-head">'
        f'<h3>Histórico de intervenções — trecho {html.escape(str(sre))}</h3>'
        '<p>O que foi executado em cada ano do horizonte</p>'
        '</div>'
        '<div class="solution-table-wrap"><table class="solution-table">'
        '<thead><tr><th>Ano</th><th>Intervenção</th><th>Extensão</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table></div>'
        '</section>',
        unsafe_allow_html=True,
    )


# ── Projeção "Solução × Vida útil" (Paragon) ─────────────────────────────────
# Gráfico ILUSTRATIVO: como cada família de solução se comporta no tempo — o IAP
# degrada após a obra; as soluções mais leves precisam reexecutar em ciclos
# (dente-de-serra) e a recomendada é destacada. Espessura/vida útil são valores
# TÍPICOS de engenharia (não há base no banco). A solução RECOMENDADA por trecho
# é dado REAL (vem da matriz Paragon). Cores: paleta do Paragon (verde→vermelho).
_PROJ_TOP, _PROJ_FAIL, _PROJ_LIMIT, _PROJ_P = 5.0, 0.85, 3.0, 1.8

# Catálogo hardcoded das 4 famílias (README §14.3): cor, espessura (cm), vida útil
# (anos) e custo/km TÍPICOS de engenharia. ATENÇÃO: estes custos NÃO batem com o
# catálogo do cenário econômico (§14.1) — ex.: Reconstrução 2,5 mi aqui vs. 1,25 mi lá.
_SOL_FAMILIES = [
    {"key": "micro",    "nome": "Microrrevestimento",      "cor": "#00a651", "espessura": 2.0,  "vida": 5,  "custo_km": 95_000,    "comport": "degradação rápida — ganho funcional"},
    {"key": "fresagem", "nome": "Fresagem + recomposição", "cor": "#fff200", "espessura": 6.5,  "vida": 8,  "custo_km": 285_000,   "comport": "degradação média — recupera a funcionalidade"},
    {"key": "reforco",  "nome": "Reforço estrutural",      "cor": "#f2a51a", "espessura": 12.0, "vida": 11, "custo_km": 740_000,   "comport": "degradação lenta — aumenta a capacidade estrutural"},
    {"key": "recon",    "nome": "Reconstrução",            "cor": "#d71920", "espessura": 30.0, "vida": 18, "custo_km": 2_500_000, "comport": "reset estrutural — vida longa e estável"},
]
_SOL_FAM_BY_KEY = {f["key"]: f for f in _SOL_FAMILIES}
# Código da matriz Paragon → família (intensidade crescente).
_CODE_TO_FAMILY = {"OK": None, "RL": "micro", "RL+RS": "micro", "RPS": "fresagem",
                   "RL+REF": "reforco", "RPS+REF": "reforco", "REC": "recon"}
_SOL_INTENSITY = {"OK": 0, "RL": 1, "RL+RS": 2, "RPS": 3, "RL+REF": 4, "RPS+REF": 5, "REC": 6}


@cached(ttl=1800)
def _recommended_family_by_sre(road: str, scenario_key: str | None) -> dict:
    """Por SRE → família recomendada = a solução MAIS INTENSA recomendada no trecho
    (mapeada das 7 soluções Paragon p/ as 4 famílias). Dado REAL da matriz Paragon."""
    data = get_solutions_data(road, scenario_key=scenario_key)
    table = data.get("table")
    out: dict = {}
    # Na tabela de soluções o trecho é a coluna "SNV" (== SRE da projeção).
    if table is None or table.empty or "SNV" not in table.columns or "_solucao_codigo" not in table.columns:
        return out
    for sre, sub in table.groupby("SNV"):
        codes = [str(c) for c in sub["_solucao_codigo"].tolist()]
        best = max(codes, key=lambda c: _SOL_INTENSITY.get(c, 0)) if codes else "OK"
        out[str(sre)] = _CODE_TO_FAMILY.get(best)
    return out


def _lifecycle_points(vida: int, horizon: int, recommended: bool, steps: int = 6):
    """Pontos (ano, IAP) ILUSTRATIVOS. Recomendada: declínio único até a falha ao
    longo da vida útil. Demais: dente-de-serra (reexecuta a cada `vida` anos)."""
    span = _PROJ_TOP - _PROJ_FAIL
    pts = []
    for i in range(horizon * steps + 1):
        t = i / steps
        x = min(t / vida, 1.0) if recommended else (t % vida) / vida
        pts.append((t, _PROJ_TOP - span * (x ** _PROJ_P)))
    return pts


def _render_solution_lifecycle_chart(rec_key: str | None, horizon: int) -> None:
    """Card (header + gráfico SVG de linhas) das 4 famílias × vida útil, ilustrativo."""
    W, H = 1200, 340
    L, R, T, B = 50, 26, 16, 34
    pw, ph = W - L - R, H - T - B
    X = lambda t: L + (t / horizon) * pw
    Y = lambda v: T + (1 - (v - _PROJ_FAIL) / (_PROJ_TOP - _PROJ_FAIL)) * ph

    p: list[str] = []
    for v in (_PROJ_TOP, _PROJ_LIMIT, _PROJ_FAIL):
        gy = Y(v)
        p.append(f'<line x1="{L}" y1="{gy:.1f}" x2="{L + pw}" y2="{gy:.1f}" stroke="rgba(148,163,184,.12)" stroke-width="1"/>')
        p.append(f'<text x="{L - 8}" y="{gy + 3:.1f}" fill="#8f9eaa" font-size="10" text-anchor="end">{v:.2f}</text>')
    ly = Y(_PROJ_LIMIT)
    p.append(f'<line x1="{L}" y1="{ly:.1f}" x2="{L + pw}" y2="{ly:.1f}" stroke="#f2a51a" stroke-width="1.5" stroke-dasharray="6 4"/>')
    p.append(f'<text x="{L + pw - 4}" y="{ly - 5:.1f}" fill="#f2a51a" font-size="10" font-weight="700" text-anchor="end">Limite mínimo (3,0)</text>')
    stepx = 1 if horizon <= 12 else 2
    for a in range(0, horizon + 1, stepx):
        p.append(f'<text x="{X(a):.1f}" y="{T + ph + 15:.0f}" fill="#8f9eaa" font-size="10" text-anchor="middle">A{a}</text>')
    # famílias não-recomendadas atrás; recomendada por cima (destaque)
    ordered = [f for f in _SOL_FAMILIES if f["key"] != rec_key] + [f for f in _SOL_FAMILIES if f["key"] == rec_key]
    for f in ordered:
        is_rec = f["key"] == rec_key
        poly = " ".join(f"{X(t):.1f},{Y(c):.1f}" for t, c in _lifecycle_points(f["vida"], horizon, is_rec))
        p.append(f'<polyline points="{poly}" fill="none" stroke="{f["cor"]}" stroke-width="{3.6 if is_rec else 1.8}" opacity="{1.0 if is_rec else 0.62}" stroke-linejoin="round" stroke-linecap="round"/>')
    svg = (f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="xMidYMid meet" '
           f'style="display:block;width:100%;height:auto">{"".join(p)}</svg>')

    rec = _SOL_FAM_BY_KEY.get(rec_key)
    kpis = [
        ("RECOMENDADA", rec["nome"] if rec else "Sem intervenção", rec["cor"] if rec else "#9aa8b3"),
        ("ESPESSURA", f"{rec['espessura']:.1f} cm" if rec else "—", "#e5edf3"),
        ("VIDA ÚTIL", f"{rec['vida']} anos" if rec else "—", "#e5edf3"),
        ("CUSTO/KM", _format_money(rec["custo_km"]) if rec else "—", "#e5edf3"),
        ("PRÓX. INTERVENÇÃO", f"Ano {rec['vida']}" if rec else "—", "#e5edf3"),
    ]
    head = "".join(
        f'<div class="kpi"><div class="kl">{l}</div><div class="kv" style="color:{c}">{html.escape(str(v))}</div></div>'
        for l, v, c in kpis
    )
    legend = "".join(
        f'<span class="leg"><span class="sw" style="background:{f["cor"]}"></span>{html.escape(f["nome"])}'
        + ('<b class="rec">● recomendada</b>' if f["key"] == rec_key else '') + '</span>'
        for f in _SOL_FAMILIES
    )
    css = (
        'html,body{margin:0;padding:0;background:#0b1d28;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;}'
        '.card{padding:18px 20px 16px;color:#f4f7fb;}'
        '.title{display:flex;align-items:center;gap:10px;}'
        '.ic{width:34px;height:34px;border-radius:12px;display:grid;place-items:center;background:#00c2e8;color:#031019;font-weight:900;}'
        '.h3{margin:0;font-size:15px;font-weight:850;}.sub{margin:2px 0 0;font-size:12px;color:#92a1ad;}'
        '.head{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 4px;}'
        '.kpi{flex:1;min-width:150px;background:rgba(7,17,25,.5);border:1px solid rgba(148,163,184,.18);border-radius:12px;padding:11px 14px;}'
        '.kl{font-size:10px;letter-spacing:.1em;color:#8f9eaa;text-transform:uppercase;}'
        '.kv{font-size:19px;font-weight:850;margin-top:3px;}'
        '.chart{margin-top:8px;}'
        '.legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;padding-top:12px;border-top:1px solid rgba(148,163,184,.12);}'
        '.leg{display:inline-flex;align-items:center;gap:7px;color:#cbd5dd;font-size:12px;font-weight:700;}'
        '.leg .sw{width:16px;height:4px;border-radius:2px;display:inline-block;}'
        '.leg .rec{color:#00c2e8;font-size:11px;font-weight:800;}'
    )
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style></head><body>"
        "<div class='card'><div class='title'><div class='ic'>🛠️</div>"
        "<div><div class='h3'>Solução × Vida útil — comportamento físico</div>"
        "<div class='sub'>Comparativo ilustrativo das 4 famílias de intervenção aplicadas ao mesmo trecho</div></div></div>"
        f"<div class='head'>{head}</div>"
        f"<div class='chart'>{svg}</div><div class='legend'>{legend}</div></div></body></html>"
    )
    components.html(doc, height=560, scrolling=False)


def _render_projection_page(road: str, scenario_key: str | None) -> None:
    """Projeção (Paragon) reformulada: Solução × Vida útil — gráfico ILUSTRATIVO que
    mostra quanto tempo cada família de solução dura no trecho selecionado."""
    proj = get_projection_data(road, scenario_key=scenario_key)
    sre_list = (proj or {}).get("sre_list") or []
    rec_map = _recommended_family_by_sre(road, scenario_key)

    if not sre_list:
        st.info("Sem trechos com projeção para este cenário.")
        return

    # Filtros da tela: Trecho (SRE) + horizonte (10/15/20 anos). Rodovia/Matriz/Cenário
    # vêm da barra do topo (render_top_bar), como nas outras telas.
    default = proj.get("default_sre")
    sel_col, hz_col = st.columns([2, 1], gap="large")
    with sel_col:
        _filter_caption("Trecho (SRE)")
        idx = sre_list.index(default) if default in sre_list else 0
        sre = st.selectbox("Trecho", sre_list, index=idx, label_visibility="collapsed")
    with hz_col:
        _filter_caption("Horizonte")
        horizon = st.radio("Horizonte", [10, 15, 20], index=2, horizontal=True,
                           format_func=lambda a: f"{a} anos", label_visibility="collapsed")

    rec_key = rec_map.get(str(sre)) or "recon"  # fallback: trecho sem código → reconstrução

    _render_solution_lifecycle_chart(rec_key, int(horizon))

    # Tabela das 4 famílias (curva destacada = recomendada).
    rows = ""
    for f in _SOL_FAMILIES:
        badge = ' <span class="sl-badge">RECOMENDADA</span>' if f["key"] == rec_key else ""
        rows += (
            "<tr>"
            f'<td><span class="sl-dot" style="background:{f["cor"]}"></span>{html.escape(f["nome"])}{badge}</td>'
            f'<td>{f["espessura"]:.1f} cm</td>'
            f'<td>{f["vida"]} anos</td>'
            f'<td>{_format_money(f["custo_km"])}/km</td>'
            f'<td class="sl-beh">{html.escape(f["comport"])}</td>'
            "</tr>"
        )
    st.markdown(
        "<style>"
        ".sl-table{width:100%;border-collapse:collapse;margin-top:14px;font-size:13px;}"
        ".sl-table th,.sl-table td{padding:11px 14px;text-align:right;border-bottom:1px solid rgba(148,163,184,.14);}"
        ".sl-table th{color:#8f9eaa;font-size:10px;letter-spacing:.08em;text-transform:uppercase;}"
        ".sl-table th:first-child,.sl-table td:first-child{text-align:left;color:#e5edf3;font-weight:700;}"
        ".sl-table .sl-beh{text-align:left;color:#9aa8b3;font-weight:400;}"
        ".sl-dot{width:10px;height:10px;border-radius:999px;display:inline-block;margin-right:8px;}"
        ".sl-badge{margin-left:8px;font-size:9px;font-weight:800;letter-spacing:.06em;color:#00c2e8;border:1px solid rgba(0,194,232,.4);border-radius:6px;padding:1px 6px;}"
        "</style>"
        "<table class='sl-table'><thead><tr>"
        "<th>Solução</th><th>Espessura</th><th>Vida útil</th><th>Custo/km</th><th>Comportamento</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )
    _rec = _SOL_FAM_BY_KEY.get(rec_key)
    if _rec:
        st.caption(
            f"Curva destacada: **{_rec['nome']}** — espessura típica {_rec['espessura']:.1f} cm, "
            f"vida útil ~{_rec['vida']} anos. As demais curvas mostram como o MESMO trecho se comportaria "
            "com soluções alternativas: as mais leves voltam ao limite em ciclos curtos (reexecução = "
            "dente-de-serra), a reconstrução dura mais. **Gráfico ilustrativo** — espessura e vida útil são "
            "valores típicos de engenharia; a solução recomendada vem da matriz Paragon do trecho."
        )


# ----------------------------------------------------------------------------
# Projeção DNIT — cronograma anual de intervenções por trecho
# ----------------------------------------------------------------------------
def _render_dnit_projection_page(road: str, scenario_key: str | None) -> None:
    """Projeção DNIT: cronograma anual de obras por SRE + custo por ano + projeção de IRI.
    Diferente da Paragon (curvas ilustrativas) — aqui os anos/custos vêm do banco."""
    data = get_dnit_projection_schedule(road, scenario_key)
    if not data.get("available"):
        disponiveis = get_dnit_available_roads()
        if disponiveis:
            quais = ", ".join(f"**{r}**" for r in disponiveis)
            st.info(
                f"Esta rodovia não foi processada com a **Matriz Revitaliza DNIT/RO**. "
                f"No banco, {quais} possui(em) esse cálculo."
            )
        else:
            st.info("Nenhuma rodovia foi processada com a **Matriz Revitaliza DNIT/RO** ainda.")
        return

    schedule = data["schedule"]
    anos = data["anos"]
    sre_list = data["sre_list"]
    custo_total = data["custo_total"]
    group_colors = data.get("group_colors", {})

    # KPI cards
    n_obras = int(len(schedule))
    n_sres = len(sre_list)
    ano_pico_row = data["custo_por_ano"].sort_values("Custo", ascending=False).head(1)
    ano_pico = int(ano_pico_row["Ano"].iloc[0]) if not ano_pico_row.empty else None
    custo_pico = float(ano_pico_row["Custo"].iloc[0]) if not ano_pico_row.empty else 0.0

    render_metric_cards([
        {"title": "TOTAL DE OBRAS", "value": f"{n_obras}",
         "subtitle": f"Intervenções DNIT entre {data['ano_inicial']}–{data['ano_final']}",
         "tone": "cyan", "icon": "#"},
        {"title": "TRECHOS COM OBRA", "value": f"{n_sres}",
         "subtitle": "SREs com pelo menos 1 intervenção", "tone": "green", "icon": "◍"},
        {"title": "CUSTO TOTAL", "value": _format_money(custo_total),
         "subtitle": f"Programa de {data['ano_inicial']}–{data['ano_final']}",
         "tone": "orange", "icon": "$"},
        {"title": "ANO DE PICO", "value": str(ano_pico) if ano_pico else "—",
         "subtitle": f"{_format_money(custo_pico)} concentrados no ano",
         "tone": "yellow", "icon": "△"},
    ])
    st.markdown("<div style='height: 14px'></div>", unsafe_allow_html=True)

    # Tabela cronograma: 1 linha por SRE × ano. Quando há múltiplos segmentos no
    # mesmo (SRE, Ano), a solução MAIS SEVERA dita o núcleo/grupo (e a cor do chip).
    # Severidade DNIT hardcoded (mesma ideia do §14.4, mas com os grupos DNIT):
    # 0 = mais severa (Reconstrução) … maior = mais leve.
    severity_order = {
        "Reconstrução": 0,
        "Fresagem + CBUQ": 1,
        "Recapeamento CBUQ": 2,
        "Microrrevestimento": 3,
        "Reparo localizado": 4,
        "Outras soluções": 5,
        "A avaliar em campo": 6,
    }
    ranked = schedule.copy()
    ranked["_sev"] = ranked["Solução grupo"].map(severity_order).fillna(99).astype(int)
    custo_por_ano_sre = (
        ranked.groupby(["SRE", "Ano"], as_index=False)["Custo"].sum()
    )
    severa_por_ano_sre = (
        ranked.sort_values(["SRE", "Ano", "_sev"])
        .drop_duplicates(["SRE", "Ano"])
        [["SRE", "Ano", "Solução núcleo", "Solução grupo"]]
    )
    by_sre_year = severa_por_ano_sre.merge(custo_por_ano_sre, on=["SRE", "Ano"])

    # Cor por solução núcleo = IRI faixa dominante dos segmentos onde aquele
    # núcleo é aplicado (mesma lógica do gráfico "Distribuição" da tela Soluções).
    nucleo_color: dict[str, str] = {}
    economic = get_dnit_economic_data(road, scenario_key)
    if economic.get("available") and not economic["table"].empty:
        t = economic["table"]
        for nucleo, sub in t.groupby("Solução núcleo"):
            if "_zona_color" in sub.columns and not sub["_zona_color"].mode().empty:
                nucleo_color[str(nucleo)] = sub["_zona_color"].mode().iloc[0]

    # Fallback: cor do grupo caso o núcleo não esteja mapeado.
    def _chip_color(nucleo: str, grupo: str) -> str:
        if nucleo in nucleo_color:
            return nucleo_color[nucleo]
        return group_colors.get(grupo, "#9fb9d9")

    rows_html = []
    nucleos_presentes: dict[str, str] = {}  # núcleo -> cor (para a legenda)
    for sre in sre_list:
        anos_sre = by_sre_year[by_sre_year["SRE"] == sre].sort_values("Ano")
        chip_parts = []
        for _, r in anos_sre.iterrows():
            ano_int = int(r["Ano"])
            nucleo = str(r["Solução núcleo"])
            grupo = str(r["Solução grupo"])
            custo_chip = float(r["Custo"])
            cor = _chip_color(nucleo, grupo)
            nucleos_presentes.setdefault(nucleo, cor)
            tip = html.escape(f"{ano_int} · {nucleo} · {_format_money(custo_chip)}", quote=True)
            chip_parts.append(
                f'<span class="sol-chip" style="background:{cor};color:{_chip_text_color(cor)}" '
                f'title="{tip}">{ano_int}</span>'
            )
        chips = "".join(chip_parts) if chip_parts else "<span class='muted'>Sem intervenção</span>"
        rows_html.append(
            "<tr>"
            f"<td class='mono'>{html.escape(sre)}</td>"
            f"<td>{chips}</td>"
            f"<td style='text-align:right'>{_format_money(float(anos_sre['Custo'].sum()))}</td>"
            "</tr>"
        )

    # Legenda lista os núcleos presentes com a cor IRI que cada um pegou.
    legend_html = "".join(
        f'<span class="cp-leg"><span class="cp-sw" style="background:{cor}"></span>{html.escape(nucleo)}</span>'
        for nucleo, cor in sorted(nucleos_presentes.items())
    )

    st.markdown(
        f"""
        <section class="solution-card">
          <div class="solution-card-head">
            <h3>Cronograma de intervenções por trecho (SRE)</h3>
            <p>Anos em que cada SRE receberá obra · cor do chip = grupo da solução</p>
          </div>
          <div class="solution-table-wrap"><table class="solution-table">
            <thead><tr>
              <th>SRE</th><th>Anos com intervenção</th><th style='text-align:right'>Custo total</th>
            </tr></thead>
            <tbody>{''.join(rows_html)}</tbody></table></div>
          <div class="cp-legend" style="padding:0 20px 18px">{legend_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    # Gráfico de barras: custo por ano (programa de obras).
    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
    cpa = data["custo_por_ano"].copy()
    if not cpa.empty:
        max_val = float(cpa["Custo"].max()) or 1
        axis_max = _axis_max_10(max_val / 1_000_000)
        ticks = _axis_ticks_10(axis_max)
        tick_markup = "".join(
            f'<span class="economic-y-tick" style="bottom:{tick / axis_max * 100:.2f}%;">{tick:.0f}</span>'
            for tick in ticks
        )
        bars = []
        labels = []
        for _, row in cpa.iterrows():
            val_mi = float(row["Custo"]) / 1_000_000
            height = max(val_mi / axis_max * 100, 1 if val_mi > 0 else 0)
            bars.append(
                '<div class="economic-bar-item">'
                f'<div class="economic-bar" style="height:{height:.2f}%"><span>{_format_money(float(row["Custo"]))}</span></div>'
                '</div>'
            )
            labels.append(f'<div>{int(row["Ano"])}</div>')
        st.markdown(
            '<section class="economic-panel">'
            '<div class="economic-head">'
            '<div class="economic-title"><div class="economic-icon">$</div>'
            '<div><h3>Custo por ano</h3><p>Programação orçamentária DNIT/RO cadastrada no banco</p></div></div>'
            f'<div class="solution-distribution-meta"><span>Total · <strong>{_format_money(custo_total)}</strong></span></div>'
            '</div>'
            '<div class="economic-chart">'
            f'<div class="economic-y-axis">{tick_markup}</div>'
            '<div>'
            f'<div class="economic-plot"><div class="economic-bars">{"".join(bars)}</div></div>'
            f'<div class="economic-labels">{"".join(labels)}</div>'
            '</div>'
            '</div>'
            '</section>',
            unsafe_allow_html=True,
        )

    # Projeção IRI por SRE — gráfico de evolução com as faixas da Matriz DNIT.
    iri_proj = get_dnit_iri_projection(road, scenario_key)
    if iri_proj.get("available") and iri_proj.get("sre_list"):
        st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
        sel_col, _ = st.columns([1, 2], gap="medium")
        with sel_col:
            _filter_caption("Trecho (SRE)")
            sre_default = iri_proj["sre_list"][0]
            selected_sre = st.selectbox(
                "Trecho",
                iri_proj["sre_list"],
                index=0,
                label_visibility="collapsed",
                key=f"dnit_iri_sre_{road}",
            )
            selected_sre = selected_sre or sre_default
        serie = iri_proj["sre_series"].get(str(selected_sre))
        if serie:
            _render_dnit_iri_chart(serie, str(selected_sre))


def _gray_shade(t: float) -> str:
    """Cor da deflexão: 0 = azul (Dc baixa, estrutura boa), 1 = vermelho (Dc alta)."""
    t = max(0.0, min(1.0, t))
    a, b = (0, 194, 232), (215, 25, 32)  # #00c2e8 -> #d71920
    r = int(a[0] + (b[0] - a[0]) * t)
    g = int(a[1] + (b[1] - a[1]) * t)
    bl = int(a[2] + (b[2] - a[2]) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


# ═══════════════════════════════════════════════════════════════════════════
# Página: DIAGNÓSTICO / VISÃO GERAL DNIT — condição por IRI/IGG/deflexão
# ═══════════════════════════════════════════════════════════════════════════

def _render_dnit_linear(segments_df, *, key: str = "dnit_linear_zoom"):
    """Diagrama linear DNIT: faixas de IRI, IGG e deflexão (Dc) por km."""
    if segments_df is None or segments_df.empty:
        return pd.DataFrame(), None

    df_full = segments_df.sort_values("km_inicial")
    full_min = float(df_full["km_inicial"].min())
    full_max = float(df_full["km_final"].max())

    slider_min = float(int(full_min))
    slider_max = float(int(full_max) + (1 if full_max > int(full_max) else 0))
    if slider_max <= slider_min:
        slider_max = slider_min + 1.0

    box = st.container(border=True)
    with box:
        # Marcador usado pelo CSS (:has) para estilizar o container como chart-card
        # e alinhar o slider à faixa de barras (mesmo padrão do gráfico IAP).
        st.markdown('<span class="iap-zoom-marker"></span>', unsafe_allow_html=True)
        st.markdown(
            '<div class="chart-heading linear-heading"><div>'
            '<h3>Diagrama linear — IRI · IGG · deflexão</h3>'
            '<p>Comportamento dos parâmetros DNIT ao longo do km</p></div></div>',
            unsafe_allow_html=True,
        )
        zoom_min, zoom_max = st.slider(
            "Filtrar trecho (km)",
            min_value=slider_min,
            max_value=slider_max,
            value=(slider_min, slider_max),
            step=1.0,
            key=f"{key}_{slider_min:.0f}_{slider_max:.0f}",
            help="Arraste as alças para ampliar um trecho específico da rodovia.",
        )

        df = df_full[(df_full["km_final"] >= zoom_min) & (df_full["km_inicial"] <= zoom_max)]
        if df.empty:
            st.info("Sem segmentos no intervalo selecionado.")
            return df, (zoom_min, zoom_max)

        min_km = zoom_min
        max_km = zoom_max
        total = max(max_km - min_km, 1.0)

        dcs = [float(v) for v in df["dc"].dropna().tolist()]
        d_min, d_max = (min(dcs), max(dcs)) if dcs else (0.0, 1.0)
        d_rng = (d_max - d_min) or 1.0

        def row(label: str, sub: str, color_fn) -> str:
            spans = []
            for r in df.to_dict("records"):
                seg_start = max(float(r["km_inicial"]), min_km)
                seg_end = min(float(r["km_final"]), max_km)
                ext = max(seg_end - seg_start, 0.001)
                width = ext / total * 100
                color, tip = color_fn(r)
                spans.append(
                    f'<span class="linear-segment" style="width:{width:.4f}%;background:{color};" title="{html.escape(tip)}"></span>'
                )
            return (
                '<div class="linear-row">'
                f'<div class="linear-row-label">{label}<br><span style="font-size:9px;color:#7f909c">{sub}</span></div>'
                f'<div class="linear-track">{"".join(spans)}</div>'
                '</div>'
            )

        def iri_fn(r):
            return r["iri_color"], f"km {r['km_inicial']:.1f}-{r['km_final']:.1f} · IRI {float(r['iri']):.2f} · {r['iri_classe']}"

        def igg_fn(r):
            return r["igg_color"], f"km {r['km_inicial']:.1f}-{r['km_final']:.1f} · IGG {float(r['igg']):.0f} · {r['igg_classe']}"

        def defl_fn(r):
            dc = r.get("dc")
            if dc is None:
                return "#46586a", f"km {r['km_inicial']:.1f}-{r['km_final']:.1f} · sem deflexão"
            t = (float(dc) - d_min) / d_rng
            status = "Dc > Dadm" if (r.get("dadm") is not None and dc > r["dadm"]) else "Dc ≤ Dadm"
            return _gray_shade(t), f"km {r['km_inicial']:.1f}-{r['km_final']:.1f} · Dc {float(dc):.2f} mm · {status}"

        ticks = "".join(
            f'<span class="linear-tick" style="left:{i / 8 * 100:.2f}%;">{min_km + total * i / 8:.0f}</span>'
            for i in range(9)
        )
        axis = f'<div class="linear-axis"><span class="linear-axis-title">Km da rodovia</span>{ticks}</div>'

        st.markdown(
            '<div class="linear-diagram">'
            + row("IRI", "m/km", iri_fn)
            + row("IGG", "", igg_fn)
            + row("Defl.", "Dc mm", defl_fn)
            + axis
            + "</div>",
            unsafe_allow_html=True,
        )
    return df, (zoom_min, zoom_max)


def _dnit_distribution(segments_df, classe_col: str, color_col: str):
    """Distribuição (classe, percentual, color) ponderada por km — p/ os donuts IRI/IGG."""
    cols = {classe_col, color_col, "km_inicial", "km_final"}
    if segments_df is None or segments_df.empty or not cols.issubset(segments_df.columns):
        return pd.DataFrame(columns=["classe", "percentual", "color"])
    df = segments_df.copy()
    df["_ext"] = (df["km_final"].astype(float) - df["km_inicial"].astype(float)).clip(lower=0)
    df = df[df[classe_col].notna()]
    if df.empty:
        return pd.DataFrame(columns=["classe", "percentual", "color"])
    grp = df.groupby([classe_col, color_col], dropna=False)["_ext"].sum().reset_index()
    total = float(grp["_ext"].sum()) or 1.0
    grp["percentual"] = grp["_ext"] / total * 100
    grp = grp.rename(columns={classe_col: "classe", color_col: "color"})
    rank = {c: i for i, c in enumerate(_DNIT_ORDER)}
    grp["_o"] = grp["classe"].map(rank).fillna(999)
    return grp.sort_values("_o")[["classe", "percentual", "color"]].reset_index(drop=True)


def _render_dnit_overview(road: str, scenario_key: str | None, year: int | None = None) -> None:
    """Visão geral DNIT: KPIs + mapa colorido pela matriz + diagrama linear (IRI/IGG/deflexão)."""
    data = get_dnit_overview_data(road, scenario_key=scenario_key, year=year)
    if not data or data.get("segments") is None or data["segments"].empty:
        st.info("Sem dados de IRI/IGG para esta rodovia/cenário.")
        return

    render_metric_cards(
        [
            {
                "title": "IRI MÉDIO",
                "value": f"{data['iri_avg']:.2f}",
                "subtitle": "Irregularidade (m/km)",
                "tone": "cyan",
                "icon": "≈",
            },
            {
                "title": "IGG MÉDIO",
                "value": f"{data['igg_avg']:.0f}",
                "subtitle": "Gravidade global (defeitos)",
                "tone": "cyan",
                "icon": "▦",
            },
            {
                "title": "% IRI CRÍTICO (> 4)",
                "value": f"{data['critico_pct']:.1f}%",
                "subtitle": "Faixa laranja/vermelha da matriz",
                "tone": "orange",
                "icon": "◎",
            },
        ]
    )
    st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
    _km_range = _diagnosis_km_range_from_state(data["segments"], "dnit_linear_zoom")
    _segments_km = _filter_by_km_range(data["segments"], _km_range)
    _iri_distribution_km = _dnit_distribution(_segments_km, "iri_classe", "iri_color")
    _selected_iri_class = _render_diagnosis_iap_class_filter(
        _iri_distribution_km,
        key="dnit_iri_distribution_class",
        class_order=_DNIT_ORDER,
    )
    _segments_filtered = _filter_by_iap_class(_segments_km, _selected_iri_class, class_col="iri_classe")
    _iri_distribution_filtered = _dnit_distribution(_segments_filtered, "iri_classe", "iri_color")
    _igg_distribution_filtered = _dnit_distribution(_segments_filtered, "igg_classe", "igg_color")
    _iri_avg_filtered = _weighted_metric_from_segments(_segments_filtered, "iri", float(data["iri_avg"]))
    _igg_avg_filtered = _weighted_metric_from_segments(_segments_filtered, "igg", float(data["igg_avg"]))
    render_dnit_map(
        _segments_filtered,
        zona_colors=data.get("zona_colors"),
        zona_order=data.get("zona_order"),
    )
    # Donuts de distribuição IRI + IGG (entre o mapa e o diagrama linear).
    _c_iri, _c_igg = st.columns(2)
    with _c_iri:
        render_iap_distribution(
            _iri_distribution_filtered if not _iri_distribution_filtered.empty else _iri_distribution_km,
            _iri_avg_filtered,
            title="IRI",
            subtitle=(
                "Faixa em km e faixa IRI aplicadas ao mapa e à distribuição"
                if _selected_iri_class == "Todas" else
                f"Mostrando no mapa e na distribuição apenas a faixa {_selected_iri_class}"
            ),
            center_label="IRI MÉDIO", value_fmt="{:.2f}",
        )
    with _c_igg:
        render_iap_distribution(
            _igg_distribution_filtered,
            _igg_avg_filtered,
            title="IGG", subtitle="Distribuição do recorte visível no mapa",
            center_label="IGG MÉDIO", value_fmt="{:.1f}",
        )
    _render_dnit_linear(data["segments"], key="dnit_linear_zoom")


def _filter_map_segments(segments_df, filtered_table):
    """Restringe os segmentos geográficos aos que sobraram na tabela filtrada
    (casando por `_segment_id`), para o mapa acompanhar os filtros da tabela."""
    if segments_df is None or segments_df.empty:
        return segments_df
    if filtered_table is None or filtered_table.empty or "_segment_id" not in filtered_table:
        return segments_df.iloc[0:0]

    selected_ids = set(filtered_table["_segment_id"].astype(int).tolist())
    return segments_df[segments_df["segment_id"].astype(int).isin(selected_ids)].copy()


# ═══════════════════════════════════════════════════════════════════════════
# Página: VISÃO GERAL (rede) — painel executivo agregando TODAS as rodovias
# ═══════════════════════════════════════════════════════════════════════════

def _build_network_overview_impl(
    is_dnit: bool,
    selected_roads: tuple[str, ...] | None = None,
    selected_scenarios: tuple[str, ...] | None = None,
    selected_years: tuple[int, ...] | None = None,
) -> dict:
    """Agrega a Visão geral respeitando múltiplas rodovias, cenários e anos."""
    roads = list(selected_roads) if selected_roads else (
        get_dnit_available_roads() if is_dnit else get_available_roads()
    )
    selected_scenario_tokens = list(selected_scenarios or [])
    selected_year_values = [int(year) for year in (selected_years or [])]
    scenario_map: dict[str, list[str]] = {}
    for token in selected_scenario_tokens:
        road_code, scenario_key = _parse_network_scenario_token(token)
        if road_code and scenario_key:
            scenario_map.setdefault(road_code, []).append(scenario_key)

    rows = []
    paragon_segments = []
    dnit_segments = []
    zona_colors = None
    zona_order = None

    for road in roads:
        road_code = _normalize_road_code(road) or str(road)
        road_scenarios = scenario_map.get(road_code, [None])
        if selected_scenario_tokens and road_code not in scenario_map:
            continue
        road_years = selected_year_values or [None]

        for scenario_key in road_scenarios:
            for year in road_years:
                label_parts = [road]
                if scenario_key:
                    raw_label = get_scenario_label(road, scenario_key)
                    short_label = _network_scenario_label({"cenario": raw_label, "key": scenario_key}) or str(scenario_key)
                    label_parts.append(short_label)
                if year is not None:
                    label_parts.append(str(year))
                display_label = " - ".join(label_parts)

                if is_dnit:
                    dn = get_dnit_overview_data(road, scenario_key=scenario_key, year=year)
                    eco = get_dnit_economic_data(road, scenario_key=scenario_key, year=year)
                    segs = dn.get("segments") if dn else None
                    table = eco.get("table") if eco else None
                    if dn is None or not dn or segs is None or segs.empty:
                        continue

                    ext = (segs["km_final"].astype(float) - segs["km_inicial"].astype(float)).clip(lower=0)
                    ext_sum = float(ext.sum()) or 1.0
                    interv_km = 0.0
                    prio_alta_crit = 0
                    custo_total = 0.0

                    if table is not None and not table.empty:
                        work = _economic_work_table(table)
                        if not work.empty:
                            segmentos = [
                                {
                                    "rodovia": road,
                                    "snv": row.get("SNV"),
                                    "extensao_km": row.get("Extensão"),
                                    "iri": row.get("IRI"),
                                    "igg": row.get("IGG"),
                                    "custo": row.get("Custo econômico"),
                                }
                                for _, row in work.iterrows()
                            ]
                            prio = {item["snv"]: item for item in calcular_indice_priorizacao_dnit(segmentos)}
                            prio_alta_crit = sum(
                                1 for v in prio.values()
                                if v.get("classificacao") in ("Prioridade Crítica", "Prioridade Alta")
                            )
                        interv_km = float(table["Extensão"].astype(float).sum())
                        custo_total = _necessidade_total(
                            table,
                            _budget_items_for_year(eco.get("budget_items"), year),
                            _ECONOMIC_DEFAULT_HORIZON,
                        )

                    rows.append(
                        {
                            "Rodovia": display_label,
                            "_road_label": road,
                            "_code": road_code,
                            "_scenario_key": scenario_key,
                            "_year": year,
                            "IAP": 0.0,
                            "IRI": float(dn.get("iri_avg") or 0.0),
                            "IGG": float(dn.get("igg_avg") or 0.0),
                            "ext_km": ext_sum,
                            "interv_km": interv_km,
                            "iap_bad_pct": 0.0,
                            "iri_bad_pct": float(dn.get("critico_pct") or 0.0),
                            "custo": custo_total,
                            "prio": prio_alta_crit,
                        }
                    )

                    dnit_segments.append(segs)
                    zona_colors = dn.get("zona_colors")
                    zona_order = dn.get("zona_order")
                    continue

                sol = get_solutions_data(road, scenario_key=scenario_key, year=year)
                table = sol.get("table")
                if table is None or table.empty:
                    continue
                work = _economic_work_table(table)
                ext = table["Extensão"].astype(float)
                ext_sum = float(ext.sum()) or 1.0
                iap_col = table["IAP"].astype(float)
                iri_col = table["IRI"].astype(float)
                igg_col = table["IGG"].astype(float)

                iap_bad_km = float(ext[iap_col < IAP_META].sum())
                iri_bad_km = float(ext[iri_col > 4].sum())
                if "Solução recomendada" in table.columns:
                    _interv_mask = ~table["Solução recomendada"].astype(str).str.strip().isin(
                        ["Sem intervenção", "OK", "", "nan", "None"]
                    )
                    interv_km = float(table.loc[_interv_mask, "Extensão"].astype(float).sum())
                else:
                    interv_km = 0.0

                prio = _prioridade_por_snv(work)
                prio_alta_crit = sum(
                    1 for v in prio.values()
                    if v.get("classificacao") in ("Prioridade Crítica", "Prioridade Alta")
                )

                rows.append(
                    {
                        "Rodovia": display_label,
                        "_road_label": road,
                        "_code": road_code,
                        "_scenario_key": scenario_key,
                        "_year": year,
                        "IAP": float((iap_col * ext).sum() / ext_sum),
                        "IRI": float((iri_col * ext).sum() / ext_sum),
                        "IGG": float((igg_col * ext).sum() / ext_sum),
                        "ext_km": ext_sum,
                        "interv_km": interv_km,
                        "iap_bad_pct": iap_bad_km / ext_sum * 100,
                        "iri_bad_pct": iri_bad_km / ext_sum * 100,
                        "custo": _necessidade_total(
                            table,
                            _budget_items_for_year(sol.get("budget_items"), year),
                            _ECONOMIC_DEFAULT_HORIZON,
                        ),
                        "prio": prio_alta_crit,
                    }
                )

                if sol.get("segments") is not None and not sol["segments"].empty:
                    paragon_segments.append(sol["segments"])

    if not rows:
        return {}

    df = pd.DataFrame(rows)
    prio_total = int(df["prio"].sum())
    tot_ext = float(df["ext_km"].sum()) or 1.0

    return {
        "roads_df": df,
        "prio_total": prio_total,
        "net_iap": float((df["IAP"] * df["ext_km"]).sum() / tot_ext),
        "net_iri": float((df["IRI"] * df["ext_km"]).sum() / tot_ext),
        "net_igg": float((df["IGG"] * df["ext_km"]).sum() / tot_ext),
        "net_custo": float(df["custo"].sum()),
        "total_km": tot_ext,
        "paragon_map": pd.concat(paragon_segments, ignore_index=True) if paragon_segments else pd.DataFrame(),
        "dnit_map": pd.concat(dnit_segments, ignore_index=True) if dnit_segments else pd.DataFrame(),
        "zona_colors": zona_colors,
        "zona_order": zona_order,
    }


@cached(ttl=1800)
def _build_network_overview_cached(
    is_dnit: bool,
    selected_roads: tuple[str, ...] | None = None,
    selected_scenarios: tuple[str, ...] | None = None,
    selected_years: tuple[int, ...] | None = None,
) -> dict:
    """Versão cacheada da Visão geral."""
    return _build_network_overview_impl(
        is_dnit=is_dnit,
        selected_roads=selected_roads,
        selected_scenarios=selected_scenarios,
        selected_years=selected_years,
    )


def _build_network_overview(
    is_dnit: bool,
    selected_roads: list[str] | None = None,
    selected_scenarios: list[str] | None = None,
    selected_years: list[int] | None = None,
) -> dict:
    """Carrega a Visão geral e evita reaproveitar vazio indevido em filtros específicos.

    Se uma combinação específica de filtros voltar vazia por falha transitória do banco,
    tenta uma leitura fresca uma vez antes de assumir que realmente não há dados.
    """
    data = _build_network_overview_cached(
        is_dnit=is_dnit,
        selected_roads=tuple(selected_roads or []),
        selected_scenarios=tuple(selected_scenarios or []),
        selected_years=tuple(selected_years or []),
    )
    if data or not selected_roads:
        return data

    fresh = _build_network_overview_impl(
        is_dnit=is_dnit,
        selected_roads=tuple(selected_roads or []),
        selected_scenarios=tuple(selected_scenarios or []),
        selected_years=tuple(selected_years or []),
    )
    if fresh:
        _build_network_overview_cached.cache_clear()
    return fresh


def _render_network_ranking(df: pd.DataFrame, is_dnit: bool) -> None:
    """Rodovias por EXTENSÃO TOTAL. A barra (comprimento ∝ km) mostra, dentro do total,
    quanto precisa de intervenção (laranja) vs OK (verde). Maior extensão primeiro;
    clique na rodovia abre o diagnóstico."""
    ordered = df.sort_values("ext_km", ascending=False)
    max_ext = max(float(ordered["ext_km"].max()), 1.0)
    selected_filter = set(st.session_state.get("topbar_network_road") or [])
    has_filtered_slices = ordered["_scenario_key"].notna().any() or ordered["_year"].notna().any()
    title = "Extensão das rodovias" if not has_filtered_slices else "Extensão das rodovias e recortes"
    subtitle = (
        "Comparação visual da extensão total e da parte que precisa de intervenção."
        if not has_filtered_slices else
        "Comparação visual dos recortes escolhidos na combinação de rodovia, cenário e ano."
    )

    rows = []
    for i, row in enumerate(ordered.to_dict("records"), start=1):
        total = float(row["ext_km"])
        interv = min(max(float(row.get("interv_km", 0.0) or 0.0), 0.0), total)
        ext_pct = total / max_ext * 100
        interv_frac = (interv / total * 100) if total else 0.0
        pct = (interv / total * 100) if total else 0.0
        active_class = " active" if selected_filter and str(row.get("_road_label") or row["Rodovia"]) in selected_filter else ""
        visible_name = str(row.get("_road_label") or row["Rodovia"])
        slice_label = str(row["Rodovia"])
        tooltip = html.escape(
            f'{slice_label} · Extensão total {total:.1f} km · '
            f'Intervenção {interv:.1f} km ({pct:.1f}%)',
            quote=True,
        )
        inline_label = (
            f'<span class="net-rank-interv-label">{pct:.0f}%</span>'
            if interv_frac >= 26 and ext_pct >= 18
            else ""
        )
        rows.append(
            f'<div class="net-rank-row{active_class}" title="{tooltip}">'
            f'<a class="net-rank-name" href="?page=overview&road={html.escape(str(row["_code"]))}" target="_self" title="{tooltip}">'
            f'{i}. {html.escape(visible_name)}</a>'
            f'<div class="net-rank-track" title="{tooltip}"><div class="net-rank-bar" style="width:{ext_pct:.1f}%">'
            f'<div class="net-rank-interv" style="width:{interv_frac:.1f}%">{inline_label}</div></div></div>'
            f'<div class="net-rank-val">{total:.0f} km</div>'
            f'<div class="net-rank-extra">{interv:.0f} km precisam de intervenção ({pct:.0f}%)</div>'
            '</div>'
        )

    st.markdown(
        '<section class="solution-card"><div class="solution-card-head">'
        f'<h3>{title}</h3>'
        f'<p>{subtitle}</p>'
        '<div class="net-rank-legend">'
        '<span class="net-rank-legend-item"><span class="net-rank-legend-sw interv"></span>Precisa de intervenção</span>'
        '<span class="net-rank-legend-item"><span class="net-rank-legend-sw ok"></span>Trecho OK</span>'
        '<span class="net-rank-legend-note">Clique na rodovia para abrir o diagnóstico.</span>'
        '</div>'
        '</div>'
        f'<div class="net-rank-body">{"".join(rows)}</div></section>',
        unsafe_allow_html=True,
    )


def _render_network_cost(df: pd.DataFrame) -> None:
    grouped = df.sort_values("custo", ascending=False)
    total_cost = float(grouped["custo"].sum())
    has_filtered_slices = grouped["_scenario_key"].notna().any() or grouped["_year"].notna().any()
    max_cost = max(float(grouped["custo"].max()), 1)
    axis_max = _axis_max_10(max_cost / 1_000_000)
    ticks = _axis_ticks_10(axis_max)
    tick_markup = "".join(
        f'<span class="economic-y-tick" style="bottom:{tick / axis_max * 100:.2f}%;">{tick:.0f}</span>'
        for tick in ticks
    )
    bars, labels = [], []
    for row in grouped.to_dict("records"):
        cost_mi = float(row["custo"]) / 1_000_000
        height = max(cost_mi / axis_max * 100, 2 if cost_mi > 0 else 0)
        bars.append(
            '<div class="economic-bar-item">'
            f'<div class="economic-bar" style="height:{height:.2f}%;background:#00c2e8;"><span>{_format_money_chart(float(row["custo"]))}</span></div>'
            '</div>'
        )
        labels.append(f'<div>{html.escape(str(row["Rodovia"]))}</div>')

    st.markdown(
        '<section class="economic-panel">'
        '<div class="economic-head">'
        '<div class="economic-title"><div class="economic-icon">$</div>'
        f'<div><h3>{"Custo por rodovia" if not has_filtered_slices else "Custo por recorte"}</h3>'
        f'<p>{"Necessidade total para tratar cada rodovia" if not has_filtered_slices else "Necessidade total para os recortes filtrados"}</p></div></div>'
        f'<div class="solution-distribution-meta"><span>Total · <strong>{_format_money(total_cost)}</strong></span></div>'
        '</div>'
        '<div class="economic-chart">'
        f'<div class="economic-y-axis">{tick_markup}</div>'
        '<div class="economic-scroll">'
        f'<div class="economic-plot"><div class="economic-bars">{"".join(bars)}</div></div>'
        f'<div class="economic-labels">{"".join(labels)}</div>'
        '</div>'
        '</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def _render_network_overview(
    diagnosis: str,
    selected_roads: list[str] | None = None,
    selected_scenarios: list[str] | None = None,
    selected_years: list[int] | None = None,
) -> None:
    """Painel executivo da malha: KPIs + mapa de todas as rodovias + ranking + custo."""
    is_dnit = diagnosis == "Diagnóstico DNIT"
    data = _build_network_overview(
        is_dnit,
        selected_roads=selected_roads,
        selected_scenarios=selected_scenarios,
        selected_years=selected_years,
    )
    if not data:
        st.info("Sem dados para a malha.")
        return

    df = data["roads_df"]
    # Na rede, médias de IAP/IRI/IGG não dizem muito (misturam rodovias/metodologias) —
    # o que importa é o backlog de prioridade e o custo. Mantemos só esses dois.
    render_metric_cards(
        [
            {"title": "TRECHOS PRIORITÁRIOS", "value": f"{data['prio_total']}", "subtitle": "Prioridade Alta/Crítica (IP)", "tone": "orange", "icon": "▲"},
            {
                "title": "CUSTO TOTAL",
                "value": _format_money(data["net_custo"]),
                "subtitle": (
                    f"Necessidade dos anos selecionados · {data['total_km']:.0f} km"
                    if selected_years else
                    f"Necessidade · {data['total_km']:.0f} km"
                ),
                "tone": "green",
                "icon": "$",
            },
        ]
    )
    st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)

    if is_dnit:
        render_dnit_map(data["dnit_map"], zona_colors=data.get("zona_colors"), zona_order=data.get("zona_order"))
    else:
        render_overview_map(data["paragon_map"], data["total_km"])

    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    _render_network_ranking(df, is_dnit)
    _render_network_cost(df)


# ═══════════════════════════════════════════════════════════════════════════
# IAGON — assistente de IA embutido (chat/análise). FORA DO ESCOPO desta
# documentação (ver README, "Fora de escopo"). Todo o bloco abaixo, até a seção
# "Roteamento / main()", pertence ao assistente IAGON e não é documentado aqui.
# ═══════════════════════════════════════════════════════════════════════════
def _cond_class(v: float) -> str:
    """Classe dos índices estruturais 0–5 (maior = melhor condição) — mesma régua do painel."""
    return ("Excelente" if v >= 4.5 else "Bom" if v >= 3.5 else
            "Regular" if v >= 2.5 else "Mau" if v >= 1.5 else "Péssimo")


def _iagon_enrich_detail(road: str) -> dict:
    """Dados extras p/ o contexto da IAGON, via funções já cacheadas do relatório:
    (a) por sentido CRESCENTE/DECRESCENTE (IAP, extensão, necessidade 8a);
    (b) sub-índices estruturais ICDS/ICDP/ICDE (média ponderada por extensão);
    (c) deflexão média (mm). Cada item é defensivo — falha isolada não derruba o contexto."""
    out: dict = {"sentidos": [], "subindices": None, "def_mm": None}
    try:  # (a) por sentido — só cenários CRESCENTE/DECRESCENTE da Paragon
        for s in get_available_scenarios(road, "Paragon"):
            if _sentido_label(s.get("cenario", "")) not in ("CRESCENTE", "DECRESCENTE"):
                continue
            sol = get_solutions_data(road, scenario_key=s["key"])
            t = sol.get("table")
            if t is None or t.empty:
                continue
            bi = sol.get("budget_items")  # necessidade = TODOS os anos do programa
            out["sentidos"].append({
                "sentido": _sentido_label(s["cenario"]),
                "iap": round(float(t["IAP"].mean()), 2) if "IAP" in t.columns else None,
                "ext": round(float(t["Extensão"].sum()), 1),
                "necessidade": float(bi["Custo"].sum()) if bi is not None and not bi.empty else 0.0,
            })
    except Exception:
        pass
    try:  # (b) sub-índices estruturais (média ponderada por extensão)
        ld = get_overview_data(road).get("linear_diagram")
        if ld is not None and not ld.empty and "extensao" in ld.columns and float(ld["extensao"].sum()) > 0:
            tot = float(ld["extensao"].sum())
            sub = {}
            for c in ("icds", "icdp", "icde"):
                if c in ld.columns:
                    avg = float((ld[c] * ld["extensao"]).sum() / tot)
                    sub[c] = (round(avg, 2), _cond_class(avg))
            out["subindices"] = sub or None
    except Exception:
        pass
    try:  # (c) deflexão média (mm) — tabela de soluções (cenário default)
        t = get_solutions_data(road).get("table")
        if t is not None and not t.empty and "DEF" in t.columns:
            d = t[["DEF", "Extensão"]].dropna(subset=["DEF"])
            if not d.empty and float(d["Extensão"].sum()) > 0:
                out["def_mm"] = round(float((d["DEF"] * d["Extensão"]).sum() / d["Extensão"].sum()), 2)
    except Exception:
        pass
    return out


def _iagon_road_detail(road: str) -> tuple[list[tuple[int, float]], list[tuple[str, float]], list[dict], float]:
    """Dados Paragon de uma rodovia: (custo por ano, distribuição de soluções, trechos SNV
    priorizados, NECESSIDADE TOTAL do programa).

    Inclui mistura completa de soluções por SNV (não só a dominante) para evitar omissão
    de Reconstrução quando ela aparece em poucos segmentos.
    """
    sol = get_solutions_data(road)
    # Necessidade TOTAL e custo por ano = TODOS os anos do programa (não horizonte fixo de 8 anos).
    nec_total = float(_necessidade_total(sol.get("table"), sol.get("budget_items"), 9999) or 0.0)
    bi = sol.get("budget_items")
    if bi is not None and not bi.empty and "Ano" in bi:
        grp = bi.groupby("Ano", as_index=False)["Custo"].sum().sort_values("Ano")
        cby = [(int(r["Ano"]), float(r["Custo"])) for _, r in grp.iterrows()]
    else:
        cby = []

    table = sol.get("table")
    sdist: list[tuple[str, float]] = []
    trechos: list[dict] = []
    if table is not None and not table.empty and "Solução recomendada" in table:
        gd = table.groupby("Solução recomendada")["Extensão"].sum().sort_values(ascending=False)
        sdist = [(str(name), round(float(km), 1)) for name, km in gd.items()]

        work = _economic_work_table(table)
        prio = _prioridade_por_snv(work)
        ext_by = work.groupby("SNV")["Extensão"].sum()
        iap_by = work.groupby("SNV")["IAP"].mean()
        # MIX de soluções por SNV — preserva Reconstrução mesmo quando ela é minoria.
        mix_by: dict[str, list[tuple[str, float]]] = {}
        if "Solução recomendada" in work.columns:
            grouped_mix = (
                work.groupby(["SNV", "Solução recomendada"])["Extensão"].sum().reset_index()
            )
            for snv_id, sub in grouped_mix.groupby("SNV"):
                sub_sorted = sub.sort_values("Extensão", ascending=False)
                mix_by[str(snv_id)] = [
                    (str(r["Solução recomendada"]), round(float(r["Extensão"]), 1))
                    for _, r in sub_sorted.iterrows()
                    if r["Solução recomendada"]
                ]
        for snv, p in prio.items():
            mix = mix_by.get(str(snv), [])
            mix_txt = " · ".join(f"{n} {km}km" for n, km in mix) if mix else "-"
            trechos.append(
                {
                    "snv": str(snv),
                    "priorizacao": int(round(float(p.get("priorizacao", 0) or 0))),
                    "classe": str(p.get("classificacao", "-")).replace("Prioridade ", ""),
                    "rank": int(p.get("ranking", 999)),
                    "ext": round(float(ext_by.get(snv, 0) or 0), 1),
                    "iap": round(float(iap_by.get(snv, 0) or 0), 2),
                    "mix_solucoes": mix_txt,
                }
            )
        trechos.sort(key=lambda x: x["rank"])
    return cby, sdist, trechos, nec_total


def _iagon_road_scenarios(road: str) -> list[dict]:
    """Cenários Paragon cadastrados para a rodovia, numerados (1..N) com rótulo curto."""
    out: list[dict] = []
    try:
        for i, s in enumerate(get_available_scenarios(road, "Paragon") or [], start=1):
            out.append({"n": i, "key": s.get("key"), "label": _short_scenario_label(s)})
    except Exception:
        pass
    return out


def _iagon_norm_road(token: str) -> str:
    m = re.search(r"BR[\s-]?0*(\d{2,3})", (token or "").upper())
    return f"BR-{int(m.group(1)):03d}" if m else ""


def _iagon_scenario_gate(user_msg: str, history: list[dict]) -> str | None:
    """Gate DETERMINÍSTICO (não depende do modelo): se a pergunta é sobre UMA rodovia com
    >1 cenário sem especificar qual, devolve a pergunta do cenário. Senão None (segue p/ o modelo).

    Garante que a IAGON NUNCA cravе número de um cenário padrão sem o gestor escolher."""
    low = (user_msg or "").lower()
    # rede / panorama / comparação entre rodovias → não pergunta cenário (é visão geral)
    if any(w in low for w in ("todas", "toda a rede", "da rede", "na rede", "panorama",
                              "ranking", "compare as rodovias", "comparar as rodovias",
                              "todas as rodovias", "a malha")):
        return None
    roads = {r for tok in re.findall(r"BR[\s-]?0*\d{2,3}", (user_msg or "").upper())
             if (r := _iagon_norm_road(tok))}
    if len(roads) != 1:
        return None  # 0 rodovias (genérico) ou 2+ (comparação) → o modelo decide
    road = next(iter(roads))
    scs = _iagon_road_scenarios(road)
    if len(scs) <= 1:
        return None
    labels_low = [s["label"].lower() for s in scs]
    # pedido de COMPARAÇÃO de cenários → deixa o modelo comparar (não pergunta)
    if "compar" in low and "cen" in low:
        return None
    # cenário(s) já especificado(s) na mensagem (nº singular/plural ou rótulo)?
    if re.search(r"cen[áa]rios?\s*\d|cen[áa]rio\s+(um|dois|tr[êe]s|quatro)", low) or any(l in low for l in labels_low):
        return None
    # já perguntado p/ esta rodovia nesta sessão? (não insistir)
    try:
        asked = st.session_state.setdefault("_iagon_asked_scen", set())
    except Exception:
        asked = set()
    if road in asked:
        return None
    # usuário já escolheu cenário em mensagens anteriores?
    prev = " ".join(m.get("content", "") for m in history[:-1] if m.get("role") == "user").lower()
    if re.search(r"cen[áa]rios?\s*\d", prev) or any(l in prev for l in labels_low):
        return None
    asked.add(road)
    linhas = "\n".join(f"- **{s['n']})** {s['label']}" for s in scs)
    return (
        f"A **{road}** tem **{len(scs)} cenários** cadastrados — e o resultado muda conforme o cenário "
        f"(ex.: análise segmentada, fixa, todas as faixas, só crescente ou só decrescente). "
        f"Por isso, antes de te passar números:\n\n{linhas}\n\n"
        f"**Qual cenário você quer?** Posso também fazer uma **análise técnica comparando** os cenários."
    )


def _iagon_situacao_text(road: str, cenario: int = 1) -> str:
    """Situação da rodovia em UM cenário: IAP médio, % crítico, NECESSIDADE TOTAL (soma de
    TODOS os anos do programa — não um horizonte fixo), km por solução, segmentos críticos."""
    scs = _iagon_road_scenarios(road)
    if not scs:
        return f"Sem cenários Paragon cadastrados para {road}."
    idx = max(1, min(int(cenario or 1), len(scs))) - 1
    sc = scs[idx]
    sol = get_solutions_data(road, scenario_key=sc["key"])
    table = sol.get("table")
    if table is None or table.empty:
        return f"Sem dados Paragon para {road} (cenário {sc['n']}: {sc['label']})."
    ext = float(table["Extensão"].sum()) or 1.0
    iap_avg = float((table["IAP"] * table["Extensão"]).sum() / ext)
    pct_bad = float(table[table["IAP"] < 2.5]["Extensão"].sum() / ext * 100)
    bi = sol.get("budget_items")
    nec, anos_txt = 0.0, ""
    if bi is not None and not bi.empty and "Custo" in bi.columns:
        nec = float(bi["Custo"].sum())  # TODOS os anos do programa (não 8 anos)
        anos = pd.to_numeric(bi["Ano"], errors="coerce").dropna()
        if not anos.empty:
            anos_txt = f" (programa {int(anos.min())}–{int(anos.max())}, TODOS os anos)"
    sd = table.groupby("Solução recomendada")["Extensão"].sum().sort_values(ascending=False)
    sol_txt = " · ".join(f"{str(n).replace(' + ', ' / ')} {km:.1f} km" for n, km in sd.items() if str(n).strip()) or "sem dados"
    seg = _segment_priority_table(_aplicar_indice_priorizacao(_economic_work_table(table)), bi)
    crit = int((seg["Priorização"] <= 3).sum()) if not seg.empty else 0
    alta = int(((seg["Priorização"] > 3) & (seg["Priorização"] <= 5)).sum()) if not seg.empty else 0
    return (
        f"Situação — {road} · cenário {sc['n']}: {sc['label']}\n"
        f"- IAP médio: {iap_avg:.2f} (meta 2,5)\n"
        f"- % da extensão com IAP < 2,5: {pct_bad:.0f}%\n"
        f"- Extensão total: {ext:.1f} km\n"
        f"- NECESSIDADE TOTAL{anos_txt}: {_format_money(nec)}\n"
        f"- Segmentos prioritários: {crit} Crítica (nível ≤ 3) · {alta} Alta (nível 4–5)\n"
        f"- Soluções (km): {sol_txt}"
    )


_SCREEN_IAGON_INSTR = (
    "Você é um engenheiro de pavimentos SÊNIOR analisando UMA tela do relatório para um gestor. "
    "NÃO se limite a repetir os números que já aparecem na tela — faça uma ANÁLISE TÉCNICA COMPLETA E "
    "PROFUNDA usando TODOS os dados do contexto abaixo (situação, trechos por segmento, custos, programa):\n"
    "1. Leitura crítica: o que os números revelam (gravidade, padrões, onde a degradação se concentra).\n"
    "2. ONDE estão os pontos críticos — cite trechos/SRE e km específicos do contexto e por que são críticos.\n"
    "3. Implicações de risco e de custo; o que atacar PRIMEIRO e por quê.\n"
    "4. Recomendações práticas + próximo passo objetivo.\n"
    "Cite SEMPRE números e trechos concretos do contexto (não generalize). Use markdown (negrito, listas, "
    "tabela curta quando ajudar). Seja completo, porém objetivo. Responda apenas sobre ESTA tela.\n\nPergunta: "
)


def _scenario_num(road: str, scenario_key: str | None) -> int:
    for s in _iagon_road_scenarios(road):
        if s.get("key") == scenario_key:
            return s["n"]
    return 1


def _screen_ctx(titulo: str, filtros: dict, dados_md: str) -> str:
    fl = " · ".join(f"{k}: {v}" for k, v in filtros.items() if v)
    return f"TELA: {titulo}\nFILTROS APLICADOS: {fl}\n\nDADOS EXIBIDOS NESTA TELA:\n{dados_md}"


# Assistente IAGON (fora do escopo desta documentação).
def _render_screen_iagon(screen: str, titulo: str, filtro_md: str, context_fn,
                         sugestoes: list[str] | None = None) -> None:
    """Painel da IAGON escopado a UMA tela: detalha o filtro e faz análise técnica dos dados
    DAQUELA tela. `context_fn` é um callable (ou string) montado SÓ quando há pergunta — assim
    o contexto pesado (priorização) não roda a cada render."""
    sugestoes = sugestoes or ["Análise completa", "Pontos críticos", "O que priorizar?"]
    with st.container(border=True):
        st.markdown('<span class="iagon-fab-mark"></span>', unsafe_allow_html=True)
        with st.popover("✦ IAGON", use_container_width=False):
            st.markdown(
                f"<div class='iagon-cv-head'>✦ <b>IAGON</b> · {html.escape(titulo)}</div>"
                "<div class='iagon-cv-sub'>Análise técnica desta tela com os filtros aplicados.</div>"
                f"<div class='iagon-cv-filtro'>{filtro_md}</div>",
                unsafe_allow_html=True,
            )
            if not iagon.is_configured():
                st.caption("IAGON indisponível (sem chave de API).")
                return
            cols = st.columns(len(sugestoes))
            clicked = None
            for i, s in enumerate(sugestoes):
                if cols[i].button(s, key=f"iagon_sug_{screen}_{i}", use_container_width=True):
                    clicked = s
            q = st.text_input("Pergunte sobre esta tela…", key=f"iagon_in_{screen}",
                              label_visibility="collapsed", placeholder="Pergunte sobre esta tela…")
            pergunta = (clicked or (q or "").strip())
            if pergunta and pergunta != st.session_state.get(f"iagon_lastq_{screen}"):
                st.session_state[f"iagon_lastq_{screen}"] = pergunta
                with st.spinner("Analisando esta tela…"):
                    try:
                        ctx = context_fn() if callable(context_fn) else context_fn
                        ans = iagon.analisar(ctx, _SCREEN_IAGON_INSTR + pergunta)
                    except Exception as e:
                        ans = f"Não consegui responder agora ({type(e).__name__})."
                st.session_state[f"iagon_ans_{screen}"] = {"q": pergunta, "a": ans}
            last = st.session_state.get(f"iagon_ans_{screen}")
            if last:
                st.markdown(f"<div class='iagon-cv-q'>🧑 {html.escape(last['q'])}</div>", unsafe_allow_html=True)
                st.markdown(last["a"])


def _iagon_trechos_priorizados_text(road: str, cenario: int = 1, top: int = 25, horizonte: int = 1) -> str:
    """Top trechos prioritários POR SEGMENTO de um CENÁRIO — mesmos números do relatório
    (extensão por segmento, IPT, nível de prioridade 1–10, solução, custo).

    O CUSTO por trecho depende do `horizonte` (anos): igual ao relatório, o custo é a soma
    da programação do orçamento DENTRO do horizonte. Default 1 = só a 1ª intervenção (visão
    'orçamento anual'). Horizonte maior soma a manutenção futura."""
    scs = _iagon_road_scenarios(road)
    if not scs:
        return f"Sem cenários Paragon cadastrados para {road}."
    idx = max(1, min(int(cenario or 1), len(scs))) - 1
    sc = scs[idx]
    sol = get_solutions_data(road, scenario_key=sc["key"])
    table = sol.get("table")
    if table is None or table.empty:
        return f"Sem dados Paragon para {road} (cenário {sc['n']}: {sc['label']})."
    h = max(1, int(horizonte or 1))
    bi = _limit_budget_to_horizon(sol.get("budget_items"), h)
    seg = _segment_priority_table(
        _aplicar_indice_priorizacao(_economic_work_table(table)), bi
    )
    if seg.empty:
        return f"Sem segmentos com intervenção para {road} (cenário {sc['n']}: {sc['label']})."
    total = len(seg)
    seg = seg.sort_values("Prioridade").head(int(top or 25))
    linhas = "\n".join(
        f"  {int(r['Prioridade'])}º · {r['SNV']} · km {_format_km(float(r['Km Inicial']))}–{_format_km(float(r['Km Final']))} · "
        f"{float(r['Extensão']):.2f} km · nível {int(round(float(r['Priorização'])))} · IPT {float(r['IPT']):.2f} · "
        f"{str(r['Solução recomendada']).replace(' + ', ' / ')} · {_format_money(float(r['Custo econômico']))}"
        for _, r in seg.iterrows()
    )
    return (
        f"Trechos prioritários POR SEGMENTO — {road} · cenário {sc['n']}: {sc['label']} "
        f"(top {len(seg)} de {total} segmentos; CUSTO no horizonte de {h} ano(s) — "
        f"mesmo critério do relatório; nível 1 = mais crítico):\n{linhas}"
    )


def _iagon_full_road_context(road: str, scenario_key: str | None, titulo: str,
                             filtros: dict, extra: str = "") -> str:
    """Contexto RICO de uma rodovia+cenário p/ o painel da tela: situação completa +
    trechos prioritários POR SEGMENTO (top 15) + extra específico da tela. Montado sob
    demanda (lazy) — só roda quando há pergunta."""
    num = _scenario_num(road, scenario_key)
    partes = [
        _iagon_situacao_text(road, num),
        _iagon_trechos_priorizados_text(road, num, top=15, horizonte=1),
    ]
    if extra:
        partes.append(str(extra))
    return _screen_ctx(titulo, filtros, "\n\n".join(partes))


def _iagon_dnit_detail(road: str) -> dict | None:
    """Resumo DNIT de uma rodovia: distribuição de soluções DNIT, custo por ano, SREs."""
    data = get_dnit_economic_data(road)
    if not data.get("available") or data.get("table") is None or data["table"].empty:
        return None

    table = data["table"]
    budget_items = data.get("budget_items")

    # Distribuição de soluções DNIT por núcleo (curto, ex. Micro(1,5), FR5+CBUQ+Drenagem).
    sdist_nuc = (
        table.groupby("Solução núcleo")["Extensão"].sum().sort_values(ascending=False)
    )
    solucoes_dnit = [
        (str(name), round(float(km), 1)) for name, km in sdist_nuc.items()
    ]

    # Custo anual no horizonte 8 anos (mantém paridade com Paragon no contexto).
    cby_dnit: list[tuple[int, float]] = []
    if budget_items is not None and not budget_items.empty:
        ano_base = int(data.get("ano_base") or 2027)
        sub = budget_items[
            (budget_items["Ano"] >= ano_base)
            & (budget_items["Ano"] <= ano_base + _ECONOMIC_DEFAULT_HORIZON - 1)
        ]
        cby_dnit = [
            (int(r["Ano"]), float(r["Custo"]))
            for _, r in sub.groupby("Ano", as_index=False)["Custo"].sum().sort_values("Ano").iterrows()
        ]

    # SREs com priorização DNIT — agrega extensão por SRE (soma dos segmentos).
    work = table.copy()
    work["Custo econômico"] = work["Custo estimado"].astype(float)
    work = _aplicar_indice_priorizacao_dnit(work)
    sre_agg = (
        work.groupby("SNV", as_index=False).agg(
            Priorização=("Priorização", "max"),
            ClassePrio=("Classe prioridade", "first"),
            Prioridade=("Prioridade", "min"),
            Extensão=("Extensão", "sum"),
            IRI=("IRI", "mean"),
            IGG=("IGG", "mean"),
            Custo=("Custo econômico", "sum"),
        )
        .sort_values("Prioridade")
    )
    sres = []
    for _, r in sre_agg.iterrows():
        sres.append({
            "sre": str(r["SNV"]),
            "rank": int(r["Prioridade"]),
            "priorizacao": int(round(float(r["Priorização"]))),
            "classe": str(r["ClassePrio"]).replace("Prioridade ", ""),
            "ext": round(float(r["Extensão"]), 1),
            "iri": round(float(r["IRI"]), 2),
            "igg": round(float(r["IGG"]), 0),
            "custo": float(r["Custo"]),
        })

    return {
        "necessidade": float(table["Custo estimado"].sum()),
        "ext_km": round(float(table["Extensão"].sum()), 1),
        "solucoes": solucoes_dnit,
        "custo_por_ano": cby_dnit,
        "sres": sres,
        "ano_base": int(data.get("ano_base") or 2027),
    }


def _iagon_projection_summary(road: str) -> dict | None:
    """Resumo de projeção: Paragon (IAP) ou DNIT (cronograma + IRI)."""
    out: dict = {}
    # Paragon (curva IAP)
    try:
        pp = get_projection_data(road)
        if pp and pp.get("years"):
            out["paragon"] = {
                "base_year": int(pp["base_year"]),
                "base_iap": round(float(pp["base_avg"]), 2),
                "final_year": int(pp["years"][-1]),
                "final_iap": round(float(pp["final_avg"]), 2),
                "worst_iap": round(float(pp["worst_future_val"]), 2),
                "worst_year": int(pp["worst_future_year"]),
                "below_meta_km": round(float(pp["base_below_km"]), 1),
            }
    except Exception:
        pass
    # DNIT (cronograma de obras)
    try:
        ps = get_dnit_projection_schedule(road)
        if ps.get("available"):
            df = ps["schedule"]
            top_sols = df["Solução núcleo"].value_counts().head(3).to_dict()
            out["dnit"] = {
                "obras_total": int(len(df)),
                "sres_com_obra": len(ps["sre_list"]),
                "anos_range": f"{ps['ano_inicial']}-{ps['ano_final']}",
                "custo_total": float(ps["custo_total"]),
                "solucoes_principais": [(n, int(c)) for n, c in top_sols.items()],
            }
    except Exception:
        pass
    return out or None


def _build_iagon_context() -> tuple[str, dict]:
    """Resumo COMPLETO para o IAGON: Paragon + DNIT + Projeção + Cenário econômico.

    Removido o `@lru_cache` para refletir mudanças no banco a cada conversa (custa pouco
    em tempo de execução e evita o IAGON respondendo com dados velhos).
    """
    data = _build_network_overview(is_dnit=False)
    if not data:
        return "Sem dados disponíveis.", {}
    df = data["roads_df"]
    dnit_roads_list = get_dnit_available_roads()
    dnit_set = set(dnit_roads_list)

    roads: dict[str, dict] = {}
    paragon_cost_lines: list[str] = []
    paragon_sol_lines: list[str] = []
    paragon_trecho_blocks: list[str] = []
    dnit_blocks: list[str] = []
    proj_blocks: list[str] = []
    sentido_blocks: list[str] = []
    cond_blocks: list[str] = []
    cen_lines: list[str] = []
    nec_by_road: dict[str, float] = {}
    net_nec = 0.0

    for _, r in df.iterrows():
        road = r["Rodovia"]
        cby, sdist, trechos, nec_total = _iagon_road_detail(road)
        nec_by_road[road] = nec_total
        net_nec += nec_total
        scs = _iagon_road_scenarios(road)
        if len(scs) > 1:
            cen_lines.append(
                f"- **{road}**: {len(scs)} cenários — "
                + " · ".join(f"{s['n']}) {s['label']}" for s in scs)
                + "  →  PERGUNTE qual cenário antes de listar trechos/extensões."
            )
        elif scs:
            cen_lines.append(f"- {road}: 1 cenário ({scs[0]['label']}).")
        dnit = _iagon_dnit_detail(road) if road in dnit_set else None
        proj = _iagon_projection_summary(road)

        roads[road] = {
            "code": r["_code"],
            "metrics": {
                "IAP": round(float(r["IAP"]), 2),
                "IRI": round(float(r["IRI"]), 2),
                "IGG": round(float(r["IGG"]), 0),
                "iap_bad_pct": round(float(r["iap_bad_pct"]), 0),
                "iri_bad_pct": round(float(r["iri_bad_pct"]), 0),
                "prio": int(r["prio"]),
                "custo": float(nec_total),
                "ext_km": round(float(r["ext_km"]), 1),
            },
            "paragon": {
                "cost_by_year": cby,
                "solucoes": sdist,
                "trechos": trechos,
            },
            "dnit": dnit,
            "projecao": proj,
        }

        anos = " · ".join(f"{ano} {_format_money(c)}" for ano, c in cby) or "sem programação anual"
        paragon_cost_lines.append(f"- {road} (necessidade total, todos os anos: {_format_money(nec_total)}): {anos}")
        sol_txt = " · ".join(f"{name} {km:.1f} km" for name, km in sdist) or "sem dados"
        paragon_sol_lines.append(f"- {road}: {sol_txt}")
        if trechos:
            tl = "\n".join(
                f"  {t['rank']}º · {t['snv']} · {t['classe']} · priorização **{t['priorizacao']}** "
                f"(escala 1–10, menor=pior) · {t['ext']:.0f} km · IAP {t['iap']:.2f} · "
                f"mix de soluções: {t['mix_solucoes']}"
                for t in trechos
            )
            paragon_trecho_blocks.append(f"### {road}\n{tl}")

        if dnit:
            sols_txt = " · ".join(f"{n} {km}km" for n, km in dnit["solucoes"]) or "sem dados"
            anos_dnit = (
                " · ".join(f"{a} {_format_money(c)}" for a, c in dnit["custo_por_ano"])
                or "sem programação"
            )
            sres_txt = "\n".join(
                f"  {s['rank']}º · {s['sre']} · {s['classe']} · priorização **{s['priorizacao']}** · "
                f"{s['ext']:.0f} km · IRI {s['iri']:.2f} · IGG {s['igg']:.0f}"
                for s in dnit["sres"]
            )
            dnit_blocks.append(
                f"### {road} (DNIT / Matriz Revitaliza DNIT/RO)\n"
                f"- Necessidade: {_format_money(dnit['necessidade'])} · {dnit['ext_km']} km\n"
                f"- Soluções DNIT (nomes técnicos): {sols_txt}\n"
                f"- Custo por ano (horizonte {_ECONOMIC_DEFAULT_HORIZON}a a partir de {dnit['ano_base']}): {anos_dnit}\n"
                f"- SREs ordenados por prioridade:\n{sres_txt}"
            )

        if proj:
            chunks = []
            if proj.get("paragon"):
                pp = proj["paragon"]
                chunks.append(
                    f"  Paragon (IAP): base {pp['base_year']} = {pp['base_iap']} → "
                    f"final {pp['final_year']} = {pp['final_iap']} · "
                    f"pior IAP {pp['worst_iap']} em {pp['worst_year']} · "
                    f"{pp['below_meta_km']} km abaixo da meta hoje"
                )
            if proj.get("dnit"):
                pd_ = proj["dnit"]
                top = ", ".join(f"{n} ({c})" for n, c in pd_["solucoes_principais"])
                chunks.append(
                    f"  DNIT (cronograma): {pd_['obras_total']} obras em "
                    f"{pd_['sres_com_obra']} SREs · {pd_['anos_range']} · "
                    f"custo total {_format_money(pd_['custo_total'])} · top: {top}"
                )
            proj_blocks.append(f"### {road}\n" + "\n".join(chunks))

        enrich = _iagon_enrich_detail(road)
        if enrich["sentidos"]:
            sl = " · ".join(
                f"**{s['sentido']}** IAP {s['iap']:.2f} · {s['ext']:.0f} km · "
                f"necessidade {_format_money(s['necessidade'])}"
                for s in enrich["sentidos"] if s.get("iap") is not None
            )
            if sl:
                sentido_blocks.append(f"- {road}: {sl}")
        sub = enrich.get("subindices")
        if sub or enrich.get("def_mm") is not None:
            parts = []
            for c, nome in (("icds", "ICDS"), ("icdp", "ICDP"), ("icde", "ICDE")):
                if sub and c in sub:
                    parts.append(f"{nome} {sub[c][0]:.2f} ({sub[c][1]})")
            if enrich.get("def_mm") is not None:
                parts.append(f"Deflexão média {enrich['def_mm']:.2f} mm")
            if parts:
                cond_blocks.append(f"- {road}: " + " · ".join(parts))

    linhas = "\n".join(
        f"| {r['Rodovia']} | {r['IAP']:.2f} | {r['IRI']:.2f} | {r['IGG']:.0f} | "
        f"{r['iap_bad_pct']:.0f}% | {r['iri_bad_pct']:.0f}% | {int(r['prio'])} | {_format_money(nec_by_road.get(r['Rodovia'], 0.0))} |"
        for _, r in df.sort_values("IAP").iterrows()
    )
    dnit_roads_str = ", ".join(dnit_roads_list) or "nenhuma"

    context = f"""# Malha rodoviária (Rondônia) — dados completos

**Rodovias:** {len(df)} · **Extensão total:** {data['total_km']:.0f} km
**Necessidade total Paragon (todos os anos do programa):** {_format_money(net_nec)}
**Trechos prioritários (Paragon, Alta/Crítica):** {data['prio_total']}
**Médias da rede:** IAP {data['net_iap']:.2f} (meta 2,5) · IRI {data['net_iri']:.2f} · IGG {data['net_igg']:.0f}
**Rodovias com cálculo DNIT/Revitaliza disponível:** {dnit_roads_str}

## 1) Diagnóstico — Indicadores por rodovia (pior IAP primeiro)
| Rodovia | IAP | IRI | IGG | % IAP<2,5 | % IRI>4 | Trechos prio. | Necessidade total (programa) |
|---|---|---|---|---|---|---|---|
{linhas}

## 2) Soluções Paragon por rodovia
Nomes Paragon (use EXATAMENTE estes): *Reconstrução, Fresagem e recomposição, Recarga Superficial + Reparo localizado, Sem intervenção*.
{chr(10).join(paragon_sol_lines)}

## 3) Cenário econômico Paragon — custo por ano (programa completo, todos os anos)
{chr(10).join(paragon_cost_lines)}

## 4) Cenários cadastrados e trechos prioritários (Paragon)

### Cenários cadastrados por rodovia
{chr(10).join(cen_lines) or "_sem cenários listados_"}
> ⚠️ Cada rodovia pode ter MAIS DE UM cenário Paragon. Quando o usuário pedir trechos prioritários, extensão ou custos POR TRECHO de uma rodovia com **mais de um cenário**, **PERGUNTE primeiro qual cenário** (apresente numerados: 1) …, 2) …) e ofereça uma análise técnica comparando os dois. Para a listagem EXATA (por segmento, do cenário escolhido), chame **`listar_trechos_priorizados(rodovia, cenario)`** — NÃO use a visão geral abaixo para extensões por trecho.

### Visão geral (cenário padrão, agregada por SNV — APROXIMADA)
- Nível de prioridade **1–10** (escala invertida, MENOR = mais crítico): Crítica ≤ 3 · Alta ≤ 5 · Média ≤ 7 · Baixa > 7.
- "Rank" = posição (1 = topo). Esta visão é **por SNV e do cenário padrão**; para extensão/priorização exatas POR SEGMENTO e por cenário, use a ferramenta acima.
- Sempre cite o **mix completo de soluções** (não só a dominante) — se o SNV tem Reconstrução, mencione mesmo que minoria em km.
{chr(10).join(paragon_trecho_blocks)}

## 5) Soluções e SREs DNIT (Matriz Revitaliza DNIT/RO)
DNIT usa nomes técnicos: *Micro(0,8), Micro(1,5), FR5 + CBUQ(3) + CBUQ(4), Drenagem, Reconstrução*.
Não confunda com Paragon. Cada metodologia tem o próprio cálculo de priorização (DNIT usa IRI+IGG, sem VMDA/DEF).
{chr(10).join(dnit_blocks) or "_Sem rodovias DNIT no momento_"}

## 6) Projeção (evolução ano a ano)
{chr(10).join(proj_blocks) or "_Sem projeção disponível_"}

## 6b) Sentidos Paragon — CRESCENTE × DECRESCENTE (por rodovia)
A matriz processada não tem faixa; cada rodovia foi rodada por sentido. Use quando o usuário perguntar de um sentido específico ou da diferença entre eles. Necessidade = total do programa (todos os anos).
{chr(10).join(sentido_blocks) or "_Sem separação por sentido disponível_"}

## 6c) Condição estrutural — ICDS/ICDP/ICDE e Deflexão (média ponderada por extensão)
Índices estruturais 0–5, **MAIOR = MELHOR** condição (≥4,5 Excelente · ≥3,5 Bom · ≥2,5 Regular · ≥1,5 Mau · <1,5 Péssimo). NÃO confunda com o IAP. ICDP baixo = pavimento estruturalmente fraco; Deflexão (mm) alta = estrutura mais frágil.
{chr(10).join(cond_blocks) or "_Sem dados estruturais disponíveis_"}

## 7) Regras de interpretação
- **Diagnóstico padrão = Paragon**. Use DNIT só quando o usuário pedir explicitamente "matriz DNIT", "Revitaliza" ou citar nomes DNIT (CBUQ, FR5, Micro(0,8/1,5), Drenagem).
- **Cenários**: cada rodovia pode ter >1 cenário Paragon (seção 4). Antes de listar trechos/extensões/custos por trecho de uma rodovia com mais de um cenário, **PERGUNTE qual cenário** e ofereça comparar; depois use `listar_trechos_priorizados(rodovia, cenario)` para os números exatos.
- **Priorização 1–10**: menor valor = MAIS crítico. NUNCA inverta o sentido — priorização 2 é pior que priorização 8.
- **"Rank" ≠ "Priorização"**: rank é ordinal (1, 2, 3…); priorização é o valor 1–10. Não troque os dois.
- **Mix de soluções**: ao listar um SNV, cite TODAS as soluções presentes (com km), nunca apenas a dominante.
  Se houver Reconstrução, ela vai SEMPRE primeiro na lista (severidade mais alta).
- Custos são necessidades cadastradas no banco; cobertura anual depende do orçamento.
- **Por sentido**: ao citar CRESCENTE/DECRESCENTE, use a seção "6b) Sentidos Paragon". As seções 1–4 trazem o cenário padrão de cada rodovia (em geral um dos sentidos); a 6b traz os dois lado a lado.
- **Estrutura ≠ superfície**: ICDS/ICDP/ICDE (seção 6c) são índices ESTRUTURAIS (maior = melhor); o IAP tem régua de classe própria. Não troque os dois.
- **Necessidade = TODOS os anos do programa** (não um horizonte fixo). A "Necessidade total" (seções 1–3) já soma todos os anos do cenário padrão, e a seção 3 ("custo por ano") lista a programação ano a ano do programa completo. NUNCA diga "horizonte de 8 anos" para a necessidade. Para o número EXATO de um cenário específico, use `situacao_rodovia(rodovia, cenario)`.
"""
    report_data = {
        "network_df": df,
        "roads": roads,
        "totals": {
            "iap": data["net_iap"], "iri": data["net_iri"], "igg": data["net_igg"],
            "custo": data["net_custo"], "prio": data["prio_total"], "km": data["total_km"],
        },
        "dnit_roads": dnit_roads_list,
    }
    return context, report_data


def _iagon_resolve_scope(report_data: dict, escopo: str):
    """Resolve 'rede' ou um código/nome de rodovia -> (rótulo, dados | None)."""
    e = (escopo or "rede").strip().lower()
    if e in ("rede", "malha", "todas", "geral", "all"):
        return "rede", None
    code = _normalize_road_code(escopo)
    for road, info in report_data.get("roads", {}).items():
        if info.get("code") == code or road.lower() == e:
            return road, info
    return None, None


def _iagon_pdf_bytes(title: str, subtitle: str, sections: list[tuple]) -> bytes:
    """PDF com uma ou mais seções [(heading, headers, rows)]; células quebram linha (Paragraph)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm)
    usable = A4[0] - 36 * mm
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#0b1d28"))
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#5b6b78"))
    sec = ParagraphStyle("sec", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#0b1d28"))
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#1f2a33"))
    hcell = ParagraphStyle("hcell", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.white, fontName="Helvetica-Bold")
    foot = ParagraphStyle("foot", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#90a0ad"))

    story = [Paragraph(title, h), Spacer(1, 4), Paragraph(subtitle, sub), Spacer(1, 14)]
    for heading, headers, rows in sections:
        if heading:
            story += [Paragraph(heading, sec), Spacer(1, 4)]
        ncols = max(len(headers), 1)
        col_w = [usable / ncols] * ncols
        data = [[Paragraph(str(c), hcell) for c in headers]]
        data += [[Paragraph(str(c), cell) for c in row] for row in rows]
        table = Table(data, colWidths=col_w, repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1d28")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f8")]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d6dee5")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story += [table, Spacer(1, 14)]
    story += [Paragraph("Gerado pelo IAGON · Painel de Pavimentos Paragon/DNIT", foot)]
    doc.build(story)
    return buf.getvalue()


def _iagon_chart_style():
    """Estilo padronizado para todos os gráficos do IAGON (cores do painel)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": "#ffffff",
        "axes.facecolor": "#f7fafc",
        "axes.edgecolor": "#475569",
        "axes.labelcolor": "#1b2a35",
        "axes.titlecolor": "#0f2230",
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "xtick.color": "#475569",
        "ytick.color": "#475569",
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "grid.color": "#cbd5dd",
        "grid.alpha": 0.5,
        "grid.linestyle": ":",
        "font.family": ["DejaVu Sans"],
        "savefig.dpi": 170,
        "savefig.facecolor": "#ffffff",
    })
    return plt


def _iagon_render_chart(
    tipo: str,
    rodovia: str | None = None,
    rodovias: list[str] | None = None,
    metodologia: str = "paragon",
    sre: str | None = None,
) -> tuple[str, bytes, str] | None:
    """Gera um PNG de gráfico segundo `tipo`. Devolve (filename, bytes, mime) ou None.

    Tipos suportados:
      - distribuicao_iap: pie/donut IAP de uma rodovia (Paragon)
      - distribuicao_solucoes: bar km por solução de uma rodovia (Paragon ou DNIT)
      - custo_por_ano: bar R$/ano de uma rodovia (Paragon ou DNIT)
      - comparativo_rodovias: bar duplo IAP médio + km abaixo da meta entre rodovias
      - projecao_iap: line IAP ano a ano de um SRE específico
    """
    plt = _iagon_chart_style()
    import io

    tipo = (tipo or "").lower().strip()
    meth = (metodologia or "paragon").lower()

    if tipo == "distribuicao_iap":
        if not rodovia:
            return None
        data = get_solutions_data(rodovia)
        t = data.get("table")
        if t is None or t.empty:
            return None
        dist = t.groupby("_classe_iap", as_index=False)["Extensão"].sum()
        order = ["Excelente", "Bom", "++ Regular", "+ Regular", "- Regular", "Mau", "Péssimo"]
        dist["_ord"] = dist["_classe_iap"].apply(lambda x: order.index(x) if x in order else 99)
        dist = dist.sort_values("_ord")
        colors = [_IAGON_PARAGON_CLASS_COLORS.get(c, "#9aa8b3") for c in dist["_classe_iap"]]
        total = float(dist["Extensão"].sum()) or 1.0

        fig, ax = plt.subplots(figsize=(9, 6))
        wedges, _ = ax.pie(
            dist["Extensão"], colors=colors, startangle=90, counterclock=False,
            wedgeprops={"width": 0.40, "edgecolor": "#ffffff", "linewidth": 2},
        )
        legend_labels = [
            f"{c}: {km:.1f} km ({km/total*100:.1f}%)"
            for c, km in zip(dist["_classe_iap"], dist["Extensão"])
        ]
        ax.legend(wedges, legend_labels, title="Conceito IAP",
                  loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=10)
        ax.set_title(f"Distribuição IAP — {rodovia}\nExtensão total: {total:.1f} km")
        ax.text(0, 0, f"{total:.0f}\nkm", ha="center", va="center",
                fontsize=18, fontweight="bold", color="#0f2230")
        ax.set_aspect("equal")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return f"grafico_distribuicao_iap_{rodovia.replace('/', '-')}.png", buf.getvalue(), "image/png"

    if tipo == "distribuicao_solucoes":
        if not rodovia:
            return None
        if meth == "dnit":
            data = get_dnit_solutions_data(rodovia)
            if not data.get("available") or data.get("table") is None or data["table"].empty:
                return None
            t = data["table"]
            grouped = t.groupby("Solução núcleo")["Extensão"].sum().sort_values(ascending=True)
            colors = ["#f2a51a"] * len(grouped)
            title_extra = "Matriz Revitaliza DNIT/RO"
        else:
            data = get_solutions_data(rodovia)
            t = data.get("table")
            if t is None or t.empty:
                return None
            grouped = t.groupby("Solução recomendada")["Extensão"].sum().sort_values(ascending=True)
            color_map = {
                "Reconstrução": "#d71920",
                "Fresagem e recomposição": "#fff200",
                "Recarga Superficial + Reparo localizado": "#b6d7a8",
                "Reparo localizado + Recarga Superficial": "#b6d7a8",
                "Sem intervenção": "#82929d",
            }
            colors = [color_map.get(str(s), "#9aa8b3") for s in grouped.index]
            title_extra = "Paragon"

        fig, ax = plt.subplots(figsize=(10, max(4, len(grouped) * 0.7)))
        bars = ax.barh(range(len(grouped)), grouped.values, color=colors, edgecolor="#06222b", linewidth=0.5)
        ax.set_yticks(range(len(grouped)))
        ax.set_yticklabels(grouped.index, fontsize=10)
        ax.set_xlabel("Extensão (km)")
        ax.set_title(f"Soluções recomendadas — {rodovia} · {title_extra}")
        ax.grid(True, axis="x", linestyle=":", alpha=0.5)
        for b, v in zip(bars, grouped.values):
            ax.text(v + max(grouped.values) * 0.01, b.get_y() + b.get_height() / 2,
                    f"{v:.1f} km", va="center", fontsize=9, fontweight="bold", color="#0f2230")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return f"grafico_solucoes_{rodovia.replace('/', '-')}_{meth}.png", buf.getvalue(), "image/png"

    if tipo == "custo_por_ano":
        if not rodovia:
            return None
        if meth == "dnit":
            data = get_dnit_economic_data(rodovia)
            if not data.get("available"):
                return None
            bi = data.get("budget_items")
            ano_base = int(data.get("ano_base") or 2027)
            if bi is None or bi.empty:
                return None
            bi = bi[(bi["Ano"] >= ano_base) & (bi["Ano"] <= ano_base + _ECONOMIC_DEFAULT_HORIZON - 1)]
            grp = bi.groupby("Ano", as_index=False)["Custo"].sum().sort_values("Ano")
            title_extra = "DNIT · Matriz Revitaliza"
            color = "#f2a51a"
        else:
            data = get_solutions_data(rodovia)
            bi = _limit_budget_to_horizon(data.get("budget_items"), _ECONOMIC_DEFAULT_HORIZON)
            if bi is None or bi.empty:
                return None
            grp = bi.groupby("Ano", as_index=False)["Custo"].sum().sort_values("Ano")
            title_extra = "Paragon"
            color = "#00c2e8"

        anos = grp["Ano"].astype(int).tolist()
        custos = grp["Custo"].tolist()
        total = sum(custos)

        fig, ax = plt.subplots(figsize=(10, 5))
        bars = ax.bar([str(a) for a in anos], [c / 1e6 for c in custos],
                      color=color, edgecolor="#06222b", linewidth=0.6)
        ax.set_ylabel("R$ milhões")
        ax.set_title(f"Custo por ano — {rodovia} · {title_extra}\nTotal: {_format_money(total)}")
        ax.grid(True, axis="y", linestyle=":", alpha=0.5)
        ymax = max([c / 1e6 for c in custos]) if custos else 1
        for b, v in zip(bars, custos):
            ax.text(b.get_x() + b.get_width() / 2, v / 1e6 + ymax * 0.02,
                    _format_money(v), ha="center", fontsize=8, fontweight="bold", color="#0f2230")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return f"grafico_custo_ano_{rodovia.replace('/', '-')}_{meth}.png", buf.getvalue(), "image/png"

    if tipo == "comparativo_rodovias":
        roads = rodovias or get_available_roads()
        rows = []
        for r in roads:
            d = get_solutions_data(r)
            t = d.get("table")
            if t is None or t.empty:
                continue
            ext = float(t["Extensão"].sum())
            iap_med = float((t["IAP"] * t["Extensão"]).sum() / ext) if ext > 0 else 0.0
            km_below = float(t[t["IAP"] < IAP_META]["Extensão"].sum())
            bi = _limit_budget_to_horizon(d.get("budget_items"), _ECONOMIC_DEFAULT_HORIZON)
            custo = float(bi["Custo"].sum()) if bi is not None and not bi.empty else 0.0
            rows.append({"Rodovia": r, "IAP": iap_med, "km_below": km_below, "ext": ext, "custo": custo})
        if not rows:
            return None
        import numpy as np
        labels = [r["Rodovia"] for r in rows]
        x = np.arange(len(labels))
        iap_vals = [r["IAP"] for r in rows]
        custo_mi = [r["custo"] / 1e6 for r in rows]
        km_below = [r["km_below"] for r in rows]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
        # IAP médio + linha da meta
        bars1 = ax1.bar(labels, iap_vals, color="#00c2e8", edgecolor="#06222b", linewidth=0.6, width=0.55)
        ax1.axhline(2.5, color="#d71920", linestyle="--", linewidth=1.4, label="Meta 2,5")
        ax1.set_ylim(0, max(5.5, max(iap_vals) + 0.5))
        ax1.set_ylabel("IAP médio")
        ax1.set_title("IAP médio por rodovia\n(meta 2,5)")
        ax1.legend(loc="lower right", frameon=False)
        ax1.grid(True, axis="y", linestyle=":", alpha=0.5)
        for b, v in zip(bars1, iap_vals):
            ax1.text(b.get_x() + b.get_width() / 2, v + 0.08, f"{v:.2f}",
                     ha="center", fontsize=10, fontweight="bold", color="#0f2230")

        # Necessidade R$ mi + sobreposição km abaixo da meta
        bars2 = ax2.bar(labels, custo_mi, color="#f2a51a", edgecolor="#06222b", linewidth=0.6, width=0.55)
        ax2.set_ylabel("Necessidade (R$ milhões)")
        ax2.set_title("Necessidade no horizonte 8 anos")
        ax2.grid(True, axis="y", linestyle=":", alpha=0.5)
        for b, v, kb in zip(bars2, custo_mi, km_below):
            ax2.text(b.get_x() + b.get_width() / 2, v + max(custo_mi) * 0.02,
                     f"R$ {v:.0f} mi", ha="center", fontsize=10, fontweight="bold", color="#0f2230")
            ax2.text(b.get_x() + b.get_width() / 2, v / 2,
                     f"{kb:.0f} km <2,5", ha="center", fontsize=9, color="#0f2230")

        fig.suptitle("Comparativo da malha Paragon", fontsize=14, fontweight="bold", color="#0f2230", y=1.02)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return f"grafico_comparativo_rodovias.png", buf.getvalue(), "image/png"

    if tipo == "projecao_iap":
        if not rodovia:
            return None
        d = get_projection_data(rodovia)
        if not d or not d.get("sre_series"):
            return None
        sre_use = sre or d.get("default_sre") or next(iter(d["sre_series"]))
        serie = d["sre_series"].get(sre_use) or d["sre_series"][next(iter(d["sre_series"]))]
        years = serie.get("years", [])
        iaps = serie.get("iap", [])
        intervs = serie.get("interv", [])

        fig, ax = plt.subplots(figsize=(12, 5.5))
        # Bandas IAP
        bands = [
            (0.0, 1.0, "#d71920", "Péssimo"),
            (1.0, 2.0, "#f2a51a", "Mau"),
            (2.0, 2.5, "#fff200", "− Regular"),
            (2.5, 3.5, "#f4f1a6", "+ Regular"),
            (3.5, 4.0, "#b6d7a8", "++ Regular"),
            (4.0, 5.0, "#00a651", "Bom"),
            (5.0, 6.0, "#00c2e8", "Excelente"),
        ]
        for lo, hi, c, _ in bands:
            ax.axhspan(lo, hi, color=c, alpha=0.18)
        ax.axhline(2.5, color="#d71920", linestyle="--", linewidth=1.4, label="Meta 2,5")
        ax.plot(years, iaps, color="#0f2230", linewidth=2.6, marker="o",
                markersize=5, markerfacecolor="#ffffff", markeredgecolor="#0f2230")
        # Marcadores azuis = anos com intervenção
        for i, (yr, val, it) in enumerate(zip(years, iaps, intervs)):
            if it:
                ax.scatter([yr], [val], color="#00c2e8", s=120, zorder=5,
                           edgecolor="#06222b", linewidth=1.4)
        ax.set_xlabel("Ano")
        ax.set_ylabel("IAP")
        ax.set_ylim(0, max(6, max(iaps) + 0.5 if iaps else 6))
        ax.set_title(f"Projeção IAP — {rodovia} · SRE {sre_use}\nMarcador azul = ano com intervenção · faixas = conceito")
        ax.legend(loc="lower right", frameon=True, fontsize=9)
        ax.grid(True, axis="x", linestyle=":", alpha=0.4)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return f"grafico_projecao_{rodovia.replace('/', '-')}_{sre_use}.png", buf.getvalue(), "image/png"

    return None


# A base de dados usa "Recarga Superficial + Reparo localizado". O nome legado
# "Microrrevestimento + Reparo localizado" ainda pode vir do modelo/usuário — tratamos
# como sinônimo para o filtro de solução (substring) não retornar vazio à toa.
def _iagon_norm_solucoes(solucoes: list[str] | None) -> set[str]:
    out: set[str] = set()
    for s in (solucoes or []):
        if not s or not s.strip():
            continue
        low = s.strip().lower()
        out.add(low)
        if "microrrev" in low:
            out.add(low.replace("microrrevestimento", "recarga superficial"))
            out.add("recarga superficial")
    return out


def _iagon_generate_work_plan(
    road: str,
    metodologia: str = "paragon",
    classes: list[str] | None = None,
    solucoes: list[str] | None = None,
    faixas_iri: list[str] | None = None,
    snvs: list[str] | None = None,
    formato: str = "pdf",
) -> tuple[str, bytes, str] | None:
    """Plano de trabalho real para uma rodovia (com filtros opcionais).

    Lista, segmento por segmento, o que vai ser feito: SNV, km, IAP/IRI, classe,
    intervenção recomendada e custo. Filtros (classes/soluções/faixas IRI) recortam
    o plano para o subconjunto que o usuário já está olhando no mapa.

    Devolve (filename, bytes, mime) ou None se não há dados.
    """
    metodologia = (metodologia or "paragon").lower()
    classes_set = {c.strip() for c in (classes or []) if c and c.strip()}
    solucoes_set = _iagon_norm_solucoes(solucoes)
    faixas_set = {f.strip() for f in (faixas_iri or []) if f and f.strip()}
    snvs_set = {s.strip().upper() for s in (snvs or []) if s and s.strip()}

    if metodologia == "dnit":
        data = get_dnit_solutions_data(road)
        if not data.get("available") or data.get("table") is None or data["table"].empty:
            return None
        table = data["table"].copy()
        if snvs_set:
            table = table[table["SNV"].astype(str).str.upper().isin(snvs_set)]
        if faixas_set:
            table = table[table["Faixa"].astype(str).isin(faixas_set)]
        if table.empty:
            return None
        rows = []
        for _, r in table.sort_values("Km Inicial").iterrows():
            rows.append({
                "SNV": str(r.get("SNV") or "—"),
                "Km Inicial": float(r["Km Inicial"]),
                "Km Final": float(r["Km Final"]),
                "Extensão": float(r["Extensão"]),
                "IRI": float(r.get("IRI", 0) or 0),
                "IGG": float(r.get("IGG", 0) or 0),
                "Faixa": str(r.get("Faixa") or "-"),
                "Solução núcleo": str(r.get("Solução núcleo") or "-"),
                "Solução completa": str(r.get("Solução recomendada") or "-"),
                "Custo": float(r.get("Custo estimado", 0) or 0),
            })
    else:
        data = get_solutions_data(road)
        table = data.get("table")
        if table is None or table.empty:
            return None
        # _economic_work_table aplica fallback paramétrico quando o banco não tem
        # custo cadastrado para o segmento — é o mesmo cálculo da tela Cenário.
        work = _economic_work_table(table)
        if snvs_set:
            work = work[work["SNV"].astype(str).str.upper().isin(snvs_set)]
        if classes_set:
            work = work[work["_classe_iap"].astype(str).isin(classes_set)]
        if solucoes_set:
            work = work[
                work["Solução recomendada"].astype(str).str.lower().apply(
                    lambda s: any(needle in s for needle in solucoes_set)
                )
            ]
        if work.empty:
            return None
        rows = []
        for _, r in work.sort_values("Km Inicial").iterrows():
            rows.append({
                "SNV": str(r.get("SNV") or "—"),
                "Km Inicial": float(r["Km Inicial"]),
                "Km Final": float(r["Km Final"]),
                "Extensão": float(r["Extensão"]),
                "IAP": float(r.get("IAP", 0) or 0),
                "Classe IAP": str(r.get("_classe_iap") or "-"),
                "Solução recomendada": str(r.get("Solução recomendada") or "-"),
                "Custo estimado": float(r.get("Custo econômico", 0) or 0),
                "Custo origem": str(r.get("Custo origem") or "—"),
            })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    total_km = float(df["Extensão"].sum())
    total_custo = float(df["Custo estimado"].sum() if "Custo estimado" in df.columns else df["Custo"].sum())

    filtros_parts = []
    if snvs_set: filtros_parts.append("SNVs: " + ", ".join(sorted(snvs_set)))
    if classes_set: filtros_parts.append("classes: " + ", ".join(sorted(classes_set)))
    if solucoes_set: filtros_parts.append("soluções: " + ", ".join(sorted(solucoes_set)))
    if faixas_set: filtros_parts.append("faixas IRI: " + ", ".join(sorted(faixas_set)))
    filt_txt = " · ".join(filtros_parts) if filtros_parts else "todos os trechos"
    title = f"Plano de Trabalho — {road} ({metodologia.upper()})"
    subtitle = (
        f"{len(df)} trechos · {total_km:.1f} km · custo total {_format_money(total_custo)} · "
        f"recorte: {filt_txt}"
    )

    fmt = (formato or "pdf").lower()
    safe_road = road.replace('/', '-')
    filt_tag = ""
    if snvs_set: filt_tag += "-snv-" + "_".join(sorted(snvs_set))
    if classes_set: filt_tag += "-cls-" + "_".join(sorted({c.replace(' ', '') for c in classes_set}))
    if solucoes_set: filt_tag += "-sol-" + "_".join(sorted({s.split()[0] for s in solucoes_set}))
    if faixas_set: filt_tag += "-iri-" + "_".join(sorted({f.split()[-1] for f in faixas_set}))

    # Resumo por solução / faixa.
    if metodologia == "paragon":
        resumo = (
            df.groupby("Solução recomendada", as_index=False)
            .agg(Trechos=("SNV", "count"), Extensão=("Extensão", "sum"), Custo=("Custo estimado", "sum"))
            .sort_values("Custo", ascending=False)
        )
        resumo_headers = ["Solução", "# Trechos", "Extensão (km)", "Custo total"]
        resumo_rows = [
            [r["Solução recomendada"], str(int(r["Trechos"])), f"{r['Extensão']:.2f}", _format_money(r["Custo"])]
            for _, r in resumo.iterrows()
        ]
        plan_headers = ["SNV", "Km I", "Km F", "Ext (km)", "IAP", "Classe", "Solução recomendada", "Custo"]
        plan_rows = [
            [r["SNV"], f"{r['Km Inicial']:.2f}", f"{r['Km Final']:.2f}",
             f"{r['Extensão']:.2f}", f"{r['IAP']:.2f}", r["Classe IAP"],
             r["Solução recomendada"], _format_money(r["Custo estimado"])]
            for r in rows
        ]
    else:
        resumo = (
            df.groupby("Solução núcleo", as_index=False)
            .agg(Trechos=("SNV", "count"), Extensão=("Extensão", "sum"), Custo=("Custo", "sum"))
            .sort_values("Custo", ascending=False)
        )
        resumo_headers = ["Solução núcleo (DNIT)", "# Trechos", "Extensão (km)", "Custo total"]
        resumo_rows = [
            [r["Solução núcleo"], str(int(r["Trechos"])), f"{r['Extensão']:.2f}", _format_money(r["Custo"])]
            for _, r in resumo.iterrows()
        ]
        plan_headers = ["SNV", "Km I", "Km F", "Ext (km)", "IRI", "IGG", "Faixa", "Solução (DNIT)", "Custo"]
        plan_rows = [
            [r["SNV"], f"{r['Km Inicial']:.2f}", f"{r['Km Final']:.2f}",
             f"{r['Extensão']:.2f}", f"{r['IRI']:.2f}", f"{r['IGG']:.0f}",
             r["Faixa"], r["Solução núcleo"], _format_money(r["Custo"])]
            for r in rows
        ]

    sections = [
        ("Resumo por solução", resumo_headers, resumo_rows),
        ("Plano de trabalho — segmento a segmento", plan_headers, plan_rows),
    ]

    if fmt == "pdf":
        pdf_bytes = _iagon_pdf_bytes(title, subtitle, sections)
        return f"plano_trabalho_{safe_road}_{metodologia}{filt_tag}.pdf", pdf_bytes, "application/pdf"

    if fmt == "excel":
        from io import BytesIO
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
            df.to_excel(w, index=False, sheet_name="Trechos")
            resumo.to_excel(w, index=False, sheet_name="Resumo por solução")
        return (
            f"plano_trabalho_{safe_road}_{metodologia}{filt_tag}.xlsx",
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # CSV
    csv = "# " + title + "\n# " + subtitle + "\n\n" + df.to_csv(index=False)
    return (
        f"plano_trabalho_{safe_road}_{metodologia}{filt_tag}.csv",
        csv.encode("utf-8-sig"),
        "text/csv",
    )


def _iagon_simulate_economic_scenario(
    road: str,
    annual_budget_mi: int,
    horizon: int = _ECONOMIC_DEFAULT_HORIZON,
    metodologia: str = "paragon",
) -> dict:
    """Roda o MESMO pipeline da página Cenário Econômico e devolve os números exatos
    que o usuário vê no painel: cobertura anual, km atendidos, orçamento faltante,
    SNVs atendidos vs fora do orçamento, custo por ano.
    """
    metodologia = (metodologia or "paragon").lower()
    if metodologia == "dnit":
        pipe = _compute_dnit_pipeline(road, annual_budget_mi, horizon)
    else:
        pipe = _compute_paragon_pipeline(road, annual_budget_mi, horizon)
    if not pipe.get("available"):
        return {"error": f"Não há dados {metodologia.upper()} para {road}."}

    total_need = float(pipe["total_need"])
    annual_budget_val = annual_budget_mi * 1_000_000
    annual_coverage = float(pipe["annual_coverage"])
    attended_km = float(pipe["attended_km"])
    scope_km = float(pipe["scope_km"])
    faltante = max(total_need - annual_budget_val, 0.0)
    custo_por_ano = pipe.get("custo_por_ano")
    custo_por_snv = pipe.get("custo_por_snv")

    # Lista SNVs por prioridade — atendidos vs fora. Usa a carteira POR SEGMENTO
    # do pipeline (_segment_attendance), em que um SNV pode entrar parcialmente,
    # garantindo sum(atendidos.ext) == attended_km. SNV com porção atendida conta
    # como atendido (a extensão/custo são apenas a parte coberta pelo orçamento).
    snvs_atendidos: list[dict] = [
        {"snv": a["snv"], "ext_km": a["ext_km"], "custo": a["custo"]}
        for a in pipe.get("attended_snv", [])
    ]
    atendidos_set = {a["snv"] for a in snvs_atendidos}
    snvs_fora: list[dict] = []
    if custo_por_snv is not None and not custo_por_snv.empty:
        for _, r in custo_por_snv.iterrows():
            if str(r["SNV"]) in atendidos_set:
                continue  # já listado em atendidos (parcial ou total)
            snvs_fora.append({
                "snv": str(r["SNV"]),
                "ext_km": round(float(r["Extensão"]), 2),
                "custo": float(r["Custo"]),
            })

    return {
        "available": True,
        "road": road,
        "metodologia": metodologia,
        "annual_budget_mi": annual_budget_mi,
        "annual_budget_value": annual_budget_val,
        "horizon": horizon,
        "total_need": total_need,
        "annual_coverage_pct": annual_coverage,
        "attended_km": attended_km,
        "scope_km": scope_km,
        "faltante": faltante,
        "snvs_atendidos": snvs_atendidos,
        "snvs_fora": snvs_fora,
        "custo_por_ano": (
            [(int(r["Ano"]), float(r["Custo"])) for _, r in custo_por_ano.iterrows()]
            if custo_por_ano is not None and not custo_por_ano.empty else []
        ),
        "scenario_label": pipe.get("scenario_label"),
    }


def _iagon_simulate_to_pdf(sim: dict) -> tuple[str, bytes, str] | None:
    """Gera o PDF do cenário simulado com a estrutura completa (KPIs + atendidos + custo/ano)."""
    if sim.get("error") or not sim.get("available"):
        return None
    road = sim["road"]
    bm = sim["annual_budget_mi"]

    headers_kpi = ["Indicador", "Valor"]
    rows_kpi = [
        ["Necessidade total", _format_money(sim["total_need"])],
        ["Orçamento anual", _format_money(sim["annual_budget_value"])],
        ["Cobertura anual", f"{sim['annual_coverage_pct']:.1f}%"],
        ["Km atendidos", f"{sim['attended_km']:.1f} / {sim['scope_km']:.1f} km"],
        ["Orçamento faltante", _format_money(sim['faltante'])],
        ["SNVs no escopo", str(len(sim['snvs_atendidos']) + len(sim['snvs_fora']))],
        ["SNVs atendidos", str(len(sim['snvs_atendidos']))],
    ]

    sections: list[tuple] = [("KPIs do cenário", headers_kpi, rows_kpi)]

    if sim["snvs_atendidos"]:
        sections.append((
            "SNVs ATENDIDOS pelo orçamento",
            ["SNV", "Extensão", "Custo"],
            [[s["snv"], f"{s['ext_km']:.1f} km", _format_money(s["custo"])] for s in sim["snvs_atendidos"]],
        ))
    if sim["snvs_fora"]:
        sections.append((
            "SNVs FORA do orçamento (precisarão de fase futura)",
            ["SNV", "Extensão", "Custo"],
            [[s["snv"], f"{s['ext_km']:.1f} km", _format_money(s["custo"])] for s in sim["snvs_fora"]],
        ))
    if sim["custo_por_ano"]:
        sections.append((
            "Custo por ano (programação cadastrada)",
            ["Ano", "Custo"],
            [[str(a), _format_money(c)] for a, c in sim["custo_por_ano"]],
        ))

    title = f"Cenário econômico — {road} ({sim['metodologia'].upper()}) · R$ {bm} mi/ano"
    subtitle = (
        f"Horizonte {sim['horizon']} anos · "
        f"cobertura {sim['annual_coverage_pct']:.1f}% · "
        f"atende {sim['attended_km']:.1f} de {sim['scope_km']:.1f} km · "
        f"faltam {_format_money(sim['faltante'])}"
    )
    pdf_bytes = _iagon_pdf_bytes(title, subtitle, sections)
    fname = f"cenario_{road.replace('/', '-')}_{sim['metodologia']}_{bm}mi.pdf"
    return fname, pdf_bytes, "application/pdf"


def _iagon_compare_methodologies(road: str, annual_budget_mi: int = 50, horizon: int = _ECONOMIC_DEFAULT_HORIZON) -> dict:
    """Comparativo Paragon × DNIT para uma rodovia — devolve métricas + delta.

    Usa os mesmos pipelines do `_render_comparativo_page` para garantir aderência ao
    que o usuário vê na UI.
    """
    out: dict[str, Any] = {"road": road, "annual_budget_mi": annual_budget_mi, "horizon": horizon}
    # Espelha o comparativo da UI: atendidos/cobertura medidos no horizonte (anual × anos).
    paragon = _compute_paragon_pipeline(road, annual_budget_mi, horizon, attended_budget_mi=annual_budget_mi * horizon)
    dnit = _compute_dnit_pipeline(road, annual_budget_mi, horizon, attended_budget_mi=annual_budget_mi * horizon)
    if not paragon.get("available"):
        out["error"] = f"Sem dados Paragon para {road}."
        return out
    if not dnit.get("available"):
        out["error"] = f"Sem dados DNIT para {road} (esta rodovia não foi processada com a Matriz Revitaliza DNIT/RO)."
        return out

    p_total = float(paragon["total_need"])
    d_total = float(dnit["total_need"])
    out.update({
        "paragon": {
            "scenario": paragon.get("scenario_label"),
            "necessidade": p_total,
            "cobertura_pct": float(paragon["annual_coverage"]),
            "atendido_km": float(paragon["attended_km"]),
            "escopo_km": float(paragon["scope_km"]),
        },
        "dnit": {
            "scenario": dnit.get("scenario_label"),
            "necessidade": d_total,
            "cobertura_pct": float(dnit["annual_coverage"]),
            "atendido_km": float(dnit["attended_km"]),
            "escopo_km": float(dnit["scope_km"]),
        },
        "delta_custo": p_total - d_total,
        "delta_km": float(paragon["attended_km"]) - float(dnit["attended_km"]),
    })
    return out


_IAGON_PARAGON_CLASS_COLORS = {
    "Excelente": "#00c2e8", "Bom": "#00a651", "++ Regular": "#b6d7a8",
    "+ Regular": "#f4f1a6", "- Regular": "#fff200", "Mau": "#f2a51a",
    "Péssimo": "#d71920",
}
_IAGON_DNIT_FAIXA_COLORS = {
    "IRI ≤ 3": "#00a651",
    "3 < IRI ≤ 4": "#fff200",
    "4 < IRI ≤ 5,5": "#f2a51a",
    "IRI > 5,5": "#d71920",
}


def _iagon_render_map(
    road: str,
    metodologia: str = "paragon",
    *,
    classes: list[str] | None = None,
    solucoes: list[str] | None = None,
    faixas_iri: list[str] | None = None,
) -> tuple[bytes, str] | None:
    """Renderiza um PNG do mapa com basemap OSM real (contextily) + linhas filtradas.

    Argumentos:
      road        — código/nome da rodovia (ex.: 'BR-421').
      metodologia — 'paragon' (colore por classe IAP) ou 'dnit' (faixa IRI).
      classes/solucoes/faixas_iri — filtros opcionais.

    Retorna (bytes_png, mime) ou None se não há nada para plotar.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.patches import Patch
    import math
    import io

    metodologia = (metodologia or "paragon").lower()
    classes_filter = {c.strip() for c in (classes or []) if c and c.strip()}
    solucoes_filter = _iagon_norm_solucoes(solucoes)
    faixas_filter = {f.strip() for f in (faixas_iri or []) if f and f.strip()}

    if metodologia == "dnit":
        data = get_dnit_solutions_data(road)
        if not data.get("available") or data.get("segments") is None or data["segments"].empty:
            return None
        segs = data["segments"]
        table = data.get("table")
    else:
        data = get_solutions_data(road)
        segs = data.get("segments")
        if segs is None or segs.empty:
            return None
        table = data.get("table")

    sol_by_seg: dict[int, str] = {}
    if metodologia == "paragon" and table is not None and not table.empty and "_segment_id" in table.columns:
        sol_by_seg = dict(zip(table["_segment_id"].astype(int), table["Solução recomendada"].astype(str)))

    rendered: list[tuple[list[tuple[float, float]], str, str]] = []
    all_pts: list[tuple[float, float]] = []
    for _, seg in segs.iterrows():
        paths = seg.get("paths") or []
        if metodologia == "dnit":
            faixa = str(seg.get("matriz_categoria", "")).strip()
            color = str(seg.get("matriz_color", "#fff200"))
            label = faixa
            if faixas_filter and faixa not in faixas_filter:
                continue
        else:
            klass = str(seg.get("classe_iap", "")).strip()
            color = _IAGON_PARAGON_CLASS_COLORS.get(klass, "#9aa8b3")
            label = klass
            if classes_filter and klass not in classes_filter:
                continue
            if solucoes_filter:
                sol = sol_by_seg.get(int(seg.get("segment_id", -1)), "").lower()
                if not any(needle in sol for needle in solucoes_filter):
                    continue
        for path in paths:
            cleaned = [(float(p[0]), float(p[1])) for p in path if len(p) >= 2]
            if len(cleaned) < 2:
                continue
            rendered.append((cleaned, color, label))
            all_pts.extend(cleaned)

    if not rendered:
        return None

    # bbox em lat/lon com padding 12%.
    lats = [p[0] for p in all_pts]
    lons = [p[1] for p in all_pts]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    rng_lat = max_lat - min_lat or 1e-3
    rng_lon = max_lon - min_lon or 1e-3
    pad = 0.12
    min_lat -= rng_lat * pad
    max_lat += rng_lat * pad
    min_lon -= rng_lon * pad
    max_lon += rng_lon * pad

    # Conversão lat/lon → Web Mercator (EPSG:3857) para alinhar com tiles OSM.
    def to_merc(lat: float, lon: float) -> tuple[float, float]:
        R = 6378137.0
        x = math.radians(lon) * R
        y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
        return x, y

    # Figura grande, alta densidade.
    cos_lat = math.cos(math.radians((min_lat + max_lat) / 2))
    span_lat = max_lat - min_lat
    span_lon = (max_lon - min_lon) * cos_lat
    fig_h = 8.5
    fig_w = max(7.0, min(15.0, fig_h * (span_lon / span_lat)))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=180)
    fig.patch.set_facecolor("#ffffff")

    # Define limites em Mercator e busca o basemap OSM.
    x0, y0 = to_merc(min_lat, min_lon)
    x1, y1 = to_merc(max_lat, max_lon)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")

    try:
        import contextily as cx
        cx.add_basemap(
            ax, source=cx.providers.OpenStreetMap.Mapnik, crs="EPSG:3857",
            attribution=False, zoom="auto",
        )
        has_basemap = True
    except Exception:
        # Sem internet ou falha: fundo neutro e segue o plot.
        ax.set_facecolor("#eef2f6")
        ax.grid(True, linestyle=":", color="#cbd5dd", alpha=0.6)
        has_basemap = False

    # Linhas em Mercator. Cor sólida grossa — sem path_effects pra não escurecer
    # quando há muitos segmentos sobrepostos.
    for path, color, _ in rendered:
        xs, ys = zip(*(to_merc(lat, lon) for lat, lon in path))
        ax.plot(
            xs, ys,
            color=color, linewidth=4.5, solid_capstyle="round", solid_joinstyle="round",
            alpha=0.95, zorder=3,
        )

    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor("#475569")
        sp.set_linewidth(0.6)

    filtros_parts = []
    if classes_filter:
        filtros_parts.append("classes: " + ", ".join(sorted(classes_filter)))
    if solucoes_filter:
        filtros_parts.append("soluções: " + ", ".join(sorted(solucoes_filter)))
    if faixas_filter:
        filtros_parts.append("faixas IRI: " + ", ".join(sorted(faixas_filter)))
    filtros_txt = (" · " + " · ".join(filtros_parts)) if filtros_parts else ""
    n_seg = len(rendered)
    ax.set_title(
        f"Mapa — {road} · {metodologia.upper()}{filtros_txt}\n{n_seg} polylines exibidas",
        fontsize=13, fontweight="bold", color="#0f2230", pad=14, loc="left",
    )

    # Legenda só com categorias presentes (matplotlib desenha por cima do basemap).
    presentes = [lbl for _, _, lbl in rendered]
    if metodologia == "dnit":
        order = ["IRI ≤ 3", "3 < IRI ≤ 4", "4 < IRI ≤ 5,5", "IRI > 5,5"]
        items = [(lbl, _IAGON_DNIT_FAIXA_COLORS[lbl]) for lbl in order if lbl in set(presentes)]
        leg_title = "Faixa IRI (Matriz DNIT)"
    else:
        order = list(_IAGON_PARAGON_CLASS_COLORS.keys())
        items = [(lbl, _IAGON_PARAGON_CLASS_COLORS[lbl]) for lbl in order if lbl in set(presentes)]
        leg_title = "Conceito IAP (Paragon)"
    if items:
        handles = [Patch(facecolor=c, edgecolor="#06222b", label=lbl) for lbl, c in items]
        leg = ax.legend(
            handles=handles, title=leg_title, loc="upper right",
            frameon=True, fontsize=10, title_fontsize=11, framealpha=0.95,
        )
        leg.get_frame().set_facecolor("#ffffff")
        leg.get_frame().set_edgecolor("#06222b")

    # Atribuição OSM (obrigatória).
    footer = "© OpenStreetMap contributors · Painel Paragon/DNIT · IAGON" if has_basemap else "Painel Paragon/DNIT · IAGON"
    fig.text(0.01, 0.005, footer, fontsize=8, color="#475569")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)
    return buf.getvalue(), "image/png"


def _iagon_render_map_svg(road: str, metodologia: str = "paragon") -> bytes | None:
    """Wrapper de compatibilidade — usa o renderer matplotlib (PNG) sem filtros."""
    out = _iagon_render_map(road, metodologia)
    if out is None:
        return None
    return out[0]


def _iagon_filter_segments_for_map(
    road: str,
    metodologia: str,
    classes: list[str] | None,
    solucoes: list[str] | None,
    faixas_iri: list[str] | None,
    snvs: list[str] | None = None,
):
    """Pega os mesmos segmentos que a UI usa, aplica os filtros pedidos, devolve
    (segments_filtered_df, extent_km, data_completo, num_segmentos).

    Importante: NÃO recorta colunas — preserva `paths`, `classe_iap`, `intervencao_iap`,
    `matriz_categoria` etc., porque os componentes de mapa (`render_overview_map` /
    `render_dnit_map`) leem essas chaves direto do dict.
    """
    metodologia = (metodologia or "paragon").lower()
    classes_set = {c.strip() for c in (classes or []) if c and c.strip()}
    faixas_set = {f.strip() for f in (faixas_iri or []) if f and f.strip()}
    solucoes_set = _iagon_norm_solucoes(solucoes)
    snvs_set = {s.strip().upper() for s in (snvs or []) if s and s.strip()}

    if metodologia == "dnit":
        data = get_dnit_solutions_data(road)
        if not data.get("available") or data.get("segments") is None or data["segments"].empty:
            return None, 0.0, data, 0
        segs = data["segments"]
        if snvs_set:
            segs = segs[segs["sre"].astype(str).str.upper().isin(snvs_set)]
        if faixas_set:
            segs = segs[segs["matriz_categoria"].astype(str).isin(faixas_set)]
        extent_km = float((segs["km_final"] - segs["km_inicial"]).clip(lower=0).sum()) if not segs.empty else 0.0
        return segs, extent_km, data, int(len(segs))

    # Paragon
    data = get_solutions_data(road)
    segs = data.get("segments")
    if segs is None or segs.empty:
        return None, 0.0, data, 0

    if snvs_set:
        segs = segs[segs["sre"].astype(str).str.upper().isin(snvs_set)]

    if classes_set:
        segs = segs[segs["classe_iap"].astype(str).isin(classes_set)]

    if solucoes_set:
        table = data.get("table")
        if table is not None and not table.empty and "_segment_id" in table.columns:
            sol_by_seg = dict(zip(
                table["_segment_id"].astype(int),
                table["Solução recomendada"].astype(str).str.lower(),
            ))
            def match_sol(seg_id):
                sol = sol_by_seg.get(int(seg_id), "")
                return any(needle in sol for needle in solucoes_set)
            segs = segs[segs["segment_id"].astype(int).apply(match_sol)]

    extent_km = float((segs["km_final"] - segs["km_inicial"]).clip(lower=0).sum()) if not segs.empty else 0.0
    return segs, extent_km, data, int(len(segs))


def _iagon_render_interactive_map(spec: dict) -> None:
    """Renderiza o mapa interativo (Leaflet + Satélite) DENTRO do chat, usando os
    mesmos componentes da tela do painel (`render_overview_map` para Paragon /
    `render_dnit_map` para DNIT). Aceita filtros já aplicados no `spec`.
    """
    road = spec.get("road")
    meth = (spec.get("metodologia") or "paragon").lower()
    classes = spec.get("classes")
    solucoes = spec.get("solucoes")
    faixas = spec.get("faixas_iri")
    snvs = spec.get("snvs")
    segs, extent_km, data, n_seg = _iagon_filter_segments_for_map(
        road, meth, classes, solucoes, faixas, snvs=snvs,
    )
    if segs is None or segs.empty:
        st.info(f"Sem segmentos para o mapa de {road} ({meth}) com esses filtros.")
        return

    filtros = []
    if snvs: filtros.append("SNVs=" + ",".join(snvs))
    if classes: filtros.append("classes=" + ",".join(classes))
    if solucoes: filtros.append("soluções=" + ",".join(solucoes))
    if faixas: filtros.append("faixas IRI=" + ",".join(faixas))
    filt_txt = (" · " + " · ".join(filtros)) if filtros else " (sem filtros)"
    st.caption(f"**{road}** · {meth.upper()}{filt_txt} · **{n_seg}** segmentos · **{extent_km:.1f} km**")

    if meth == "dnit":
        render_dnit_map(
            segs,
            zona_colors=data.get("zona_colors"),
            zona_order=data.get("zona_order"),
        )
    else:
        # Paragon — color_by="iap" replica a tela Diagnóstico (Satélite + Conceito IAP).
        render_overview_map(segs, extent_km, color_by="iap")


def _iagon_export(report_data: dict, escopo: str, formato: str, titulo: str | None = None):
    """Gera (filename, bytes, mime) reais a partir dos dados do banco. None se escopo inválido."""
    label, info = _iagon_resolve_scope(report_data, escopo)
    if label is None:
        return None
    fmt = (formato or "pdf").strip().lower()

    sheets: dict[str, pd.DataFrame] = {}
    sections: list[tuple] = []

    if label == "rede":
        df = report_data["network_df"].sort_values("IAP")
        headers = ["Rodovia", "IAP", "IRI", "IGG", "% IAP<2,5", "Trechos prio.", "Necessidade"]
        rows = [
            [r["Rodovia"], f"{r['IAP']:.2f}", f"{r['IRI']:.2f}", f"{r['IGG']:.0f}",
             f"{r['iap_bad_pct']:.0f}%", str(int(r["prio"])), _format_money(float(r["custo"]))]
            for _, r in df.iterrows()
        ]
        sections = [(None, headers, rows)]
        sheets["Malha"] = pd.DataFrame(
            [[r["Rodovia"], round(float(r["IAP"]), 2), round(float(r["IRI"]), 2), round(float(r["IGG"])),
              round(float(r["iap_bad_pct"])), int(r["prio"]), round(float(r["custo"]), 2)] for _, r in df.iterrows()],
            columns=["Rodovia", "IAP", "IRI", "IGG", "% IAP<2,5", "Trechos prioritários", "Necessidade (R$)"],
        )
        primary = sheets["Malha"]
        title = titulo or "Relatório executivo da malha — Paragon/DNIT"
        subtitle = f"Necessidade no horizonte de {_ECONOMIC_DEFAULT_HORIZON} anos · valores do orçamento cadastrado"
        base = "iagon_relatorio_malha"
    else:
        cby = info.get("cost_by_year", [])
        cby_rows = [[str(ano), _format_money(c)] for ano, c in cby] or [["—", _format_money(info["metrics"]["custo"])]]
        sections.append(("Necessidade por ano", ["Ano", "Custo"], cby_rows))
        sheets["Custo por ano"] = pd.DataFrame(cby or [(0, info["metrics"]["custo"])], columns=["Ano", "Custo (R$)"])

        trechos = info.get("trechos", [])
        if trechos:
            tr_headers = ["#", "SNV", "Prioridade", "Priorização", "Extensão (km)", "IAP", "Solução"]
            tr_rows = [
                [str(t["rank"]), t["snv"], t["classe"], str(int(round(t["priorizacao"]))), f"{t['ext']:.0f}", f"{t['iap']:.2f}", t["solucao"]]
                for t in trechos
            ]
            sections.append(("Trechos prioritários (SNV)", tr_headers, tr_rows))
            sheets["Trechos"] = pd.DataFrame(
                [[t["rank"], t["snv"], t["classe"], t["priorizacao"], t["ext"], t["iap"], t["solucao"]] for t in trechos],
                columns=["Ranking", "SNV", "Prioridade", "Priorização", "Extensão (km)", "IAP", "Solução"],
            )
        primary = sheets.get("Trechos", sheets["Custo por ano"])
        title = titulo or f"Relatório {label}"
        subtitle = f"Necessidade no horizonte de {_ECONOMIC_DEFAULT_HORIZON} anos · dados do banco"
        base = f"iagon_relatorio_{info['code']}"

    if fmt == "csv":
        return f"{base}.csv", primary.to_csv(index=False).encode("utf-8-sig"), "text/csv"
    if fmt in ("excel", "xlsx"):
        out = BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            wb = writer.book
            hdr = wb.add_format({"bold": True, "bg_color": "#0b1d28", "font_color": "#ffffff", "border": 1})
            for sheet_name, sdf in sheets.items():
                sdf.to_excel(writer, index=False, sheet_name=sheet_name[:31])
                ws = writer.sheets[sheet_name[:31]]
                for ci, col in enumerate(sdf.columns):
                    ws.write(0, ci, col, hdr)
                    ws.set_column(ci, ci, max(12, min(46, int(sdf[col].astype(str).str.len().max() or 12) + 2)))
        return f"{base}.xlsx", out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return f"{base}.pdf", _iagon_pdf_bytes(title, subtitle, sections), "application/pdf"


def _iagon_dynamic_suggestions() -> list[str]:
    """Sugestões geradas a partir das rodovias e cenários reais do banco.
    Evita exemplos genéricos (ex.: BR-364) que não existem na malha atual."""
    roads = get_available_roads()
    dnit_roads = set(get_dnit_available_roads())

    if not roads:
        return ["Quais rodovias estão disponíveis no sistema?"]

    primeira = roads[0]
    dnit_road = next(iter(dnit_roads), None)
    par_a, par_b = (roads[0], roads[1]) if len(roads) >= 2 else (roads[0], roads[0])

    sugs = [
        f"Qual a situação atual da {primeira}?",
        "Quais as rodovias prioritárias da malha?",
        f"Compare {par_a} e {par_b} (condição e custo).",
    ]
    if dnit_road:
        sugs.append(f"Quanto custa o plano DNIT da {dnit_road}?")
    else:
        sugs.append("Gere um relatório PDF da malha.")
    return sugs


# Assistente IAGON — página dedicada de chat (fora do escopo desta documentação).
def _render_iagon_page() -> None:
    if not iagon.is_configured():
        st.info("IAGON indisponível: configure a chave **API_OPENAI_KEY** no arquivo .env.")
        return

    context_text, report_data = _build_iagon_context()
    st.session_state.setdefault("iagon_messages", [])

    st.markdown(
        '<section class="iagon-hero">'
        '<div class="iagon-avatar">✦</div>'
        '<div><h3>IAGON · assistente de pavimentos</h3>'
        '<p>Pergunte sobre condição, custos, prioridades e soluções de toda a malha. '
        'Eu interpreto os dados, comparo rodovias e gero relatórios (PDF, Excel, CSV).</p></div>'
        '</section>',
        unsafe_allow_html=True,
    )

    if not st.session_state.iagon_messages:
        st.markdown('<div class="iagon-suggest-label">Comece por aqui</div>', unsafe_allow_html=True)
        cols = st.columns(2, gap="small")
        for i, sug in enumerate(_iagon_dynamic_suggestions()):
            if cols[i % 2].button(sug, key=f"iagon_sug_{i}", use_container_width=True):
                st.session_state.iagon_pending = sug
                st.rerun()

    for idx, msg in enumerate(st.session_state.iagon_messages):
        avatar = "🤖" if msg["role"] == "assistant" else "🧑"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            for ai, art in enumerate(msg.get("artifacts", [])):
                if art[2] == "application/x-iagon-interactive-map":
                    # Mapa Leaflet interativo (mesmo componente do painel).
                    try:
                        _iagon_render_interactive_map(art[1])
                    except Exception as exc:
                        st.warning(f"Não consegui renderizar o mapa interativo: {exc}")
                    continue
                if art[2] == "image/png":
                    st.image(art[1])
                elif art[2] == "image/svg+xml":
                    try:
                        st.markdown(art[1].decode("utf-8"), unsafe_allow_html=True)
                    except Exception:
                        pass
                st.download_button(
                    f"⬇️  {art[0]}", data=art[1], file_name=art[0], mime=art[2],
                    key=f"iagon_dl_{idx}_{ai}",
                )

    prompt = st.chat_input("Pergunte ao IAGON…") or st.session_state.pop("iagon_pending", None)
    if not prompt:
        return

    st.session_state.iagon_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        artifacts: list[tuple] = []

        def on_tool(name: str, args: dict) -> str:
            if name == "lembrar":
                iagon.remember(args.get("fato", ""), args.get("categoria", "geral"))
                return "Memória de longo prazo atualizada."
            if name == "listar_trechos_priorizados":
                road = (args.get("rodovia") or "").strip()
                if not road:
                    return "Informe a rodovia (ex.: 'BR-421')."
                try:
                    return _iagon_trechos_priorizados_text(
                        road, int(args.get("cenario") or 1), int(args.get("top") or 25), int(args.get("horizonte") or 1)
                    )
                except Exception as e:
                    return f"Não consegui listar os trechos: {e}"
            if name == "situacao_rodovia":
                road = (args.get("rodovia") or "").strip()
                if not road:
                    return "Informe a rodovia (ex.: 'BR-421')."
                try:
                    return _iagon_situacao_text(road, int(args.get("cenario") or 1))
                except Exception as e:
                    return f"Não consegui montar a situação: {e}"
            if name == "exportar_relatorio":
                out = _iagon_export(report_data, args.get("escopo", "rede"), args.get("formato", "pdf"), args.get("titulo"))
                if not out:
                    disponiveis = ", ".join(report_data.get("roads", {}).keys()) or "BR-421/BR-429/BR-435"
                    return f"Não encontrei esse escopo. Use 'rede' ou uma rodovia válida (ex.: {disponiveis})."
                artifacts.append(out)
                return f"Arquivo '{out[0]}' gerado com sucesso e disponível para download."
            if name == "gerar_mapa":
                road = (args.get("rodovia") or "").strip()
                meth = (args.get("metodologia") or "paragon").lower()
                classes = args.get("classes") or None
                solucoes = args.get("solucoes") or None
                faixas = args.get("faixas_iri") or None
                snvs = args.get("snvs") or None
                label, info = _iagon_resolve_scope(report_data, road)
                if not info or label is None or label == "rede":
                    return "Especifique a rodovia para o mapa (BR-421, BR-429 ou BR-435)."
                segs, ext_km, _, n_seg = _iagon_filter_segments_for_map(
                    label, meth, classes, solucoes, faixas, snvs=snvs,
                )
                if segs is None or segs.empty:
                    filt_desc = []
                    if snvs: filt_desc.append(f"SNVs={snvs}")
                    if classes: filt_desc.append(f"classes={classes}")
                    if solucoes: filt_desc.append(f"soluções={solucoes}")
                    if faixas: filt_desc.append(f"faixas={faixas}")
                    filt_txt = (" com " + ", ".join(filt_desc)) if filt_desc else ""
                    return f"Não há segmentos para o mapa de {label} ({meth}){filt_txt}."
                fname = f"mapa_{label.replace('/', '-')}_{meth}"
                spec = {
                    "road": label, "metodologia": meth,
                    "classes": classes, "solucoes": solucoes,
                    "faixas_iri": faixas, "snvs": snvs,
                }
                artifacts.append((fname, spec, "application/x-iagon-interactive-map"))
                filtros_resumo = []
                if snvs: filtros_resumo.append("SNVs=" + ",".join(snvs))
                if classes: filtros_resumo.append("classes=" + ",".join(classes))
                if solucoes: filtros_resumo.append("soluções=" + ",".join(solucoes))
                if faixas: filtros_resumo.append("faixas IRI=" + ",".join(faixas))
                filt_part = (" · filtros: " + " · ".join(filtros_resumo)) if filtros_resumo else " (sem filtros)"
                return (
                    f"Mapa interativo de {label} ({meth}){filt_part} renderizado — "
                    f"{n_seg} segmentos · {ext_km:.1f} km. Você pode dar zoom/pan e trocar "
                    f"a camada base (Satélite/Padrão/Topográfico) no canto superior direito."
                )
            if name == "gerar_grafico":
                tipo = (args.get("tipo") or "").lower()
                rodovia = (args.get("rodovia") or "").strip() or None
                rodovias = args.get("rodovias") or None
                meth = (args.get("metodologia") or "paragon").lower()
                sre = (args.get("sre") or "").strip() or None
                # Resolve nome canônico da rodovia se vier abreviado.
                if rodovia:
                    label, _ = _iagon_resolve_scope(report_data, rodovia)
                    if label and label != "rede":
                        rodovia = label
                if rodovias:
                    resolved = []
                    for r in rodovias:
                        lbl, _ = _iagon_resolve_scope(report_data, r)
                        if lbl and lbl != "rede":
                            resolved.append(lbl)
                    rodovias = resolved or None
                out = _iagon_render_chart(
                    tipo, rodovia=rodovia, rodovias=rodovias,
                    metodologia=meth, sre=sre,
                )
                if out is None:
                    return f"Não consegui gerar o gráfico '{tipo}' — verifique os dados disponíveis."
                artifacts.append(out)
                return f"Gráfico '{tipo}' gerado — exibindo acima."

            if name == "gerar_plano_trabalho":
                road = (args.get("rodovia") or "").strip()
                meth = (args.get("metodologia") or "paragon").lower()
                classes = args.get("classes") or None
                solucoes = args.get("solucoes") or None
                faixas = args.get("faixas_iri") or None
                snvs = args.get("snvs") or None
                fmt = (args.get("formato") or "pdf").lower()
                label, info = _iagon_resolve_scope(report_data, road)
                if not info or label is None or label == "rede":
                    return "Especifique a rodovia para o plano de trabalho."
                out = _iagon_generate_work_plan(
                    label, metodologia=meth, classes=classes, solucoes=solucoes,
                    faixas_iri=faixas, snvs=snvs, formato=fmt,
                )
                if out is None:
                    return (
                        f"Não há trechos para o plano de trabalho de {label} ({meth}) "
                        f"com os filtros pedidos."
                    )
                artifacts.append(out)
                filt_parts = []
                if snvs: filt_parts.append("SNVs=" + ",".join(snvs))
                if classes: filt_parts.append("classes=" + ",".join(classes))
                if solucoes: filt_parts.append("soluções=" + ",".join(solucoes))
                if faixas: filt_parts.append("faixas IRI=" + ",".join(faixas))
                filt_txt = (" · filtros: " + " · ".join(filt_parts)) if filt_parts else " (todos os trechos)"
                return (
                    f"Plano de trabalho de {label} ({meth}){filt_txt} gerado em {fmt.upper()} — "
                    f"botão de download acima. O arquivo lista cada SNV com a intervenção recomendada, "
                    f"extensão e custo."
                )

            if name == "simular_cenario_economico":
                road = (args.get("rodovia") or "").strip()
                budget = int(args.get("orcamento_anual_mi") or 0)
                horizon = int(args.get("horizonte_anos") or _ECONOMIC_DEFAULT_HORIZON)
                meth = (args.get("metodologia") or "paragon").lower()
                formato = (args.get("formato") or "").lower() or None
                label, info = _iagon_resolve_scope(report_data, road)
                if not info or label is None or label == "rede":
                    return "Especifique a rodovia (ex.: 'BR-421')."
                if budget <= 0:
                    return "Informe um orçamento anual em R$ milhões (orcamento_anual_mi)."
                sim = _iagon_simulate_economic_scenario(label, budget, horizon, meth)
                if sim.get("error"):
                    return sim["error"]
                # Opcionalmente gera o arquivo no formato pedido.
                if formato == "pdf":
                    out = _iagon_simulate_to_pdf(sim)
                    if out:
                        artifacts.append(out)
                elif formato in ("excel", "csv"):
                    # Excel/CSV usam a infra do exportar_relatorio adaptada ao cenário.
                    sheets = {
                        "KPIs": pd.DataFrame([
                            ["Necessidade total", _format_money(sim["total_need"])],
                            ["Orçamento anual", _format_money(sim["annual_budget_value"])],
                            ["Cobertura anual", f"{sim['annual_coverage_pct']:.1f}%"],
                            ["Km atendidos / escopo", f"{sim['attended_km']:.1f} / {sim['scope_km']:.1f} km"],
                            ["Orçamento faltante", _format_money(sim['faltante'])],
                        ], columns=["Indicador", "Valor"]),
                        "SNVs atendidos": pd.DataFrame(sim["snvs_atendidos"]),
                        "SNVs fora": pd.DataFrame(sim["snvs_fora"]),
                        "Custo por ano": pd.DataFrame(sim["custo_por_ano"], columns=["Ano", "Custo (R$)"]),
                    }
                    if formato == "excel":
                        from io import BytesIO
                        buf = BytesIO()
                        with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
                            for sname, df in sheets.items():
                                if not df.empty:
                                    df.to_excel(w, index=False, sheet_name=sname[:31])
                        artifacts.append((
                            f"cenario_{label.replace('/', '-')}_{meth}_{budget}mi.xlsx",
                            buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ))
                    else:  # csv — junta tudo em texto único.
                        csv_parts = []
                        for sname, df in sheets.items():
                            if df.empty:
                                continue
                            csv_parts.append(f"# {sname}\n" + df.to_csv(index=False))
                        artifacts.append((
                            f"cenario_{label.replace('/', '-')}_{meth}_{budget}mi.csv",
                            "\n".join(csv_parts).encode("utf-8-sig"),
                            "text/csv",
                        ))
                # Retorno textual rico para o IAGON contextualizar a resposta.
                atendidos_txt = (
                    ", ".join(f"{s['snv']} ({s['ext_km']:.1f} km)" for s in sim["snvs_atendidos"][:6])
                    or "nenhum"
                )
                fora_txt = (
                    ", ".join(f"{s['snv']} ({s['ext_km']:.1f} km)" for s in sim["snvs_fora"][:6])
                    or "nenhum"
                )
                return (
                    f"CENÁRIO {label} {meth.upper()} | R$ {budget} mi/ano · {horizon} anos\n"
                    f"Necessidade total: R$ {sim['total_need']/1e6:.2f} mi\n"
                    f"Cobertura anual: {sim['annual_coverage_pct']:.1f}% (orçamento cobre essa fatia da necessidade)\n"
                    f"Km atendidos pelo orçamento: {sim['attended_km']:.1f} / {sim['scope_km']:.1f} km\n"
                    f"Orçamento faltante para 100%: R$ {sim['faltante']/1e6:.2f} mi\n"
                    f"SNVs ATENDIDOS ({len(sim['snvs_atendidos'])}): {atendidos_txt}\n"
                    f"SNVs FORA ({len(sim['snvs_fora'])}): {fora_txt}"
                )

            if name == "comparar_metodologias":
                road = (args.get("rodovia") or "").strip()
                budget = int(args.get("orcamento_anual_mi") or 50)
                horizon = int(args.get("horizonte_anos") or 10)
                label, info = _iagon_resolve_scope(report_data, road)
                if not info or label is None or label == "rede":
                    return "Especifique a rodovia para o comparativo (BR-421, BR-429 ou BR-435)."
                cmp_data = _iagon_compare_methodologies(label, budget, horizon)
                # Devolve como texto compacto pro modelo formatar.
                if "error" in cmp_data:
                    return cmp_data["error"]
                p = cmp_data["paragon"]
                d = cmp_data["dnit"]
                return (
                    f"COMPARATIVO {label} | orçamento R$ {budget} mi/ano · horizonte {horizon} anos\n"
                    f"PARAGON: necessidade R$ {p['necessidade']/1e6:.2f} mi · cobertura {p['cobertura_pct']:.1f}% "
                    f"· km atendidos {p['atendido_km']:.1f}/{p['escopo_km']:.1f} (cenário '{p['scenario']}')\n"
                    f"DNIT: necessidade R$ {d['necessidade']/1e6:.2f} mi · cobertura {d['cobertura_pct']:.1f}% "
                    f"· km atendidos {d['atendido_km']:.1f}/{d['escopo_km']:.1f} (cenário '{d['scenario']}')\n"
                    f"DELTA (P-D): R$ {cmp_data['delta_custo']/1e6:.2f} mi · {cmp_data['delta_km']:.1f} km"
                )
            return "ok"

        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.iagon_messages]
        # Gate determinístico: rodovia com >1 cenário sem cenário escolhido → pergunta antes.
        gate = _iagon_scenario_gate(prompt, history)
        if gate:
            full = gate
            st.markdown(full)
        else:
            try:
                full = st.write_stream(iagon.run_chat(context_text, history, on_tool))
            except Exception as exc:  # erro de API/rede — mostra sem derrubar a tela
                full = f"⚠️ Não consegui responder agora ({type(exc).__name__}). Tente novamente."
                st.markdown(full)

        for ai, art in enumerate(artifacts):
            if art[2] == "application/x-iagon-interactive-map":
                try:
                    _iagon_render_interactive_map(art[1])
                except Exception as exc:
                    st.warning(f"Não consegui renderizar o mapa interativo: {exc}")
                continue
            if art[2] == "image/png":
                st.image(art[1])
            elif art[2] == "image/svg+xml":
                try:
                    st.markdown(art[1].decode("utf-8"), unsafe_allow_html=True)
                except Exception:
                    pass
            st.download_button(
                f"⬇️  {art[0]}", data=art[1], file_name=art[0], mime=art[2],
                key=f"iagon_dl_live_{len(st.session_state.iagon_messages)}_{ai}",
            )

    st.session_state.iagon_messages.append({"role": "assistant", "content": full, "artifacts": artifacts})
    try:  # memória RAG: captura automática da troca (conversa crua + fatos destilados)
        iagon.capture_exchange(prompt, full)
    except Exception:
        pass
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# Fim do bloco IAGON. Helpers de geometria/sentido do mapa, comparativo de
# cenários e o ROTEADOR main() (abaixo).
# ═══════════════════════════════════════════════════════════════════════════

def _offset_path(coords, meters):
    """Desloca uma polilinha perpendicularmente por `meters` (sinal = lado).

    Separa visualmente os sentidos no mesmo pavimento (pista simples): CRESCENTE
    para um lado, DECRESCENTE para o outro.
    """
    if len(coords) < 2 or not meters:
        return coords
    out = []
    n = len(coords)
    for i in range(n):
        lat, lon = coords[i][0], coords[i][1]
        a = coords[max(0, i - 1)]
        b = coords[min(n - 1, i + 1)]
        dlat = b[0] - a[0]
        dlon = (b[1] - a[1]) * math.cos(math.radians(lat))
        L = math.hypot(dlat, dlon) or 1e-9
        plat, plon = -dlon / L, dlat / L  # perpendicular unitária (rotação +90°)
        off_lat = (meters / 111000.0) * plat
        off_lon = (meters / 111000.0) * plon / (math.cos(math.radians(lat)) or 1e-9)
        out.append([lat + off_lat, lon + off_lon])
    return out


def _sentido_label(nome: str) -> str:
    """Extrai o sentido PURO (CRESCENTE/DECRESCENTE) do nome do cenário, para LÓGICA.
    Ordem importa: 'decrescente' antes de 'crescente' (a 2ª é substring da 1ª)."""
    low = str(nome).lower()
    if "decrescente" in low:
        return "DECRESCENTE"
    if "crescente" in low:
        return "CRESCENTE"
    return str(nome)


def _sentido_faixa(nome: str) -> str:
    """Rótulo de EXIBIÇÃO do sentido como pista simples: DECRESCENTE ⇒ 'Pista simples - LE',
    CRESCENTE ⇒ 'Pista simples - LD'. Para nomes que não são sentido, devolve o próprio.
    NÃO use em lógica/comparação — para isso use _sentido_label (mantém CRESCENTE/DECRESCENTE puros)."""
    s = _sentido_label(nome)
    if s == "CRESCENTE":
        return "Pista simples - LD"
    if s == "DECRESCENTE":
        return "Pista simples - LE"
    return s


def _scenarios_map_segments(road: str, keys, by_key: dict | None = None):
    """Segmentos dos CENÁRIOS SELECIONADOS no filtro do topo, em camadas deslocadas
    (offset por pixel, zoom-aware no mapa). Reflete a seleção: 1 cenário → None (o mapa
    usa a camada única); 2+ → concat com `offset_side` (lado simétrico) e `sentido` (rótulo)."""
    keys = [k for k in (keys or []) if k]
    if len(keys) < 2:
        return None
    if by_key is None:
        by_key = {s["key"]: s for s in get_available_scenarios(road, "Paragon")}
    n = len(keys)
    parts = []
    for i, k in enumerate(keys):
        seg = get_overview_data(road, scenario_key=k).get("segments")
        if seg is None or seg.empty:
            continue
        seg = seg.copy()
        seg["offset_side"] = i - (n - 1) / 2.0   # lado simétrico; offset em px no mapa
        seg["sentido"] = _short_scenario_label(by_key.get(k))
        parts.append(seg)
    if len(parts) < 2:
        return None
    return pd.concat(parts, ignore_index=True)


# Linhas do comparativo de cenários (rótulo, campo em metrics, formatação, marca "pior").
_CMP_METRICS = [
    ("IAP médio", "iap_average", lambda v: f"{v:.2f}", None),
    ("% trechos críticos", "critical_percent", lambda v: f"{v:.1f}%", "max"),
    ("Km críticos", "critical_km", lambda v: f"{v:.1f} km", "max"),
    ("Extensão total", "extension_km", lambda v: f"{v:.1f} km", None),
    ("Custo (necessidade)", "_custo", lambda v: _format_money(v), "max"),
]


def _render_scenario_comparison(road: str, selected_keys: list[str] | None = None) -> None:
    """Comparativo de métricas entre os cenários SELECIONADOS no filtro único do topo
    (ex.: CRESCENTE × DECRESCENTE, ou SH × Fixa). Aparece quando há 2+ cenários
    marcados — não há um 2º campo de cenário; o sentido/segmentação vira o eixo.
    """
    scenarios = get_available_scenarios(road, "Paragon")
    if len(scenarios) < 2:
        return
    by_key = {s["key"]: s for s in scenarios}
    selected = [k for k in (selected_keys or []) if k in by_key]
    if len(selected) < 2:
        return  # com 0/1 cenário não há o que comparar (sem campo extra)

    with st.expander("⚖️  Comparar cenários selecionados", expanded=True):
        rows = []
        with st.spinner("Calculando comparativo…"):
            for k in selected:
                metrics = dict(get_overview_data(road, scenario_key=k)["metrics"])
                sol = get_solutions_data(road, scenario_key=k)
                metrics["_custo"] = _necessidade_total(
                    sol.get("table"), sol.get("budget_items"), _ECONOMIC_DEFAULT_HORIZON
                )
                metrics["_label"] = _short_scenario_label(by_key[k])
                rows.append(metrics)

        ths = "".join(f"<th>{html.escape(r['_label'])}</th>" for r in rows)
        body = []
        for nome, campo, fmt, marca in _CMP_METRICS:
            vals = [float(r.get(campo) or 0) for r in rows]
            pior = max(vals) if marca == "max" else None
            tds = ""
            for v in vals:
                worse = pior is not None and v == pior and len(set(vals)) > 1
                tds += f"<td class='cmp-worse'>{fmt(v)}</td>" if worse else f"<td>{fmt(v)}</td>"
            body.append(f"<tr><th class='cmp-metric'>{nome}</th>{tds}</tr>")

        st.markdown(
            "<style>"
            ".cmp-table{width:100%;border-collapse:collapse;margin-top:6px;font-size:14px}"
            ".cmp-table th,.cmp-table td{padding:10px 14px;text-align:right;"
            "border-bottom:1px solid rgba(148,163,184,.16)}"
            ".cmp-table thead th{color:#9aa8b3;font-size:11px;letter-spacing:.06em;text-transform:uppercase}"
            ".cmp-table th.cmp-metric{text-align:left;color:#cbd5df;font-weight:600}"
            ".cmp-table td.cmp-worse{color:#ff6b6b;font-weight:700}"
            "</style>"
            f"<table class='cmp-table'><thead><tr><th class='cmp-metric'>Métrica</th>{ths}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Vermelho = pior valor entre os cenários (mais crítico / maior custo). "
            "Sem faixa na matriz, o sentido é o eixo de diferenciação."
        )


def main() -> None:
    """Ponto de entrada e ROTEADOR da aplicação.

    Lê `?page=` da URL e monta a tela correspondente (overview/visaogeral,
    solucoes, cenario, projecao, risco=IAGON). Dentro de cada página, o "Tipo de
    Matriz" escolhido na top bar decide se chama a versão Paragon (`_render_*`) ou
    DNIT (`_render_dnit_*`). Cada tela publica ao final o contexto do IAGON da tela.
    """
    # Invalida o cache automaticamente se os cenários mudaram no banco (SIGMA).
    # Mesma quantidade e mesma data => mantém cache; diferente => recarrega tudo.
    ensure_fresh_data()
    inject_css()
    # Roteamento por query param. `page` fora da lista branca cai em "overview".
    page = st.query_params.get("page", "overview")
    if page not in {"visaogeral", "overview", "solucoes", "projecao", "cenario", "risco"}:
        page = "overview"
    render_sidebar(active_key=page)

    default_road = get_available_roads()[0]

    # ─── Página SOLUÇÕES (o que fazer) ───
    if page == "solucoes":
        diagnosis, selected_road, scenario_key, selected_year = render_solution_top_bar(default_road)
        if diagnosis == "Diagnóstico DNIT":
            _render_dnit_solutions_page(selected_road, scenario_key)
            return
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        _d = get_solutions_data(selected_road, scenario_key=scenario_key, year=selected_year)
        _base_table, _base_segments = _d["table"], _d["segments"]
        intervention_table = (
            _base_table[_base_table["Solução recomendada"].astype(str) != "Sem intervenção"].copy()
            if _base_table is not None and not _base_table.empty
            and "Solução recomendada" in _base_table.columns
            else _base_table
        )
        no_intervention_master = (
            _base_table is not None and not _base_table.empty
            and (intervention_table is None or intervention_table.empty)
        )

        if no_intervention_master:
            st.info("Sem intervenção prevista para a rodovia, cenário e ano selecionados.")
            base_extension = (
                float(_base_table["Extensão"].sum())
                if _base_table is not None and not _base_table.empty
                else 0
            )
            render_overview_map(_base_segments, base_extension, color_by="iap")
            st.info("Todos os trechos deste recorte estão sem intervenção prevista.")
            paginated_table = pd.DataFrame()
        else:
            intervention_segments = _filter_map_segments(_base_segments, intervention_table)
            filtered_table = _render_solution_filter_panel(intervention_table)
            filtered_segments = _filter_map_segments(intervention_segments, filtered_table)
            filtered_extension = (
                float(filtered_table["Extensão"].sum())
                if filtered_table is not None and not filtered_table.empty
                else 0
            )
            render_overview_map(filtered_segments, filtered_extension, color_by="solucao")
            _render_solution_distribution(filtered_table)
            _, paginated_table = _render_solution_table_controls(filtered_table)
            _render_solutions_table(paginated_table)

        # IAGON desta tela (Soluções).
        _sol_by = {s["key"]: s for s in get_available_scenarios(selected_road, "Paragon")}
        _sol_lbls = _network_scenario_label(_sol_by.get(scenario_key)) if scenario_key else "—"
        if not no_intervention_master and filtered_table is not None and not filtered_table.empty and "Solução recomendada" in filtered_table.columns:
            _isd = filtered_table.groupby("Solução recomendada")["Extensão"].sum().sort_values(ascending=False)
            _sdados = (
                "Intervenções recomendadas (km por solução, já com os filtros desta tela):\n"
                + "\n".join(f"- {str(n).replace(' + ', ' / ')}: {km:.1f} km" for n, km in _isd.items() if str(n).strip())
                + f"\nExtensão total com intervenção exibida: {float(filtered_table['Extensão'].sum()):.1f} km."
            )
        elif no_intervention_master:
            _sdados = "Sem intervenção prevista para o recorte atual desta tela."
        else:
            _sdados = "Nenhuma intervenção no filtro atual desta tela."
        _render_screen_iagon(
            "solucoes", f"Soluções · {selected_road}",
            (
                f"<b>Rodovia:</b> {selected_road} &nbsp;·&nbsp; <b>Cenário:</b> {html.escape(_sol_lbls)}"
                f" &nbsp;·&nbsp; <b>Ano:</b> {selected_year if selected_year is not None else '—'}"
            ),
            lambda: _iagon_full_road_context(
                selected_road, scenario_key, "Soluções (intervenções recomendadas)",
                {"Rodovia": selected_road, "Cenário": _sol_lbls, "Ano": selected_year or "—"},
                extra="O que está EXIBIDO nesta tela agora (com os filtros aplicados):\n" + _sdados),
            sugestoes=["Análise das soluções", "Onde concentra obra pesada?", "O que priorizar?"],
        )
        return

    # ─── Página CENÁRIO ECONÔMICO (quanto custa) ─── Paragon / DNIT / Comparativo
    if page == "cenario":
        diagnosis, selected_road, scenario_key = render_top_bar(
            default_road,
            page_title="Cenário econômico",
            show_diagnosis=True,
            keep_title=True,
            show_scenario=False,
            diagnosis_options=[
                "Diagnóstico Paragon",
                "Diagnóstico DNIT",
                "Comparativo Paragon × DNIT",
            ],
        )
        if diagnosis == "Comparativo Paragon × DNIT":
            _render_comparativo_page(selected_road, scenario_key)
            return
        if diagnosis == "Diagnóstico DNIT":
            _render_dnit_economic_page(selected_road, scenario_key)
            return
        st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
        _eco_keys, _eco_labels = _solutions_sentido_keys(
            selected_road, scenario_key, widget_key="eco_scen"
        )
        if len(_eco_keys) >= 2:
            _ec = _combined_economic_data(selected_road, _eco_keys, _eco_labels)
            _render_economic_comparison(_ec["per_sentido"])
            _render_economic_page(
                _ec["table"],
                _ec["budget_items"],
                _ec["segments"],
                scenario_key=f"{selected_road}:multi",
                road=selected_road,
                scenario_label="Paragon · CR + DE",
            )
        else:
            _ekey = _eco_keys[0] if _eco_keys else scenario_key
            data = get_solutions_data(selected_road, scenario_key=_ekey)
            scenario_label = get_scenario_label(selected_road, _ekey) or "Paragon"
            _render_economic_page(
                data["table"],
                data.get("budget_items"),
                data.get("segments"),
                scenario_key=f"{selected_road}:{_ekey}",
                road=selected_road,
                scenario_label=scenario_label,
            )
        return

    # ─── Página PROJEÇÃO (evolução) ───
    if page == "projecao":
        diagnosis, selected_road, scenario_key = render_top_bar(
            default_road,
            page_title="Projeção",
            show_diagnosis=True,
            keep_title=True,
        )
        if diagnosis == "Diagnóstico DNIT":
            _render_dnit_projection_page(selected_road, scenario_key)
            return
        _render_projection_page(selected_road, scenario_key)
        return

    # ─── Página VISÃO GERAL (rede) — panorama de todas as rodovias ───
    if page == "visaogeral":
        diagnosis, selected_roads, selected_scenarios, selected_years = render_network_top_bar()
        _render_network_overview(
            diagnosis,
            selected_roads=selected_roads,
            selected_scenarios=selected_scenarios,
            selected_years=selected_years,
        )

        # IAGON desta tela (Visão geral da rede).
        _is_dnit = diagnosis == "Diagnóstico DNIT"
        _scenario_options = _collect_network_scenario_options(
            _network_filter_roads(selected_roads, diagnosis),
            "Paragon" if diagnosis == "Diagnóstico Paragon" else "Matriz Cadastrada",
        )
        _scenario_labels = {item["token"]: item["display_label"] for item in _scenario_options}
        _has_filtered_slices = bool(selected_scenarios or selected_years)
        _net = _build_network_overview(
            is_dnit=_is_dnit,
            selected_roads=selected_roads,
            selected_scenarios=selected_scenarios,
            selected_years=selected_years,
        )
        if _net:
            _ndf = _net["roads_df"]
            _escopo = ", ".join(selected_roads) if selected_roads else "rede inteira"
            _item_label = "recortes" if _has_filtered_slices else "rodovias"
            if _is_dnit:
                _ndados = (
                    f"Escopo {_escopo} (DNIT): {len(_ndf)} {_item_label} · {_net['total_km']:.0f} km · "
                    f"necessidade total {_format_money(_net['net_custo'])} · {_net['prio_total']} trechos prioritários (Alta/Crítica). "
                    f"Médias da rede: IRI {_net['net_iri']:.2f} · IGG {_net['net_igg']:.0f}.\n"
                    + "\n".join(
                        f"- {r['Rodovia']}: IRI {r['IRI']:.2f} · {r['iri_bad_pct']:.0f}% crítico · necessidade {_format_money(float(r['custo']))}"
                        for _, r in _ndf.sort_values("IRI", ascending=False).iterrows())
                )
            else:
                _ndados = (
                    f"Escopo {_escopo} (Paragon): {len(_ndf)} {_item_label} · {_net['total_km']:.0f} km · "
                    f"necessidade total {_format_money(_net['net_custo'])} · {_net['prio_total']} trechos prioritários (Alta/Crítica). "
                    f"Médias da rede: IAP {_net['net_iap']:.2f} (meta 2,5) · IRI {_net['net_iri']:.2f} · IGG {_net['net_igg']:.0f}.\n"
                    + "\n".join(
                        f"- {r['Rodovia']}: IAP {r['IAP']:.2f} · {r['iap_bad_pct']:.0f}% crítico · necessidade {_format_money(float(r['custo']))}"
                        for _, r in _ndf.sort_values("IAP").iterrows())
                )
        else:
            _ndados = "Sem dados de rede."
        _render_screen_iagon(
            "visaogeral", "Visão geral da rede",
            (
                f"<b>Escopo:</b> {html.escape(', '.join(selected_roads) if selected_roads else 'rede inteira')} "
                f"&nbsp;·&nbsp; <b>Matriz:</b> {'DNIT' if _is_dnit else 'Paragon'}"
            ),
            _screen_ctx("Visão geral (panorama executivo da rede)",
                        {
                            "Matriz": "DNIT" if _is_dnit else "Paragon",
                            "Rodovia": ", ".join(selected_roads) if selected_roads else "Todas as rodovias",
                            "Cenário": (
                                ", ".join(_scenario_labels.get(token, token) for token in selected_scenarios)
                                if selected_scenarios else
                                "Todos os cenários padrão"
                            ),
                            "Ano": ", ".join(str(year) for year in selected_years) if selected_years else "Todos os anos disponíveis",
                        }, _ndados),
            sugestoes=["Análise da rede", "Qual a pior rodovia?", "Onde investir primeiro?"],
        )
        return

    # ─── Página IAGON (chave interna "risco") — assistente de IA ───
    if page == "risco":
        render_top_bar(default_road, page_title="IAGON", show_diagnosis=False, show_filters=False)
        _render_iagon_page()
        return

    # Salvaguarda: qualquer página não tratada acima (que não seja overview) é um stub.
    if page != "overview":
        _, _, _ = render_top_bar(default_road, page_title="DNIT · Pavimentos", show_diagnosis=False)
        st.info("Este módulo será montado na próxima etapa.")
        return

    # ─── Página OVERVIEW (default) — DIAGNÓSTICO da rodovia selecionada ───
    diagnosis, selected_road, scenario_key, selected_year = render_diagnosis_top_bar(default_road)

    if diagnosis == "Diagnóstico DNIT":
        _render_dnit_overview(selected_road, scenario_key, year=selected_year)
        return

    data = get_overview_data(selected_road, scenario_key=scenario_key, year=selected_year)
    metrics = data["metrics"]
    _scenario_options = get_available_scenarios(selected_road, "Paragon")
    _by_key = {s["key"]: s for s in _scenario_options}
    _diag_lbl = (
        _network_scenario_label(_by_key.get(scenario_key))
        if scenario_key
        else "—"
    )
    render_metric_cards(data["cards"])
    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
    _km_range = _diagnosis_km_range_from_state(data["linear_diagram"], "paragon_linear_zoom")
    _linear_km = _filter_by_km_range(data["linear_diagram"], _km_range)
    _distribution_km = _build_distribution_from_linear(_linear_km)
    _selected_iap_class = _render_diagnosis_iap_class_filter(
        _distribution_km if not _distribution_km.empty else data["distribution"],
        key="diagnosis_iap_distribution_class",
    )
    _distribution_filtered = _filter_by_iap_class(_distribution_km, _selected_iap_class, class_col="classe")
    _map_segments = _filter_by_km_range(data["segments"], _km_range)
    _map_segments = _filter_by_iap_class(_map_segments, _selected_iap_class, class_col="classe_iap")
    _distribution_avg = _weighted_iap_from_linear(
        _filter_by_iap_class(_linear_km, _selected_iap_class, class_col="classe_iap"),
        metrics["iap_average"],
    )
    render_overview_map(_map_segments, metrics["extension_km"])
    render_iap_distribution(
        _distribution_filtered if not _distribution_filtered.empty else _distribution_km,
        _distribution_avg,
        subtitle=(
            "Faixa em km e faixa IAP aplicadas ao mapa e à distribuição"
            if _selected_iap_class == "Todas" else
            f"Mostrando no mapa e na distribuição apenas a faixa {_selected_iap_class}"
        ),
    )
    st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)
    filtered_diagram, km_range = render_iap_linear_zoomable(
        data["linear_diagram"], key="paragon_linear_zoom"
    )
    with st.expander("Mostrar detalhes técnicos (ICDS, ICDP, ICDE)"):
        render_condition_linear(filtered_diagram, km_range=km_range)

    # IAGON desta tela (Diagnóstico da rodovia selecionada).
    _render_screen_iagon(
        "diagnostico", f"Diagnóstico · {selected_road}",
        (
            f"<b>Rodovia:</b> {selected_road} &nbsp;·&nbsp; <b>Matriz:</b> Paragon "
            f"&nbsp;·&nbsp; <b>Cenário:</b> {html.escape(_diag_lbl)}"
            f" &nbsp;·&nbsp; <b>Ano:</b> {selected_year if selected_year is not None else '—'}"
        ),
        lambda: _iagon_full_road_context(
            selected_road, scenario_key, "Diagnóstico (condição da rodovia)",
            {
                "Rodovia": selected_road,
                "Matriz": "Paragon",
                "Cenário": _diag_lbl,
                "Ano": selected_year or "—",
            }),
        sugestoes=["Análise completa", "Onde está pior?", "O que priorizar?"],
    )


if __name__ == "__main__":
    main()
