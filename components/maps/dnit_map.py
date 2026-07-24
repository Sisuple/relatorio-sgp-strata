"""Mapa DNIT: rede colorida pela zona de IRI / intervenção da matriz CBUQ.

Variante do mapa Leaflet voltada ao pipeline DNIT (matriz cadastrada). Cada
segmento é desenhado com a cor que já vem pronta na coluna 'matriz_color' e o
tooltip traz IRI/IGG. A legenda explica a mesma coisa que colore o mapa: a faixa
de IRI presente nos segmentos. Reaproveita o drawer de Street View
(components.maps.streetview). Diferente de overview_map, aqui as cores NÃO vêm
de um dicionário hardcoded — chegam prontas nos dados/zona_colors.
"""
from __future__ import annotations

import json
from string import Template

import streamlit as st
import streamlit.components.v1 as components

from components.maps.streetview import SV_CSS, SV_MODAL_HTML, sv_init_js, road_from_sre, clean


def _render_empty_dnit_map(message: str) -> None:
    """Mantém o espaço do mapa DNIT visível mesmo sem segmentos."""
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
            .map-card { position: relative; height: 456px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 0; }
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
    components.html(
        empty_html.substitute(message=message),
        height=456,
        scrolling=False,
    )


def render_dnit_map(
    segments_df,
    zona_colors: dict | None = None,
    zona_order: list | None = None,
    gap_px: int | float = 18,
    legend_title: str = "CLASSE IRI (MATRIZ DNIT)",
    attended_ids=None,
    unattended_color: str = "#ef4444",
    legend_extra_items: dict[str, str] | None = None,
) -> None:
    """Mapa DNIT colorido pela intervenção da matriz (faixas de cor da matriz CBUQ).

    Parâmetros:
    - segments_df: segmentos com geometria ('paths') e os campos da matriz DNIT
      (iri, igg, matriz_categoria, matriz_color; opcionalmente solucao_grupo).
    - zona_colors: mapa categoria->cor hex para a legenda (fallback #fff200).
    - zona_order: ordem das zonas do pior IRI ao melhor, usada para ordenar a legenda.
    - gap_px: afastamento lateral entre cenários/sentidos sobrepostos.
    Mantém o card do mapa visível mesmo sem dados, usando uma base vazia com aviso discreto.
    """
    if segments_df is None or segments_df.empty:
        _render_empty_dnit_map("Sem segmentos de IRI/IGG para desenhar neste filtro.")
        return

    cols = [
        "segment_id", "sre", "km_inicial", "km_final",
        "iri", "igg", "matriz_categoria", "matriz_color", "paths",
    ]
    if not set(cols).issubset(set(segments_df.columns)):
        _render_empty_dnit_map("Sem geometria disponível para desenhar neste filtro.")
        return

    df = segments_df.copy()

    def _row_detail(r):
        """Monta o dict de detalhe (título + linhas chave/valor) do drawer para um segmento."""
        ext = max(float(r.get("km_final") or 0) - float(r.get("km_inicial") or 0), 0.0)
        # Solução exibida: usa 'solucao'; se vazia, cai para 'solucao_grupo'.
        solucao = clean(r.get("solucao"), default=clean(r.get("solucao_grupo")))
        rows = [
            ["Rodovia", road_from_sre(r.get("sre"))],
            ["Situação", clean(r.get("matriz_categoria"))],
            ["Solução recomendada", solucao],
            ["Extensão", (f"{ext:.2f} km").replace(".", ",")],
        ]
        if r.get("_custo_sre_label"):
            rows.insert(2, ["Custo do SRE", clean(r.get("_custo_sre_label"))])
        return {
            "title": "Trecho " + clean(r.get("sre")),
            "rows": rows,
        }

    df["detail"] = df.apply(_row_detail, axis=1)
    if attended_ids is not None:
        attended = {str(value) for value in attended_ids}
        key_col = "_attendance_key" if "_attendance_key" in df.columns else "segment_id"
        df["attended"] = df[key_col].astype(str).isin(attended)
    else:
        df["attended"] = True
    optional_cols = [
        col for col in ("sentido", "offset_side", "_custo_sre_label", "_attendance_key", "attended")
        if col in df.columns
    ]
    # Serializa só as colunas necessárias + detalhe; default=str tolera tipos não-JSON.
    segments_json = json.dumps(df[cols + optional_cols + ["detail"]].to_dict("records"), ensure_ascii=False, default=str)

    visible_df = df[df["attended"]] if attended_ids is not None else df
    has_unattended = bool((~df["attended"]).any()) if attended_ids is not None else False
    presentes_set = set(visible_df["matriz_categoria"].dropna().astype(str))
    ordered = [z for z in (zona_order or []) if z in presentes_set]
    extras = sorted(presentes_set - set(ordered))
    legend_items = "".join(
        f'<div class="legend-item"><span class="legend-dot" style="background:{(zona_colors or {}).get(z, "#fff200")}"></span>{z}</div>'
        for z in ordered + extras
    )
    if legend_extra_items:
        legend_items += "".join(
            f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span>{label}</div>'
            for label, color in legend_extra_items.items()
            if label != "Fora do orçamento" or has_unattended
        )

    # Template HTML/JS do iframe do mapa; placeholders $... preenchidos no .substitute() abaixo.
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
            .map-card { position: relative; height: 456px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 0; }
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
$sv_css
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
                <option value="satellite" selected>Satélite</option>
                <option value="osm">Padrão</option>
                <option value="light">Claro</option>
                <option value="dark">Escuro</option>
                <option value="topographic">Topográfico</option>
              </select>
            </div>
            <div class="map-legend">
              <div class="legend-title">$legend_title</div>
              <div class="legend-grid">$legend_items</div>
            </div>
$sv_modal
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
            const GAP_PX = $gap_px;
            const pts = [];
            const drawn = [];
            const fmt = (v) => Number(v).toFixed(2);

            function offsetPathPixels(coords, sidePx) {
              if (coords.length < 2 || !sidePx) return coords;
              const z = map.getZoom();
              const projected = coords.map((c) => map.project(L.latLng(c[0], c[1]), z));
              const out = [];
              for (let i = 0; i < projected.length; i++) {
                const a = projected[Math.max(0, i - 1)];
                const b = projected[Math.min(projected.length - 1, i + 1)];
                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const len = Math.hypot(dx, dy) || 1e-9;
                const px = -dy / len;
                const py = dx / len;
                const p = projected[i];
                const ll = map.unproject(L.point(p.x + px * sidePx, p.y + py * sidePx), z);
                out.push([ll.lat, ll.lng]);
              }
              return out;
            }

            // Padroniza apenas a ordem geométrica usada no cálculo do offset.
            // O sentido real vem do cadastro: Crescente = km 0 -> X e
            // Decrescente = km X -> 0.
            function canonicalPath(coords) {
              if (coords.length < 2) return coords;
              const first = coords[0], last = coords[coords.length - 1];
              const reversed = first[0] > last[0] || (first[0] === last[0] && first[1] > last[1]);
              return reversed ? coords.slice().reverse() : coords;
            }

            segments.forEach((s) => {
              const attended = s.attended !== false;
              const sidePx = (Number(s.offset_side) || 0) * GAP_PX;
              s.paths.forEach((path) => {
                const coords = canonicalPath(path.map((c) => [Number(c[0]), Number(c[1])]));
                if (coords.length < 2) return;
                coords.forEach((c) => pts.push(c));
                const pl = L.polyline(coords, {
                  color: attended ? s.matriz_color : '$unattended_color',
                  weight: 5,
                  opacity: .96,
                  lineCap: 'round',
                  lineJoin: 'round'
                })
                  .addTo(map)
                  .bindTooltip((s.sentido ? s.sentido + ' · ' : '') + 'SRE ' + (s.sre || '-') + ' · km ' + fmt(s.km_inicial) + ' - ' + fmt(s.km_final)
                    + ' · IRI ' + Number(s.iri).toFixed(2) + ' · IGG ' + Number(s.igg).toFixed(0)
                    + ' · ' + s.matriz_categoria
                    + (s._custo_sre_label ? ' · Custo ' + s._custo_sre_label : '')
                    + (attended ? '' : ' · Fora do orçamento'))
                  .on('click', (e) => window.__openTrecho(e.latlng.lat, e.latlng.lng, s.detail));
                drawn.push({ polyline: pl, coords, sidePx });
              });
            });
            if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [34, 34] });
            function redrawOffsets() {
              drawn.forEach((d) => {
                if (d.sidePx) d.polyline.setLatLngs(offsetPathPixels(d.coords, d.sidePx));
              });
            }
            redrawOffsets();
            map.on('zoomend', redrawOffsets);
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
            $sv_js
          </script>
        </body>
        </html>
        """
    )

    components.html(
        html_template.substitute(
            segments_json=segments_json,
            legend_items=legend_items,
            legend_title=legend_title,
            unattended_color=unattended_color,
            gap_px=float(gap_px),
            sv_css=SV_CSS,
            sv_modal=SV_MODAL_HTML,
            sv_js=sv_init_js(),
        ),
        height=456,
        scrolling=False,
    )
