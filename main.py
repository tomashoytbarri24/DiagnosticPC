import customtkinter as ctk
import threading
import time
import psutil
import os
import platform

from collections import deque
from tkinter import messagebox, filedialog
from datetime import datetime

from PIL import Image


# =========================================================
# SISTEMA OPERATIVO
# =========================================================

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    try:
        import pythoncom
    except ImportError:
        pythoncom = None
else:
    pythoncom = None


# =========================================================
# MATPLOTLIB
# =========================================================

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# =========================================================
# CORE
# =========================================================

from core.telemetry import (
    get_system_telemetry,
    get_all_disks_data,
    calculate_preliminary_score
)

from core.report_generator import (
    generate_pdf_report
)

from core.cleaner import (
    clean_temp_files,
    empty_recycle_bin,
    flush_dns_cache,
    optimize_ram_memory,
    find_duplicate_files,
    delete_duplicate_file
)

from database.db import (
    init_db,
    save_telemetry_record
)

from gui.overlay import GameOverlay


# =========================================================
# APARIENCIA
# =========================================================

ctk.set_appearance_mode("Dark")

BG_MAIN = "#0b0f19"
BG_CARD = "#151c2c"
BG_SIDEBAR = "#0d1322"
BORDER_COLOR = "#232f48"

COLOR_CPU = "#38bdf8"
COLOR_RAM = "#10b981"
COLOR_GPU = "#a855f7"
COLOR_TEXT_DIM = "#94a3b8"


# =========================================================
# DUPLICATE SCANNER
# =========================================================

class DuplicateScannerWindow(ctk.CTkToplevel):

    def __init__(
        self,
        master=None,
        **kwargs
    ):

        super().__init__(
            master,
            **kwargs
        )

        self.title(
            "Buscador de Archivos Duplicados"
        )

        self.geometry(
            "900x650"
        )

        self.configure(
            fg_color=BG_MAIN
        )

        self.lift()
        self.focus_force()

        self.grid_columnconfigure(
            0,
            weight=1
        )

        self.grid_rowconfigure(
            3,
            weight=1
        )

        # =================================================
        # PANEL SUPERIOR
        # =================================================

        frame_top = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_COLOR
        )

        frame_top.grid(
            row=0,
            column=0,
            padx=15,
            pady=(15, 5),
            sticky="ew"
        )

        ctk.CTkLabel(
            frame_top,
            text="Carpeta:",
            font=("Segoe UI", 11, "bold")
        ).pack(
            side="left",
            padx=10,
            pady=10
        )

        default_folder = os.path.expanduser(
            "~/Downloads"
        )

        if IS_WINDOWS:
            fallback_path = "C:\\"
        else:
            fallback_path = "/"

        self.entry_path = ctk.CTkEntry(
            frame_top,
            font=("Segoe UI", 10)
        )

        self.entry_path.insert(
            0,
            (
                default_folder
                if os.path.exists(default_folder)
                else fallback_path
            )
        )

        self.entry_path.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5,
            pady=10
        )

        btn_browse = ctk.CTkButton(
            frame_top,
            text="📁 Buscar",
            width=80,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self.browse_folder
        )

        btn_browse.pack(
            side="left",
            padx=5,
            pady=10
        )

        self.btn_scan = ctk.CTkButton(
            frame_top,
            text="🔍 Iniciar Escaneo",
            width=130,
            fg_color="#10b981",
            hover_color="#059669",
            command=self.start_scan
        )

        self.btn_scan.pack(
            side="left",
            padx=(5, 10),
            pady=10
        )

        # =================================================
        # ACCIONES
        # =================================================

        frame_actions = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        frame_actions.grid(
            row=1,
            column=0,
            padx=15,
            pady=5,
            sticky="ew"
        )

        ctk.CTkLabel(
            frame_actions,
            text="Accesos rápidos:",
            font=("Segoe UI", 10, "bold"),
            text_color=COLOR_TEXT_DIM
        ).pack(
            side="left",
            padx=(0, 5)
        )

        ctk.CTkButton(
            frame_actions,
            text="📥 Descargas",
            width=90,
            height=26,
            fg_color="#1e293b",
            hover_color="#334155",
            command=lambda: self.set_preset_path(
                os.path.expanduser("~/Downloads")
            )
        ).pack(
            side="left",
            padx=3
        )

        ctk.CTkButton(
            frame_actions,
            text="📄 Documentos",
            width=95,
            height=26,
            fg_color="#1e293b",
            hover_color="#334155",
            command=lambda: self.set_preset_path(
                os.path.expanduser("~/Documents")
            )
        ).pack(
            side="left",
            padx=3
        )

        root_label = (
            "💾 Disco C:"
            if IS_WINDOWS
            else "💾 Raíz /"
        )

        root_path = (
            "C:\\"
            if IS_WINDOWS
            else "/"
        )

        ctk.CTkButton(
            frame_actions,
            text=root_label,
            width=80,
            height=26,
            fg_color="#1e293b",
            hover_color="#334155",
            command=lambda: self.set_preset_path(
                root_path
            )
        ).pack(
            side="left",
            padx=3
        )

        self.btn_auto_select = ctk.CTkButton(
            frame_actions,
            text="⚡ Auto-Seleccionar Copias",
            width=160,
            height=26,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            state="disabled",
            command=self.auto_select_duplicates
        )

        self.btn_auto_select.pack(
            side="right",
            padx=3
        )

        self.btn_delete_selected = ctk.CTkButton(
            frame_actions,
            text="🗑️ Eliminar Seleccionados",
            width=160,
            height=26,
            fg_color="#ef4444",
            hover_color="#dc2626",
            state="disabled",
            command=self.delete_selected_batch
        )

        self.btn_delete_selected.pack(
            side="right",
            padx=3
        )

        # =================================================
        # STATUS
        # =================================================

        frame_status = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        frame_status.grid(
            row=2,
            column=0,
            padx=15,
            pady=(5, 5),
            sticky="ew"
        )

        self.lbl_status = ctk.CTkLabel(
            frame_status,
            text=(
                "Presiona 'Iniciar Escaneo' "
                "o elige un acceso rápido."
            ),
            font=("Segoe UI", 10),
            text_color=COLOR_TEXT_DIM
        )

        self.lbl_status.pack(
            anchor="w",
            side="top",
            pady=(0, 2)
        )

        self.progress_bar = ctk.CTkProgressBar(
            frame_status,
            height=6,
            progress_color="#38bdf8",
            fg_color="#0f172a"
        )

        self.progress_bar.set(0)

        self.progress_bar.pack(
            fill="x",
            side="bottom"
        )

        # =================================================
        # RESULTADOS
        # =================================================

        self.scroll_results = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent"
        )

        self.scroll_results.grid(
            row=3,
            column=0,
            padx=15,
            pady=(0, 15),
            sticky="nsew"
        )

        self.checkboxes_map = {}

        # Estado del escaneo
        self.scan_running = False

        # Cerrar correctamente
        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

    # -----------------------------------------------------
    # PRESETS
    # -----------------------------------------------------

    def set_preset_path(self, path):

        if not os.path.exists(path):
            return

        self.entry_path.delete(
            0,
            "end"
        )

        self.entry_path.insert(
            0,
            path
        )

        self.start_scan()

    # -----------------------------------------------------
    # BROWSE
    # -----------------------------------------------------

    def browse_folder(self):

        if not self.winfo_exists():
            return

        folder = filedialog.askdirectory(
            title=(
                "Selecciona la carpeta "
                "para escanear duplicados"
            ),
            parent=self
        )

        if folder:

            self.entry_path.delete(
                0,
                "end"
            )

            self.entry_path.insert(
                0,
                folder
            )

    # -----------------------------------------------------
    # SCAN
    # -----------------------------------------------------

    def start_scan(self):

        if not self.winfo_exists():
            return

        if self.scan_running:
            return

        path = self.entry_path.get().strip()

        if (
            not path
            or not os.path.exists(path)
        ):

            messagebox.showwarning(
                "DiagnosticPC",
                "Por favor selecciona una ruta válida.",
                parent=self
            )

            return

        self.scan_running = True

        self.btn_scan.configure(
            state="disabled"
        )

        self.btn_auto_select.configure(
            state="disabled"
        )

        self.btn_delete_selected.configure(
            state="disabled"
        )

        self.lbl_status.configure(
            text=f"Escaneando carpeta: {path}...",
            text_color="#38bdf8"
        )

        self.progress_bar.configure(
            mode="indeterminate"
        )

        self.progress_bar.start()

        for widget in (
            self.scroll_results.winfo_children()
        ):
            widget.destroy()

        self.checkboxes_map.clear()

        threading.Thread(
            target=self._run_scan_thread,
            args=(path,),
            daemon=True,
            name="DiagnosticPC-DuplicateScanner"
        ).start()

    # -----------------------------------------------------
    # THREAD SCAN
    # -----------------------------------------------------

    def _run_scan_thread(self, target_path):

        try:

            duplicates = find_duplicate_files(
                target_path,
                status_callback=self._update_status_safe
            )

            try:

                self.after(
                    0,
                    self._render_results,
                    duplicates
                )

            except Exception:
                pass

        except Exception as e:

            try:

                self.after(
                    0,
                    self._scan_error,
                    str(e)
                )

            except Exception:
                pass

    # -----------------------------------------------------
    # SCAN ERROR
    # -----------------------------------------------------

    def _scan_error(self, error):

        if not self.winfo_exists():
            return

        self.scan_running = False

        self.progress_bar.stop()

        self.progress_bar.configure(
            mode="determinate"
        )

        self.progress_bar.set(0)

        self.btn_scan.configure(
            state="normal"
        )

        self.lbl_status.configure(
            text=f"Error durante el escaneo: {error}",
            text_color="#ef4444"
        )

    # -----------------------------------------------------
    # STATUS SAFE
    # -----------------------------------------------------

    def _update_status_safe(self, text):

        try:

            if not self.winfo_exists():
                return

            self.after(
                0,
                lambda: self._set_status_if_alive(
                    text
                )
            )

        except Exception:
            pass

    def _set_status_if_alive(self, text):

        try:

            if self.winfo_exists():

                self.lbl_status.configure(
                    text=text
                )

        except Exception:
            pass

    # -----------------------------------------------------
    # RENDER RESULTS
    # -----------------------------------------------------

    def _render_results(self, duplicates):

        if not self.winfo_exists():
            return

        self.scan_running = False

        self.progress_bar.stop()

        self.progress_bar.configure(
            mode="determinate"
        )

        self.progress_bar.set(1.0)

        self.btn_scan.configure(
            state="normal"
        )

        if not duplicates:

            self.btn_auto_select.configure(
                state="disabled"
            )

            self.btn_delete_selected.configure(
                state="disabled"
            )

            self.lbl_status.configure(
                text=(
                    "¡No se encontraron archivos "
                    "duplicados en esta ruta!"
                ),
                text_color="#10b981"
            )

            return

        total_groups = len(
            duplicates
        )

        total_files = sum(
            len(paths)
            for paths in duplicates.values()
        )

        self.lbl_status.configure(
            text=(
                f"Se encontraron {total_groups} "
                f"grupos de duplicados "
                f"({total_files} archivos en total)."
            ),
            text_color="#f59e0b"
        )

        self.btn_auto_select.configure(
            state="normal"
        )

        self.btn_delete_selected.configure(
            state="normal"
        )

        for (file_hash, size), paths in duplicates.items():

            size_mb = round(
                size / (1024 ** 2),
                2
            )

            card = ctk.CTkFrame(
                self.scroll_results,
                fg_color=BG_CARD,
                corner_radius=8,
                border_width=1,
                border_color=BORDER_COLOR
            )

            card.pack(
                fill="x",
                pady=5,
                padx=2
            )

            ctk.CTkLabel(
                card,
                text=(
                    f"📄 Grupo Duplicado "
                    f"({len(paths)} copias) — "
                    f"Tamaño por copia: {size_mb} MB"
                ),
                font=("Segoe UI", 10, "bold"),
                text_color="#38bdf8"
            ).pack(
                anchor="w",
                padx=10,
                pady=(6, 4)
            )

            for idx, path in enumerate(paths):

                row = ctk.CTkFrame(
                    card,
                    fg_color="transparent"
                )

                row.pack(
                    fill="x",
                    padx=10,
                    pady=2
                )

                chk_var = ctk.BooleanVar(
                    value=False
                )

                chk = ctk.CTkCheckBox(
                    row,
                    text="",
                    variable=chk_var,
                    width=20
                )

                chk.pack(
                    side="left",
                    padx=(0, 5)
                )

                lbl_tag = (
                    " [ORIGINAL]"
                    if idx == 0
                    else " [COPIA]"
                )

                tag_color = (
                    "#10b981"
                    if idx == 0
                    else COLOR_TEXT_DIM
                )

                ctk.CTkLabel(
                    row,
                    text=path + lbl_tag,
                    font=("Segoe UI", 9),
                    text_color=tag_color,
                    anchor="w"
                ).pack(
                    side="left",
                    fill="x",
                    expand=True
                )

                self.checkboxes_map[path] = {
                    "var": chk_var,
                    "row": row,
                    "card": card,
                    "is_original": idx == 0
                }

    # -----------------------------------------------------
    # AUTO SELECT
    # -----------------------------------------------------

    def auto_select_duplicates(self):

        if not self.winfo_exists():
            return

        selected_count = 0

        for item in (
            self.checkboxes_map.values()
        ):

            if not item["is_original"]:

                item["var"].set(True)

                selected_count += 1

            else:

                item["var"].set(False)

        messagebox.showinfo(
            "Auto-Selección",
            (
                f"Se seleccionaron automáticamente "
                f"{selected_count} copias duplicadas "
                f"para eliminar."
            ),
            parent=self
        )

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    def delete_selected_batch(self):

        if not self.winfo_exists():
            return

        to_delete = [
            path
            for path, item
            in self.checkboxes_map.items()
            if item["var"].get()
        ]

        if not to_delete:

            messagebox.showwarning(
                "DiagnosticPC",
                (
                    "No has seleccionado ninguna "
                    "copia para eliminar."
                ),
                parent=self
            )

            return

        confirmed = messagebox.askyesno(
            "Confirmar Eliminación en Lote",
            (
                f"¿Estás seguro de eliminar "
                f"permanentemente los "
                f"{len(to_delete)} archivos seleccionados?"
            ),
            parent=self
        )

        if not confirmed:
            return

        deleted_count = 0

        for path in to_delete:

            try:

                deleted = delete_duplicate_file(
                    path
                )

            except Exception:

                deleted = False

            if deleted:

                deleted_count += 1

                item = self.checkboxes_map.get(
                    path
                )

                if item is None:
                    continue

                try:
                    item["row"].destroy()
                except Exception:
                    pass

                card = item["card"]

                try:

                    remaining_rows = [
                        child
                        for child
                        in card.winfo_children()
                        if isinstance(
                            child,
                            ctk.CTkFrame
                        )
                    ]

                    # El primer CTkFrame puede ser
                    # el header interno del grupo.
                    # Verificamos si quedan filas.
                    visible_children = [
                        child
                        for child
                        in card.winfo_children()
                        if child.winfo_exists()
                    ]

                    if len(visible_children) <= 1:

                        card.destroy()

                except Exception:
                    pass

                self.checkboxes_map.pop(
                    path,
                    None
                )

        messagebox.showinfo(
            "Proceso Finalizado",
            (
                f"Se eliminaron {deleted_count} "
                f"archivos duplicados con éxito."
            ),
            parent=self
        )

        self.lbl_status.configure(
            text=(
                f"Limpieza completada: "
                f"{deleted_count} archivos eliminados."
            ),
            text_color="#10b981"
        )

        if not self.checkboxes_map:

            self.btn_auto_select.configure(
                state="disabled"
            )

            self.btn_delete_selected.configure(
                state="disabled"
            )

    # -----------------------------------------------------
    # CLOSE
    # -----------------------------------------------------

    def on_close(self):

        self.scan_running = False

        try:
            self.destroy()
        except Exception:
            pass


# =========================================================
# APP PRINCIPAL
# =========================================================

class App(ctk.CTk):

    def __init__(self):

        super().__init__()

        # =================================================
        # CONFIGURACIÓN
        # =================================================

        self.title(
            "DiagnosticPC - Predictive Analytics Dashboard"
        )

        self.geometry(
            "1000x700"
        )

        self.minsize(
            850,
            600
        )

        self.resizable(
            True,
            True
        )

        self.configure(
            fg_color=BG_MAIN
        )

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

        # =================================================
        # ICONO
        # =================================================

        icon_path = os.path.join(
            "assets",
            "app_icon.ico"
        )

        if os.path.exists(icon_path):

            try:
                self.iconbitmap(
                    icon_path
                )
            except Exception:
                pass

        # =================================================
        # FULLSCREEN
        # =================================================

        self.is_fullscreen = False

        self.bind(
            "<F11>",
            self.toggle_fullscreen
        )

        self.bind(
            "<Escape>",
            self.exit_fullscreen
        )

        # =================================================
        # RESIZE
        # =================================================

        self.is_resizing = False
        self.resize_timer = None

        self.bind(
            "<Configure>",
            self.on_window_resize
        )

        # =================================================
        # DATABASE
        # =================================================

        init_db()

        # =================================================
        # ESTADO
        # =================================================

        self.is_running = True

        self.overlay_window = None
        self.duplicate_window = None

        self.latest_telemetry = None
        self.latest_disks = []
        self.latest_score = 100.0

        self.max_points = 25

        self.cpu_history = deque(
            [0] * self.max_points,
            maxlen=self.max_points
        )

        self.ram_history = deque(
            [0] * self.max_points,
            maxlen=self.max_points
        )

        self.gpu_history = deque(
            [0] * self.max_points,
            maxlen=self.max_points
        )

        self.db_counter = 0

        # =================================================
        # COLAS DE ACTUALIZACIÓN
        # =================================================

        self.telemetry_lock = threading.Lock()

        self.pending_telemetry = None
        self.pending_disks = []

        # =================================================
        # AFTER IDs
        # =================================================

        self.telemetry_after_id = None
        self.chart_after_id = None

        # =================================================
        # GRID
        # =================================================

        self.grid_columnconfigure(
            1,
            weight=1
        )

        self.grid_rowconfigure(
            0,
            weight=1
        )

        # =================================================
        # SIDEBAR
        # =================================================

        self.sidebar = ctk.CTkFrame(
            self,
            fg_color=BG_SIDEBAR,
            corner_radius=0,
            width=230
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.sidebar.grid_propagate(
            False
        )

        # =================================================
        # LOGO
        # =================================================

        self.frame_logo = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent"
        )

        self.frame_logo.pack(
            anchor="w",
            padx=15,
            pady=(20, 2),
            fill="x"
        )

        logo_img_path = None

        for possible_path in [

            os.path.join(
                "assets",
                "logo_neon_pulse.png"
            ),

            os.path.join(
                "assets",
                "logo_shield_health.png"
            ),

            os.path.join(
                "assets",
                "logo.png"
            )

        ]:

            if os.path.exists(
                possible_path
            ):

                logo_img_path = (
                    possible_path
                )

                break

        if logo_img_path:

            try:

                pil_img = Image.open(
                    logo_img_path
                )

                self.ctk_logo = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(28, 28)
                )

                self.lbl_logo_icon = ctk.CTkLabel(
                    self.frame_logo,
                    image=self.ctk_logo,
                    text=""
                )

                self.lbl_logo_icon.pack(
                    side="left",
                    padx=(0, 8)
                )

            except Exception:
                pass

        self.lbl_brand = ctk.CTkLabel(
            self.frame_logo,
            text="DiagnosticPC",
            font=("Segoe UI", 18, "bold"),
            text_color="#f8fafc"
        )

        self.lbl_brand.pack(
            side="left"
        )

        self.lbl_subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Predictive Telemetry Engine",
            font=("Segoe UI", 10),
            text_color=COLOR_TEXT_DIM
        )

        self.lbl_subtitle.pack(
            anchor="w",
            padx=15,
            pady=(0, 15)
        )

        # =================================================
        # HEALTH CARD
        # =================================================

        self.card_health_sidebar = ctk.CTkFrame(
            self.sidebar,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            corner_radius=10
        )

        self.card_health_sidebar.pack(
            fill="x",
            padx=12,
            pady=5
        )

        self.lbl_health_title = ctk.CTkLabel(
            self.card_health_sidebar,
            text="SALUD DEL SISTEMA",
            font=("Segoe UI", 9, "bold"),
            text_color=COLOR_TEXT_DIM
        )

        self.lbl_health_title.pack(
            anchor="w",
            padx=12,
            pady=(10, 2)
        )

        self.lbl_health_val = ctk.CTkLabel(
            self.card_health_sidebar,
            text="--%",
            font=("Segoe UI", 22, "bold"),
            text_color=COLOR_RAM
        )

        self.lbl_health_val.pack(
            anchor="w",
            padx=12,
            pady=(0, 2)
        )

        self.lbl_health_status = ctk.CTkLabel(
            self.card_health_sidebar,
            text="Evaluando...",
            font=("Segoe UI", 10, "bold"),
            text_color="#f8fafc"
        )

        self.lbl_health_status.pack(
            anchor="w",
            padx=12,
            pady=(0, 10)
        )

        # =================================================
        # BUTTONS
        # =================================================

        self.btn_overlay = ctk.CTkButton(
            self.sidebar,
            text="🎮 Overlay In-Game",
            fg_color="#10b981",
            hover_color="#059669",
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
            command=self.toggle_overlay
        )

        self.btn_overlay.pack(
            fill="x",
            padx=12,
            pady=(15, 5)
        )

        self.btn_pdf = ctk.CTkButton(
            self.sidebar,
            text="📄 Exportar PDF",
            fg_color="#3b82f6",
            hover_color="#2563eb",
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
            command=self.export_pdf_report
        )

        self.btn_pdf.pack(
            fill="x",
            padx=12,
            pady=5
        )

        self.btn_clean = ctk.CTkButton(
            self.sidebar,
            text="🧹 Limpiar Sistema",
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
            command=self.run_system_cleanup
        )

        self.btn_clean.pack(
            fill="x",
            padx=12,
            pady=(0, 5)
        )

        self.btn_duplicates = ctk.CTkButton(
            self.sidebar,
            text="🔍 Archivos Duplicados",
            fg_color="#ec4899",
            hover_color="#db2777",
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
            command=self.open_duplicate_scanner
        )

        self.btn_duplicates.pack(
            fill="x",
            padx=12,
            pady=(0, 0)
        )

        # =================================================
        # FOOTER
        # =================================================

        self.lbl_footer = ctk.CTkLabel(
            self.sidebar,
            text=(
                "[F11] Pantalla Completa\n"
                "[Esc] Modo Ventana"
            ),
            font=("Segoe UI", 9),
            text_color=COLOR_TEXT_DIM,
            justify="center"
        )

        self.lbl_footer.pack(
            side="bottom",
            pady=12,
            padx=10
        )

        # =================================================
        # MAIN CONTENT
        # =================================================

        self.main_content = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.main_content.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=15,
            pady=15
        )

        # =================================================
        # METRIC CARDS
        # =================================================

        self.frame_meters = ctk.CTkFrame(
            self.main_content,
            fg_color="transparent"
        )

        self.frame_meters.pack(
            fill="x",
            pady=(0, 10)
        )

        # CPU

        self.card_cpu = self.create_metric_card(
            self.frame_meters,
            "CPU",
            COLOR_CPU
        )

        self.card_cpu.pack(
            side="left",
            expand=True,
            fill="both",
            padx=(0, 5)
        )

        (
            self.lbl_cpu,
            self.bar_cpu,
            self.lbl_cpu_temp,
            self.lbl_cpu_title
        ) = self.build_card_content(
            self.card_cpu,
            COLOR_CPU
        )

        # RAM

        self.card_ram = self.create_metric_card(
            self.frame_meters,
            "MEMORIA RAM",
            COLOR_RAM
        )

        self.card_ram.pack(
            side="left",
            expand=True,
            fill="both",
            padx=3
        )

        (
            self.lbl_ram,
            self.bar_ram,
            self.lbl_ram_gb,
            self.lbl_ram_title
        ) = self.build_card_content(
            self.card_ram,
            COLOR_RAM
        )

        # GPU

        self.card_gpu = self.create_metric_card(
            self.frame_meters,
            "GPU",
            COLOR_GPU
        )

        self.card_gpu.pack(
            side="left",
            expand=True,
            fill="both",
            padx=(5, 0)
        )

        (
            self.lbl_gpu,
            self.bar_gpu,
            self.lbl_gpu_temp,
            self.lbl_gpu_title
        ) = self.build_card_content(
            self.card_gpu,
            COLOR_GPU
        )

        # =================================================
        # DISKS
        # =================================================

        self.lbl_disks_header = ctk.CTkLabel(
            self.main_content,
            text="UNIDADES DE ALMACENAMIENTO DETECTADAS",
            font=("Segoe UI", 10, "bold"),
            text_color=COLOR_TEXT_DIM
        )

        self.lbl_disks_header.pack(
            anchor="w",
            pady=(0, 4)
        )

        self.scroll_disks = ctk.CTkScrollableFrame(
            self.main_content,
            fg_color="transparent",
            height=120
        )

        self.scroll_disks.pack(
            fill="x",
            pady=(0, 10)
        )

        self.disk_widgets = {}

        # =================================================
        # CHARTS
        # =================================================

        self.frame_charts = ctk.CTkFrame(
            self.main_content,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            corner_radius=10
        )

        self.frame_charts.pack(
            fill="both",
            expand=True
        )

        self.fig = Figure(
            figsize=(7, 2.0),
            dpi=85,
            facecolor=BG_CARD
        )

        self.ax_cpu = self.fig.add_subplot(
            131,
            facecolor=BG_CARD
        )

        self.ax_ram = self.fig.add_subplot(
            132,
            facecolor=BG_CARD
        )

        self.ax_gpu = self.fig.add_subplot(
            133,
            facecolor=BG_CARD
        )

        self.line_cpu, = self.ax_cpu.plot(
            list(self.cpu_history),
            color=COLOR_CPU,
            linewidth=2
        )

        self.line_ram, = self.ax_ram.plot(
            list(self.ram_history),
            color=COLOR_RAM,
            linewidth=2
        )

        self.line_gpu, = self.ax_gpu.plot(
            list(self.gpu_history),
            color=COLOR_GPU,
            linewidth=2
        )

        self.format_axes(
            self.ax_cpu,
            "Historial CPU (%)"
        )

        self.format_axes(
            self.ax_ram,
            "Historial RAM (%)"
        )

        self.format_axes(
            self.ax_gpu,
            "Historial GPU (%)"
        )

        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(
            self.fig,
            master=self.frame_charts
        )

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True,
            padx=8,
            pady=6
        )

        self.canvas.draw()

        self.background = None

        self.canvas.mpl_connect(
            "draw_event",
            self.on_draw
        )

        # =================================================
        # TELEMETRÍA
        # =================================================

        self.telemetry_thread = threading.Thread(
            target=self.telemetry_loop,
            daemon=True,
            name="DiagnosticPC-Telemetry"
        )

        self.telemetry_thread.start()

        # =================================================
        # POLLING DE UI
        # =================================================

        self.telemetry_after_id = self.after(
            100,
            self.process_pending_telemetry
        )

        self.chart_after_id = self.after(
            33,
            self.update_charts_fast
        )

    # =====================================================
    # DUPLICADOS
    # =====================================================

    def open_duplicate_scanner(self):

        if not self.is_running:
            return

        try:

            if (
                self.duplicate_window is None
                or not self.duplicate_window.winfo_exists()
            ):

                self.duplicate_window = (
                    DuplicateScannerWindow(
                        master=self
                    )
                )

                self.duplicate_window.protocol(
                    "WM_DELETE_WINDOW",
                    self.close_duplicate_scanner
                )

            else:

                self.duplicate_window.lift()

                self.duplicate_window.focus_force()

        except Exception:

            self.duplicate_window = None

    def close_duplicate_scanner(self):

        try:

            if (
                self.duplicate_window
                and self.duplicate_window.winfo_exists()
            ):

                self.duplicate_window.destroy()

        except Exception:
            pass

        finally:

            self.duplicate_window = None

    # =====================================================
    # LIMPIEZA
    # =====================================================

    def run_system_cleanup(self):

        if not self.is_running:
            return

        try:

            res = clean_temp_files()

            empty_recycle_bin()

            dns_ok = flush_dns_cache()

            ram_ok = optimize_ram_memory()

            messagebox.showinfo(
                "Limpieza Completada",
                (
                    "¡Mantenimiento finalizado con éxito!\n\n"
                    f"• Espacio liberado: "
                    f"{res.get('freed_mb', 0)} MB\n"
                    f"• Archivos eliminados: "
                    f"{res.get('deleted_files', 0)}\n"
                    "• Papelera de Reciclaje vaciada.\n"
                    f"• Caché DNS: "
                    f"{'Restablecida' if dns_ok else 'Omitida'}\n"
                    f"• Memoria RAM: "
                    f"{'Limpieza ejecutada' if ram_ok else 'Omitida'}"
                ),
                parent=self
            )

            threading.Thread(
                target=self._refresh_disks_after_cleanup,
                daemon=True,
                name="DiagnosticPC-DiskRefresh"
            ).start()

        except Exception as e:

            try:

                messagebox.showerror(
                    "Error",
                    f"No se pudo completar la limpieza:\n{e}",
                    parent=self
                )

            except Exception:
                pass

    def _refresh_disks_after_cleanup(self):

        if not self.is_running:
            return

        try:

            disks = get_all_disks_data()

            self.after(
                0,
                lambda: (
                    self.update_disks_ui(disks)
                    if self.is_running
                    else None
                )
            )

        except Exception:
            pass

    # =====================================================
    # RESIZE
    # =====================================================

    def on_window_resize(self, event):

        if event.widget != self:
            return

        if not self.is_running:
            return

        self.is_resizing = True

        if self.resize_timer:

            try:

                self.after_cancel(
                    self.resize_timer
                )

            except Exception:
                pass

        self.resize_timer = self.after(
            300,
            self.finish_resizing
        )

    def finish_resizing(self):

        if not self.is_running:
            return

        self.is_resizing = False

        self.resize_timer = None

        self.background = None

        try:
            self.canvas.draw()
        except Exception:
            pass

    # =====================================================
    # FULLSCREEN
    # =====================================================

    def toggle_fullscreen(self, event=None):

        if not self.is_running:
            return

        self.is_fullscreen = (
            not self.is_fullscreen
        )

        try:

            self.attributes(
                "-fullscreen",
                self.is_fullscreen
            )

        except Exception:
            pass

    def exit_fullscreen(self, event=None):

        if not self.is_running:
            return

        if self.is_fullscreen:

            self.is_fullscreen = False

            try:

                self.attributes(
                    "-fullscreen",
                    False
                )

            except Exception:
                pass

    # =====================================================
    # PDF
    # =====================================================

    def export_pdf_report(self):

        if not self.is_running:
            return

        if not self.latest_telemetry:

            messagebox.showwarning(
                "DiagnosticPC",
                (
                    "Aún no hay datos de "
                    "telemetría para exportar."
                ),
                parent=self
            )

            return

        default_filename = (
            "Reporte_DiagnosticPC_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            + ".pdf"
        )

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[
                (
                    "Archivos PDF",
                    "*.pdf"
                )
            ],
            initialfile=default_filename,
            title="Guardar Reporte PDF",
            parent=self
        )

        if not file_path:
            return

        self.btn_pdf.configure(
            state="disabled",
            text="⏳ Generando..."
        )

        telemetry_snapshot = (
            self.latest_telemetry.copy()
        )

        disks_snapshot = list(
            self.latest_disks
        )

        score_snapshot = (
            self.latest_score
        )

        def generate_thread():

            try:

                generate_pdf_report(
                    telemetry_snapshot,
                    disks_snapshot,
                    score_snapshot,
                    output_path=file_path
                )

                if self.is_running:

                    self.after(
                        0,
                        lambda: self._show_pdf_success(
                            file_path
                        )
                    )

            except Exception as e:

                if self.is_running:

                    self.after(
                        0,
                        lambda: self._show_pdf_error(
                            str(e)
                        )
                    )

            finally:

                if self.is_running:

                    try:

                        self.after(
                            0,
                            self._restore_pdf_button
                        )

                    except Exception:
                        pass

        threading.Thread(
            target=generate_thread,
            daemon=True,
            name="DiagnosticPC-PDF"
        ).start()

    def _show_pdf_success(self, file_path):

        if not self.is_running:
            return

        try:

            messagebox.showinfo(
                "Reporte Creado",
                (
                    "El informe PDF fue "
                    "generado correctamente:\n\n"
                    f"{file_path}"
                ),
                parent=self
            )

        except Exception:
            pass

    def _show_pdf_error(self, error):

        if not self.is_running:
            return

        try:

            messagebox.showerror(
                "Error",
                (
                    "No se pudo generar "
                    f"el reporte PDF:\n{error}"
                ),
                parent=self
            )

        except Exception:
            pass

    def _restore_pdf_button(self):

        if not self.is_running:
            return

        try:

            self.btn_pdf.configure(
                state="normal",
                text="📄 Exportar PDF"
            )

        except Exception:
            pass

    # =====================================================
    # OVERLAY
    # =====================================================

    def toggle_overlay(self):

        if not self.is_running:
            return

        try:

            # ---------------------------------------------
            # ABRIR
            # ---------------------------------------------

            if (
                self.overlay_window is None
                or not self.overlay_window.winfo_exists()
            ):

                self.overlay_window = GameOverlay(
                    master=self
                )

                self.btn_overlay.configure(
                    text="❌ Cerrar Overlay",
                    fg_color="#ef4444",
                    hover_color="#dc2626"
                )

                return

            # ---------------------------------------------
            # CERRAR
            # ---------------------------------------------

            self.close_overlay()

        except Exception as e:

            self.overlay_window = None

            try:

                self.btn_overlay.configure(
                    text="🎮 Overlay In-Game",
                    fg_color="#10b981",
                    hover_color="#059669"
                )

            except Exception:
                pass

            try:

                messagebox.showerror(
                    "DiagnosticPC - Overlay",
                    (
                        "No se pudo iniciar el overlay.\n\n"
                        f"Error: {e}"
                    ),
                    parent=self
                )

            except Exception:
                pass

    def close_overlay(self):

        try:

            if (
                self.overlay_window
                and self.overlay_window.winfo_exists()
            ):

                self.overlay_window.destroy()

        except Exception:
            pass

        finally:

            self.overlay_window = None

            try:

                self.btn_overlay.configure(
                    text="🎮 Overlay In-Game",
                    fg_color="#10b981",
                    hover_color="#059669"
                )

            except Exception:
                pass

    # =====================================================
    # METRIC CARD
    # =====================================================

    def create_metric_card(
        self,
        parent,
        title,
        color
    ):

        card = ctk.CTkFrame(
            parent,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            corner_radius=10
        )

        lbl_title = ctk.CTkLabel(
            card,
            text=title,
            font=("Segoe UI", 9, "bold"),
            text_color=COLOR_TEXT_DIM
        )

        lbl_title.pack(
            anchor="w",
            padx=10,
            pady=(8, 2)
        )

        return card

    # =====================================================
    # CARD CONTENT
    # =====================================================

    def build_card_content(
        self,
        card,
        color,
        hide_sublabel=False
    ):

        lbl_val = ctk.CTkLabel(
            card,
            text="0%",
            font=("Segoe UI", 16, "bold"),
            text_color="#f8fafc"
        )

        lbl_val.pack(
            anchor="w",
            padx=10,
            pady=(0, 2)
        )

        bar = ctk.CTkProgressBar(
            card,
            height=5,
            progress_color=color,
            fg_color="#0f172a"
        )

        bar.set(0)

        bar.pack(
            fill="x",
            padx=10,
            pady=(0, 6)
        )

        lbl_sub = ctk.CTkLabel(
            card,
            text="--",
            font=("Segoe UI", 10, "bold"),
            text_color=color
        )

        lbl_sub.pack(
            anchor="w",
            padx=10,
            pady=(0, 6)
        )

        children = card.winfo_children()

        title_widget = (
            children[0]
            if children
            else None
        )

        return (
            lbl_val,
            bar,
            lbl_sub,
            title_widget
        )

    # =====================================================
    # CHART AXES
    # =====================================================

    def format_axes(
        self,
        ax,
        title
    ):

        ax.set_title(
            title,
            color="#e2e8f0",
            fontsize=8,
            fontweight="bold",
            pad=6
        )

        ax.set_ylim(
            0,
            100
        )

        ax.set_xlim(
            0,
            self.max_points - 1
        )

        ax.tick_params(
            colors=COLOR_TEXT_DIM,
            labelsize=7
        )

        for spine in ax.spines.values():

            spine.set_color(
                "#1e293b"
            )

        ax.grid(
            True,
            color="#1e293b",
            linestyle="--",
            linewidth=0.5
        )

    # =====================================================
    # DRAW EVENT
    # =====================================================

    def on_draw(self, event):

        if not self.is_running:
            return

        if event.canvas != self.canvas:
            return

        try:

            self.background = (
                self.canvas.copy_from_bbox(
                    self.fig.bbox
                )
            )

        except Exception:

            self.background = None

    # =====================================================
    # FAST CHART UPDATE
    # =====================================================

    def update_charts_fast(self):

        if not self.is_running:
            return

        try:

            if (
                self.background is not None
                and not self.is_resizing
            ):

                with self.telemetry_lock:

                    cpu_data = list(
                        self.cpu_history
                    )

                    ram_data = list(
                        self.ram_history
                    )

                    gpu_data = list(
                        self.gpu_history
                    )

                self.canvas.restore_region(
                    self.background
                )

                self.line_cpu.set_ydata(
                    cpu_data
                )

                self.line_ram.set_ydata(
                    ram_data
                )

                self.line_gpu.set_ydata(
                    gpu_data
                )

                self.ax_cpu.draw_artist(
                    self.line_cpu
                )

                self.ax_ram.draw_artist(
                    self.line_ram
                )

                self.ax_gpu.draw_artist(
                    self.line_gpu
                )

                self.canvas.blit(
                    self.fig.bbox
                )

        except Exception:

            self.background = None

        if self.is_running:

            try:

                self.chart_after_id = self.after(
                    33,
                    self.update_charts_fast
                )

            except Exception:

                self.chart_after_id = None

    # =====================================================
    # DISKS UI
    # =====================================================

    def update_disks_ui(
        self,
        disks_data
    ):

        if not self.is_running:
            return

        try:

            if not self.winfo_exists():
                return

        except Exception:
            return

        active_indexes = {
            d["index"]
            for d in disks_data
        }

        # ---------------------------------------------
        # Eliminar discos que ya no existen
        # ---------------------------------------------

        for idx in list(
            self.disk_widgets.keys()
        ):

            if idx not in active_indexes:

                try:

                    self.disk_widgets[idx][
                        "card"
                    ].destroy()

                except Exception:
                    pass

                del self.disk_widgets[idx]

        # ---------------------------------------------
        # Crear / actualizar
        # ---------------------------------------------

        for d in disks_data:

            try:

                idx = d["index"]

                if idx not in self.disk_widgets:

                    card = ctk.CTkFrame(
                        self.scroll_disks,
                        fg_color=BG_CARD,
                        border_width=1,
                        border_color=BORDER_COLOR,
                        corner_radius=8
                    )

                    card.pack(
                        fill="x",
                        pady=3,
                        padx=2
                    )

                    header = ctk.CTkFrame(
                        card,
                        fg_color="transparent"
                    )

                    header.pack(
                        fill="x",
                        padx=10,
                        pady=(6, 2)
                    )

                    lbl_name = ctk.CTkLabel(
                        header,
                        text="",
                        font=(
                            "Segoe UI",
                            10,
                            "bold"
                        ),
                        text_color="#f8fafc"
                    )

                    lbl_name.pack(
                        side="left"
                    )

                    lbl_badge = ctk.CTkLabel(
                        header,
                        text="",
                        font=(
                            "Segoe UI",
                            10,
                            "bold"
                        )
                    )

                    lbl_badge.pack(
                        side="right"
                    )

                    lbl_exact = ctk.CTkLabel(
                        card,
                        text="",
                        font=("Segoe UI", 9),
                        text_color=COLOR_CPU
                    )

                    lbl_exact.pack(
                        anchor="w",
                        padx=10,
                        pady=(0, 3)
                    )

                    bar = ctk.CTkProgressBar(
                        card,
                        height=5,
                        progress_color=COLOR_CPU,
                        fg_color="#0f172a"
                    )

                    bar.set(0)

                    bar.pack(
                        fill="x",
                        padx=10,
                        pady=(0, 6)
                    )

                    self.disk_widgets[idx] = {
                        "card": card,
                        "lbl_name": lbl_name,
                        "lbl_badge": lbl_badge,
                        "lbl_exact": lbl_exact,
                        "bar": bar
                    }

                w = self.disk_widgets[idx]

                w["lbl_name"].configure(
                    text=(
                        f"💾 Disco {idx}: "
                        f"{d['model']} "
                        f"[{d['mount_points']}] "
                        f"({d['total_gb']} GB)"
                    )
                )

                health = float(
                    d.get(
                        "health",
                        100
                    )
                )

                if health >= 90:

                    h_color = COLOR_RAM

                elif health >= 70:

                    h_color = "#f59e0b"

                else:

                    h_color = "#ef4444"

                w["lbl_badge"].configure(
                    text=f"Salud: {health:.0f}%",
                    text_color=h_color
                )

                w["lbl_exact"].configure(
                    text=(
                        f"Usado: "
                        f"{d['used_percent']}%  -->  "
                        f"{d['used_gb']} GB  |  "
                        f"{d['used_mb']:,} MB  |  "
                        f"{d['used_kb']:,} KB"
                    )
                )

                percent = max(
                    0.0,
                    min(
                        100.0,
                        float(
                            d["used_percent"]
                        )
                    )
                )

                w["bar"].set(
                    percent / 100.0
                )

            except Exception:
                continue

    # =====================================================
    # TELEMETRY THREAD
    # =====================================================

    def telemetry_loop(self):

        if IS_WINDOWS and pythoncom:

            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        try:

            # Primera lectura para inicializar
            # el contador de CPU de psutil.
            try:

                psutil.cpu_percent(
                    interval=None
                )

            except Exception:
                pass

            disk_timer = 0
            disks = []

            while self.is_running:

                cycle_start = time.monotonic()

                try:

                    # -------------------------------------
                    # TELEMETRÍA
                    # -------------------------------------

                    telemetry = (
                        get_system_telemetry()
                    )

                    # -------------------------------------
                    # DISCOS
                    # Cada ~5 segundos
                    # -------------------------------------

                    if (
                        disk_timer % 20 == 0
                        or not disks
                    ):

                        try:

                            disks = (
                                get_all_disks_data()
                            )

                        except Exception:
                            pass

                    disk_timer += 1

                    # -------------------------------------
                    # SCORE
                    # -------------------------------------

                    score = (
                        calculate_preliminary_score(
                            telemetry["cpu_usage"],
                            telemetry["ram_usage"],
                            telemetry["cpu_temp"],
                            telemetry["gpu_temp"],
                            disks
                        )
                    )

                    # -------------------------------------
                    # SNAPSHOT PARA UI
                    # -------------------------------------

                    with self.telemetry_lock:

                        self.pending_telemetry = (
                            telemetry
                        )

                        self.pending_disks = list(
                            disks
                        )

                        self.latest_score = (
                            score
                        )

                        # ---------------------------------
                        # HISTORIAL
                        # ---------------------------------

                        self.cpu_history.append(
                            telemetry["cpu_usage"]
                        )

                        self.ram_history.append(
                            telemetry["ram_usage"]
                        )

                        self.gpu_history.append(
                            telemetry["gpu_usage"]
                        )

                    # -------------------------------------
                    # DATABASE
                    # -------------------------------------

                    self.db_counter += 1

                    if self.db_counter >= 20:

                        try:

                            save_telemetry_record(
                                telemetry["cpu_usage"],
                                telemetry["ram_usage"],
                                0,
                                0,
                                score
                            )

                        except Exception:
                            pass

                        self.db_counter = 0

                except Exception:

                    # La telemetría nunca debe matar
                    # el thread.
                    pass

                # -----------------------------------------
                # Mantener aproximadamente 4 Hz
                # -----------------------------------------

                elapsed = (
                    time.monotonic()
                    - cycle_start
                )

                sleep_time = max(
                    0.05,
                    0.25 - elapsed
                )

                end_time = (
                    time.monotonic()
                    + sleep_time
                )

                while (
                    self.is_running
                    and time.monotonic() < end_time
                ):

                    remaining = (
                        end_time
                        - time.monotonic()
                    )

                    if remaining <= 0:
                        break

                    time.sleep(
                        min(
                            0.05,
                            remaining
                        )
                    )

        finally:

            if IS_WINDOWS and pythoncom:

                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    # =====================================================
    # PROCESS TELEMETRY ON MAIN THREAD
    # =====================================================

    def process_pending_telemetry(self):

        if not self.is_running:
            return

        telemetry = None
        disks = None

        try:

            with self.telemetry_lock:

                if self.pending_telemetry is not None:

                    telemetry = (
                        self.pending_telemetry
                    )

                    disks = list(
                        self.pending_disks
                    )

                    self.pending_telemetry = None

            if telemetry is not None:

                self.apply_telemetry_to_ui(
                    telemetry,
                    disks
                )

        except Exception:
            pass

        if self.is_running:

            try:

                self.telemetry_after_id = self.after(
                    100,
                    self.process_pending_telemetry
                )

            except Exception:

                self.telemetry_after_id = None

    # =====================================================
    # APPLY TELEMETRY TO UI
    # =====================================================

    def apply_telemetry_to_ui(
        self,
        telemetry,
        disks
    ):

        if not self.is_running:
            return

        try:

            if not self.winfo_exists():
                return

        except Exception:
            return

        try:

            self.latest_telemetry = (
                telemetry
            )

            self.latest_disks = (
                list(disks)
            )

            # -----------------------------------------
            # CPU
            # -----------------------------------------

            self.lbl_cpu_title.configure(
                text=(
                    f"CPU: "
                    f"{telemetry['cpu_name']}"
                )
            )

            cpu_usage = max(
                0.0,
                min(
                    100.0,
                    float(
                        telemetry["cpu_usage"]
                    )
                )
            )

            self.lbl_cpu.configure(
                text=(
                    f"{cpu_usage:.1f}%"
                )
            )

            self.bar_cpu.set(
                cpu_usage / 100.0
            )

            self.lbl_cpu_temp.configure(
                text=(
                    f"Temp: "
                    f"{telemetry['cpu_temp']} °C"
                )
            )

            # -----------------------------------------
            # RAM
            # -----------------------------------------

            ram_usage = max(
                0.0,
                min(
                    100.0,
                    float(
                        telemetry["ram_usage"]
                    )
                )
            )

            self.lbl_ram.configure(
                text=(
                    f"{ram_usage:.1f}%"
                )
            )

            self.bar_ram.set(
                ram_usage / 100.0
            )

            self.lbl_ram_gb.configure(
                text=(
                    f"{telemetry['ram_used_gb']} GB "
                    f"/ "
                    f"{telemetry['ram_total_gb']} GB"
                )
            )

            # -----------------------------------------
            # GPU
            # -----------------------------------------

            self.lbl_gpu_title.configure(
                text=(
                    f"GPU: "
                    f"{telemetry['gpu_name']}"
                )
            )

            gpu_usage = max(
                0.0,
                min(
                    100.0,
                    float(
                        telemetry["gpu_usage"]
                    )
                )
            )

            self.lbl_gpu.configure(
                text=(
                    f"{gpu_usage:.1f}%"
                )
            )

            self.bar_gpu.set(
                gpu_usage / 100.0
            )

            self.lbl_gpu_temp.configure(
                text=(
                    f"Temp: "
                    f"{telemetry['gpu_temp']} °C"
                )
            )

            # -----------------------------------------
            # DISKS
            # -----------------------------------------

            self.update_disks_ui(
                disks
            )

            # -----------------------------------------
            # HEALTH
            # -----------------------------------------

            score = (
                calculate_preliminary_score(
                    telemetry["cpu_usage"],
                    telemetry["ram_usage"],
                    telemetry["cpu_temp"],
                    telemetry["gpu_temp"],
                    disks
                )
            )

            self.latest_score = score

            self.lbl_health_val.configure(
                text=f"{score:.1f}%"
            )

            if score < 50:

                self.lbl_health_status.configure(
                    text="ESTADO CRÍTICO",
                    text_color="#ef4444"
                )

                self.lbl_health_val.configure(
                    text_color="#ef4444"
                )

            elif score < 70:

                self.lbl_health_status.configure(
                    text="ADVERTENCIA",
                    text_color="#f59e0b"
                )

                self.lbl_health_val.configure(
                    text_color="#f59e0b"
                )

            elif score < 85:

                self.lbl_health_status.configure(
                    text="ESTADO ESTABLE",
                    text_color="#38bdf8"
                )

                self.lbl_health_val.configure(
                    text_color="#38bdf8"
                )

            else:

                self.lbl_health_status.configure(
                    text="ESTADO ÓPTIMO",
                    text_color=COLOR_RAM
                )

                self.lbl_health_val.configure(
                    text_color=COLOR_RAM
                )

        except Exception:
            pass

    # =====================================================
    # CLOSE
    # =====================================================

    def on_close(self):

        # Evitar doble cierre
        if not self.is_running:
            return

        # ---------------------------------------------
        # DETENER EJECUCIÓN
        # ---------------------------------------------

        self.is_running = False

        # ---------------------------------------------
        # CANCELAR CALLBACK DE RESIZE
        # ---------------------------------------------

        if self.resize_timer:

            try:

                self.after_cancel(
                    self.resize_timer
                )

            except Exception:
                pass

            self.resize_timer = None

        # ---------------------------------------------
        # CANCELAR CALLBACK TELEMETRÍA UI
        # ---------------------------------------------

        if self.telemetry_after_id:

            try:

                self.after_cancel(
                    self.telemetry_after_id
                )

            except Exception:
                pass

            self.telemetry_after_id = None

        # ---------------------------------------------
        # CANCELAR CALLBACK GRÁFICOS
        # ---------------------------------------------

        if self.chart_after_id:

            try:

                self.after_cancel(
                    self.chart_after_id
                )

            except Exception:
                pass

            self.chart_after_id = None

        # ---------------------------------------------
        # CERRAR OVERLAY
        # ---------------------------------------------

        self.close_overlay()

        # ---------------------------------------------
        # CERRAR DUPLICATE SCANNER
        # ---------------------------------------------

        self.close_duplicate_scanner()

        # ---------------------------------------------
        # ESPERAR THREAD DE TELEMETRÍA
        # ---------------------------------------------

        try:

            if (
                hasattr(
                    self,
                    "telemetry_thread"
                )
                and self.telemetry_thread.is_alive()
            ):

                self.telemetry_thread.join(
                    timeout=1.0
                )

        except Exception:
            pass

        # ---------------------------------------------
        # DESTRUIR APP
        # ---------------------------------------------

        try:

            self.destroy()

        except Exception:
            pass


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    app = App()

    app.mainloop()
