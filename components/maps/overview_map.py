from __future__ import annotations

import json
from string import Template

import streamlit as st
import streamlit.components.v1 as components

from components.maps.streetview import SV_CSS, SV_MODAL_HTML, sv_init_js, road_from_sre, clean


_CLASS_COLORS = {
    "Excelente": "#00c2e8",
    "Bom": "#00a651",
    "++ Regular": "#b6d7a8",
    "+ Regular": "#f4f1a6",
    "- Regular": "#fff200",
    "Mau": "#f2a51a",
    "Péssimo": "#d71920",
}

_SOLUTION_ORDER = ["RL", "RL+RS", "RL+REF", "RPS", "RPS+REF", "REC"]
_SOLUTION_COLORS = {
    "OK": "#00c2e8",
    "RL": "#00a651",
    "RL+RS": "#b6d7a8",
    "RL+REF": "#f4f1a6",
    "RPS": "#fff200",
    "RPS+REF": "#f2a51a",
    "REC": "#d71920",
    "Sem intervenção": "#82929d",
}


def render_overview_map(
    segments_df,
    extent_km: int | float,
    *,
    attended_ids=None,
    legend_foot: str | None = None,
    color_by: str = "iap",
) -> None:
    if segments_df is None or segments_df.empty:
        st.info("Sem segmentos para exibir no mapa.")
        return

    base_columns = {"segment_id", "sre", "km_inicial", "km_final", "iap", "classe_iap", "paths"}
    if color_by == "solucao":
        required_columns = base_columns | {"intervencao_iap"}
    else:
        required_columns = base_columns
    if not required_columns.issubset(set(segments_df.columns)):
        st.info("Sem geometria real para exibir no mapa.")
        return

    selected_cols = [
        "segment_id",
        "sre",
        "km_inicial",
        "km_final",
        "iap",
        "classe_iap",
        "paths",
    ]
    if color_by == "solucao":
        selected_cols.append("intervencao_iap")
    if "sentido" in segments_df.columns:
        selected_cols.append("sentido")
    records = segments_df[selected_cols].copy()
    if attended_ids is not None:
        attended = {int(value) for value in attended_ids}
        records["attended"] = records["segment_id"].astype(int).isin(attended)
    else:
        records["attended"] = True

    from services.overview_service import _SOLUTION_LABELS

    def _row_detail(r):
        ext = max(float(r.get("km_final") or 0) - float(r.get("km_inicial") or 0), 0.0)
        cod = clean(r.get("intervencao_iap"), default="")
        solucao = _SOLUTION_LABELS.get(cod, cod) if cod else "—"
        return {
            "title": "Trecho " + clean(r.get("sre")),
            "rows": [
                ["Rodovia", road_from_sre(r.get("sre"))],
                ["Situação", clean(r.get("classe_iap"))],
                ["Solução recomendada", solucao],
                ["Extensão", (f"{ext:.2f} km").replace(".", ",")],
            ],
        }

    records["detail"] = segments_df.apply(_row_detail, axis=1)

    segments = records.to_dict("records")
    segments_json = json.dumps(segments, ensure_ascii=False)

    if color_by == "solucao":
        colors_json = json.dumps(_SOLUTION_COLORS, ensure_ascii=False)
        color_key_js = "intervencao_iap"
        tooltip_label = "Solução"
        legend_title = "SOLUÇÃO CORRETIVA"
        present = {str(v) for v in segments_df["intervencao_iap"].dropna().unique()}
        legend_labels = [label for label in _SOLUTION_ORDER if label in present]
        legend_items_html = "".join(
            f'<div class="legend-item"><span class="legend-dot" style="background:{_SOLUTION_COLORS[label]}"></span>{label}</div>'
            for label in legend_labels
        )
        legend_foot_default = '<span class="legend-line"></span>Trechos coloridos pela solução corretiva'
    else:
        colors_json = json.dumps(_CLASS_COLORS, ensure_ascii=False)
        color_key_js = "classe_iap"
        tooltip_label = "Conceito"
        legend_title = "CONCEITO IAP"
        present = {str(v) for v in segments_df["classe_iap"].dropna().unique()}
        legend_items_html = "".join(
            f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span>{label}</div>'
            for label, color in _CLASS_COLORS.items()
            if label in present
        )
        legend_foot_default = '<span class="legend-line"></span>Trechos coloridos por conceito IAP'

    legend_foot_html = legend_foot or legend_foot_default

    html_template = Template(
        """
        <!doctype html>
        <html lang="pt-BR">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
          <style>
            html, body { margin: 0; padding: 0; background: #061018; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
            .map-card { position: relative; height: 456px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 1px solid #1d3848; }
            .map-card:fullscreen { width: 100vw; height: 100vh; border-radius: 0; border: 0; }
            .map-card:fullscreen #map { height: 100vh; }
            #map { height: 100%; width: 100%; }
            .map-card:after { content: ""; position: absolute; inset: 0; pointer-events: none; box-shadow: inset 0 0 0 1px rgba(255,255,255,.03), inset 0 -60px 80px rgba(6,16,24,.12); }
            .map-zoom { position: absolute; z-index: 710; top: 14px; left: 14px; transform: translateY(0); display: grid; overflow: hidden; border-radius: 6px; border: 1px solid rgba(148,163,184,.22); }
            .map-zoom button { width: 32px; height: 32px; border: 0; background: rgba(7,17,25,.96); color: #f4f7fb; font-size: 22px; line-height: 1; font-weight: 700; cursor: pointer; }
            .map-zoom button:hover { background: rgba(14,31,44,.98); }
            .map-zoom button + button { border-top: 1px solid rgba(148,163,184,.22); }
            .map-legend { position: absolute; z-index: 700; left: 14px; bottom: 14px; width: 238px; background: rgba(7,17,25,.94); color: #e5edf3; border-radius: 12px; padding: 14px 14px 12px; border: 1px solid rgba(148,163,184,.2); box-shadow: 0 18px 40px rgba(0,0,0,.34); }
            .legend-title { font-size: 10px; letter-spacing: .12em; color: #9aa8b3; font-weight: 800; margin-bottom: 12px; }
            .legend-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px 12px; }
            .legend-item { display: flex; align-items: center; gap: 7px; font-size: 12px; color: #e6edf2; white-space: nowrap; }
            .legend-dot { width: 14px; height: 14px; border-radius: 999px; display: inline-block; }
            .legend-line { width: 15px; height: 4px; border-radius: 999px; background: #82929d; display: inline-block; }
            .legend-foot { margin-top: 13px; padding-top: 10px; border-top: 1px solid rgba(148,163,184,.16); display: flex; align-items: center; gap: 8px; font-size: 11px; color: #7f909c; }
            .map-actions { position: absolute; z-index: 710; top: 14px; right: 14px; display: flex; align-items: stretch; gap: 8px; }
            .map-button,
            .map-layer-select {
              height: 36px;
              border: 1px solid rgba(148,163,184,.24);
              background: rgba(7,17,25,.94);
              color: #f4f7fb;
              border-radius: 8px;
              box-shadow: 0 14px 32px rgba(0,0,0,.28);
            }
            .map-button { width: 38px; display: grid; place-items: center; padding: 0; cursor: pointer; }
            .map-button:hover,
            .map-layer-select:hover { background: rgba(14,31,44,.98); }
            .map-button svg { width: 18px; height: 18px; stroke: currentColor; }
            .map-layer-select {
              width: 152px;
              padding: 0 32px 0 12px;
              font-size: 12px;
              font-weight: 700;
              outline: none;
              cursor: pointer;
              appearance: none;
              background-image:
                linear-gradient(45deg, transparent 50%, #cbd5df 50%),
                linear-gradient(135deg, #cbd5df 50%, transparent 50%);
              background-position:
                calc(100% - 17px) 15px,
                calc(100% - 12px) 15px;
              background-size: 5px 5px, 5px 5px;
              background-repeat: no-repeat;
            }
            .leaflet-control-container .leaflet-top, .leaflet-control-container .leaflet-bottom { display: none; }
$sv_css
          </style>
        </head>
        <body>
          <div class="map-card">
            <div id="map"></div>
            <div class="map-zoom">
              <button type="button" data-zoom="in" aria-label="Aproximar mapa">+</button>
              <button type="button" data-zoom="out" aria-label="Afastar mapa">−</button>
            </div>
            <div class="map-actions">
              <button class="map-button" type="button" data-fullscreen aria-label="Expandir mapa">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M8 3H5a2 2 0 0 0-2 2v3"></path>
                  <path d="M16 3h3a2 2 0 0 1 2 2v3"></path>
                  <path d="M8 21H5a2 2 0 0 1-2-2v-3"></path>
                  <path d="M16 21h3a2 2 0 0 0 2-2v-3"></path>
                </svg>
              </button>
              <select class="map-layer-select" data-layer aria-label="Camada base do mapa">
                <option value="satellite" selected>Satélite</option>
                <option value="osm">Padrão</option>
                <option value="light">Claro</option>
                <option value="dark">Escuro</option>
                <option value="topographic">Topográfico</option>
              </select>
            </div>
            <div class="map-legend">
              <div class="legend-title">$legend_title</div>
              <div class="legend-grid">$legend_items_html</div>
              <div class="legend-foot">$legend_foot_html</div>
            </div>
$sv_modal
          </div>
          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <script>
            const segments = $segments_json;
            const colors = $colors_json;
            const map = L.map('map', {
              zoomControl: false,
              attributionControl: true,
              scrollWheelZoom: true,
              doubleClickZoom: true,
              boxZoom: true,
              keyboard: true,
              wheelDebounceTime: 40,
              wheelPxPerZoomLevel: 90
            });
            const baseLayers = {
              osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap'
              }),
              light: L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                maxZoom: 20,
                attribution: '&copy; OpenStreetMap &copy; CARTO'
              }),
              dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                maxZoom: 20,
                attribution: '&copy; OpenStreetMap &copy; CARTO'
              }),
              satellite: L.layerGroup([
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                  maxZoom: 22,
                  maxNativeZoom: 17,
                  attribution: 'Tiles &copy; Esri'
                }),
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}', {
                  maxZoom: 22,
                  maxNativeZoom: 17,
                  attribution: 'Reference &copy; Esri'
                }),
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
                  maxZoom: 22,
                  maxNativeZoom: 17
                })
              ]),
              topographic: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                maxZoom: 17,
                attribution: '&copy; OpenTopoMap &copy; OpenStreetMap'
              })
            };
            let currentBaseLayer = baseLayers.satellite.addTo(map);

            const latLngs = [];
            const formatKm = (value) => Number(value).toFixed(2);

            segments.forEach((segment) => {
              const attended = segment.attended !== false;
              const colorKey = segment.$color_key_js;
              const color = attended ? (colors[colorKey] || '#fff200') : '#46586a';
              const opacity = attended ? 0.96 : 0.45;
              const weight = attended ? 5 : 3;
              const dashArray = attended ? null : '4 7';

              segment.paths.forEach((path) => {
                const coordinates = path.map((coord) => [Number(coord[0]), Number(coord[1])]);
                if (coordinates.length < 2) return;

                coordinates.forEach((coord) => latLngs.push(coord));
                L.polyline(coordinates, {
                  color,
                  weight,
                  opacity,
                  dashArray,
                  lineCap: 'round',
                  lineJoin: 'round'
                }).addTo(map).bindTooltip(
                  (segment.sentido ? '◆ ' + segment.sentido + ' · ' : '') +
                  'SRE ' + (segment.sre || '-') +
                  ' · Segmento ' + segment.segment_id +
                  ' · km ' + formatKm(segment.km_inicial) +
                  ' - ' + formatKm(segment.km_final) +
                  ' · IAP ' + Number(segment.iap).toFixed(2) +
                  ' · $tooltip_label ' + colorKey +
                  (attended ? '' : ' · Fora do orçamento')
                ).on('click', (e) => window.__openTrecho(e.latlng.lat, e.latlng.lng, segment.detail));
              });
            });

            const bounds = L.latLngBounds(latLngs);
            map.fitBounds(bounds, { padding: [34, 34] });

            document.querySelector('[data-zoom="in"]').addEventListener('click', () => map.zoomIn());
            document.querySelector('[data-zoom="out"]').addEventListener('click', () => map.zoomOut());

            document.querySelector('[data-layer]').addEventListener('change', (event) => {
              const nextLayer = baseLayers[event.target.value] || baseLayers.osm;
              if (nextLayer === currentBaseLayer) return;
              map.removeLayer(currentBaseLayer);
              currentBaseLayer = nextLayer.addTo(map);
            });

            document.querySelector('[data-fullscreen]').addEventListener('click', async () => {
              const card = document.querySelector('.map-card');
              if (!document.fullscreenElement) {
                await card.requestFullscreen();
              } else {
                await document.exitFullscreen();
              }
              setTimeout(() => map.invalidateSize(), 120);
            });

            document.addEventListener('fullscreenchange', () => {
              setTimeout(() => map.invalidateSize(), 120);
            });
            $sv_js
          </script>
        </body>
        </html>
        """
    )

    components.html(
        html_template.substitute(
            segments_json=segments_json,
            colors_json=colors_json,
            legend_foot_html=legend_foot_html,
            legend_title=legend_title,
            legend_items_html=legend_items_html,
            color_key_js=color_key_js,
            tooltip_label=tooltip_label,
            sv_css=SV_CSS,
            sv_modal=SV_MODAL_HTML,
            sv_js=sv_init_js(),
        ),
        height=456,
        scrolling=False,
    )
