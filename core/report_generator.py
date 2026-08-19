import os
import random
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

HARDWARE_TIPS = [
    "La pasta térmica no debe cubrir todo el procesador manualmente; la presión del disipador la distribuirá de forma uniforme sin crear burbujas de aire.",
    "Un SSD o NVMe lleno a más del 90% de su capacidad reduce su velocidad de escritura y acorta su vida útil debido al desgaste de las celdas NAND.",
    "El polvo acumulado en los disipadores actúa como un aislante térmico, aumentando la temperatura de CPU y GPU hasta en 15°C.",
    "Usar un solo módulo de memoria RAM desperdicia hasta un 20% de rendimiento al no aprovechar el modo Dual-Channel de la placa base.",
    "Formatear un SSD con frecuencia no mejora su velocidad y consume ciclos de escritura innecesarios. Es mejor usar la herramienta TRIM de Windows."
]

def get_maintenance_recommendations(telemetry_data, disks_data):
    """
    Genera recomendaciones personalizadas diferenciando si el equipo es Laptop o Torre.
    """
    recommendations = []
    
    is_laptop = telemetry_data.get('is_laptop', False)
    cpu_name = telemetry_data.get('cpu_name', 'Procesador').upper()
    gpu_name = telemetry_data.get('gpu_name', 'Gráfica').upper()
    cpu_temp = telemetry_data.get('cpu_temp', 0)
    gpu_temp = telemetry_data.get('gpu_temp', 0)

    # 1. Mantenimiento CPU & Pasta Térmica (Diferenciado por Laptop vs Torre)
    if cpu_temp > 70 or "INTEL" in cpu_name or "RYZEN" in cpu_name:
        if is_laptop:
            recommendations.append({
                "component": f"Procesador Laptop ({telemetry_data.get('cpu_name', 'CPU')})",
                "action": "Limpieza de Modulo Térmico y Repaste en Portátil",
                "steps": "1. Desconectar cargador y retirar tapa trasera. 2. ¡DESCONECTAR BATERÍA INTERNA! 3. Retirar heatsink/heatpipes de cobre. 4. Limpiar con isopropílico y aplicar pasta de alta viscosidad (Honeywell PTM7950 o Noctua NT-H2).",
                "supplies": "Destornilladores de precisión (PH00/Torx), Púa de plástico (Spudger), Alcohol Isopropílico 99%, Pasta térmica densa.",
                "link": "https://www.youtube.com/results?search_query=como+limpiar+y+cambiar+pasta+termica+laptop+gaming"
            })
        else:
            recommendations.append({
                "component": f"Procesador Torre ({telemetry_data.get('cpu_name', 'CPU')})",
                "action": "Cambio de Pasta Térmica y Mantenimiento de Cooler",
                "steps": "1. Apagar fuente y retirar cristal lateral. 2. Desmontar disipador/AIO. 3. Limpiar pasta residual con isopropílico. 4. Aplicar gota central de pasta y reinstalar disipador.",
                "supplies": "Pasta Térmica (Arctic MX-4 / Noctua NT-H1), Alcohol Isopropílico 99%, Aire Comprimido.",
                "link": "https://www.youtube.com/results?search_query=como+cambiar+pasta+termica+pc+escritorio"
            })

    # 2. Mantenimiento GPU
    if gpu_temp > 75:
        if is_laptop:
            recommendations.append({
                "component": f"GPU Laptop ({telemetry_data.get('gpu_name', 'GPU')})",
                "action": "Limpieza de Aletas de Cobre y Turbinas (Fans)",
                "steps": "1. Bloquear las aspas del ventilador con un dedo para no dañarlo. 2. Sopletear las rejillas de ventilación. 3. Verificar si requiere Thermal Putty en VRAM.",
                "supplies": "Brocha antiestática, Aire comprimido en ráfagas cortas, Thermal Putty o Pads de 0.5mm.",
                "link": "https://www.youtube.com/results?search_query=limpieza+ventiladores+laptop+gaming"
            })
        else:
            recommendations.append({
                "component": f"Tarjeta Gráfica ({telemetry_data.get('gpu_name', 'GPU')})",
                "action": "Mantenimiento Térmico Avanzado de GPU",
                "steps": "1. Retirar GPU del puerto PCIe. 2. Desarmar backplate. 3. Reemplazar pads térmicos agrietados y renovar pasta en el die.",
                "supplies": "Thermal Pads Gelid (1.0mm/1.5mm), Pasta Térmica Thermal Grizzly Hydronaut.",
                "link": "https://www.youtube.com/results?search_query=mantenimiento+termico+gpu+desktop"
            })

    # 3. Almacenamiento
    for d in disks_data:
        model = d.get('model', '').upper()
        health = d.get('health', 100)
        used_p = d.get('used_percent', 0)

        if "NVME" in model or "SSD" in model:
            if health < 85 or used_p > 85:
                recommendations.append({
                    "component": f"SSD / NVMe: {d.get('model', 'Unidad SSD')}",
                    "action": "Optimización TRIM y Gestión Térmica M.2",
                    "steps": "1. Ejecutar 'Optimizar Unidades' en Windows. 2. Si es Laptop, verificar pad térmico contra tapa metálica. En Torre, instalar disipador pasivo de aluminio.",
                    "supplies": "Disipador M.2 de perfil bajo (Laptop) / Disipador de cobre con aletas (Torre).",
                    "link": "https://www.youtube.com/results?search_query=instalar+disipador+m2+nvme"
                })

    return recommendations


def generate_pdf_report(telemetry_data, disks_data, health_score, output_path=None):
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
        'DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor("#0f172a"), spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor("#2563eb"), spaceAfter=8
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor("#0f172a"), spaceBefore=8, spaceAfter=4
    )
    body_style = ParagraphStyle(
        'Body_Custom', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor("#334155"), spaceAfter=2
    )
    tip_style = ParagraphStyle(
        'Tip_Custom', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor("#1e293b")
    )
    link_style = ParagraphStyle(
        'Link_Custom', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor("#2563eb")
    )

    elements = []

    # Encabezado con detección de Tipo de Equipo, BIOS y Placa Base
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    elements.append(Paragraph("⚡ DiagnosticPC - Informe de Diagnóstico Hardware", title_style))
    elements.append(Paragraph("Predictive Analytics Engine & Hardware Telemetry System", subtitle_style))
    
    info_header = (
        f"<b>Fecha:</b> {now_str} &nbsp;|&nbsp; "
        f"<b>Factor de Forma:</b> <font color='#2563eb'><b>{telemetry_data.get('chassis_label', 'N/A')}</b></font> &nbsp;|&nbsp; "
        f"<b>Salud Global:</b> <font color='#10b981'><b>{health_score:.1f}%</b></font><br/>"
        f"<b>Placa Base:</b> {telemetry_data.get('board_info', 'N/A')} &nbsp;|&nbsp; "
        f"<b>BIOS:</b> {telemetry_data.get('bios_info', 'N/A')}"
    )
    elements.append(Paragraph(info_header, body_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=6, spaceAfter=8))

    # Tabla Diagnóstico
    elements.append(Paragraph("1. Resumen de Componentes Clave", h2_style))
    table_data = [
        ["Componente", "Modelo Detectado", "Uso / Estado", "Temperatura / Capacidad"],
        ["CPU", telemetry_data.get('cpu_name', 'Procesador'), f"{telemetry_data.get('cpu_usage', 0)} %", f"{telemetry_data.get('cpu_temp', '--')} °C"],
        ["RAM", "Memoria del Sistema", f"{telemetry_data.get('ram_usage', 0)} %", f"{telemetry_data.get('ram_used_gb', 0)} GB / {telemetry_data.get('ram_total_gb', 0)} GB"],
        ["GPU", telemetry_data.get('gpu_name', 'Tarjeta Gráfica'), f"{telemetry_data.get('gpu_usage', 0)} %", f"{telemetry_data.get('gpu_temp', '--')} °C"]
    ]

    t = Table(table_data, colWidths=[60, 220, 100, 160])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))

    # Tabla Almacenamiento
    elements.append(Paragraph("2. Salud y Espacio de Almacenamiento (S.M.A.R.T.)", h2_style))
    disk_rows = [["Unidad", "Modelo / Letra(s)", "Salud S.M.A.R.T.", "Espacio Ocupado"]]

    for d in disks_data:
        disk_rows.append([
            f"Disco {d.get('index', 0)}",
            f"{d.get('model', 'N/A')} [{d.get('mount_points', '')}]",
            f"{d.get('health', 0)}%",
            f"{d.get('used_gb', 0)} GB / {d.get('total_gb', 0)} GB ({d.get('used_percent', 0)}%)"
        ])

    t_disks = Table(disk_rows, colWidths=[55, 225, 100, 160])
    t_disks.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    elements.append(t_disks)
    elements.append(Spacer(1, 8))

    # Matriz Mantenimiento
    elements.append(Paragraph(f"3. Plan de Mantenimiento Adaptado ({telemetry_data.get('chassis_label', 'Equipo')})", h2_style))
    recs = get_maintenance_recommendations(telemetry_data, disks_data)

    rec_table_data = [["Componente", "Acción Recomendada", "Pasos a Seguir e Insumos Sugeridos", "Guía"]]
    for r in recs:
        steps_text = f"<b>Pasos:</b> {r['steps']}<br/><b>Insumos:</b> {r['supplies']}"
        link_p = Paragraph(f"<a href='{r['link']}'><u>Ver Tutorial</u></a>", link_style)

        rec_table_data.append([
            Paragraph(f"<b>{r['component']}</b>", body_style),
            Paragraph(r['action'], body_style),
            Paragraph(steps_text, body_style),
            link_p
        ])

    t_recs = Table(rec_table_data, colWidths=[100, 110, 250, 80])
    t_recs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(t_recs)
    elements.append(Spacer(1, 8))

    # Tip del Día
    elements.append(Paragraph("💡 ¿Sabías que...?", h2_style))
    tip_selected = random.choice(HARDWARE_TIPS)
    t_tip = Table([[Paragraph(f"<i>“{tip_selected}”</i>", tip_style)]], colWidths=[540])
    t_tip.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_tip)

    doc.build(elements)
    return output_path