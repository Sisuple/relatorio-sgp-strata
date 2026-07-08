"""Drawer deslizante (da esquerda) com os dados do trecho + Street View do Google.

Ao clicar num segmento do mapa Leaflet (que roda em iframe via `components.html`),
abre um painel que desliza da esquerda mostrando: Rodovia, Situação, Solução
recomendada e Extensão — e, abaixo, o Street View embutido (Maps Embed API) no
ponto clicado. A chave vem de `GOOGLE_MAPS_API_KEY` (Maps Embed API habilitada).

Uso no template (string.Template) de cada mapa:
- `$sv_css`   dentro do <style>
- `$sv_modal` dentro de .map-card
- `$sv_js`    antes de fechar o <script> principal
E na polyline: `.on('click', (e) => window.__openTrecho(e.latlng.lat, e.latlng.lng, s.detail))`
onde `s.detail = {"title": "...", "rows": [["Rodovia","BR-421"], ...]}`.
"""
from __future__ import annotations

import json
import os
import re


# Fragmento de CSS do drawer + Street View, injetado em $sv_css no <style> de cada
# mapa. Classes .td-* : backdrop (fundo), drawer (painel deslizante), head/rows
# (dados do trecho) e sv-wrap/frame (iframe do Street View). A animação de abrir
# é o transform translateX(-100% -> 0) em .td-drawer.open.
SV_CSS = """
            .td-backdrop { display: none; position: absolute; inset: 0; z-index: 1190; background: rgba(3,8,12,.35); }
            .td-backdrop.open { display: block; }
            .td-drawer { position: absolute; top: 0; bottom: 0; left: 0; z-index: 1200; width: min(420px, 92%); background: #0b1d28; border-right: 1px solid #1d3848; box-shadow: 24px 0 60px rgba(0,0,0,.45); transform: translateX(-100%); transition: transform .28s cubic-bezier(.22,.61,.36,1); display: flex; flex-direction: column; }
            .td-drawer.open { transform: translateX(0); }
            .td-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 14px 12px; border-bottom: 1px solid #1d3848; flex: none; }
            .td-title { color: #f4f7fb; font-size: 13px; font-weight: 850; line-height: 1.25; overflow: hidden; }
            .td-close { width: 30px; height: 30px; flex: none; border: 0; border-radius: 8px; background: rgba(148,163,184,.16); color: #f4f7fb; font-size: 20px; line-height: 1; cursor: pointer; }
            .td-close:hover { background: rgba(148,163,184,.32); }
            .td-rows { padding: 12px 14px 4px; display: grid; gap: 11px; flex: none; }
            .td-row { display: grid; gap: 2px; }
            .td-k { color: #9aa8b3; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; font-weight: 800; }
            .td-v { color: #e5edf3; font-size: 14px; font-weight: 700; }
            .td-sv-wrap { flex: 1; min-height: 180px; margin: 10px 14px 14px; border-radius: 10px; overflow: hidden; border: 1px solid #1d3848; background: #06121a; }
            .td-frame { border: 0; width: 100%; height: 100%; display: block; }
            .td-empty { display: grid; place-items: center; height: 100%; color: #9aa8b3; font-size: 12px; text-align: center; padding: 0 18px; }
"""

# Marcação HTML do drawer, injetada em $sv_modal dentro de .map-card. É a casca
# vazia (título, lista de linhas e iframe) — preenchida em runtime pelo JS de
# sv_init_js quando um segmento é clicado. IDs td-* são os hooks usados pelo JS.
SV_MODAL_HTML = """
            <div id="td-backdrop" class="td-backdrop"></div>
            <aside id="td-drawer" class="td-drawer" role="dialog" aria-modal="true" aria-label="Detalhes do trecho">
              <div class="td-head">
                <div id="td-title" class="td-title">Trecho</div>
                <button id="td-close" class="td-close" type="button" aria-label="Fechar">&times;</button>
              </div>
              <div id="td-rows" class="td-rows"></div>
              <div class="td-sv-wrap">
                <iframe id="td-frame" class="td-frame" allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                <div id="td-empty" class="td-empty" style="display:none"></div>
              </div>
            </aside>
"""


def get_api_key() -> str:
    """Lê a chave do Google Maps de GOOGLE_MAPS_API_KEY no ambiente (.env).

    Devolve string vazia se não estiver configurada — nesse caso o drawer mostra
    um aviso no lugar do Street View (ver sv_init_js).
    """
    return (os.getenv("GOOGLE_MAPS_API_KEY", "") or "").strip()


def clean(value, default: str = "—") -> str:
    """Normaliza valores para exibição: trata None, NaN (float != self) e strings vazias."""
    if value is None:
        return default
    if isinstance(value, float) and value != value:  # NaN
        return default
    text = str(value).strip()
    return text if text and text.lower() != "nan" else default


def road_from_sre(sre: str | None) -> str:
    """Deriva a rodovia (BR-XXX) a partir do código SRE (ex.: '421BRO0010' -> 'BR-421')."""
    m = re.match(r"\s*(\d{2,3})", str(sre or ""))
    return f"BR-{m.group(1)}" if m else (str(sre or "—"))


def sv_init_js(api_key: str | None = None) -> str:
    """JS que define window.__openTrecho(lat, lng, detail) e fecha o drawer."""
    key = api_key if api_key is not None else get_api_key()
    # json.dumps serializa a chave como literal JS já com aspas e escapes seguros.
    key_literal = json.dumps(key)
    # IIFE que fecha sobre os elementos do drawer e expõe window.__openTrecho.
    # As linhas abaixo são concatenação implícita de literais → string JS única.
    return (
        "(function(){"
        "  var KEY = " + key_literal + ";"
        "  var drawer = document.getElementById('td-drawer');"
        "  var backdrop = document.getElementById('td-backdrop');"
        "  var titleEl = document.getElementById('td-title');"
        "  var rowsEl = document.getElementById('td-rows');"
        "  var frame = document.getElementById('td-frame');"
        "  var empty = document.getElementById('td-empty');"
        "  if (!drawer) return;"
        # esc(): escapa HTML no lado JS antes de injetar detail.title/rows via innerHTML.
        "  function esc(v){ return String(v == null ? '' : v).replace(/[&<>\"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]; }); }"
        # Entrada global chamada no .on('click') das polylines de cada mapa:
        # recebe (lat, lng, detail) e abre o drawer preenchido no ponto clicado.
        "  window.__openTrecho = function(lat, lng, detail){"
        "    detail = detail || {};"
        "    titleEl.textContent = detail.title || 'Trecho';"
        "    var rows = detail.rows || [];"
        "    rowsEl.innerHTML = rows.map(function(r){"
        "      return '<div class=\"td-row\"><span class=\"td-k\">' + esc(r[0]) + '</span><span class=\"td-v\">' + esc(r[1]) + '</span></div>';"
        "    }).join('');"
        # Coordenada "lat,lng" com 6 casas para a URL do Street View.
        "    var loc = Number(lat).toFixed(6) + ',' + Number(lng).toFixed(6);"
        # Sem chave: esconde o iframe e mostra o aviso de configuração (empty state).
        "    if (!KEY){"
        "      frame.style.display = 'none'; frame.removeAttribute('src');"
        "      empty.style.display = 'grid';"
        "      empty.textContent = 'Configure GOOGLE_MAPS_API_KEY no .env (Maps Embed API) para o Street View.';"
        "    } else {"
        # Com chave: aponta o iframe para a Maps Embed API (streetview) no ponto; fov=90 = zoom padrão.
        "      empty.style.display = 'none'; frame.style.display = 'block';"
        "      frame.src = 'https://www.google.com/maps/embed/v1/streetview?key=' + KEY + '&location=' + loc + '&fov=90';"
        "    }"
        "    drawer.classList.add('open'); backdrop.classList.add('open');"
        "  };"
        # Fecha o drawer e limpa o src do iframe (para o Street View parar de carregar).
        "  function closeTrecho(){ drawer.classList.remove('open'); backdrop.classList.remove('open'); frame.removeAttribute('src'); }"
        "  document.getElementById('td-close').addEventListener('click', closeTrecho);"
        "  backdrop.addEventListener('click', closeTrecho);"
        "  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeTrecho(); });"
        "})();"
    )
