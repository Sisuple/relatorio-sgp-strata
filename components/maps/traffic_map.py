"""Mapa de VMDA por segmento de tráfego.

Variante enxuta do mapa Leaflet (mesmo padrão de components.maps.dnit_map):
cada segmento é uma polyline colorida por intensidade de VMDA — um gradiente
contínuo (sequencial, um hue só), não categorias discretas como os outros
mapas do projeto. Sem drawer de Street View / clique-pra-detalhe: aqui o
segmento já mostra tudo que precisa no tooltip.
"""
from __future__ import annotations

import json
from string import Template

import streamlit.components.v1 as components

# Tons de laranja (claro -> escuro): azul/branco no mapa confunde com água e
# limites administrativos nas camadas de satélite/topográfico, por isso não
# reaproveitamos aqui a mesma cor do resto da página de Tráfego.
_VMDA_COLOR_LOW = (0xFB, 0xC2, 0x90)
_VMDA_COLOR_HIGH = (0xC2, 0x41, 0x0C)


def _vmda_color_scale(value: float, vmin: float, vmax: float) -> str:
    """Interpola linearmente (RGB) entre o azul claro (menor VMDA) e o azul
    escuro (maior VMDA). Sem variação (`vmin == vmax`), usa o tom escuro."""
    if vmax <= vmin:
        t = 1.0
    else:
        t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    r = round(_VMDA_COLOR_LOW[0] + (_VMDA_COLOR_HIGH[0] - _VMDA_COLOR_LOW[0]) * t)
    g = round(_VMDA_COLOR_LOW[1] + (_VMDA_COLOR_HIGH[1] - _VMDA_COLOR_LOW[1]) * t)
    b = round(_VMDA_COLOR_LOW[2] + (_VMDA_COLOR_HIGH[2] - _VMDA_COLOR_LOW[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _render_empty_traffic_map(message: str) -> None:
    """Mantém o espaço do mapa visível mesmo sem geometria disponível."""
    empty_html = Template(
        """
        <!doctype html>
        <html lang="pt-BR">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
          <style>
            html, body { margin: 0; padding: 0; background: #061018; font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif; }
            .map-card { position: relative; height: 420px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 0; }
            #map { height: 100%; width: 100%; }
            .empty-note {
              position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
              z-index: 720; min-width: 280px; max-width: 420px; padding: 14px 16px;
              border-radius: 12px; border: 1px solid rgba(148,163,184,.20);
              background: rgba(7,17,25,.88); color: #dbe5ec; text-align: center;
              box-shadow: 0 18px 40px rgba(0,0,0,.34); font-size: 13px; line-height: 1.45;
            }
          </style>
        </head>
        <body>
          <div class="map-card">
            <div id="map"></div>
            <div class="empty-note">$message</div>
          </div>
          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <script>
            const map = L.map('map', { zoomControl: false, attributionControl: true, scrollWheelZoom: true });
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
              maxZoom: 17,
              maxNativeZoom: 17,
              attribution: 'Tiles &copy; Esri'
            }).addTo(map);
            map.setView([-10.9, -63.3], 6);
          </script>
        </body>
        </html>
        """
    )
    components.html(empty_html.substitute(message=message), height=420, scrolling=False)


def render_traffic_vmda_map(segments_df) -> None:
    """Mapa da rodovia dividida pelos segmentos de tráfego, coloridos por VMDA.

    `segments_df` precisa das colunas: segmento, km_inicial, km_final,
    vmda_total, color (hex já calculado via _vmda_color_scale), paths (lista
    de coordenadas [lat,lng] por trecho de geometria).
    """
    if segments_df is None or segments_df.empty:
        _render_empty_traffic_map("Sem segmentos de tráfego para este recorte.")
        return

    df = segments_df[segments_df["paths"].apply(bool)]
    if df.empty:
        _render_empty_traffic_map("Sem geometria disponível para esta rodovia.")
        return

    vmin = float(df["vmda_total"].min())
    vmax = float(df["vmda_total"].max())
    segments_json = json.dumps(
        df[["segmento", "km_inicial", "km_final", "vmda_total", "color", "paths"]].to_dict("records"),
        ensure_ascii=False, default=str,
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
            .map-card { position: relative; height: 420px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 0; }
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
            .map-layer-select { height: 36px; width: 152px; padding: 0 32px 0 12px; font-size: 12px; font-weight: 700; color: #f4f7fb; border: 1px solid rgba(148,163,184,.24); background-color: rgba(7,17,25,.94); border-radius: 8px; box-shadow: 0 14px 32px rgba(0,0,0,.28); outline: none; cursor: pointer; appearance: none; background-image: linear-gradient(45deg, transparent 50%, #cbd5df 50%), linear-gradient(135deg, #cbd5df 50%, transparent 50%); background-position: calc(100% - 17px) 15px, calc(100% - 12px) 15px; background-size: 5px 5px, 5px 5px; background-repeat: no-repeat; }
            .map-layer-select:hover { background-color: rgba(14,31,44,.98); }
            .map-legend { position: absolute; z-index: 700; left: 14px; bottom: 14px; background: rgba(7,17,25,.94); color: #e5edf3; border-radius: 12px; padding: 13px 14px 11px; border: 1px solid rgba(148,163,184,.2); box-shadow: 0 18px 40px rgba(0,0,0,.34); }
            .legend-title { font-size: 10px; letter-spacing: .12em; color: #9aa8b3; font-weight: 800; margin-bottom: 9px; }
            .legend-bar { width: 180px; height: 10px; border-radius: 999px; background: linear-gradient(90deg, $color_low, $color_high); }
            .legend-scale { display: flex; justify-content: space-between; margin-top: 6px; font-size: 11px; color: #cbd5df; }
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
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M8 3H5a2 2 0 0 0-2 2v3"></path><path d="M16 3h3a2 2 0 0 1 2 2v3"></path>
                  <path d="M8 21H5a2 2 0 0 1-2-2v-3"></path><path d="M16 21h3a2 2 0 0 0 2-2v-3"></path>
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
              <div class="legend-title">VMDA POR SEGMENTO</div>
              <div class="legend-bar"></div>
              <div class="legend-scale"><span>$vmin_label</span><span>$vmax_label</span></div>
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
              satellite: L.layerGroup([
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 17, maxNativeZoom: 17, attribution: 'Tiles &copy; Esri' }),
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}', { maxZoom: 17, maxNativeZoom: 17, attribution: 'Reference &copy; Esri' }),
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { maxZoom: 17, maxNativeZoom: 17 })
              ]),
              topographic: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17, attribution: '&copy; OpenTopoMap &copy; OpenStreetMap' })
            };
            let currentBaseLayer = baseLayers.satellite.addTo(map);
            const pts = [];
            const fmt = (v) => Number(v).toFixed(2);
            const fmtInt = (v) => Math.round(Number(v)).toLocaleString('pt-BR');

            segments.forEach((s) => {
              s.paths.forEach((path) => {
                const coords = path.map((c) => [Number(c[0]), Number(c[1])]);
                if (coords.length < 2) return;
                coords.forEach((c) => pts.push(c));
                L.polyline(coords, { color: s.color, weight: 6, opacity: .92, lineCap: 'round', lineJoin: 'round' })
                  .addTo(map)
                  .bindTooltip('Segmento ' + s.segmento + ' · km ' + fmt(s.km_inicial) + ' - ' + fmt(s.km_final) + ' · VMDA ' + fmtInt(s.vmda_total));
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
        html_template.substitute(
            segments_json=segments_json,
            color_low=f"#{_VMDA_COLOR_LOW[0]:02x}{_VMDA_COLOR_LOW[1]:02x}{_VMDA_COLOR_LOW[2]:02x}",
            color_high=f"#{_VMDA_COLOR_HIGH[0]:02x}{_VMDA_COLOR_HIGH[1]:02x}{_VMDA_COLOR_HIGH[2]:02x}",
            vmin_label=f"{vmin:,.0f}".replace(",", "."),
            vmax_label=f"{vmax:,.0f}".replace(",", "."),
        ),
        height=420,
        scrolling=False,
    )
