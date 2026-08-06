"""
Gera o PDF do Plano de Trabalho do Cenário Econômico.

Monta um relatório com cabeçalho, KPIs (necessidade, orçamento, cobertura,
SNV atendidos, extensão), mapa esquemático dos trechos atendidos, gráficos de
custo (por solução e por ano) e a tabela dos trechos atendidos.

Tudo é desenhado com reportlab (Python puro) — o mapa é vetorial, usando a
geometria real dos trechos (sem depender de tiles/imagens externas).
"""

from __future__ import annotations

import math
import re
from io import BytesIO
from typing import Any, Callable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Tema do relatório (claro, próprio para impressão).
_INK = HexColor("#16242e")
_MUTED = HexColor("#5b6b77")
_ACCENT = HexColor("#0e7c8a")
_LINE = HexColor("#d4dde3")
_PANEL = HexColor("#f3f6f8")
_GREY_LINE = HexColor("#9aa8b3")

_PAGE_W, _PAGE_H = A4
_CONTENT_W = _PAGE_W - 32 * mm  # margens de 16mm
# Até esta quantidade de linhas, a tabela cabe numa página e é mantida inteira
# (KeepTogether) em vez de quebrar deixando poucas linhas órfãs na página seguinte.
_MAX_KEEP_ROWS = 22


def first_available_year_budget_items(
    budget_items: pd.DataFrame | None,
) -> tuple[int | None, pd.DataFrame | None]:
    """Recorta o orçamento para o menor ano válido disponível."""
    if budget_items is None:
        return None, None
    if budget_items.empty or "Ano" not in budget_items.columns:
        return None, budget_items.copy()

    years = pd.to_numeric(budget_items["Ano"], errors="coerce")
    valid_years = years.dropna()
    if valid_years.empty:
        return None, budget_items.iloc[0:0].copy()

    first_year = int(valid_years.min())
    return first_year, budget_items.loc[years == first_year].copy()


def _money(value: float) -> str:
    """Formata reais de forma compacta: 'R$ 1.2 mi', 'R$ 350 mil' ou 'R$ 42'."""
    value = float(value or 0)
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi"
    if value >= 1_000:
        return f"R$ {value / 1_000:.0f} mil"
    return f"R$ {value:.0f}"


def _km(value: float) -> str:
    """Formata uma extensão em km com uma casa decimal (ex.: '12.3 km')."""
    return f"{float(value or 0):.1f} km"


def _truncate(text: str, limit: int) -> str:
    """Limita ``text`` a ``limit`` caracteres, acrescentando '…' se estourar."""
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _styles() -> dict[str, ParagraphStyle]:
    """Estilos de parágrafo do relatório: título, subtítulo, seção e texto pequeno.

    Duas decisões tipográficas que endereçam o título "destoando do layout":

    1) O estilo `Title` do reportlab vem com `alignment=TA_CENTER`. O título ficava
       CENTRALIZADO enquanto todo o resto do relatório (subtítulo, KPIs, seções,
       tabelas) é alinhado à esquerda. Aqui ele é forçado à esquerda.
    2) As seções eram Heading2 12pt em quase-preto — do mesmo peso do título da
       capa, competindo com ele. Passam a caixa alta 9pt no tom de acento, que é a
       mesma linguagem dos rótulos dos KPIs ("NECESSIDADE TOTAL"), um degrau
       abaixo do título. Ver também `_section`.
    """
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "wp_title", parent=base["Title"], fontSize=19, leading=22,
            alignment=TA_LEFT, textColor=_INK, spaceAfter=3,
        ),
        "sub": ParagraphStyle("wp_sub", parent=base["Normal"], fontSize=9.5, leading=13, textColor=_MUTED, spaceAfter=2),
        "h2": ParagraphStyle(
            "wp_h2", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9,
            leading=11, textColor=_ACCENT, spaceBefore=12, spaceAfter=3,
        ),
        "small": ParagraphStyle("wp_small", parent=base["Normal"], fontSize=8, leading=10, textColor=_MUTED),
    }


def _section(title: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Marcador de seção: título em caixa alta + fio fino, como bloco de 2 peças.

    O fio separa as seções, que antes só flutuavam no branco. Devolve uma lista
    para ser espalhada (`*_section(...)`) na story ou dentro de um KeepTogether.
    """
    rule = Drawing(_CONTENT_W, 3)
    rule.add(Rect(0, 1, _CONTENT_W, 0.5, fillColor=_LINE, strokeColor=None))
    return [Paragraph(title.upper(), styles["h2"]), rule, Spacer(1, 5)]


def _kpi_table(kpis: list[tuple[str, str]]) -> Table:
    """KPIs em uma faixa: valor (grande) sobre o rótulo (pequeno)."""
    values = [k[1] for k in kpis]
    labels = [k[0] for k in kpis]
    table = Table([values, labels], colWidths=[_CONTENT_W / len(kpis)] * len(kpis))
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 13),
                ("TEXTCOLOR", (0, 0), (-1, 0), _ACCENT),
                ("FONTSIZE", (0, 1), (-1, 1), 7.5),
                ("TEXTCOLOR", (0, 1), (-1, 1), _MUTED),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
                ("BACKGROUND", (0, 0), (-1, -1), _PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
                ("LINEAFTER", (0, 0), (-2, -1), 0.6, _LINE),
            ]
        )
    )
    return table


def _map_drawing(
    segments: list[dict],
    attended_ids: set[int],
    class_colors: dict[str, str],
    width: float = _CONTENT_W,
    height: float = 250,
) -> Drawing:
    """Desenha o mapa esquemático (vetorial) dos trechos do cenário.

    Usa a geometria real (lat/lon) de cada segmento e projeta num plano com
    correção de longitude por ``cos(latitude média)`` (aproximação
    equirretangular) para não distorcer as distâncias. Os segmentos NÃO
    atendidos são desenhados primeiro em cinza e os atendidos por cima,
    coloridos pela classe IAP, para ficarem em destaque.

    ``attended_ids`` é o conjunto de ``segment_id`` atendidos; ``class_colors``
    mapeia classe IAP -> cor hex.
    """
    # Junta todos os pontos (lat, lon) de todos os caminhos para achar a bbox.
    coords = [(la, lo) for seg in segments for path in seg.get("paths", []) for (la, lo) in path]
    if not coords:
        d = Drawing(width, 60)
        d.add(Rect(0, 0, width, 60, fillColor=HexColor("#fbfdfe"), strokeColor=_LINE, strokeWidth=0.8))
        d.add(String(width / 2, 27, "Sem geometria para o mapa", fontSize=9, textAnchor="middle", fillColor=_MUTED))
        return d

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    mean_lat = (lat_min + lat_max) / 2
    # 1 grau de longitude "encurta" longe do equador; corrige por cos(lat média).
    cos_lat = math.cos(math.radians(mean_lat)) or 1e-6

    pad = 16
    dlat = (lat_max - lat_min) or 1e-6
    dlon = ((lon_max - lon_min) or 1e-6) * cos_lat
    # Escala única (mantém proporção) que faz a bbox caber na área útil c/ padding.
    scale = min((width - 2 * pad) / dlon, (height - 2 * pad) / dlat)
    map_w, map_h = dlon * scale, dlat * scale

    # O QUADRO acompanha o traçado, em vez de ser sempre 504x250: um trecho
    # estreito (quase vertical, como a BR-174) desenhava uma linha fininha no meio
    # de uma moldura larga e vazia — a maior fonte de "espaço jogado" do relatório.
    # A largura encolhe até o traçado + padding; a altura nunca passa do teto
    # recebido, e há um piso para o quadro não virar uma tira.
    frame_w = min(width, max(map_w + 2 * pad, 200.0))
    frame_h = min(height, max(map_h + 2 * pad, 120.0))
    d = Drawing(frame_w, frame_h)
    # Drawing nasce com hAlign='LEFT': sem isto, um quadro estreito (traçado quase
    # vertical) ficaria encostado na margem esquerda da página.
    d.hAlign = "CENTER"
    d.add(Rect(0, 0, frame_w, frame_h, fillColor=HexColor("#fbfdfe"), strokeColor=_LINE, strokeWidth=0.8))
    ox, oy = (frame_w - map_w) / 2, (frame_h - map_h) / 2  # offsets p/ centralizar

    def to_xy(la: float, lo: float) -> tuple[float, float]:
        """Projeta (lat, lon) para coordenadas de tela (x, y) do Drawing."""
        return ox + (lo - lon_min) * cos_lat * scale, oy + (la - lat_min) * scale

    # Desenha primeiro os não atendidos (cinza) e depois os atendidos (coloridos).
    for attended_pass in (False, True):
        for seg in segments:
            is_att = int(seg.get("segment_id", -1)) in attended_ids
            if is_att != attended_pass:
                continue
            color = class_colors.get(seg.get("classe_iap"), "#fff200") if is_att else "#c2ccd3"
            stroke = 1.8 if is_att else 1.0
            for path in seg.get("paths", []):
                pts: list[float] = []
                for (la, lo) in path:
                    x, y = to_xy(la, lo)
                    pts.extend([x, y])
                if len(pts) >= 4:
                    d.add(PolyLine(pts, strokeColor=HexColor(color), strokeWidth=stroke, strokeLineCap=1, strokeLineJoin=1))
    return d


def _legend_drawing(items: list[tuple[str, str]], width: float = _CONTENT_W) -> Drawing:
    """Legenda horizontal: para cada (rótulo, cor), um quadradinho + texto lado a lado."""
    height = 16
    d = Drawing(width, height)
    x = 0.0
    for label, color in items:
        d.add(Rect(x, 4, 9, 9, fillColor=HexColor(color), strokeColor=None))
        d.add(String(x + 13, 5, label, fontSize=7.5, fillColor=_MUTED))
        # Avança x pela largura estimada do item (texto ~4.6px por caractere).
        x += 16 + len(label) * 4.6 + 14
    return d




def _hbar_chart(
    data: list[tuple[str, float, str]],
    value_fmt: Callable[[float], str],
    width: float = _CONTENT_W,
) -> Drawing:
    """Gráfico de barras horizontais.

    Cada item de ``data`` é (rótulo, valor, cor). Por linha desenha: rótulo à
    esquerda, uma trilha de fundo, a barra preenchida proporcional ao maior
    valor e o valor formatado por ``value_fmt`` à direita.
    """
    rows = len(data)
    row_h = 22
    height = max(rows * row_h + 6, row_h)
    d = Drawing(width, height)
    if not data:
        return d

    # Barras proporcionais ao maior valor; larguras fixas p/ rótulo e valor.
    # Rótulos alinhados à ESQUERDA (eram alinhados à direita numa coluna de 150pt,
    # o que deixava ~110pt de vazio antes de rótulos curtos como "Reforço") e
    # coluna do valor mais justa — sobra tudo para a trilha da barra.
    max_val = max((v for _, v, _ in data), default=1.0) or 1.0
    label_w = 132.0
    val_w = 74.0
    track_x = label_w
    track_w = max(width - label_w - val_w, 40)

    y = height - 18
    for label, value, color in data:
        d.add(String(0, y + 3, _truncate(label, 28), fontSize=8, fillColor=_INK))
        d.add(Rect(track_x, y, track_w, 12, fillColor=_PANEL, strokeColor=None))  # trilha de fundo
        # Barra preenchida: mínimo de 1px para valores ~0 ainda ficarem visíveis.
        d.add(Rect(track_x, y, max(track_w * float(value) / max_val, 1.0), 12, fillColor=HexColor(color), strokeColor=None))
        d.add(String(track_x + track_w + 8, y + 3, value_fmt(value), fontSize=8, fillColor=_MUTED))
        y -= row_h  # desce uma linha
    return d


def _short_scenario(scenario_label: Any, road: str) -> str:
    """Encurta o nome do cenário para o cabeçalho do PDF.

    O nome vem cru do banco — "Rodovia: BR-174 - Análise dos Segmentos Homogêneos:
    BR-174 (SH) - Pista: CRESCENTE - Método de Análise: Paragon" — o que repetia a
    rodovia 3x, estourava para duas linhas e enterrava o que interessa. Guarda só
    o que identifica o cenário: segmentação, sentido e gatilho.
    """
    text = str(scenario_label or "").strip()
    if not text:
        return ""
    low = text.lower()
    parts: list[str] = []

    segmentacao = re.search(r"\((SH|Fixa|\d+\s*km)\)", text, re.I)
    if segmentacao:
        parts.append(segmentacao.group(1).strip())
    elif "segmentos homog" in low:
        parts.append("SH")
    elif re.search(r"\bfixa\b", low):
        parts.append("Fixa")

    trecho = re.search(r"\b[A-Z]{2,3}-?\d+[_-](?:trecho\s+)?([IVXLC]+|\d+)\b", text, re.I)
    if trecho:
        parts.append(f"trecho {trecho.group(1).upper()}")

    if "decrescente" in low:
        parts.append("DECRESCENTE")
    elif "crescente" in low:
        parts.append("CRESCENTE")
    elif re.search(r"\btodos\b", low):
        parts.append("TODOS")

    variante = re.search(r"\b(IRI)\s*(\d+(?:[.,]\d+)?)", text, re.I)
    if variante:
        parts.append(f"{variante.group(1).upper()} {variante.group(2)}")

    gatilho = re.search(r"(GATILHO\s+[A-Z0-9._/-]+)", text, re.I)
    if gatilho:
        parts.append(gatilho.group(1).upper())

    if parts:
        return " · ".join(dict.fromkeys(parts))
    # Sem nenhum token reconhecido: tira ao menos os prefixos e a rodovia repetida.
    limpo = re.sub(r"^Rodovia:\s*", "", text, flags=re.I)
    limpo = re.sub(rf"\b{re.escape(str(road))}\b\s*-?\s*", "", limpo).strip(" -·")
    return _truncate(limpo or text, 70)


def _direction_label(sentido: Any) -> str:
    """Reduz o valor de `Sentido` (nome completo do cenário) a apenas
    'Crescente' ou 'Decrescente' — o resto do nome do cenário não interessa
    ao PDF. Ordem importa: 'decrescente' contém 'crescente' como substring."""
    low = str(sentido or "").strip().lower()
    if "decrescente" in low:
        return "Decrescente"
    if "crescente" in low:
        return "Crescente"
    return str(sentido or "")


def _snv_table(attended: pd.DataFrame) -> Table:
    """Tabela dos trechos atendidos: ranking, SRE, km inicial/final, extensão, IPI e custo.

    O km inicial/final é obrigatório para identificar a linha: cada linha é UM
    segmento, e o mesmo SRE aparece várias vezes (a tabela é por segmento, não por
    SRE). Sem o km, duas linhas do mesmo SRE ficavam indistinguíveis.
    """
    header = ["#", "SRE", "Sentido", "Km Inicial", "Km Final", "Extensão", "IPI", "Custo"]
    rows: list[list[Any]] = [header]
    for i, r in enumerate(attended.to_dict("records"), start=1):
        ipi = r.get("IPI", r.get("IPT", 0))
        rows.append(
            [
                str(i),
                _truncate(str(r.get("SNV", "")), 14),
                _truncate(_direction_label(r.get("Sentido", "")), 18),
                f"{float(r.get('Km Inicial', 0) or 0):.2f}",
                f"{float(r.get('Km Final', 0) or 0):.2f}",
                _km(r.get("Extensão", 0)),
                f"{float(ipi or 0):.2f}",
                _money(r.get("Custo econômico", 0)),
            ]
        )
    col_w = [22, 78, 96, 48, 48, 54, 42, None]
    used = sum(w for w in col_w if w)
    col_w[-1] = _CONTENT_W - used
    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), _INK),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _PANEL]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, _LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _segments_detail_table(detail: pd.DataFrame) -> Table:
    """Tabela de ordem de serviço: por segmento, km inicial/final e intervenção."""
    header = ["SRE", "Sentido", "Km Inicial", "Km Final", "Extensão", "Intervenção a executar", "Custo"]
    rows: list[list[Any]] = [header]
    for r in detail.to_dict("records"):
        rows.append(
            [
                _truncate(str(r.get("SNV", "")), 14),
                _truncate(_direction_label(r.get("Sentido", "")), 22),
                f"{float(r.get('Km Inicial', 0) or 0):.2f}",
                f"{float(r.get('Km Final', 0) or 0):.2f}",
                _km(r.get("Extensão", 0)),
                _truncate(str(r.get("Intervenção", "")), 36),
                _money(r.get("Custo", 0)),
            ]
        )
    # Mesmas larguras da tabela de trechos atendidos nas colunas equivalentes
    # (SRE, Sentido, km, extensão), para as duas tabelas ficarem alinhadas em vez
    # de cada uma ter a sua medida. A folga vai para "Intervenção a executar",
    # que é a única coluna de texto livre.
    col_w = [78, 96, 48, 48, 54, None, 74]
    col_w[5] = _CONTENT_W - sum(w for w in col_w if w)
    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("TEXTCOLOR", (0, 1), (-1, -1), _INK),
                ("ALIGN", (2, 0), (4, -1), "RIGHT"),
                ("ALIGN", (6, 0), (6, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _PANEL]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, _LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                # Sem RIGHTPADDING, o valor de custo (alinhado à direita) encostava
                # na borda e colava no texto da coluna anterior.
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _page_footer(canvas, doc) -> None:
    """Rodapé de toda página: linha divisória, crédito à esquerda e nº da página à direita."""
    canvas.saveState()
    canvas.setStrokeColor(_LINE)
    canvas.line(16 * mm, 12 * mm, _PAGE_W - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(_MUTED)
    canvas.drawString(16 * mm, 8 * mm, "SIGMA · Plano de trabalho")
    canvas.drawRightString(_PAGE_W - 16 * mm, 8 * mm, f"Página {doc.page}")
    canvas.restoreState()


def build_work_plan_pdf(
    *,
    road: str,
    scenario_label: str,
    generated_at: str,
    annual_budget_mi: int,
    horizon: int,
    top_label: str,
    metrics: dict,
    annual_coverage: float,
    attended_snv_table: pd.DataFrame,
    scope_snv: int,
    attended_km: float,
    budget_items: pd.DataFrame | None,
    segments: list[dict],
    attended_ids: set[int],
    class_colors: dict[str, str],
    solution_color: Callable[[str], str],
    segments_detail: pd.DataFrame | None = None,
) -> bytes:
    """Monta o PDF do Plano de Trabalho e devolve os bytes prontos p/ download.

    Recebe tudo já calculado pela camada de serviço (argumentos keyword-only):
    - identificação: ``road``, ``scenario_label``, ``generated_at``;
    - premissas: ``annual_budget_mi`` (orçamento anual em milhões), ``horizon``
      (anos), ``top_label`` (descrição dos trechos);
    - números: ``metrics`` (KPIs, ex. total_need), ``annual_coverage`` (%),
      ``scope_snv``, ``attended_km``;
    - tabelas (pandas): ``attended_snv_table``, ``budget_items``,
      ``segments_detail``;
    - mapa: ``segments`` (geometria), ``attended_ids``, ``class_colors``;
    - cores: ``solution_color`` (mapeia solução -> cor hex).

    As seções são montadas nesta ordem: cabeçalho, faixa de KPIs, mapa +
    legenda, gráficos de custo (por solução e por ano), tabela de SNV atendidos
    e detalhamento por segmento (ordem de serviço). As seções condicionais só
    aparecem quando os DataFrames correspondentes têm dados.
    """
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="Plano de Trabalho — Paragon",
    )

    story: list[Any] = []
    # Cabeçalho: rodovia + cenário curto na 1ª linha; premissas na 2ª. O orçamento
    # anual saiu daqui porque já é um dos KPIs logo abaixo — repetido em duas
    # linhas seguidas, era ruído.
    story.append(Paragraph("Plano de Trabalho", styles["title"]))
    horizon_label = "1 ano" if int(horizon) == 1 else f"{int(horizon)} anos"
    cenario_curto = _short_scenario(scenario_label, road)
    story.append(
        Paragraph(
            f"<b>{road}</b>" + (f" &nbsp;·&nbsp; {cenario_curto}" if cenario_curto else ""),
            styles["sub"],
        )
    )
    story.append(
        Paragraph(
            f"Horizonte: <b>{horizon_label}</b> &nbsp;·&nbsp; Trechos: <b>{top_label}</b>"
            f" &nbsp;·&nbsp; gerado em {generated_at}",
            styles["sub"],
        )
    )
    # Régua de acento fechando o cabeçalho: separa a identificação do conteúdo
    # sem custar altura (2pt) nem depender de mais um título.
    regua = Drawing(_CONTENT_W, 3)
    regua.add(Rect(0, 1, _CONTENT_W, 1.6, fillColor=_ACCENT, strokeColor=None))
    story.append(Spacer(1, 6))
    story.append(regua)
    story.append(Spacer(1, 8))

    attended_count = int(len(attended_snv_table)) if attended_snv_table is not None else 0
    story.append(
        _kpi_table(
            [
                ("NECESSIDADE TOTAL", _money(metrics.get("total_need", 0))),
                ("ORÇAMENTO ANUAL", _money(annual_budget_mi * 1_000_000)),
                ("COBERTURA", f"{annual_coverage:.0f}%"),
                ("SNV ATENDIDOS", f"{attended_count}/{scope_snv}"),
                ("EXTENSÃO ATENDIDA", _km(attended_km)),
            ]
        )
    )

    # --- Mapa dos trechos atendidos ---
    classes_presentes = list(
        dict.fromkeys(
            s.get("classe_iap")
            for s in segments
            if int(s.get("segment_id", -1)) in attended_ids and s.get("classe_iap")
        )
    )
    legenda = [(c, class_colors.get(c, "#fff200")) for c in classes_presentes]
    legenda.append(("Não atendido", "#c2ccd3"))
    # KeepTogether: título, mapa e legenda formam um bloco só — sem isso a legenda
    # podia cair sozinha na página seguinte, longe do mapa que ela explica.
    story.append(
        KeepTogether([
            *_section("Mapa dos trechos atendidos", styles),
            _map_drawing(segments, attended_ids, class_colors),
            Spacer(1, 6),
            _legend_drawing(legenda),
        ])
    )

    # --- Gráficos de custo (a partir do orçamento detalhado) ---
    if budget_items is not None and not budget_items.empty:
        by_sol = (
            budget_items.groupby("Solução", as_index=False)["Custo"].sum().sort_values("Custo", ascending=False)
        )
        sol_data = [(str(r["Solução"]), float(r["Custo"]), solution_color(str(r["Solução"]))) for r in by_sol.to_dict("records")]
        if sol_data:
            story.append(
                KeepTogether([
                    *_section("Custos por solução", styles),
                    _hbar_chart(sol_data, _money),
                ])
            )

        by_year = budget_items.groupby("Ano", as_index=False)["Custo"].sum().sort_values("Ano")
        year_data = [(str(int(r["Ano"])), float(r["Custo"]), "#0e7c8a") for r in by_year.to_dict("records")]
        if year_data:
            story.append(
                KeepTogether([
                    *_section("Custo por ano", styles),
                    _hbar_chart(year_data, _money),
                ])
            )

    # --- Tabela dos trechos atendidos ---
    # Tabelas curtas viajam inteiras para a página seguinte em vez de deixar duas
    # linhas órfãs com o cabeçalho repetido (era o caso do print: 3 linhas na
    # página 1 e 2 na página 2). Acima de _MAX_KEEP_ROWS a tabela é longa demais
    # para caber numa página só e aí a divisão natural do reportlab é o certo.
    if attended_snv_table is not None and not attended_snv_table.empty:
        bloco = [
            *_section("Trechos atendidos (ordem de prioridade)", styles),
            _snv_table(attended_snv_table),
        ]
        story.extend(
            [KeepTogether(bloco)] if len(attended_snv_table) <= _MAX_KEEP_ROWS else bloco
        )

    # --- Detalhamento por segmento (ordem de serviço) ---
    if segments_detail is not None and not segments_detail.empty:
        bloco = [
            *_section("Detalhamento por segmento — ordem de serviço", styles),
            Paragraph(
                "Trechos que precisam de intervenção, com km inicial/final e a solução a executar.",
                styles["small"],
            ),
            Spacer(1, 4),
            _segments_detail_table(segments_detail),
        ]
        story.extend(
            [KeepTogether(bloco)] if len(segments_detail) <= _MAX_KEEP_ROWS else bloco
        )

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
