from __future__ import annotations

import json
from string import Template

import streamlit as st
import streamlit.components.v1 as components


_CLASS_COLORS = {
    "Excelente": "#9fb9d9",
    "Bom": "#00a651",
    "++ Regular": "#b6d7a8",
    "+ Regular": "#f4f1a6",
    "- Regular": "#fff200",
    "Mau": "#f2a51a",
    "Péssimo": "#d71920",
}


def render_overview_map(segments_df, extent_km: int | float) -> None:
    if segments_df is None or segments_df.empty:
        st.info("Sem segmentos para exibir no mapa.")
        return

    required_columns = {
        "segment_id",
        "km_inicial",
        "km_final",
        "iap",
        "classe_iap",
        "paths",
    }
    if not required_columns.issubset(set(segments_df.columns)):
        st.info("Sem geometria real para exibir no mapa.")
        return

    segments = segments_df[
        [
            "segment_id",
            "km_inicial",
            "km_final",
            "iap",
            "classe_iap",
            "paths",
        ]
    ].to_dict("records")
    segments_json = json.dumps(segments, ensure_ascii=False)
    colors_json = json.dumps(_CLASS_COLORS, ensure_ascii=False)

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
            #map { height: 100%; width: 100%; }
            .map-card:after { content: ""; position: absolute; inset: 0; pointer-events: none; box-shadow: inset 0 0 0 1px rgba(255,255,255,.03), inset 0 -60px 80px rgba(6,16,24,.12); }
            .map-counter { position: absolute; z-index: 700; top: 14px; left: 14px; background: rgba(7, 17, 25, .92); border: 1px solid rgba(148,163,184,.22); color: #e5edf3; border-radius: 9px; padding: 12px 14px; min-width: 174px; box-shadow: 0 18px 40px rgba(0,0,0,.32); }
            .map-counter strong { display: block; font-size: 10px; letter-spacing: .12em; color: #9aa8b3; font-weight: 700; }
            .map-counter span { display: block; margin-top: 2px; font-size: 12px; color: #cfd8df; }
            .map-zoom { position: absolute; z-index: 710; top: 14px; left: 14px; transform: translateY(0); display: grid; overflow: hidden; border-radius: 6px; border: 1px solid rgba(148,163,184,.22); }
            .map-zoom + .map-counter { left: 54px; }
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
            .leaflet-control-container .leaflet-top, .leaflet-control-container .leaflet-bottom { display: none; }
          </style>
        </head>
        <body>
          <div class="map-card">
            <div id="map"></div>
            <div class="map-zoom">
              <button type="button" data-zoom="in" aria-label="Aproximar mapa">+</button>
              <button type="button" data-zoom="out" aria-label="Afastar mapa">−</button>
            </div>
            <div class="map-counter"><strong>PONTOS DE INTERVENÇÃO</strong><span>de $extent_km km</span></div>
            <div class="map-legend">
              <div class="legend-title">CONCEITO IAP</div>
              <div class="legend-grid">
                <div class="legend-item"><span class="legend-dot" style="background:#9fb9d9"></span>Excelente</div>
                <div class="legend-item"><span class="legend-dot" style="background:#00a651"></span>Bom</div>
                <div class="legend-item"><span class="legend-dot" style="background:#b6d7a8"></span>++ Regular</div>
                <div class="legend-item"><span class="legend-dot" style="background:#f4f1a6"></span>+ Regular</div>
                <div class="legend-item"><span class="legend-dot" style="background:#fff200"></span>- Regular</div>
                <div class="legend-item"><span class="legend-dot" style="background:#f2a51a"></span>Mau</div>
                <div class="legend-item"><span class="legend-dot" style="background:#d71920"></span>Péssimo</div>
              </div>
              <div class="legend-foot"><span class="legend-line"></span>Trechos coloridos por conceito IAP</div>
            </div>
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
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
              maxZoom: 19,
              attribution: '&copy; OpenStreetMap'
            }).addTo(map);

            const latLngs = [];
            const formatKm = (value) => Number(value).toFixed(2);

            segments.forEach((segment) => {
              const color = colors[segment.classe_iap] || '#fff200';
              const opacity = 0.96;
              const weight = 5;

              segment.paths.forEach((path) => {
                const coordinates = path.map((coord) => [Number(coord[0]), Number(coord[1])]);
                if (coordinates.length < 2) return;

                coordinates.forEach((coord) => latLngs.push(coord));
                L.polyline(coordinates, {
                  color,
                  weight,
                  opacity,
                  lineCap: 'round',
                  lineJoin: 'round'
                }).addTo(map).bindTooltip(
                  'Segmento ' + segment.segment_id +
                  ' · km ' + formatKm(segment.km_inicial) +
                  ' - ' + formatKm(segment.km_final) +
                  ' · IAP ' + Number(segment.iap).toFixed(2) +
                  ' · ' + segment.classe_iap
                );
              });
            });

            const bounds = L.latLngBounds(latLngs);
            map.fitBounds(bounds, { padding: [34, 34] });

            document.querySelector('[data-zoom="in"]').addEventListener('click', () => map.zoomIn());
            document.querySelector('[data-zoom="out"]').addEventListener('click', () => map.zoomOut());
          </script>
        </body>
        </html>
        """
    )

    components.html(
        html_template.substitute(
            segments_json=segments_json,
            colors_json=colors_json,
            extent_km=extent_km,
        ),
        height=456,
        scrolling=False,
    )
