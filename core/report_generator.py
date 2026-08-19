import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf_report(telemetry_data, disks_data, health_score, output_path=None):
    """
    Genera un informe en PDF estilizado con métricas del sistema.
    Si output_path no se especifica, se genera un archivo con fecha y hora.
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(os.path.expanduser("~"), "Desktop", f"Reporte_DiagnosticPC_{timestamp}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=12
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4
    )

    elements = []

    # Título y Encabezado
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    elements.append(Paragraph("⚡ DiagnosticPC - Reporte de Telemetría", title_style))
    elements.append(Paragraph(f"<b>Fecha de Emisión:</b> {now_str} &nbsp;|&nbsp; <b>Salud Global Estimada:</b> {health_score:.1f}%", body_style))
    elements.append(Spacer(1, 10))

    # Resumen General
    elements.append(Paragraph("Resumen de Recursos Principales", h2_style))
    
    table_data = [
        ["Métrica", "Valor Actual", "Estado / Info Extra"],
        ["Uso de CPU", f"{telemetry_data.get('cpu_usage', 0)} %", f"Temperatura: {telemetry_data.get('cpu_temp', '--')} °C"],
        ["Uso de Memoria RAM", f"{telemetry_data.get('ram_usage', 0)} %", f"{telemetry_data.get('ram_used_gb', 0)} GB / {telemetry_data.get('ram_total_gb', 0)} GB"],
        ["Uso de GPU", f"{telemetry_data.get('gpu_usage', 0)} %", f"Temperatura: {telemetry_data.get('gpu_temp', '--')} °C"]
    ]

    t = Table(table_data, colWidths=[150, 120, 250])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#0f172a')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    # Detalle de Discos
    elements.append(Paragraph("Estado de Unidades de Almacenamiento", h2_style))
    
    disk_headers = ["Disco", "Modelo / Punto Montaje", "Salud", "Espacio Usado"]
    disk_rows = [disk_headers]

    for d in disks_data:
        disk_rows.append([
            f"Disco {d.get('index', 0)}",
            f"{d.get('model', 'N/A')} [{d.get('mount_points', '')}]",
            f"{d.get('health', 0)}%",
            f"{d.get('used_gb', 0)} GB de {d.get('total_gb', 0)} GB ({d.get('used_percent', 0)}%)"
        ])

    if len(disk_rows) > 1:
        t_disks = Table(disk_rows, colWidths=[60, 220, 70, 170])
        t_disks.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        elements.append(t_disks)

    doc.build(elements)
    return output_path
