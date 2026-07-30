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
from io import BytesIO
from typing import Any, Callable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.platypus import (
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
    """Estilos de parágrafo do relatório: título, subtítulo, H2 e texto pequeno."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("wp_title", parent=base["Title"], fontSize=18, textColor=_INK, spaceAfter=2),
        "sub": ParagraphStyle("wp_sub", parent=base["Normal"], fontSize=9.5, textColor=_MUTED, spaceAfter=2),
        "h2": ParagraphStyle("wp_h2", parent=base["Heading2"], fontSize=12, textColor=_INK, spaceBefore=14, spaceAfter=6),
        "small": ParagraphStyle("wp_small", parent=base["Normal"], fontSize=8, textColor=_MUTED),
    }


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
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=HexColor("#fbfdfe"), strokeColor=_LINE, strokeWidth=0.8))

    # Junta todos os pontos (lat, lon) de todos os caminhos para achar a bbox.
    coords = [(la, lo) for seg in segments for path in seg.get("paths", []) for (la, lo) in path]
    if not coords:
        d.add(String(width / 2, height / 2, "Sem geometria para o mapa", fontSize=9, textAnchor="middle", fillColor=_MUTED))
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
    ox, oy = (width - map_w) / 2, (height - map_h) / 2  # offsets p/ centralizar

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
    max_val = max((v for _, v, _ in data), default=1.0) or 1.0
    label_w = 150.0
    val_w = 110.0
    track_x = label_w
    track_w = max(width - label_w - val_w, 40)

    y = height - 18
    for label, value, color in data:
        d.add(String(label_w - 8, y + 3, _truncate(label, 30), fontSize=8, textAnchor="end", fillColor=_INK))
        d.add(Rect(track_x, y, track_w, 12, fillColor=_PANEL, strokeColor=None))  # trilha de fundo
        # Barra preenchida: mínimo de 1px para valores ~0 ainda ficarem visíveis.
        d.add(Rect(track_x, y, max(track_w * float(value) / max_val, 1.0), 12, fillColor=HexColor(color), strokeColor=None))
        d.add(String(track_x + track_w + 8, y + 3, value_fmt(value), fontSize=8, fillColor=_MUTED))
        y -= row_h  # desce uma linha
    return d


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
    """Tabela dos SNV atendidos: ranking, SRE, extensão, IPI e custo."""
    header = ["#", "SRE", "Sentido", "Extensão", "IPI", "Custo"]
    rows: list[list[Any]] = [header]
    for i, r in enumerate(attended.to_dict("records"), start=1):
        ipi = r.get("IPI", r.get("IPT", 0))
        rows.append(
            [
                str(i),
                _truncate(str(r.get("SNV", "")), 16),
                _truncate(_direction_label(r.get("Sentido", "")), 24),
                _km(r.get("Extensão", 0)),
                f"{float(ipi or 0):.2f}",
                _money(r.get("Custo econômico", 0)),
            ]
        )
    col_w = [22, 92, 132, 62, 48, None]
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
    col_w = [72, 112, 48, 48, 52, None, 62]
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
    canvas.drawString(16 * mm, 8 * mm, "DNIT · Painel de Pavimentos Paragon — Plano de Trabalho")
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
    story.append(Paragraph("Plano de Trabalho", styles["title"]))
    story.append(Paragraph(f"{road} · Cenário {scenario_label} · gerado em {generated_at}", styles["sub"]))
    horizon_label = "1 ano" if int(horizon) == 1 else f"{int(horizon)} anos"
    story.append(
        Paragraph(
            f"Orçamento anual: <b>{_money(annual_budget_mi * 1_000_000)}</b> &nbsp;·&nbsp; "
            f"Horizonte: <b>{horizon_label}</b> &nbsp;·&nbsp; Trechos: <b>{top_label}</b>",
            styles["sub"],
        )
    )
    story.append(Spacer(1, 10))

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
    story.append(Paragraph("Mapa dos trechos atendidos", styles["h2"]))
    story.append(_map_drawing(segments, attended_ids, class_colors))
    classes_presentes = list(
        dict.fromkeys(
            s.get("classe_iap")
            for s in segments
            if int(s.get("segment_id", -1)) in attended_ids and s.get("classe_iap")
        )
    )
    legenda = [(c, class_colors.get(c, "#fff200")) for c in classes_presentes]
    legenda.append(("Não atendido", "#c2ccd3"))
    story.append(Spacer(1, 6))
    story.append(_legend_drawing(legenda))

    # --- Gráficos de custo (a partir do orçamento detalhado) ---
    if budget_items is not None and not budget_items.empty:
        by_sol = (
            budget_items.groupby("Solução", as_index=False)["Custo"].sum().sort_values("Custo", ascending=False)
        )
        sol_data = [(str(r["Solução"]), float(r["Custo"]), solution_color(str(r["Solução"]))) for r in by_sol.to_dict("records")]
        if sol_data:
            story.append(Paragraph("Custos por solução", styles["h2"]))
            story.append(_hbar_chart(sol_data, _money))

        by_year = budget_items.groupby("Ano", as_index=False)["Custo"].sum().sort_values("Ano")
        year_data = [(str(int(r["Ano"])), float(r["Custo"]), "#0e7c8a") for r in by_year.to_dict("records")]
        if year_data:
            story.append(Paragraph("Custo por ano", styles["h2"]))
            story.append(_hbar_chart(year_data, _money))

    # --- Tabela dos trechos atendidos ---
    if attended_snv_table is not None and not attended_snv_table.empty:
        story.append(Paragraph("Trechos atendidos (ordem de prioridade)", styles["h2"]))
        story.append(_snv_table(attended_snv_table))

    # --- Detalhamento por segmento (ordem de serviço) ---
    if segments_detail is not None and not segments_detail.empty:
        story.append(Paragraph("Detalhamento por segmento — ordem de serviço", styles["h2"]))
        story.append(
            Paragraph(
                "Trechos que precisam de intervenção, com km inicial/final e a solução a executar.",
                styles["small"],
            )
        )
        story.append(Spacer(1, 4))
        story.append(_segments_detail_table(segments_detail))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
