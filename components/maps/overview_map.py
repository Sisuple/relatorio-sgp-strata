"""Mapa Leaflet da rede, colorido por conceito IAP ou por solução corretiva.

Renderiza um mapa interativo (Leaflet dentro de um iframe via components.html) com
as polilinhas reais dos segmentos, tooltip por trecho, seletor de camada base,
tela cheia e o drawer de Street View (components.maps.streetview). A cor de cada
linha vem de _CLASS_COLORS (color_by="iap") ou _SOLUTION_COLORS (color_by="solucao").
Quando há sentidos sobrepostos, o JS desloca cada linha alguns pixels (offset_side)
para não se cobrirem. Segmentos "não atendidos" (fora do orçamento) ficam esmaecidos.
"""
from __future__ import annotations

import json
from string import Template

import streamlit as st
import streamlit.components.v1 as components

from components.maps.streetview import SV_CSS, SV_MODAL_HTML, sv_init_js, road_from_sre, clean


# Paleta hardcoded conceito IAP -> cor hex (7 níveis). Mesma paleta semântica
# repetida em vários arquivos (linear_diagram, dnit_map...). Ver README.md Parte II
# §11.4. Usada como legenda e passada ao JS para colorir as linhas por classe_iap.
_CLASS_COLORS = {
    "Excelente": "#00c2e8",
    "Bom": "#00a651",
    "++ Regular": "#b6d7a8",
    "+ Regular": "#f4f1a6",
    "- Regular": "#fff200",
    "Mau": "#f2a51a",
    "Péssimo": "#d71920",
    # "CA" não é nível da escala IAP, e sem cor própria caía no fallback amarelo
    # do JS — ficando igual a "- Regular". Espelha overview_service._IAP_CLASS_COLORS
    # para o mapa não contradizer a legenda da rosca. Só entra na legenda quando
    # a classe existe nos dados visíveis (filtro `label in present`).
    "CA": "#000000",
}

# Ordem (pior→melhor na legenda) e paleta hardcoded das soluções corretivas.
# _SOLUTION_ORDER define quais rótulos aparecem na legenda e em que sequência;
# "OK"/"Sem intervenção" existem no mapa de cores mas não na legenda. Mesma paleta
# de linear_diagram._SOLUTION_LEGEND. Ver README.md Parte II §11.4.
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
    # Espelha overview_service._IAP_INTERVENTION_COLORS: é esta paleta (por código)
    # que colore o mapa da tela Soluções, então sem a CA aqui ela seguia amarela lá.
    "CA": "#000000",
}


def _render_empty_overview_map(message: str) -> None:
    """Mantém o card do mapa visível mesmo sem segmentos para desenhar."""
    empty_html = Template(
        """
        <!doctype html>
        <html lang="pt-BR">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
          <style>
            html, body { margin: 0; padding: 0; background: #061018; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
            .map-card { position: relative; height: 456px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 0; }
            #map { height: 100%; width: 100%; }
            .empty-note {
              position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
              z-index: 720; min-width: 280px; max-width: 420px; padding: 14px 16px;
              border-radius: 12px; border: 1px solid rgba(148,163,184,.20);
              background: rgba(7,17,25,.88); color: #dbe5ec; text-align: center;
              box-shadow: 0 18px 40px rgba(0,0,0,.34); font-size: 13px; line-height: 1.45;
            }
            .map-card:after { content: ""; position: absolute; inset: 0; pointer-events: none; box-shadow: inset 0 0 0 1px rgba(255,255,255,.03), inset 0 -60px 80px rgba(6,16,24,.12); }
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


def render_overview_map(
    segments_df,
    extent_km: int | float,
    *,
    attended_ids=None,
    legend_foot: str | None = None,
    color_by: str = "iap",
    gap_m: int | float = 24,
    min_gap_px: int | float = 14,
    class_colors: dict[str, str] | None = None,
    class_legend_title: str | None = None,
    class_tooltip_label: str | None = None,
    unattended_color: str = "#2f6072",
    unattended_dash: str | None = "4 14",
    unattended_label: str = "Fora do orçamento",
    legend_extra_items: dict[str, str] | None = None,
) -> None:
    """Renderiza o mapa Leaflet da rede no Streamlit.

    Parâmetros:
    - segments_df: DataFrame com os segmentos (precisa das colunas de geometria
      'paths' e dos campos de condição; ver base_columns).
    - extent_km: extensão total (recebida por assinatura; o enquadramento real é
      feito pelo fitBounds no JS a partir das coordenadas).
    - attended_ids: ids atendidos pelo orçamento; os demais são desenhados
      esmaecidos/tracejados. None => todos atendidos. Os não atendidos também ficam
      FORA da legenda (ela se monta só com os visíveis), o que serve para destacar
      um filtro sem que o resto da rodovia vire uma categoria da legenda.
    - unattended_label: sufixo do tooltip dos não atendidos. Padrão "Fora do
      orçamento"; a tela Soluções usa "Fora do filtro", porque lá o esmaecido
      significa outra coisa.
    - legend_foot: rodapé customizado da legenda (senão usa o padrão do modo).
    - color_by: "iap" (cor por conceito) ou "solucao" (cor pela solução corretiva).
    - gap_m: afastamento lateral TOTAL entre sentidos sobrepostos, em METROS de
      terreno (o `offset_side` de cada segmento é a fração desse total). Em metros
      e não em pixels porque a linha tem de acompanhar a rodovia em qualquer zoom
      — ver `offsetPathPixels`.
    - min_gap_px: piso do afastamento em pixels de tela. No zoom aberto `gap_m`
      vale menos de 1 px e os dois sentidos colapsariam numa linha só. Tem de ser
      MAIOR que a espessura da linha (5 px), senão os dois traços se sobrepõem e
      continuam parecendo um: com 14 px de eixo a eixo sobram ~9 px de vão limpo.

    Mantém o card do mapa mesmo sem dados, usando uma base vazia com aviso discreto.
    """
    if segments_df is None or segments_df.empty:
        _render_empty_overview_map("Sem segmentos para desenhar neste filtro.")
        return

    # Colunas mínimas exigidas; no modo "solucao" também é preciso intervencao_iap.
    base_columns = {"segment_id", "sre", "km_inicial", "km_final", "iap", "classe_iap", "paths"}
    if color_by == "solucao":
        required_columns = base_columns | {"intervencao_iap"}
    else:
        required_columns = base_columns
    if not required_columns.issubset(set(segments_df.columns)):
        _render_empty_overview_map("Sem geometria disponível para desenhar neste filtro.")
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
    # Colunas opcionais: só entram se existirem (sentido/offset_side controlam o
    # deslocamento em pixels das linhas de sentidos sobrepostos no JS).
    if "sentido" in segments_df.columns:
        selected_cols.append("sentido")
    if "offset_side" in segments_df.columns:
        selected_cols.append("offset_side")
    if "_attendance_key" in segments_df.columns:
        selected_cols.append("_attendance_key")
    if "_custo_sre_label" in segments_df.columns:
        selected_cols.append("_custo_sre_label")
    records = segments_df[selected_cols].copy()
    # Marca cada segmento como atendido (dentro do orçamento) ou não. Sem lista de
    # atendidos, considera todos atendidos (mapa "cheio").
    if attended_ids is not None:
        attended = {str(value) for value in attended_ids}
        key_col = "_attendance_key" if "_attendance_key" in records.columns else "segment_id"
        records["attended"] = records[key_col].astype(str).isin(attended)
    else:
        records["attended"] = True

    # Rótulos legíveis das soluções (código -> texto) reusados do serviço.
    from services.overview_service import _SOLUTION_LABELS

    def _row_detail(r):
        """Monta o dict de detalhe (título + linhas chave/valor) do drawer para um segmento."""
        ext = max(float(r.get("km_final") or 0) - float(r.get("km_inicial") or 0), 0.0)
        cod = clean(r.get("intervencao_iap"), default="")
        solucao = _SOLUTION_LABELS.get(cod, cod) if cod else "—"
        rows = [
            ["Rodovia", road_from_sre(r.get("sre"))],
            ["Situação", clean(r.get("classe_iap"))],
            ["Solução recomendada", solucao],
            ["Extensão", (f"{ext:.2f} km").replace(".", ",")],
        ]
        if r.get("_custo_sre_label"):
            rows.insert(2, ["Custo do SRE", clean(r.get("_custo_sre_label"))])
        return {
            "title": "Trecho " + clean(r.get("sre")),
            "rows": rows,
        }

    records["detail"] = segments_df.apply(_row_detail, axis=1)
    visible_records = records[records["attended"]] if attended_ids is not None else records
    has_unattended = bool((~records["attended"]).any()) if attended_ids is not None else False

    # Serializa os segmentos (com geometria e detalhe) para injetar no JS do mapa.
    segments = records.to_dict("records")
    segments_json = json.dumps(segments, ensure_ascii=False)

    # Seleciona a paleta, a coluna de cor (color_key_js), os textos e a legenda
    # conforme o modo. A legenda lista só os valores realmente presentes ('present').
    if color_by == "solucao":
        colors_json = json.dumps(_SOLUTION_COLORS, ensure_ascii=False)
        color_key_js = "intervencao_iap"
        tooltip_label = "Solução"
        legend_title = "SOLUÇÃO CORRETIVA"
        present = {str(v) for v in visible_records["intervencao_iap"].dropna().unique()}
        legend_labels = [label for label in _SOLUTION_ORDER if label in present]
        legend_items = [
            f'<div class="legend-item"><span class="legend-dot" style="background:{_SOLUTION_COLORS[label]}"></span>{label}</div>'
            for label in legend_labels
        ]
        if "Sem intervenção" in present:
            legend_items.append(
                f'<div class="legend-item"><span class="legend-dot" style="background:{_SOLUTION_COLORS["Sem intervenção"]}"></span>Sem intervenção</div>'
            )
        if "OK" in present:
            legend_items.append(
                f'<div class="legend-item"><span class="legend-dot" style="background:{_SOLUTION_COLORS["OK"]}"></span>OK / sem intervenção</div>'
            )
        legend_items_html = "".join(legend_items)
        legend_foot_default = '<span class="legend-line"></span>Trechos coloridos pela solução corretiva'
    else:
        active_class_colors = class_colors or _CLASS_COLORS
        colors_json = json.dumps(active_class_colors, ensure_ascii=False)
        color_key_js = "classe_iap"
        tooltip_label = class_tooltip_label or "Conceito"
        legend_title = class_legend_title or "CONCEITO IAP"
        present = {str(v) for v in visible_records["classe_iap"].dropna().unique()}
        legend_items_html = "".join(
            f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span>{label}</div>'
            for label, color in active_class_colors.items()
            if label in present
        )
        legend_foot_default = '<span class="legend-line"></span>Trechos coloridos por conceito IAP'

    if legend_extra_items:
        legend_items_html += "".join(
            f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span>{html_label}</div>'
            for html_label, color in legend_extra_items.items()
            if html_label != "Fora do orçamento" or has_unattended
        )

    legend_foot_html = legend_foot if legend_foot is not None else legend_foot_default
    legend_foot_block = f'<div class="legend-foot">{legend_foot_html}</div>' if legend_foot_html else ""

    # Template HTML/JS completo do iframe do mapa. Os placeholders $... são
    # preenchidos no .substitute() lá embaixo (dados, cores, textos e o Street View).
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
            .map-card { position: relative; height: 456px; border-radius: 14px; overflow: hidden; background: #0b1d28; border: 0; }
            .map-card:fullscreen { width: 100vw; height: 100vh; border-radius: 0; border: 0; }
            .map-card:fullscreen #map { height: 100vh; }
            #map { height: 100%; width: 100%; }
            .map-card:after { content: ""; position: absolute; inset: 0; pointer-events: none; box-shadow: inset 0 0 0 1px rgba(255,255,255,.03), inset 0 -60px 80px rgba(6,16,24,.12); }
            .map-zoom { position: absolute; z-index: 710; top: 14px; left: 14px; transform: translateY(0); display: grid; overflow: hidden; border-radius: 6px; border: 1px solid rgba(148,163,184,.22); }
            .map-zoom button { width: 32px; height: 32px; border: 0; background: rgba(7,17,25,.96); color: #f4f7fb; font-size: 22px; line-height: 1; font-weight: 700; cursor: pointer; }
            .map-zoom button:hover { background: rgba(14,31,44,.98); }
            .map-zoom button + button { border-top: 1px solid rgba(148,163,184,.22); }
            .map-legend { position: absolute; z-index: 700; left: 14px; bottom: 14px; max-width: 280px; background: rgba(7,17,25,.94); color: #e5edf3; border-radius: 12px; padding: 13px 14px 11px; border: 1px solid rgba(148,163,184,.2); box-shadow: 0 18px 40px rgba(0,0,0,.34); }
            .legend-title { font-size: 10px; letter-spacing: .12em; color: #9aa8b3; font-weight: 800; margin-bottom: 10px; }
            .legend-grid { display: grid; gap: 8px; }
            .legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #e6edf2; white-space: nowrap; }
            .legend-dot { width: 13px; height: 13px; border-radius: 999px; display: inline-block; flex: none; }
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
              $legend_foot_block
            </div>
$sv_modal
          </div>
          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <script>
            const segments = $segments_json;
            const colors = $colors_json;
            // Afastamento entre sentidos medido em METROS de terreno, com piso em
            // pixels. Ver offsetPathPixels para o porquê.
            const GAP_M = $gap_m;
            const MIN_GAP_PX = $min_gap_px;
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
                  maxZoom: 17,
                  maxNativeZoom: 17,
                  attribution: 'Tiles &copy; Esri'
                }),
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}', {
                  maxZoom: 17,
                  maxNativeZoom: 17,
                  attribution: 'Reference &copy; Esri'
                }),
                L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
                  maxZoom: 17,
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
            const drawn = [];   // { polyline, coords (originais), sidePx }
            const formatKm = (value) => Number(value).toFixed(2);

            // Pixels por metro no zoom `z`, na latitude `lat`. Mede uma distância
            // conhecida em graus e compara projeção com distância real, então segue
            // a projeção do Leaflet em vez de assumir uma constante de Mercator.
            function pixelsPerMeter(lat, z) {
              const a = L.latLng(lat, 0), b = L.latLng(lat, 0.01);
              const metros = map.distance(a, b);
              if (!metros) return 0;
              const pa = map.project(a, z), pb = map.project(b, z);
              return Math.hypot(pb.x - pa.x, pb.y - pa.y) / metros;
            }

            // Afastamento lateral em pixels do zoom atual, a partir de GAP_M metros.
            //
            // O offset já foi em pixels fixos, e isso descolava a linha da rodovia:
            // 18 px valem ~20 m no zoom fechado (cabe na plataforma) mas centenas de
            // metros no zoom aberto, jogando o traçado no meio da mata. Medindo em
            // metros a linha acompanha a geografia em qualquer zoom; o piso em pixels
            // existe para o caso oposto — no zoom bem aberto GAP_M vale menos de 1 px
            // e os dois sentidos virariam uma linha só.
            function gapPixels(lat) {
              const z = map.getZoom();
              return Math.max(GAP_M * pixelsPerMeter(lat, z), MIN_GAP_PX);
            }

            // Desloca a polilinha perpendicularmente. `side` é a FRAÇÃO do
            // afastamento (offset_side: ±0,5 para dois sentidos, ±0,33/±0,67 quando
            // há mais de um cenário do mesmo lado).
            function offsetPathPixels(coords, side) {
              if (coords.length < 2 || !side) return coords;
              const z = map.getZoom();
              const sidePx = side * gapPixels(coords[0][0]);
              const pts = coords.map((c) => map.project(L.latLng(c[0], c[1]), z));
              const out = [];
              for (let i = 0; i < pts.length; i++) {
                const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
                const dx = b.x - a.x, dy = b.y - a.y;
                const len = Math.hypot(dx, dy) || 1e-9;
                const px = -dy / len, py = dx / len;     // perpendicular unitária (px)
                const p = pts[i];
                const ll = map.unproject(L.point(p.x + px * sidePx, p.y + py * sidePx), z);
                out.push([ll.lat, ll.lng]);
              }
              return out;
            }

            // A ordem dos pontos NÃO é normalizada aqui de propósito: ela já chega
            // coerente do banco (o shape da pista é recortado em ordem de km), e é
            // ela que define de que lado a perpendicular do offset aponta.
            //
            // Existia um `canonicalPath()` que reordenava cada trecho comparando a
            // LATITUDE do primeiro ponto com a do último. Numa rodovia que corre
            // leste-oeste a latitude quase não varia, então o sinal da comparação
            // virava ruído e trocava de segmento para segmento: o traçado saltava de
            // um lado da rodovia para o outro. Medido na BR-055: das 111 emendas
            // entre trechos, 109 vinham coerentes do banco e o canonicalPath deixava
            // 81 invertidas. Sem ele, um sentido sai todo do mesmo lado e
            // Crescente/Decrescente saem em lados opostos, que é o esperado.

            segments.forEach((segment) => {
              const attended = segment.attended !== false;
              const colorKey = segment.$color_key_js;
              const color = attended ? (colors[colorKey] || '#fff200') : '$unattended_color';
              const opacity = attended ? 0.96 : $unattended_opacity;
              const weight = attended ? 5 : $unattended_weight;
              const dashArray = attended ? null : $unattended_dash;
              const side = Number(segment.offset_side) || 0;

              segment.paths.forEach((path) => {
                const coordinates = path.map((coord) => [Number(coord[0]), Number(coord[1])]);
                if (coordinates.length < 2) return;

                coordinates.forEach((coord) => latLngs.push(coord));
                const pl = L.polyline(coordinates, {
                  color,
                  weight,
                  opacity,
                  dashArray,
                  lineCap: 'round',
                  lineJoin: 'round'
                }).addTo(map).bindTooltip(
                  (segment.sentido ? segment.sentido + ' · ' : '') +
                  'SRE ' + (segment.sre || '-') +
                  ' · Segmento ' + segment.segment_id +
                  ' · km ' + formatKm(segment.km_inicial) +
                  ' - ' + formatKm(segment.km_final) +
                  ' · IAP ' + Number(segment.iap).toFixed(2) +
                  ' · $tooltip_label ' + colorKey +
                  (segment._custo_sre_label ? ' · Custo ' + segment._custo_sre_label : '') +
                  (attended ? '' : ' · $unattended_label')
                ).on('click', (e) => window.__openTrecho(e.latlng.lat, e.latlng.lng, segment.detail));
                drawn.push({ polyline: pl, coords: coordinates, side });
              });
            });

            const bounds = L.latLngBounds(latLngs);
            map.fitBounds(bounds, { padding: [34, 34] });

            // Recalcula o offset a cada zoom: GAP_M é fixo no terreno, mas o
            // equivalente em pixels muda com o zoom.
            function redrawOffsets() {
              drawn.forEach((d) => { if (d.side) d.polyline.setLatLngs(offsetPathPixels(d.coords, d.side)); });
            }
            redrawOffsets();
            map.on('zoomend', redrawOffsets);

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
            legend_foot_block=legend_foot_block,
            legend_title=legend_title,
            legend_items_html=legend_items_html,
            color_key_js=color_key_js,
            tooltip_label=tooltip_label,
            unattended_color=unattended_color,
            unattended_opacity=0.96 if unattended_color == "#ef4444" else 0.62,
            unattended_weight=5 if unattended_color == "#ef4444" else 2.5,
            unattended_dash="null" if unattended_dash is None else json.dumps(unattended_dash),
            unattended_label=unattended_label,
            # Afastamento entre sentidos em METROS de terreno (segue a rodovia em
            # qualquer zoom), com piso em pixels para não colapsarem numa linha só.
            gap_m=float(gap_m),
            min_gap_px=float(min_gap_px),
            sv_css=SV_CSS,
            sv_modal=SV_MODAL_HTML,
            sv_js=sv_init_js(),
        ),
        height=456,
        scrolling=False,
    )
