from __future__ import annotations

import json
from string import Template

import streamlit as st
import streamlit.components.v1 as components


def render_dnit_map(segments_df, zona_colors: dict | None = None, zona_order: list | None = None) -> None:
    """Mapa DNIT colorido pela intervenção da matriz (faixas de cor da matriz CBUQ)."""
    if segments_df is None or segments_df.empty:
        st.info("Sem segmentos de IRI/IGG para exibir no mapa.")
        return

    cols = [
        "segment_id", "sre", "km_inicial", "km_final",
        "iri", "igg", "matriz_categoria", "matriz_color", "paths",
    ]
    if not set(cols).issubset(set(segments_df.columns)):
        st.info("Sem geometria real para exibir no mapa.")
        return

    segments_json = json.dumps(segments_df[cols].to_dict("records"), ensure_ascii=False, default=str)

    presentes = [z for z in (zona_order or []) if z in set(segments_df["matriz_categoria"])]
    legend_items = "".join(
        f'<div class="legend-item"><span class="legend-dot" style="background:{(zona_colors or {}).get(z, "#fff200")}"></span>{z}</div>'
        for z in presentes
    )

    html_template = Template(
        """
        <!doctype html>
        <html lang="pt-BR">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
          <style>
            html, body { margin: 0; padding: 0; background: #061018; font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif; }
            .map-card { position: relative; height: 456px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 1px solid #1d3848; }
            .map-card:fullscreen { width: 100vw; height: 100vh; border-radius: 0; border: 0; }
            .map-card:fullscreen #map { height: 100vh; }
            #map { height: 100%; width: 100%; }
            .map-zoom { position: absolute; z-index: 710; top: 14px; left: 14px; display: grid; overflow: hidden; border-radius: 6px; border: 1px solid rgba(148,163,184,.22); }
            .map-zoom button { width: 32px; height: 32px; border: 0; background: rgba(7,17,25,.96); color: #f4f7fb; font-size: 22px; line-height: 1; font-weight: 700; cursor: pointer; }
            .map-zoom button:hover { background: rgba(14,31,44,.98); }
            .map-zoom button + button { border-top: 1px solid rgba(148,163,184,.22); }
            .map-actions { position: absolute; z-index: 710; top: 14px; right: 14px; display: flex; align-items: stretch; gap: 8px; }
            .map-button { height: 36px; width: 38px; display: grid; place-items: center; border: 1px solid rgba(148,163,184,.24); background: rgba(7,17,25,.94); color: #f4f7fb; border-radius: 8px; cursor: pointer; box-shadow: 0 14px 32px rgba(0,0,0,.28); }
            .map-button:hover { background: rgba(14,31,44,.98); }
            .map-button svg { width: 18px; height: 18px; stroke: currentColor; }
            .map-layer-select { height: 36px; width: 152px; padding: 0 32px 0 12px; font-size: 12px; font-weight: 700; color: #f4f7fb; border: 1px solid rgba(148,163,184,.24); background-color: rgba(7,17,25,.94); border-radius: 8px; box-shadow: 0 14px 32px rgba(0,0,0,.28); outline: none; cursor: pointer; appearance: none; background-image: linear-gradient(45deg, transparent 50%, #cbd5df 50%), linear-gradient(135deg, #cbd5df 50%, transparent 50%); background-position: calc(100% - 17px) 15px, calc(100% - 12px) 15px; background-size: 5px 5px, 5px 5px; background-repeat: no-repeat; }
            .map-layer-select:hover { background-color: rgba(14,31,44,.98); }
            .map-legend { position: absolute; z-index: 700; left: 14px; bottom: 14px; max-width: 280px; background: rgba(7,17,25,.94); color: #e5edf3; border-radius: 12px; padding: 13px 14px 11px; border: 1px solid rgba(148,163,184,.2); box-shadow: 0 18px 40px rgba(0,0,0,.34); }
            .legend-title { font-size: 10px; letter-spacing: .12em; color: #9aa8b3; font-weight: 800; margin-bottom: 10px; }
            .legend-grid { display: grid; gap: 8px; }
            .legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; }
            .legend-dot { width: 13px; height: 13px; border-radius: 999px; display: inline-block; flex: none; }
            .leaflet-control-container .leaflet-top, .leaflet-control-container .leaflet-bottom { display: none; }
          </style>
        </head>
        <body>
          <div class="map-card">
            <div id="map"></div>
            <div class="map-zoom">
              <button type="button" data-zoom="in" aria-label="Aproximar">+</button>
              <button type="button" data-zoom="out" aria-label="Afastar">−</button>
            </div>
            <div class="map-actions">
              <button class="map-button" type="button" data-fullscreen aria-label="Expandir">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M8 3H5a2 2 0 0 0-2 2v3"></path><path d="M16 3h3a2 2 0 0 1 2 2v3"></path>
                  <path d="M8 21H5a2 2 0 0 1-2-2v-3"></path><path d="M16 21h3a2 2 0 0 0 2-2v-3"></path>
                </svg>
              </button>
              <select class="map-layer-select" data-layer aria-label="Camada base do mapa">
                <option value="osm">Padrão</option>
                <option value="light">Claro</option>
                <option value="dark">Escuro</option>
                <option value="satellite">Satélite</option>
                <option value="topographic">Topográfico</option>
              </select>
            </div>
            <div class="map-legend">
              <div class="legend-title">INTERVENÇÃO (MATRIZ DNIT)</div>
              <div class="legend-grid">$legend_items</div>
            </div>
          </div>
          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <script>
            const segments = $segments_json;
            const map = L.map('map', { zoomControl: false, attributionControl: true, scrollWheelZoom: true });
            const baseLayers = {
              osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }),
              light: L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { maxZoom: 20, attribution: '&copy; OpenStreetMap &copy; CARTO' }),
              dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 20, attribution: '&copy; OpenStreetMap &copy; CARTO' }),
              satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, attribution: 'Tiles &copy; Esri' }),
              topographic: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17, attribution: '&copy; OpenTopoMap &copy; OpenStreetMap' })
            };
            let currentBaseLayer = baseLayers.osm.addTo(map);
            const pts = [];
            const fmt = (v) => Number(v).toFixed(2);
            segments.forEach((s) => {
              s.paths.forEach((path) => {
                const coords = path.map((c) => [Number(c[0]), Number(c[1])]);
                if (coords.length < 2) return;
                coords.forEach((c) => pts.push(c));
                L.polyline(coords, { color: s.matriz_color, weight: 5, opacity: .96, lineCap: 'round', lineJoin: 'round' })
                  .addTo(map)
                  .bindTooltip('SRE ' + (s.sre || '-') + ' · km ' + fmt(s.km_inicial) + ' - ' + fmt(s.km_final)
                    + ' · IRI ' + Number(s.iri).toFixed(2) + ' · IGG ' + Number(s.igg).toFixed(0)
                    + ' · ' + s.matriz_categoria);
              });
            });
            if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [34, 34] });
            document.querySelector('[data-zoom=in]').addEventListener('click', () => map.zoomIn());
            document.querySelector('[data-zoom=out]').addEventListener('click', () => map.zoomOut());
            document.querySelector('[data-layer]').addEventListener('change', (event) => {
              const nextLayer = baseLayers[event.target.value] || baseLayers.osm;
              if (nextLayer === currentBaseLayer) return;
              map.removeLayer(currentBaseLayer);
              currentBaseLayer = nextLayer.addTo(map);
            });
            document.querySelector('[data-fullscreen]').addEventListener('click', async () => {
              const card = document.querySelector('.map-card');
              if (!document.fullscreenElement) { await card.requestFullscreen(); } else { await document.exitFullscreen(); }
              setTimeout(() => map.invalidateSize(), 120);
            });
            document.addEventListener('fullscreenchange', () => setTimeout(() => map.invalidateSize(), 120));
          </script>
        </body>
        </html>
        """
    )

    components.html(
        html_template.substitute(segments_json=segments_json, legend_items=legend_items),
        height=456,
        scrolling=False,
    )
