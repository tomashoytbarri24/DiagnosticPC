"""Reporte PDF profesional y compacto de CorePulse.

Esta capa reorganiza la presentación sin alterar la autoridad de datos:
- diagnóstico actual: `diagnostic_result` certificado;
- telemetría: snapshot real/N/A;
- vigencia anual: resultado de la capa IA/web o NO EVALUABLE;
- recomendaciones: solo problemas autorizados por el diagnóstico actual;
- trazabilidad: anexo técnico separado.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core import report_base as base
from core.pdf_context import build_strict_pdf_context
from core.version import VERSION_LABEL

VERSION = VERSION_LABEL

NAVY = colors.HexColor('#0B1F3A')
BLUE = colors.HexColor('#0B3AA4')
BLUE_2 = colors.HexColor('#2563EB')
CYAN = colors.HexColor('#06B6D4')
GREEN = colors.HexColor('#059669')
ORANGE = colors.HexColor('#D97706')
RED = colors.HexColor('#DC2626')
PURPLE = colors.HexColor('#7C3AED')
TEXT = colors.HexColor('#111827')
SECONDARY = colors.HexColor('#334155')
MUTED = colors.HexColor('#475569')
GRID = colors.HexColor('#C7D2DE')
SOFT = colors.HexColor('#F7F9FC')
BLUE_SOFT = colors.HexColor('#EFF6FF')
GREEN_SOFT = colors.HexColor('#ECFDF5')
ORANGE_SOFT = colors.HexColor('#FFF7ED')
RED_SOFT = colors.HexColor('#FEF2F2')
PURPLE_SOFT = colors.HexColor('#F5F3FF')


def _clean(value: Any, default: str = 'N/A') -> str:
    if value is None:
        return default
    text = ' '.join(str(value).replace('\u2013', '-').replace('\u2014', '-').split()).strip()
    return text or default


def _esc(value: Any) -> str:
    return escape(_clean(value))


def _machine_display_label(identity: Dict[str, Any]) -> str:
    """Devuelve una identidad legible sin duplicar fabricante/modelo.

    ``device_identity`` puede entregar ``display_model`` ya compuesto (por ejemplo,
    fabricante + modelo en notebooks o ``PC de escritorio · <placa>`` en desktop).
    El PDF debe respetar esa identidad tal como fue detectada y no volver a
    anteponer el fabricante.
    """
    manufacturer = _clean(identity.get('manufacturer'), '')
    model = _clean(identity.get('display_model') or identity.get('model'), '')
    if not model:
        return manufacturer or 'Equipo detectado'
    if not manufacturer:
        return model

    model_fold = ' '.join(model.casefold().split())
    manufacturer_fold = ' '.join(manufacturer.casefold().split())
    form_factor = _clean(identity.get('form_factor'), '').upper()

    if model_fold == manufacturer_fold or model_fold.startswith(manufacturer_fold + ' '):
        return model
    if form_factor == 'DESKTOP' and model_fold.startswith('pc de escritorio'):
        return model
    return f'{manufacturer} {model}'.strip()


def _clip(value: Any, limit: int = 180) -> str:
    text = _clean(value, '')
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(' ', 1)[0].rstrip(' ,;:-')
    return cut + '...'


def _num(value: Any):
    return base._num(value)


def _fmt(value: Any, suffix: str = '', decimals: int = 1, default: str = 'N/A') -> str:
    return base._fmt(value, suffix, decimals, default)


def _styles():
    ss = getSampleStyleSheet()
    body = ParagraphStyle('CPCompactBody', parent=ss['BodyText'], fontName='Helvetica', fontSize=8.2, leading=10.2, textColor=TEXT, spaceAfter=1.5)
    # Jerarquía secundaria con contraste suficiente en pantalla e impresión.
    small = ParagraphStyle('CPCompactSmall', parent=body, fontName='Helvetica', fontSize=7.35, leading=8.9, textColor=SECONDARY, spaceAfter=1)
    tiny = ParagraphStyle('CPCompactTiny', parent=small, fontName='Helvetica', fontSize=6.8, leading=8.1, textColor=MUTED)
    table_header = ParagraphStyle('CPCompactTableHeader', parent=small, fontName='Helvetica-Bold', fontSize=7.35, leading=8.6, textColor=colors.white, spaceAfter=0)
    heading = ParagraphStyle('CPCompactHeading', parent=body, fontName='Helvetica-Bold', fontSize=9.1, leading=11, textColor=NAVY, spaceBefore=2, spaceAfter=3)
    title = ParagraphStyle('CPCompactTitle', parent=ss['Title'], fontName='Helvetica-Bold', fontSize=17.5, leading=19.5, textColor=NAVY, alignment=TA_LEFT, spaceAfter=1)
    subtitle = ParagraphStyle('CPCompactSubtitle', parent=body, fontName='Helvetica-Bold', fontSize=8.2, leading=9.6, textColor=BLUE_2)
    center = ParagraphStyle('CPCompactCenter', parent=body, fontName='Helvetica-Bold', fontSize=8.1, leading=9.5, textColor=TEXT, alignment=TA_CENTER)
    return {'body': body, 'small': small, 'tiny': tiny, 'table_header': table_header, 'heading': heading, 'title': title, 'subtitle': subtitle, 'center': center}


def _p(text: Any, style, *, bold: bool = False):
    value = _esc(text)
    if bold:
        value = f'<b>{value}</b>'
    return Paragraph(value, style)


def _section(title: str, st):
    cell = Paragraph(f"<b><font color='#FFFFFF'>{_esc(title)}</font></b>", ParagraphStyle('CPSectionCell', parent=st['body'], fontName='Helvetica-Bold', fontSize=8.4, leading=9.7, textColor=colors.white))
    t = Table([[cell]], colWidths=[177 * mm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BOX', (0, 0), (-1, -1), 0.4, BLUE),
    ]))
    return t


def _cell(value: Any, st, *, small: bool = False, bold: bool = False, color=None):
    style = st['small'] if small else st['body']
    text = _esc(value)
    if bold:
        text = f'<b>{text}</b>'
    if color:
        text = f"<font color='{color}'>{text}</font>"
    return Paragraph(text, style)


def _table(rows: List[List[Any]], widths: List[float], st, *, header: bool = True, font_scale: str = 'normal', repeat_rows: int | None = None):
    converted = []
    for ri, row in enumerate(rows):
        out = []
        for cell in row:
            if isinstance(cell, (Paragraph, Table, list, tuple)):
                out.append(cell)
            elif header and ri == 0:
                # Los Paragraph ignoran TEXTCOLOR de TableStyle; por eso el encabezado
                # debe nacer con su estilo blanco antes de construir la tabla.
                out.append(Paragraph(f"<b>{_esc(cell)}</b>", st['table_header']))
            else:
                out.append(_cell(cell, st, small=(font_scale == 'small')))
        converted.append(out)
    repeat = (1 if header else 0) if repeat_rows is None else repeat_rows
    klass = LongTable if len(converted) > 9 else Table
    t = klass(converted, colWidths=widths, repeatRows=repeat, hAlign='LEFT', splitByRow=1)
    commands = [
        ('GRID', (0, 0), (-1, -1), 0.35, GRID),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3.5),
        ('TOPPADDING', (0, 0), (-1, -1), 3.0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.0),
    ]
    if header and converted:
        commands += [
            ('BACKGROUND', (0, 0), (-1, 0), BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]
    if len(converted) > (1 if header else 0):
        start = 1 if header else 0
        commands += [('ROWBACKGROUNDS', (0, start), (-1, -1), [colors.white, SOFT])]
    t.setStyle(TableStyle(commands))
    return t


def _status_palette(status: str):
    s = _clean(status).upper()
    if s in {'CRITICAL', 'CRITICO', 'CRÍTICO'}:
        return ('CRÍTICO', RED, RED_SOFT)
    if s in {'WARNING', 'ADVERTENCIA', 'WARNING_ADVISORY'}:
        return ('ADVERTENCIA', ORANGE, ORANGE_SOFT)
    if s in {'NORMAL', 'PASS', 'OK', 'OPTIMAL', 'OPTIMO', 'ÓPTIMO'}:
        return ('NORMAL', GREEN, GREEN_SOFT)
    return ('NO EVALUABLE', MUTED, SOFT)


def _callout(title: str, body: str, st, *, accent=BLUE_2, background=BLUE_SOFT):
    rows = [[_cell(title, st, bold=True, color=accent.hexval())], [_cell(body, st)]]
    t = Table(rows, colWidths=[177 * mm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), background),
        ('LINEBEFORE', (0, 0), (0, -1), 3.0, accent),
        ('BOX', (0, 0), (-1, -1), 0.45, GRID),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _header(identity: Dict[str, Any], score: Any, diag: Dict[str, Any], st):
    logo_path = Path(__file__).resolve().parents[1] / 'assets' / 'CorePulseIcon.png'
    logo = RLImage(str(logo_path), width=16 * mm, height=16 * mm) if logo_path.exists() else _p('COREPULSE', st['center'], bold=True)
    machine = _machine_display_label(identity)
    status, accent, _ = _status_palette(base._diag_status(diag)[0])
    left = [
        Paragraph('CorePulse - Informe de Diagnóstico Hardware', st['title']),
        Paragraph('Hardware Telemetry & Predictive Diagnostics Engine', st['subtitle']),
        Spacer(1, 1.2 * mm),
        Paragraph(f"<b>Equipo:</b> {_esc(machine)} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Diagnóstico:</b> <font color='{accent.hexval()}'><b>{_esc(status)}</b></font>", st['small']),
        Paragraph(f"<b>Emitido:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Score de telemetría:</b> {_esc(_fmt(score, '%'))}", st['small']),
    ]
    t = Table([[left, logo]], colWidths=[158 * mm, 19 * mm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 1.0, BLUE_2),
    ]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    w, _ = A4
    canvas.setStrokeColor(GRID)
    canvas.setLineWidth(0.4)
    canvas.line(16 * mm, 11 * mm, w - 16 * mm, 11 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont('Helvetica', 6.7)
    canvas.drawString(16 * mm, 7 * mm, 'CorePulse - Datos reales o N/A; sin valores sintéticos')
    canvas.drawRightString(w - 16 * mm, 7 * mm, f'{VERSION} - Página {doc.page}')
    canvas.restoreState()


def _inventory_identity(inventory: Dict[str, Any]) -> Dict[str, Any]:
    return base._identity_from_inventory(inventory)


def _inventory_rows(inventory: Dict[str, Any]):
    rows: List[List[Any]] = [['Componente', 'Hardware detectado']]
    cpu = inventory.get('cpu') if isinstance(inventory.get('cpu'), dict) else {}
    ram = inventory.get('ram') if isinstance(inventory.get('ram'), dict) else {}
    if cpu:
        rows.append(['CPU', _clean(cpu.get('name'))])
    if ram:
        total = ram.get('total_gb')
        modules = ram.get('module_count')
        text = f"{_fmt(total, ' GB')}"
        if modules not in (None, ''):
            text += f" - {modules} módulo(s)"
        rows.append(['RAM', text])
    for idx, gpu in enumerate(inventory.get('gpus') or [], 1):
        if isinstance(gpu, dict):
            rows.append([f'GPU {idx}', _clean(gpu.get('name'))])
    for idx, disk in enumerate(inventory.get('storage') or [], 1):
        if isinstance(disk, dict):
            rows.append([f'Unidad {idx}', _clean(disk.get('model') or disk.get('name'))])
    battery = inventory.get('battery')
    if isinstance(battery, dict):
        deg = battery.get('degradation_percent')
        rows.append(['Batería', f"Detectada{f' - degradación reportada: {deg}%' if deg is not None else ''}"])
    return rows


def _identity_table(identity: Dict[str, Any], st):
    rows = [
        ['Campo', 'Valor'],
        ['Fabricante', _clean(identity.get('manufacturer'))],
        ['Modelo / plataforma', _clean(identity.get('display_model') or identity.get('model'))],
        ['Tipo', _clean(identity.get('form_factor'))],
        ['Placa madre', _clean(identity.get('baseboard'))],
        ['BIOS', _clean(identity.get('bios'))],
    ]
    return _table(rows, [34 * mm, 53 * mm], st, font_scale='small')


def _summary_cards(hw: Dict[str, Any], score: Any, diag: Dict[str, Any], st):
    status, accent, bg = _status_palette(base._diag_status(diag)[0])
    items = [
        ('DIAGNÓSTICO', status, accent, bg),
        ('TELEMETRÍA', _fmt(score, '%'), BLUE_2, BLUE_SOFT),
        ('CPU', _fmt(hw.get('cpu_temp'), ' °C'), CYAN, colors.HexColor('#ECFEFF')),
        ('RAM', _fmt(hw.get('ram_usage'), '%'), GREEN, GREEN_SOFT),
        ('GPU', _fmt(hw.get('gpu_temp'), ' °C'), PURPLE, PURPLE_SOFT),
    ]
    cells = []
    for label, value, color, soft in items:
        inner = Table([
            [Paragraph(f"<b><font color='{MUTED.hexval()}'>{_esc(label)}</font></b>", st['tiny'])],
            [Paragraph(f"<b><font color='{color.hexval()}'>{_esc(value)}</font></b>", st['center'])],
        ], colWidths=[33.3 * mm])
        inner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), soft),
            ('BOX', (0, 0), (-1, -1), 0.5, GRID),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        cells.append(inner)
    outer = Table([cells], colWidths=[35.4 * mm] * 5)
    outer.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0.6), ('RIGHTPADDING', (0, 0), (-1, -1), 0.6)]))
    return outer


def _telemetry_rows(hw: Dict[str, Any]):
    cpu_name = _clean(hw.get('cpu_name'))
    if _num(hw.get('cpu_ghz')) is not None:
        cpu_name += f" - {_fmt(hw.get('cpu_ghz'), ' GHz', 2)}"
    gpu_name = _clean(hw.get('gpu_name'))
    if _num(hw.get('gpu_vram')) is not None:
        gpu_name += f" - {_fmt(hw.get('gpu_vram'), ' GB', 1)} VRAM"
    ram_cap = f"{_fmt(hw.get('ram_used'), ' GB')} / {_fmt(hw.get('ram_total'), ' GB')}" if _num(hw.get('ram_total')) is not None else _fmt(hw.get('ram_used'), ' GB')
    return [
        ['Componente', 'Modelo', 'Uso actual', 'Temperatura / capacidad'],
        ['CPU', cpu_name, _fmt(hw.get('cpu_usage'), '%'), _fmt(hw.get('cpu_temp'), ' °C')],
        ['RAM', 'Memoria del sistema', _fmt(hw.get('ram_usage'), '%'), ram_cap],
        ['GPU', gpu_name, _fmt(hw.get('gpu_usage'), '%'), _fmt(hw.get('gpu_temp'), ' °C')],
    ]


def _storage_rows(disks: List[Dict[str, Any]]):
    rows = [['Unidad', 'Modelo / montaje', 'Salud SMART', 'Temperatura', 'Ocupación']]
    for idx, disk in enumerate(disks or []):
        if not isinstance(disk, dict):
            continue
        model = _clean(base._pick(disk, 'model', 'name'))
        mount = _clean(base._pick(disk, 'mount_points', 'mount', 'letter'), '')
        health = base._pick(disk, 'health', 'health_percent', 'life', 'life_percent')
        temp = base._pick(disk, 'temperature_c', 'temperature', 'temp')
        used_pct = base._pick(disk, 'used_percent', 'used_space_percent', 'usage')
        used_gb = base._pick(disk, 'used_gb')
        total_gb = base._pick(disk, 'total_gb')
        occupied = _fmt(used_pct, '%')
        if _num(used_gb) is not None and _num(total_gb) is not None:
            occupied = f"{_fmt(used_gb, ' GB')} / {_fmt(total_gb, ' GB')} ({_fmt(used_pct, '%')})"
        rows.append([f"Disco {disk.get('index', idx)}", f'{model} {mount}'.strip(), _fmt(health, '%'), _fmt(temp, ' °C'), occupied])
    if len(rows) == 1:
        rows.append(['N/A', 'No disponible', 'N/A', 'N/A', 'N/A'])
    return rows


def _finding_level(finding: Dict[str, Any]):
    return base._finding_level(finding)[0]


def _finding_evidence(finding: Dict[str, Any], limit: int = 3):
    evidence = finding.get('evidence') if isinstance(finding.get('evidence'), list) else []
    text = ' | '.join(_clean(x, '') for x in evidence[:limit] if _clean(x, ''))
    if not text:
        text = _clean(finding.get('detail') or finding.get('explanation'))
    return _clip(text, 260)


def _diagnostic_summary(diag: Dict[str, Any], st):
    metrics = base._diagnostic_metrics(diag)
    status, accent, bg = _status_palette(base._diag_status(diag)[0])
    rows = [
        ['Estado', 'Duración', 'Muestras', 'CPU prom.', 'CPU máx.', 'RAM prom.', 'GPU máx.'],
        [status, base._duration(base._pick(diag, 'duration_seconds', 'elapsed_seconds')), _clean(base._pick(diag, 'sample_count')), _fmt(metrics['cpu_temp_avg'], ' °C'), _fmt(metrics['cpu_temp_max'], ' °C'), _fmt(metrics['ram_usage_avg'], '%'), _fmt(metrics['gpu_temp_max'], ' °C')],
    ]
    t = _table(rows, [25 * mm, 23 * mm, 20 * mm, 27 * mm, 27 * mm, 27 * mm, 28 * mm], st, font_scale='small')
    t.setStyle(TableStyle([('BACKGROUND', (0, 1), (0, 1), bg), ('TEXTCOLOR', (0, 1), (0, 1), accent)]))
    return t


def _findings_table(findings: List[Dict[str, Any]], st, *, compact: bool = True):
    rows = [['Componente', 'Estado', 'Resultado', 'Evidencia']]
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        rows.append([
            base._friendly_component(finding.get('component')),
            _finding_level(finding),
            _clip(finding.get('title') or 'Hallazgo', 105),
            _finding_evidence(finding, 3 if compact else 5),
        ])
    if len(rows) == 1:
        rows.append(['N/A', 'N/A', 'Sin hallazgos estructurados', 'N/A'])
    return _table(rows, [28 * mm, 23 * mm, 52 * mm, 74 * mm], st, font_scale='small')


def _evidence_blocks(findings: List[Dict[str, Any]], st):
    out = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        level = _finding_level(finding)
        label, accent, bg = _status_palette(level)
        title = f"{base._friendly_component(finding.get('component'))} - {_clean(finding.get('title'), 'Hallazgo')}"
        body_parts = []
        explanation = _clean(finding.get('detail') or finding.get('explanation'), '')
        if explanation:
            body_parts.append(explanation)
        evidence = finding.get('evidence') if isinstance(finding.get('evidence'), list) else []
        if evidence:
            body_parts.append('Evidencia: ' + ' | '.join(_clean(x, '') for x in evidence[:5] if _clean(x, '')))
        out += [KeepTogether([_callout(f'{label} - {title}', _clip(' '.join(body_parts), 520), st, accent=accent, background=bg), Spacer(1, 2.0 * mm)])]
    return out


def _plan_entries(ai: Dict[str, Any], ctx: Dict[str, Any]):
    rich = [x for x in (ai.get('problem_recommendations') or []) if isinstance(x, dict)]
    if rich:
        return [('ai', x) for x in rich]
    return [('deterministic', x) for x in (ctx.get('recommendations') or []) if isinstance(x, dict)]


def _plan_flowables(ai: Dict[str, Any], ctx: Dict[str, Any], st):
    plans = _plan_entries(ai, ctx)
    if not plans:
        return [_callout('Sin acciones correctivas requeridas', 'El diagnóstico actual no contiene problemas confirmados que requieran un plan de reparación. CorePulse no genera recomendaciones innecesarias.', st, accent=GREEN, background=GREEN_SOFT)]
    out = []
    for source, plan in plans:
        severity = _clean(plan.get('severity'), 'WARNING')
        _, accent, bg = _status_palette(severity)
        component = _clean(plan.get('component_type') or plan.get('component'), 'COMPONENTE')
        title = _clean(plan.get('title'), 'Condición detectada')
        priority = _clean(plan.get('priority_level'), 'PRIORITARIO' if severity.upper().startswith('CRIT') else 'RECOMENDADO')
        summary = _clean(plan.get('summary') or plan.get('finding'), '')
        evidence = plan.get('evidence')
        if isinstance(evidence, dict):
            evidence_lines = evidence.get('evidence_lines') if isinstance(evidence.get('evidence_lines'), list) else []
        else:
            evidence_lines = evidence if isinstance(evidence, list) else []
        actions = plan.get('actions') if isinstance(plan.get('actions'), list) else plan.get('steps') if isinstance(plan.get('steps'), list) else []
        supplies = plan.get('supplies') if isinstance(plan.get('supplies'), list) else []
        precautions = plan.get('precautions') if isinstance(plan.get('precautions'), list) else []
        lines = []
        if summary:
            lines.append(summary)
        if evidence_lines:
            lines.append('Evidencia: ' + ' | '.join(_clean(x, '') for x in evidence_lines[:4] if _clean(x, '')))
        block = [_callout(f'{priority} - {component}: {title}', _clip(' '.join(lines), 520), st, accent=accent, background=bg)]
        if actions:
            block.append(Paragraph('<b>Qué hacer</b>', st['heading']))
            for idx, action in enumerate(actions[:6], 1):
                block.append(Paragraph(f'<b>{idx}.</b> {_esc(_clip(action, 220))}', st['body']))
        if supplies:
            block.append(Paragraph('<b>Insumos / herramientas</b>', st['heading']))
            block.append(Paragraph(_esc(' - '.join(_clip(x, 100) for x in supplies[:5])), st['small']))
        if precautions:
            block.append(Paragraph('<b>Precauciones</b>', st['heading']))
            block.append(Paragraph(_esc(' - '.join(_clip(x, 120) for x in precautions[:4])), st['small']))
        tutorial = plan.get('tutorial') if isinstance(plan.get('tutorial'), dict) else {}
        if tutorial.get('status') == 'VERIFIED_EXACT' and str(tutorial.get('url') or '').startswith('https://'):
            url = escape(str(tutorial.get('url')))
            block.append(Paragraph(f"<b>Tutorial verificado:</b> <link href='{url}' color='#2563EB'><u>abrir tutorial exacto</u></link>", st['small']))
        elif source == 'deterministic' and plan.get('tutorial_verified'):
            block.append(Paragraph('<b>Tutorial:</b> verificado externamente.', st['small']))
        out += [KeepTogether(block), Spacer(1, 2.5 * mm)]
    return out


def _relevance_label(value: Any):
    key = _clean(value, 'NO_EVALUABLE').upper()
    return {
        'OPTIMO': 'ÓPTIMO',
        'ESTANDAR': 'ESTÁNDAR',
        'JUSTO': 'JUSTO',
        'POR_DEBAJO_DEL_ESTANDAR': 'POR DEBAJO',
        'NO_EVALUABLE': 'NO EVALUABLE',
    }.get(key, 'NO EVALUABLE')


def _relevance_color(value: Any):
    key = _clean(value, 'NO_EVALUABLE').upper()
    return {
        'OPTIMO': GREEN,
        'ESTANDAR': BLUE_2,
        'JUSTO': ORANGE,
        'POR_DEBAJO_DEL_ESTANDAR': RED,
        'NO_EVALUABLE': MUTED,
    }.get(key, MUTED)


def _relevance_flowables(ai: Dict[str, Any], st):
    year = int(ai.get('current_year') or datetime.now().year)
    relevance = [x for x in (ai.get('hardware_relevance') or []) if isinstance(x, dict)]
    rows: List[List[Any]] = [['Componente', 'Hardware detectado', f'Vigencia {year}', 'Confianza']]
    reason_groups: Dict[str, List[str]] = {}
    conflict_notes: List[tuple[str, str, str]] = []
    for item in relevance:
        classification = _clean(item.get('classification'), 'NO_EVALUABLE').upper()
        label = _relevance_label(classification)
        color = _relevance_color(classification)
        rows.append([
            _clean(item.get('component_type') or item.get('component_id')),
            _clip(item.get('detected_hardware'), 85),
            _cell(label, st, small=True, bold=True, color=color.hexval()),
            _clean(item.get('confidence'), 'BAJA'),
        ])
        reason = _clean(item.get('reason'), '')
        if reason:
            reason_groups.setdefault(reason, []).append(_clean(item.get('component_type') or item.get('component_id')))
        axes = item.get('evidence_axes') if isinstance(item.get('evidence_axes'), dict) else {}
        if axes.get('evidence_conflict'):
            affected = axes.get('conflicting_axes') if isinstance(axes.get('conflicting_axes'), list) else []
            axis_text = ', '.join(str(x).replace('_position', '').replace('_', ' ') for x in affected[:3])
            detail = _clean(axes.get('conflict_reason'), 'Las fuentes verificadas presentan una contradicción material.')
            conflict_notes.append((_clean(item.get('component_type') or item.get('component_id')), axis_text, detail))
    if len(rows) == 1:
        rows.append(['N/A', 'Sin componentes clasificables', 'NO EVALUABLE', 'N/A'])
    out = [_table(rows, [25 * mm, 82 * mm, 39 * mm, 31 * mm], st, font_scale='small'), Spacer(1, 2 * mm)]
    research = ai.get('research') if isinstance(ai.get('research'), dict) else {}
    status = _clean(research.get('relevance_status') or research.get('status'), 'UNAVAILABLE').upper()
    if ai.get('status') not in {'OK', 'PARTIAL'} or status in {'UNAVAILABLE', 'ERROR', 'RATE_LIMITED', 'ERROR_PROVIDER_413', 'DISABLED'}:
        out.append(_callout('Evaluación de vigencia limitada', 'No fue posible obtener evidencia externa verificable suficiente durante esta ejecución. Los componentes sin evidencia permanecen como NO EVALUABLE; CorePulse no sustituye la información faltante por estimaciones.', st, accent=MUTED, background=SOFT))
    elif status == 'PARTIAL_RATE_LIMITED':
        out.append(_callout('Evaluación parcial', 'Se conservaron únicamente las clasificaciones respaldadas por evidencia verificada. Los componentes pendientes permanecen como NO EVALUABLE.', st, accent=ORANGE, background=ORANGE_SOFT))
    # Reasons are grouped so identical provider/identity limitations are not repeated per row.
    useful = []
    for reason, comps in reason_groups.items():
        generic_secret = 'GROQ_API_KEY' in reason or 'api key' in reason.lower()
        if generic_secret:
            continue
        useful.append((comps, reason))
    if useful and len(useful) <= 5:
        out += [Spacer(1, 1.5 * mm), Paragraph('<b>Notas de evaluación</b>', st['heading'])]
        for comps, reason in useful[:5]:
            out.append(Paragraph(f"<b>{_esc(', '.join(comps))}:</b> {_esc(_clip(reason, 260))}", st['small']))
    if conflict_notes:
        out += [Spacer(1, 1.5 * mm), Paragraph('<b>Contradicciones de evidencia</b>', st['heading'])]
        for comp, axis_text, detail in conflict_notes[:4]:
            axis_suffix = f" · eje(s): {axis_text}" if axis_text else ''
            out.append(Paragraph(f"<b>{_esc(comp)}:</b>{_esc(axis_suffix)} · {_esc(_clip(detail, 300))}", st['small']))
    return out


def _history_is_meaningful(sessions: List[Dict[str, Any]]) -> bool:
    valid = [s for s in sessions if isinstance(s, dict) and base._profile(s) != 'LEGACY']
    if len(valid) < 3:
        return False
    points = 0
    for s in valid[:7]:
        maxima, _ = base._session_maxima(s)
        if _num(maxima.get('cpu_temp')) is not None or _num(maxima.get('gpu_temp')) is not None:
            points += 1
    return points >= 3


def _compact_trend_chart(sessions: List[Dict[str, Any]]):
    valid = [s for s in sessions if isinstance(s, dict) and base._profile(s) != 'LEGACY']
    ordered = list(reversed(valid[:7]))
    x_names = [f'S{i + 1}' for i in range(len(ordered))]
    series = []
    labels = []
    palette = []
    for target_profile, metric, label, color in (
        ('ESCRITORIO', 'cpu_temp', 'CPU escritorio', CYAN),
        ('ESCRITORIO', 'gpu_temp', 'GPU escritorio', PURPLE),
        ('JUEGO', 'cpu_temp', 'CPU juego', BLUE_2),
        ('JUEGO', 'gpu_temp', 'GPU juego', GREEN),
    ):
        values = []
        has = False
        for session in ordered:
            if base._profile(session) != target_profile:
                values.append(None)
                continue
            maxima, _ = base._session_maxima(session)
            v = _num(maxima.get(metric))
            values.append(v)
            has = has or v is not None
        if has:
            series.append(values)
            labels.append(label)
            palette.append(color)
    if not series:
        return None
    drawing = Drawing(500, 165)
    chart = HorizontalLineChart()
    chart.x = 38
    chart.y = 48
    chart.width = 420
    chart.height = 92
    chart.data = series
    chart.categoryAxis.categoryNames = x_names
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 110
    chart.valueAxis.valueStep = 20
    chart.valueAxis.labels.fontSize = 7
    chart.lines.strokeWidth = 1.6
    for i, color in enumerate(palette):
        chart.lines[i].strokeColor = color
    drawing.add(chart)
    x = 44
    for idx, (label, color) in enumerate(zip(labels, palette)):
        lx = x + (idx % 2) * 205
        ly = 21 - (idx // 2) * 14
        drawing.add(Rect(lx, ly, 8, 8, fillColor=color, strokeColor=color))
        drawing.add(String(lx + 12, ly, label, fontName='Helvetica', fontSize=6.8, fillColor=TEXT))
    return drawing


def _history_flowables(st):
    sessions = base._sessions()
    if not sessions:
        return [_callout('Historial aún no disponible', 'Todavía no existen sesiones guardadas suficientes para comparar tendencias.', st, accent=MUTED, background=SOFT)]
    out = []
    if _history_is_meaningful(sessions):
        chart = _compact_trend_chart(sessions)
        if chart is not None:
            out += [chart, Spacer(1, 1.5 * mm)]
    else:
        out += [_callout('Historial insuficiente para una tendencia fiable', 'CorePulse conserva las sesiones disponibles, pero no muestra un gráfico hasta reunir al menos tres sesiones comparables con datos térmicos válidos.', st, accent=MUTED, background=SOFT), Spacer(1, 2 * mm)]
    rows = [['Perfil', 'Duración', 'CPU máx.', 'GPU máx.', 'Alertas']]
    for session in sessions[:5]:
        maxima, _ = base._session_maxima(session)
        alerts = session.get('alerts') if isinstance(session.get('alerts'), dict) else {}
        trusted = session.get('alerts_trusted') if 'alerts_trusted' in session else base._profile(session) != 'LEGACY'
        alert_text = f"{int(_num(alerts.get('warning')) or 0)} adv. / {int(_num(alerts.get('critical')) or 0)} crit." if trusted else 'No comparable'
        rows.append([base._profile(session), base._duration(session.get('duration_seconds')), _fmt(maxima.get('cpu_temp'), ' °C'), _fmt(maxima.get('gpu_temp'), ' °C'), alert_text])
    out.append(_table(rows, [35 * mm, 31 * mm, 32 * mm, 32 * mm, 47 * mm], st, font_scale='small'))
    return out


def _trace_rows(telemetry: Dict[str, Any]):
    consistency = telemetry.get('_telemetry_consistency') if isinstance(telemetry.get('_telemetry_consistency'), dict) else {}
    metrics = telemetry.get('_metrics') if isinstance(telemetry.get('_metrics'), dict) else {}

    def meta(consistency_key: str, metric_key: str):
        c = consistency.get(consistency_key) if isinstance(consistency.get(consistency_key), dict) else {}
        m = metrics.get(metric_key) if isinstance(metrics.get(metric_key), dict) else {}
        return c or m

    def row(label: str, value: Any, suffix: str, consistency_key: str, metric_key: str):
        m = meta(consistency_key, metric_key)
        return [
            label,
            _fmt(value, suffix),
            _clean(m.get('source')),
            _clean(m.get('sensor')),
            _clean(m.get('quality')),
            _clean(m.get('timestamp')),
        ]

    rows = [['Métrica', 'Valor', 'Fuente', 'Sensor', 'Calidad', 'Timestamp']]
    cpu_temp_value = consistency.get('cpu_package_c') if consistency.get('cpu_package_c') is not None else telemetry.get('cpu_temp')
    rows.append(row('CPU temperatura', cpu_temp_value, ' °C', 'cpu_temp_metric', 'cpu_temp'))
    rows.append(row('CPU uso', telemetry.get('cpu_usage'), '%', 'cpu_usage_metric', 'cpu_usage'))
    rows.append(row('RAM uso', telemetry.get('ram_usage'), '%', 'ram_usage_metric', 'ram_usage'))
    rows.append(row('GPU uso', telemetry.get('gpu_usage'), '%', 'gpu_usage_metric', 'gpu_usage'))
    rows.append(row('GPU temperatura', telemetry.get('gpu_temp'), ' °C', 'gpu_temp_metric', 'gpu_temp'))
    if consistency:
        rows.append(['Edad del snapshot', _fmt(consistency.get('snapshot_age_seconds'), ' s', 3), 'CorePulse snapshot', 'N/A', 'STALE' if consistency.get('stale') else 'VALID', _clean(consistency.get('snapshot_timestamp'))])
    return rows


def _inventory_source_rows(inventory: Dict[str, Any]):
    rows = [['Elemento', 'Fuente de inventario']]
    cpu = inventory.get('cpu') if isinstance(inventory.get('cpu'), dict) else {}
    ram = inventory.get('ram') if isinstance(inventory.get('ram'), dict) else {}
    if cpu:
        rows.append(['CPU', _clean(cpu.get('source'))])
    if ram:
        rows.append(['RAM', _clean(ram.get('source'))])
    for idx, gpu in enumerate(inventory.get('gpus') or [], 1):
        if isinstance(gpu, dict):
            rows.append([f'GPU {idx}', _clean(gpu.get('source'))])
    for idx, disk in enumerate(inventory.get('storage') or [], 1):
        if isinstance(disk, dict):
            rows.append([f'Unidad {idx}', _clean(disk.get('source') or inventory.get('storage_source'))])
    if isinstance(inventory.get('battery'), dict):
        rows.append(['Batería', _clean(inventory.get('battery_source'))])
    return rows


def _research_note(ai: Dict[str, Any], st):
    research = ai.get('research') if isinstance(ai.get('research'), dict) else {}
    ai_status = _clean(ai.get('status'), 'UNAVAILABLE').upper()
    if ai_status not in {'OK', 'PARTIAL'}:
        return _callout('Estado de la capa de interpretación', 'La interpretación externa no estuvo disponible en esta ejecución. El diagnóstico técnico y la trazabilidad siguen siendo válidos; CorePulse no generó clasificaciones ni enlaces no verificados.', st, accent=MUTED, background=SOFT)
    sources = research.get('source_count')
    if not isinstance(sources, int):
        sources = len(research.get('sources') or []) if isinstance(research.get('sources'), list) else 0
    model = _clean(ai.get('model'))
    status = _clean(research.get('relevance_status') or research.get('status'))
    prefix = 'Interpretación parcial con fallback determinístico' if ai_status == 'PARTIAL' else 'Interpretación IA activa'
    return _callout('Trazabilidad de interpretación', f'{prefix}. Estado de investigación: {status}. Fuentes verificadas conservadas: {sources}. Modelo: {model}.', st, accent=BLUE_2, background=BLUE_SOFT)


def _build_story(telemetry: Dict[str, Any], disks: List[Dict[str, Any]], score: Any, diagnostic_result: Dict[str, Any], ai: Dict[str, Any], ctx: Dict[str, Any], inventory: Dict[str, Any]):
    st = _styles()
    diag = diagnostic_result
    identity = _inventory_identity(inventory)
    hw = base._current_hardware(telemetry)
    findings = [x for x in base._findings(diag) if isinstance(x, dict)]
    attention = [x for x in findings if _finding_level(x) in {'ADVERTENCIA', 'CRÍTICO'}]
    normal_info = [x for x in findings if x not in attention]
    status_label, status_color, status_bg = _status_palette(base._diag_status(diag)[0])

    story: List[Any] = []

    # PÁGINA 1 - Resumen técnico ejecutivo.
    story += [_header(identity, score, diag, st), Spacer(1, 3 * mm), _section('1. Resumen Ejecutivo del Equipo', st), Spacer(1, 2 * mm)]
    identity_table = _identity_table(identity, st)
    inventory_table = _table(_inventory_rows(inventory), [24 * mm, 63 * mm], st, font_scale='small')
    pair = Table([[identity_table, inventory_table]], colWidths=[88 * mm, 89 * mm], hAlign='LEFT')
    pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 1)]))
    story += [pair, Spacer(1, 2.5 * mm), _summary_cards(hw, score, diag, st), Spacer(1, 2.8 * mm)]
    story += [_section('2. Telemetría Actual y Almacenamiento', st), Spacer(1, 2 * mm), _table(_telemetry_rows(hw), [24 * mm, 85 * mm, 28 * mm, 40 * mm], st, font_scale='small'), Spacer(1, 2 * mm), _table(_storage_rows(disks), [19 * mm, 66 * mm, 26 * mm, 26 * mm, 40 * mm], st, font_scale='small'), Spacer(1, 2.8 * mm)]
    story += [_section('3. Resultado del Diagnóstico Actual', st), Spacer(1, 2 * mm), _diagnostic_summary(diag, st), Spacer(1, 2 * mm)]
    if attention:
        story += [_callout('Atención requerida', f'Se detectaron {len(attention)} condición(es) con advertencia o criticidad respaldadas por la sesión actual.', st, accent=status_color, background=status_bg), Spacer(1, 1.5 * mm), _findings_table(attention[:4], st)]
    else:
        story += [_callout('Sin condiciones correctivas activas', 'El diagnóstico actual no presenta advertencias o condiciones críticas sostenidas. Los hallazgos informativos se conservan como evidencia.', st, accent=GREEN, background=GREEN_SOFT)]
    story.append(PageBreak())

    # PÁGINA 2 - Evidencia y acciones.
    story += [_section('4. Evidencia del Diagnóstico', st), Spacer(1, 2 * mm)]
    if attention:
        story += _evidence_blocks(attention, st)
        if normal_info:
            story += [Paragraph('<b>Comprobaciones normales / informativas</b>', st['heading']), _findings_table(normal_info[:7], st), Spacer(1, 2 * mm)]
    else:
        story += [_findings_table(findings[:10], st), Spacer(1, 2 * mm)]
    story += [_section('5. Recomendaciones y Plan de Acción', st), Spacer(1, 2 * mm)]
    story += _plan_flowables(ai, ctx, st)
    if ai.get('status') in {'OK', 'PARTIAL'} and _clean(ai.get('executive_summary'), ''):
        story += [Spacer(1, 1 * mm), _callout('Conclusión interpretativa', _clip(ai.get('executive_summary'), 520), st, accent=BLUE_2, background=BLUE_SOFT)]
    else:
        conclusion = {
            'CRÍTICO': 'La sesión contiene una condición crítica respaldada por evidencia del diagnóstico actual. Prioriza el plan de acción indicado.',
            'ADVERTENCIA': 'La sesión contiene una advertencia respaldada por evidencia sostenida. Revisa las acciones recomendadas.',
            'NORMAL': 'La sesión no contiene condiciones correctivas sostenidas. Mantén seguimiento normal y repite el diagnóstico si cambia el comportamiento del equipo.',
        }.get(status_label, 'No fue posible cerrar una conclusión completa con los datos disponibles.')
        story += [Spacer(1, 1 * mm), _callout('Conclusión de la sesión', conclusion, st, accent=status_color, background=status_bg)]

    # La vigencia anual continúa de forma natural. En reportes breves usa el espacio
    # disponible de la página 2; planes complejos pueden desplazarla a la siguiente.
    story += [Spacer(1, 3 * mm)]
    year = int(ai.get('current_year') or datetime.now().year)
    story += [_section(f'6. Vigencia del Hardware para {year}', st), Spacer(1, 2 * mm), Paragraph('La vigencia describe qué tan actual es el hardware frente al estándar tecnológico del año. No equivale a salud técnica ni obliga por sí sola a reemplazar un componente.', st['small']), Spacer(1, 1.5 * mm)]
    story += _relevance_flowables(ai, st)
    story += [Spacer(1, 3 * mm), _section('7. Historial y Tendencias', st), Spacer(1, 2 * mm)]
    story += _history_flowables(st)
    story.append(PageBreak())

    # Anexo técnico: el detalle de fuentes y calidad se mantiene fuera de la página 1.
    story += [_section('Anexo Técnico - Trazabilidad y Política de Datos', st), Spacer(1, 2 * mm), Paragraph('Este anexo conserva la evidencia técnica necesaria para auditar las lecturas sin recargar el resumen principal.', st['small']), Spacer(1, 2 * mm)]
    story += [Paragraph('<b>Trazabilidad de telemetría</b>', st['heading']), _table(_trace_rows(telemetry), [25 * mm, 20 * mm, 37 * mm, 48 * mm, 20 * mm, 27 * mm], st, font_scale='small'), Spacer(1, 2.5 * mm)]
    source_rows = _inventory_source_rows(inventory)
    if len(source_rows) > 1:
        story += [Paragraph('<b>Fuentes de inventario</b>', st['heading']), _table(source_rows, [38 * mm, 139 * mm], st, font_scale='small'), Spacer(1, 2.5 * mm)]
    story += [_research_note(ai, st), Spacer(1, 2.5 * mm), Paragraph('<b>Política de integridad</b>', st['heading'])]
    policies = [
        'Los valores de sensores se reportan únicamente desde fuentes reales disponibles; si faltan, se muestra N/A.',
        'CorePulse no usa offsets artificiales, interpolaciones ni valores sintéticos para completar telemetría.',
        'FPS y frametime se reportan solo cuando existe una fuente real certificada.',
        'La vigencia anual y el estado técnico son dominios independientes.',
        'El historial del agente no crea fallas en el diagnóstico actual.',
        'Las recomendaciones correctivas se activan únicamente por problemas reales confirmados o advisories determinísticos autorizados.',
    ]
    for item in policies:
        story.append(Paragraph('&bull;&nbsp;&nbsp;' + _esc(item), st['small']))
    return story


def build_pdf_report(telemetry, disks, score, output_path, diagnostic_result: Dict[str, Any], ai: Dict[str, Any], ctx: Dict[str, Any] | None = None):
    """Genera el PDF final con jerarquía visual compacta y secciones condicionales."""
    if not isinstance(diagnostic_result, dict):
        raise RuntimeError(f'{VERSION}: no hay un resultado de diagnóstico actual para exportar.')
    telemetry = base.apply_source_consistency(telemetry if isinstance(telemetry, dict) else {})
    disks = disks if isinstance(disks, list) else []
    ctx = ctx if isinstance(ctx, dict) else build_strict_pdf_context(diagnostic_result)

    inventory = telemetry.get('_hardware_inventory') if isinstance(telemetry.get('_hardware_inventory'), dict) else None
    if not inventory or not isinstance(inventory.get('identity'), dict):
        inventory = base.collect_hardware_inventory(telemetry=telemetry, disks=disks)
        telemetry['_hardware_inventory'] = inventory

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=f'CorePulse - Informe de Diagnóstico Hardware {VERSION}',
        author='CorePulse',
        subject='Hardware Telemetry & Diagnostics',
        allowSplitting=1,
    )
    story = _build_story(telemetry, disks, score, diagnostic_result, ai if isinstance(ai, dict) else {}, ctx, inventory)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return str(output_path)


__all__ = ['build_pdf_report', '_build_story', '_history_is_meaningful']
