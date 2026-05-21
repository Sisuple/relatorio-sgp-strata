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


def _money(value: float) -> str:
    value = float(value or 0)
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi"
    if value >= 1_000:
        return f"R$ {value / 1_000:.0f} mil"
    return f"R$ {value:.0f}"


def _km(value: float) -> str:
    return f"{float(value or 0):.1f} km"


def _truncate(text: str, limit: int) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _styles() -> dict[str, ParagraphStyle]:
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
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=HexColor("#fbfdfe"), strokeColor=_LINE, strokeWidth=0.8))

    coords = [(la, lo) for seg in segments for path in seg.get("paths", []) for (la, lo) in path]
    if not coords:
        d.add(String(width / 2, height / 2, "Sem geometria para o mapa", fontSize=9, textAnchor="middle", fillColor=_MUTED))
        return d

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    mean_lat = (lat_min + lat_max) / 2
    cos_lat = math.cos(math.radians(mean_lat)) or 1e-6

    pad = 16
    dlat = (lat_max - lat_min) or 1e-6
    dlon = ((lon_max - lon_min) or 1e-6) * cos_lat
    scale = min((width - 2 * pad) / dlon, (height - 2 * pad) / dlat)
    map_w, map_h = dlon * scale, dlat * scale
    ox, oy = (width - map_w) / 2, (height - map_h) / 2

    def to_xy(la: float, lo: float) -> tuple[float, float]:
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
    height = 16
    d = Drawing(width, height)
    x = 0.0
    for label, color in items:
        d.add(Rect(x, 4, 9, 9, fillColor=HexColor(color), strokeColor=None))
        d.add(String(x + 13, 5, label, fontSize=7.5, fillColor=_MUTED))
        x += 16 + len(label) * 4.6 + 14
    return d


def _hbar_chart(
    data: list[tuple[str, float, str]],
    value_fmt: Callable[[float], str],
    width: float = _CONTENT_W,
) -> Drawing:
    rows = len(data)
    row_h = 22
    height = max(rows * row_h + 6, row_h)
    d = Drawing(width, height)
    if not data:
        return d

    max_val = max((v for _, v, _ in data), default=1.0) or 1.0
    label_w = 150.0
    val_w = 110.0
    track_x = label_w
    track_w = max(width - label_w - val_w, 40)

    y = height - 18
    for label, value, color in data:
        d.add(String(label_w - 8, y + 3, _truncate(label, 30), fontSize=8, textAnchor="end", fillColor=_INK))
        d.add(Rect(track_x, y, track_w, 12, fillColor=_PANEL, strokeColor=None))
        d.add(Rect(track_x, y, max(track_w * float(value) / max_val, 1.0), 12, fillColor=HexColor(color), strokeColor=None))
        d.add(String(track_x + track_w + 8, y + 3, value_fmt(value), fontSize=8, fillColor=_MUTED))
        y -= row_h
    return d


def _snv_table(attended: pd.DataFrame) -> Table:
    header = ["#", "SRE", "Extensão", "IPT", "IPE", "Prioriz.", "Custo"]
    rows: list[list[Any]] = [header]
    for i, r in enumerate(attended.to_dict("records"), start=1):
        rows.append(
            [
                str(i),
                _truncate(str(r.get("SNV", "")), 16),
                _km(r.get("Extensão", 0)),
                f"{float(r.get('IPT', 0) or 0):.2f}",
                f"{float(r.get('IPE', 0) or 0):.2f}",
                f"{float(r.get('Priorização', 0) or 0):.2f}",
                _money(r.get("Custo econômico", 0)),
            ]
        )
    col_w = [22, 120, 70, 50, 50, 60, None]
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
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
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
    header = ["SRE", "Km Inicial", "Km Final", "Extensão", "Intervenção a executar", "Custo"]
    rows: list[list[Any]] = [header]
    for r in detail.to_dict("records"):
        rows.append(
            [
                _truncate(str(r.get("SNV", "")), 14),
                f"{float(r.get('Km Inicial', 0) or 0):.2f}",
                f"{float(r.get('Km Final', 0) or 0):.2f}",
                _km(r.get("Extensão", 0)),
                _truncate(str(r.get("Intervenção", "")), 44),
                _money(r.get("Custo", 0)),
            ]
        )
    col_w = [86, 58, 58, 58, None, 66]
    col_w[4] = _CONTENT_W - sum(w for w in col_w if w)
    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("TEXTCOLOR", (0, 1), (-1, -1), _INK),
                ("ALIGN", (1, 0), (3, -1), "RIGHT"),
                ("ALIGN", (5, 0), (5, -1), "RIGHT"),
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
    story.append(
        Paragraph(
            f"Orçamento anual: <b>{_money(annual_budget_mi * 1_000_000)}</b> &nbsp;·&nbsp; "
            f"Horizonte: <b>{horizon} anos</b> &nbsp;·&nbsp; Trechos: <b>{top_label}</b>",
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
