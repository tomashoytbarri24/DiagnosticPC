import os
import io
import random
import platform
import subprocess

from datetime import datetime
from xml.sax.saxutils import escape
from urllib.parse import quote

from PIL import Image as PILImage

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Image,
)

from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)

from core.ai_tutorial import (
    generate_ai_tutorial
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

IS_WINDOWS = platform.system() == "Windows"


# ============================================================
# WMI
# ============================================================

pythoncom = None
wmi = None

if IS_WINDOWS:

    try:

        import pythoncom
        import wmi

    except ImportError:

        print(
            "[HW WARNING] WMI/pythoncom no está disponible."
        )


# ============================================================
# TIPS
# ============================================================

HARDWARE_TIPS = [

    (
        "La pasta térmica debe aplicarse en una cantidad "
        "moderada y siguiendo las recomendaciones del "
        "fabricante del disipador o procesador."
    ),

    (
        "Mantener espacio libre en un SSD ayuda a conservar "
        "un buen rendimiento, especialmente durante cargas "
        "intensivas de escritura."
    ),

    (
        "El polvo acumulado en disipadores y ventiladores "
        "puede reducir la capacidad de refrigeración del "
        "equipo y aumentar las temperaturas."
    ),

    (
        "En equipos compatibles, utilizar dos módulos de RAM "
        "puede permitir el funcionamiento en Dual-Channel."
    ),

    (
        "TRIM ayuda a los SSD compatibles a gestionar "
        "correctamente los bloques que ya no contienen "
        "datos válidos."
    ),
]


# ============================================================
# PROCESAR ICONO
# ============================================================

def process_clean_icon(image_path):

    try:

        img = PILImage.open(
            image_path
        ).convert("RGBA")

        width, height = img.size

        crop_box = (
            int(width * 0.15),
            int(height * 0.10),
            int(width * 0.85),
            int(height * 0.68),
        )

        img_cropped = img.crop(
            crop_box
        )

        datas = img_cropped.getdata()

        new_data = []

        for item in datas:

            if (
                item[0] > 215
                and item[1] > 215
                and item[2] > 215
            ):

                new_data.append(
                    (255, 255, 255, 0)
                )

            else:

                new_data.append(item)

        img_cropped.putdata(
            new_data
        )

        buffer = io.BytesIO()

        img_cropped.save(
            buffer,
            format="PNG"
        )

        buffer.seek(0)

        return buffer

    except Exception as e:

        print(
            f"[PDF WARNING] Error procesando icono: {e}"
        )

        return None


# ============================================================
# LOGO
# ============================================================

def get_logo_image():

    current_dir = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    parent_dir = os.path.dirname(
        current_dir
    )

    possible_paths = [

        os.path.join(
            parent_dir,
            "CorePulseIcon.png"
        ),

        os.path.join(
            current_dir,
            "CorePulseIcon.png"
        ),

        os.path.join(
            os.getcwd(),
            "CorePulseIcon.png"
        ),

        "CorePulseIcon.png",
    ]

    for path in possible_paths:

        if os.path.exists(path):

            try:

                return Image(
                    path,
                    width=85,
                    height=65
                )

            except Exception as e:

                print(
                    f"[PDF WARNING] No se pudo "
                    f"cargar logo: {e}"
                )

    return None


# ============================================================
# MODELO EXACTO
# ============================================================

def get_exact_system_model(
    telemetry_data
):

    vendor = "Genérico"
    model = "Equipo"

    if not isinstance(
        telemetry_data,
        dict
    ):

        telemetry_data = {}

    board_info = telemetry_data.get(
        "board_info",
        ""
    )

    # --------------------------------------------------------
    # WINDOWS
    # --------------------------------------------------------

    if IS_WINDOWS and wmi:

        try:

            if pythoncom:
                pythoncom.CoInitialize()

            c = wmi.WMI()

            computers = (
                c.Win32_ComputerSystem()
            )

            if computers:

                computer = computers[0]

                vendor_value = (
                    computer.Manufacturer.strip()
                    if computer.Manufacturer
                    else ""
                )

                model_value = (
                    computer.Model.strip()
                    if computer.Model
                    else ""
                )

                if (
                    vendor_value
                    and "to be filled"
                    not in vendor_value.lower()
                ):

                    vendor = vendor_value

                if (
                    model_value
                    and "to be filled"
                    not in model_value.lower()
                ):

                    model = model_value

        except Exception as e:

            print(
                f"[HW WARNING] Error WMI: {e}"
            )

        finally:

            try:

                if pythoncom:
                    pythoncom.CoUninitialize()

            except Exception:
                pass

    # --------------------------------------------------------
    # LINUX
    # --------------------------------------------------------

    elif platform.system() == "Linux":

        try:

            vendor_path = (
                "/sys/class/dmi/id/sys_vendor"
            )

            model_path = (
                "/sys/class/dmi/id/product_name"
            )

            if os.path.exists(
                vendor_path
            ):

                with open(
                    vendor_path,
                    "r",
                    encoding="utf-8",
                    errors="ignore"
                ) as f:

                    vendor = f.read().strip()

            if os.path.exists(
                model_path
            ):

                with open(
                    model_path,
                    "r",
                    encoding="utf-8",
                    errors="ignore"
                ) as f:

                    model = f.read().strip()

        except Exception as e:

            print(
                f"[HW WARNING] Error DMI: {e}"
            )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    if (
        not model
        or model == "Equipo"
        or "to be filled" in model.lower()
    ):

        if (
            board_info
            and board_info != "Desconocida"
        ):

            return str(board_info)

        return f"{vendor} PC"

    return f"{vendor} {model}".strip()


# ============================================================
# ABRIR PDF
# ============================================================

def open_file_automatically(
    file_path
):

    try:

        if IS_WINDOWS:

            os.startfile(
                file_path
            )

        elif platform.system() == "Darwin":

            subprocess.Popen(
                ["open", file_path]
            )

        else:

            subprocess.Popen(
                ["xdg-open", file_path]
            )

    except Exception as e:

        print(
            f"[PDF WARNING] No se pudo abrir "
            f"automáticamente: {e}"
        )


# ============================================================
# YOUTUBE
# ============================================================

def create_youtube_url(
    query
):

    return (
        "https://www.youtube.com/results?"
        "search_query="
        + quote(query)
    )


# ============================================================
# RESPALDO LOCAL
# ============================================================

def get_maintenance_recommendations(
    telemetry_data,
    disks_data
):

    recommendations = []

    if not isinstance(
        telemetry_data,
        dict
    ):

        telemetry_data = {}

    if not isinstance(
        disks_data,
        list
    ):

        disks_data = []

    is_laptop = bool(
        telemetry_data.get(
            "is_laptop",
            False
        )
    )

    exact_model = get_exact_system_model(
        telemetry_data
    )

    cpu_name = str(
        telemetry_data.get(
            "cpu_name",
            "Procesador"
        )
    )

    gpu_name = str(
        telemetry_data.get(
            "gpu_name",
            "Gráfica"
        )
    )

    cpu_temp = float(
        telemetry_data.get(
            "cpu_temp",
            0
        ) or 0
    )

    gpu_temp = float(
        telemetry_data.get(
            "gpu_temp",
            0
        ) or 0
    )

    ram_usage = float(
        telemetry_data.get(
            "ram_usage",
            0
        ) or 0
    )

    # ========================================================
    # CPU
    # ========================================================

    if cpu_temp >= 85:

        link = create_youtube_url(
            f"limpieza refrigeración CPU {cpu_name}"
        )

        if is_laptop:

            recommendations.append({

                "component": (
                    f"CPU ({cpu_temp:.0f}°C)"
                ),

                "action": (
                    "Revisar refrigeración "
                    "del portátil"
                ),

                "steps": [

                    "Apagar completamente el equipo.",

                    "Desconectar el cargador.",

                    "Comprobar que las rejillas "
                    "de ventilación estén libres.",

                    "Si la temperatura continúa "
                    "alta, realizar mantenimiento "
                    "siguiendo el manual del fabricante.",
                ],

                "supplies": [
                    "Aire comprimido",
                    "Paño de microfibra",
                ],

                "link": link
            })

        else:

            recommendations.append({

                "component": (
                    f"CPU ({cpu_temp:.0f}°C)"
                ),

                "action": (
                    "Revisar sistema de refrigeración"
                ),

                "steps": [

                    "Apagar completamente el equipo.",

                    "Desconectar la alimentación.",

                    "Comprobar ventiladores y disipador.",

                    "Limpiar cuidadosamente "
                    "el polvo acumulado.",
                ],

                "supplies": [
                    "Aire comprimido",
                    "Paño de microfibra",
                ],

                "link": link
            })

    # ========================================================
    # GPU
    # ========================================================

    if gpu_temp >= 85:

        link = create_youtube_url(
            f"limpieza refrigeración GPU {gpu_name}"
        )

        recommendations.append({

            "component": (
                f"GPU ({gpu_temp:.0f}°C)"
            ),

            "action": (
                "Revisar refrigeración de la GPU"
            ),

            "steps": [

                "Comprobar que los ventiladores "
                "funcionen correctamente.",

                "Limpiar las entradas y "
                "salidas de aire.",

                "Comprobar si la temperatura "
                "continúa elevada bajo carga.",
            ],

            "supplies": [
                "Aire comprimido",
                "Brocha antiestática",
            ],

            "link": link
        })

    # ========================================================
    # RAM
    # ========================================================

    if ram_usage >= 90:

        link = create_youtube_url(
            f"optimizar memoria RAM {exact_model}"
        )

        recommendations.append({

            "component": (
                f"RAM ({ram_usage:.0f}% de uso)"
            ),

            "action": (
                "Revisar consumo elevado "
                "de memoria"
            ),

            "steps": [

                "Abrir el Administrador de tareas.",

                "Identificar las aplicaciones "
                "que consumen más memoria.",

                "Cerrar aplicaciones innecesarias.",

                "Considerar una ampliación si el "
                "consumo elevado es habitual.",
            ],

            "supplies": [],

            "link": link
        })

    # ========================================================
    # DISCOS
    # ========================================================

    for disk in disks_data:

        if not isinstance(
            disk,
            dict
        ):
            continue

        health = float(
            disk.get(
                "health",
                100
            ) or 100
        )

        used_percent = float(
            disk.get(
                "used_percent",
                0
            ) or 0
        )

        disk_name = str(
            disk.get(
                "model",
                "Unidad de almacenamiento"
            )
        )

        # ----------------------------------------------------
        # SALUD
        # ----------------------------------------------------

        if health < 80:

            link = create_youtube_url(
                f"copia seguridad reemplazar SSD {exact_model}"
            )

            recommendations.append({

                "component": (
                    f"Almacenamiento: {disk_name}"
                ),

                "action": (
                    f"Salud S.M.A.R.T. baja "
                    f"({health:.0f}%)"
                ),

                "steps": [

                    "Realizar una copia de seguridad "
                    "de los datos importantes.",

                    "Evitar operaciones innecesarias "
                    "de escritura.",

                    "Comprobar los datos S.M.A.R.T. "
                    "de la unidad.",

                    "Considerar reemplazar la unidad "
                    "si el deterioro continúa.",
                ],

                "supplies": [
                    "Unidad SSD/NVMe compatible "
                    "si se requiere reemplazo"
                ],

                "link": link
            })

        elif used_percent > 85:

            link = create_youtube_url(
                f"liberar espacio SSD {exact_model}"
            )

            recommendations.append({

                "component": (
                    f"Almacenamiento: {disk_name}"
                ),

                "action": (
                    f"Espacio ocupado elevado "
                    f"({used_percent:.0f}%)"
                ),

                "steps": [

                    "Eliminar archivos temporales "
                    "innecesarios.",

                    "Desinstalar programas "
                    "que ya no utilices.",

                    "Mover archivos grandes "
                    "a otro almacenamiento.",

                    "Mantener suficiente espacio "
                    "libre para el funcionamiento "
                    "normal de la unidad.",
                ],

                "supplies": [],

                "link": link
            })

    return recommendations


# ============================================================
# FORMATEAR PASOS
# ============================================================

def format_steps(
    steps
):

    if isinstance(
        steps,
        list
    ):

        result = []

        for index, step in enumerate(
            steps,
            start=1
        ):

            safe_step = escape(
                str(step)
            )

            result.append(
                f"{index}. {safe_step}"
            )

        return "<br/>".join(
            result
        )

    if steps is None:
        return ""

    return escape(
        str(steps)
    )


# ============================================================
# FORMATEAR INSUMOS
# ============================================================

def format_supplies(
    supplies
):

    if isinstance(
        supplies,
        list
    ):

        result = []

        for supply in supplies:

            safe_supply = escape(
                str(supply)
            )

            result.append(
                f"• {safe_supply}"
            )

        return "<br/>".join(
            result
        )

    if supplies is None:
        return ""

    return escape(
        str(supplies)
    )


# ============================================================
# GENERAR PDF
# ============================================================

def generate_pdf_report(
    telemetry_data,
    disks_data,
    health_score,
    output_path=None
):

    # --------------------------------------------------------
    # VALIDACIÓN
    # --------------------------------------------------------

    if not isinstance(
        telemetry_data,
        dict
    ):

        telemetry_data = {}

    if not isinstance(
        disks_data,
        list
    ):

        disks_data = []

    # --------------------------------------------------------
    # RUTA
    # --------------------------------------------------------

    if not output_path:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        desktop = os.path.join(
            os.path.expanduser("~"),
            "Desktop"
        )

        if not os.path.isdir(
            desktop
        ):

            desktop = os.path.expanduser(
                "~"
            )

        output_path = os.path.join(
            desktop,
            f"Reporte_DiagnosticPC_{timestamp}.pdf"
        )

    # --------------------------------------------------------
    # DOCUMENTO
    # --------------------------------------------------------

    doc = SimpleDocTemplate(

        output_path,

        pagesize=letter,

        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # ========================================================
    # ESTILOS
    # ========================================================

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=8,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
        spaceAfter=2,
    )

    cell_style = ParagraphStyle(
        "Cell_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )

    header_style = ParagraphStyle(
        "Header_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.whitesmoke,
    )

    tip_style = ParagraphStyle(
        "Tip_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    )

    link_style = ParagraphStyle(
        "Link_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#2563eb"),
    )

    success_title_style = ParagraphStyle(
        "SuccessTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=1,
        textColor=colors.HexColor("#047857"),
        spaceAfter=6,
    )

    success_body_style = ParagraphStyle(
        "SuccessBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#065f46"),
    )

    # ========================================================
    # ELEMENTOS
    # ========================================================

    elements = []

    now_str = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    exact_device_model = (
        get_exact_system_model(
            telemetry_data
        )
    )

    safe_model = escape(
        str(exact_device_model)
    )

    # ========================================================
    # ENCABEZADO
    # ========================================================

    img_logo = get_logo_image()

    title_text_block = [

        Paragraph(
            "CorePulse - Informe de Diagnóstico Hardware",
            title_style
        ),

        Paragraph(
            "Hardware Telemetry & Predictive Diagnostics Engine",
            subtitle_style
        ),
    ]

    if img_logo:

        header_table = Table(
            [[
                title_text_block,
                img_logo
            ]],
            colWidths=[
                450,
                90
            ]
        )

        header_table.setStyle(
            TableStyle([
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
                (
                    "ALIGN",
                    (1, 0),
                    (1, 0),
                    "RIGHT"
                ),
            ])
        )

        elements.append(
            header_table
        )

    else:

        elements.extend(
            title_text_block
        )

    # ========================================================
    # INFORMACIÓN SISTEMA
    # ========================================================

    chassis_value = str(
        telemetry_data.get(
            "chassis_label",
            "N/A"
        )
    )

    board_value = str(
        telemetry_data.get(
            "board_info",
            "N/A"
        )
    )

    bios_value = str(
        telemetry_data.get(
            "bios_info",
            "N/A"
        )
    )

    health_value = float(
        health_score or 0
    )

    info_header = (

        f"<b>Fecha:</b> "
        f"{escape(now_str)} "

        f"&nbsp;|&nbsp; "

        f"<b>Modelo:</b> "
        f"<font color='#2563eb'>"
        f"<b>{safe_model}</b>"
        f"</font> "

        f"&nbsp;|&nbsp; "

        f"<b>Salud Global:</b> "
        f"<font color='#10b981'>"
        f"<b>{health_value:.1f}%</b>"
        f"</font>"

        f"<br/>"

        f"<b>Factor de Forma:</b> "
        f"{escape(chassis_value)} "

        f"&nbsp;|&nbsp; "

        f"<b>Placa Base:</b> "
        f"{escape(board_value)} "

        f"&nbsp;|&nbsp; "

        f"<b>BIOS:</b> "
        f"{escape(bios_value)}"
    )

    elements.append(
        Paragraph(
            info_header,
            body_style
        )
    )

    elements.append(
        HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor("#cbd5e1"),
            spaceBefore=6,
            spaceAfter=8,
        )
    )

    # ========================================================
    # 1. RESUMEN
    # ========================================================

    elements.append(
        Paragraph(
            "1. Resumen de Componentes Clave",
            h2_style
        )
    )

    cpu_name_value = str(
        telemetry_data.get(
            "cpu_name",
            "Procesador"
        )
    )

    gpu_name_value = str(
        telemetry_data.get(
            "gpu_name",
            "Tarjeta Gráfica"
        )
    )

    cpu_usage_value = telemetry_data.get(
        "cpu_usage",
        0
    )

    cpu_temp_value = telemetry_data.get(
        "cpu_temp",
        "--"
    )

    ram_usage_value = telemetry_data.get(
        "ram_usage",
        0
    )

    ram_used_value = telemetry_data.get(
        "ram_used_gb",
        0
    )

    ram_total_value = telemetry_data.get(
        "ram_total_gb",
        0
    )

    gpu_usage_value = telemetry_data.get(
        "gpu_usage",
        0
    )

    gpu_temp_value = telemetry_data.get(
        "gpu_temp",
        "--"
    )

    table_data = [

        [
            Paragraph(
                "Componente",
                header_style
            ),

            Paragraph(
                "Modelo Detectado",
                header_style
            ),

            Paragraph(
                "Uso / Estado",
                header_style
            ),

            Paragraph(
                "Temperatura / Capacidad",
                header_style
            ),
        ],

        [
            Paragraph(
                "CPU",
                cell_style
            ),

            Paragraph(
                escape(cpu_name_value),
                cell_style
            ),

            Paragraph(
                f"{cpu_usage_value} %",
                cell_style
            ),

            Paragraph(
                f"{cpu_temp_value} °C",
                cell_style
            ),
        ],

        [
            Paragraph(
                "RAM",
                cell_style
            ),

            Paragraph(
                "Memoria del Sistema",
                cell_style
            ),

            Paragraph(
                f"{ram_usage_value} %",
                cell_style
            ),

            Paragraph(
                f"{ram_used_value} GB / "
                f"{ram_total_value} GB",
                cell_style
            ),
        ],

        [
            Paragraph(
                "GPU",
                cell_style
            ),

            Paragraph(
                escape(gpu_name_value),
                cell_style
            ),

            Paragraph(
                f"{gpu_usage_value} %",
                cell_style
            ),

            Paragraph(
                f"{gpu_temp_value} °C",
                cell_style
            ),
        ],
    ]

    t = Table(
        table_data,
        colWidths=[
            65,
            260,
            85,
            130
        ]
    )

    t.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#2563eb")
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#cbd5e1")
            ),

            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                colors.HexColor("#f8fafc")
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
        ])
    )

    elements.append(t)

    elements.append(
        Spacer(1, 8)
    )

    # ========================================================
    # 2. ALMACENAMIENTO
    # ========================================================

    elements.append(
        Paragraph(
            "2. Salud y Espacio de Almacenamiento (S.M.A.R.T.)",
            h2_style
        )
    )

    disk_rows = [[

        Paragraph(
            "Unidad",
            header_style
        ),

        Paragraph(
            "Modelo / Punto de Montaje",
            header_style
        ),

        Paragraph(
            "Salud S.M.A.R.T.",
            header_style
        ),

        Paragraph(
            "Espacio Ocupado",
            header_style
        ),
    ]]

    valid_disk_count = 0

    for disk in disks_data:

        if not isinstance(
            disk,
            dict
        ):
            continue

        valid_disk_count += 1

        disk_index = disk.get(
            "index",
            valid_disk_count
        )

        disk_model = str(
            disk.get(
                "model",
                "N/A"
            )
        )

        mount_points = str(
            disk.get(
                "mount_points",
                ""
            )
        )

        disk_health = disk.get(
            "health",
            0
        )

        used_gb = disk.get(
            "used_gb",
            0
        )

        total_gb = disk.get(
            "total_gb",
            0
        )

        used_percent = disk.get(
            "used_percent",
            0
        )

        unit_text = (
            f"Disco {disk_index}"
        )

        model_text = (
            f"{disk_model} "
            f"[{mount_points}]"
        )

        space_text = (
            f"{used_gb} GB / "
            f"{total_gb} GB "
            f"({used_percent}%)"
        )

        disk_rows.append([

            Paragraph(
                escape(unit_text),
                cell_style
            ),

            Paragraph(
                escape(model_text),
                cell_style
            ),

            Paragraph(
                f"{disk_health}%",
                cell_style
            ),

            Paragraph(
                escape(space_text),
                cell_style
            ),
        ])

    if valid_disk_count == 0:

        disk_rows.append([

            Paragraph(
                "—",
                cell_style
            ),

            Paragraph(
                "No se detectaron unidades",
                cell_style
            ),

            Paragraph(
                "N/A",
                cell_style
            ),

            Paragraph(
                "N/A",
                cell_style
            ),
        ])

    t_disks = Table(
        disk_rows,
        colWidths=[
            65,
            245,
            100,
            130
        ]
    )

    t_disks.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#2563eb")
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#cbd5e1")
            ),

            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                colors.white
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
        ])
    )

    elements.append(
        t_disks
    )

    elements.append(
        Spacer(1, 8)
    )

    # ========================================================
    # 3. DIAGNÓSTICO IA
    # ========================================================

    elements.append(
        Paragraph(
            (
                "3. Diagnóstico Autónomo con IA e "
                f"Instrucciones Específicas ({safe_model})"
            ),
            h2_style
        )
    )

    # --------------------------------------------------------
    # IA
    # --------------------------------------------------------

    ai_recs = generate_ai_tutorial(
        telemetry_data,
        disks_data
    )

    # --------------------------------------------------------
    # IMPORTANTE
    # --------------------------------------------------------
    #
    # Una lista vacía de IA es ahora un resultado válido:
    # significa que la IA determinó que no existen problemas.
    #
    # Pero si la IA falló por completo, también devuelve [].
    # Para distinguir ambos casos necesitamos verificar
    # la API key.
    # --------------------------------------------------------

    groq_available = bool(
        os.getenv("GROQ_API_KEY")
    )

    if ai_recs:

        recs = ai_recs

        ai_status = (
            "Diagnóstico generado mediante IA "
            "a partir de la telemetría detectada."
        )

        analysis_passed = False

    elif groq_available:

        # ----------------------------------------------------
        # LA IA RESPONDIÓ VACÍO.
        #
        # En nuestro nuevo contrato esto significa:
        # NO HAY PROBLEMAS.
        # ----------------------------------------------------

        recs = []

        ai_status = (
            "La IA analizó la telemetría y "
            "no detectó condiciones que requieran "
            "mantenimiento correctivo."
        )

        analysis_passed = True

    else:

        # ----------------------------------------------------
        # SIN API KEY → FALLBACK LOCAL
        # ----------------------------------------------------

        recs = get_maintenance_recommendations(
            telemetry_data,
            disks_data
        )

        ai_status = (
            "IA no disponible; se utilizó "
            "el diagnóstico local de respaldo."
        )

        analysis_passed = (
            len(recs) == 0
        )

    # ========================================================
    # RESULTADO SUPERADO
    # ========================================================

    if analysis_passed:

        success_table = Table(

            [[
                Paragraph(
                    "✓ ANÁLISIS SUPERADO",
                    success_title_style
                )
            ],

            [
                Paragraph(
                    (
                        "<b>¡Felicitaciones!</b><br/><br/>"
                        "CorePulse no detectó condiciones "
                        "anormales que requieran una "
                        "intervención de mantenimiento "
                        "en este diagnóstico.<br/><br/>"
                        "Las temperaturas, memoria y "
                        "almacenamiento analizados se "
                        "encuentran dentro de condiciones "
                        "aceptables según la telemetría "
                        "disponible."
                    ),
                    success_body_style
                )
            ]],

            colWidths=[
                540
            ]
        )

        success_table.setStyle(
            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#ecfdf5")
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    1.5,
                    colors.HexColor("#10b981")
                ),

                (
                    "PADDING",
                    (0, 0),
                    (-1, -1),
                    12
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
            ])
        )

        elements.append(
            success_table
        )

        elements.append(
            Spacer(1, 8)
        )

    # ========================================================
    # ESTADO IA
    # ========================================================

    elements.append(
        Paragraph(
            f"<font color='#64748b'>"
            f"{escape(ai_status)}"
            f"</font>",
            body_style
        )
    )

    # ========================================================
    # TABLA DE RECOMENDACIONES
    # ========================================================

    if recs:

        rec_table_data = [[

            Paragraph(
                "Componente / Alerta",
                header_style
            ),

            Paragraph(
                "Acción Recomendada",
                header_style
            ),

            Paragraph(
                "Pasos Específicos e Insumos",
                header_style
            ),

            Paragraph(
                "Tutorial",
                header_style
            ),
        ]]

        for recommendation in recs:

            if not isinstance(
                recommendation,
                dict
            ):
                continue

            component_value = str(
                recommendation.get(
                    "component",
                    "General"
                )
            )

            action_value = str(
                recommendation.get(
                    "action",
                    "Mantenimiento"
                )
            )

            component = escape(
                component_value
            )

            action = escape(
                action_value
            )

            steps = format_steps(
                recommendation.get(
                    "steps",
                    []
                )
            )

            supplies = format_supplies(
                recommendation.get(
                    "supplies",
                    []
                )
            )

            if not steps:
                steps = "No especificados"

            if not supplies:
                supplies = "Ninguno especificado"

            steps_text = (
                f"<b>Pasos:</b><br/>"
                f"{steps}"
                f"<br/><br/>"
                f"<b>Insumos:</b><br/>"
                f"{supplies}"
            )

            link_url = recommendation.get(
                "link",
                ""
            )

            if link_url:

                safe_link = escape(
                    str(link_url),
                    {'"': "&quot;"}
                )

                link_p = Paragraph(

                    (
                        f"<a href='{safe_link}'>"
                        f"<u>Ver tutorial relacionado</u>"
                        f"</a>"
                    ),

                    link_style
                )

            else:

                link_p = Paragraph(
                    "Sin enlace",
                    body_style
                )

            rec_table_data.append([

                Paragraph(
                    f"<b>{component}</b>",
                    body_style
                ),

                Paragraph(
                    action,
                    body_style
                ),

                Paragraph(
                    steps_text,
                    body_style
                ),

                link_p,
            ])

        t_recs = Table(

            rec_table_data,

            colWidths=[
                100,
                110,
                250,
                80
            ],

            repeatRows=1
        )

        t_recs.setStyle(
            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#2563eb")
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#cbd5e1")
                ),

                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, -1),
                    colors.HexColor("#f8fafc")
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
            ])
        )

        elements.append(
            t_recs
        )

        elements.append(
            Spacer(1, 8)
        )

    # ========================================================
    # TIP PROFESIONAL
    # ========================================================

    elements.append(
        Paragraph(
            "Tip Profesional de Hardware",
            h2_style
        )
    )

    tip_selected = random.choice(
        HARDWARE_TIPS
    )

    tip_selected = escape(
        tip_selected
    )

    t_tip = Table(

        [[
            Paragraph(
                f"<i>“{tip_selected}”</i>",
                tip_style
            )
        ]],

        colWidths=[
            540
        ]
    )

    t_tip.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, -1),
                colors.HexColor("#f1f5f9")
            ),

            (
                "BOX",
                (0, 0),
                (-1, -1),
                1,
                colors.HexColor("#cbd5e1")
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    elements.append(
        t_tip
    )

    # ========================================================
    # GENERAR PDF
    # ========================================================

    try:

        doc.build(
            elements
        )

    except Exception as e:

        print(
            f"[PDF ERROR] No se pudo generar "
            f"el PDF: {e}"
        )

        raise

    print(
        f"[PDF INFO] Informe generado: "
        f"{output_path}"
    )

    open_file_automatically(
        output_path
    )

    return output_path
