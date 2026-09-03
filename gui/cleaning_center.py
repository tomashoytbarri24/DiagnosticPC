"""Presenta la interfaz profesional del centro de limpieza reutilizando acciones seguras."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import customtkinter as ctk
from gui.cleaning_actions import CleaningCenterPanel, CleaningToolCard, PURPLE, BLUE, CYAN, GREEN, ORANGE

DESIGN_ID = 'COREPULSE_PRO_CLEANING_CENTER'
SURFACE = theme_color('#0d1828')
SURFACE_2 = theme_color('#101d2e')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#aebdd0')
MUTED = theme_color('#72849b')


class ProfessionalCleaningToolCard(CleaningToolCard):
    """Tarjeta profesional de limpieza con layout más estable y legible."""

    def __init__(
        self,
        parent,
        title,
        icon,
        accent,
        description,
        action_label,
        action_command,
        analyze_command=None,
        footer='',
        action_color=None,
        secondary_action_label=None,
        secondary_action_command=None,
    ):
        ctk.CTkFrame.__init__(self, parent, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=13)
        self.accent = accent
        self.grid_columnconfigure(0, weight=1)
        # La zona de resultado absorbe el espacio vertical sobrante. Así los
        # botones y el pie de cada tarjeta permanecen visibles y alineados.
        self.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self, fg_color='transparent')
        head.grid(row=0, column=0, sticky='ew', padx=15, pady=(9, 3))
        head.grid_columnconfigure(1, weight=1)

        marker = ctk.CTkFrame(head, width=6, height=32, corner_radius=4, fg_color=accent)
        marker.grid(row=0, column=0, rowspan=2, sticky='nsw', padx=(0, 10))
        marker.grid_propagate(False)

        ctk.CTkLabel(head, text=title.upper(), font=('Segoe UI', 11, 'bold'), text_color=TEXT, anchor='w', height=19).grid(row=0, column=1, sticky='ew')
        category = {
            'Limpiar Caché': 'TEMPORALES',
            'Liberar RAM': 'MEMORIA',
            'Archivos Duplicados': 'ARCHIVOS',
            'Liberar Almacenamiento': 'ALMACENAMIENTO',
        }.get(title, 'MANTENIMIENTO')
        ctk.CTkLabel(head, text=category, font=('Segoe UI', 8, 'bold'), text_color=accent, anchor='w', height=14).grid(row=1, column=1, sticky='ew', pady=(1, 0))

        self.lbl_description = ctk.CTkLabel(
            self,
            text=description,
            font=('Segoe UI', 9),
            text_color=TEXT_2,
            justify='left',
            anchor='w',
            wraplength=430,
            height=32,
        )
        self.lbl_description.grid(row=1, column=0, sticky='ew', padx=15, pady=(0, 6))

        result = ctk.CTkFrame(self, fg_color=SURFACE_2, border_width=1, border_color=theme_color('#182a40'), corner_radius=10, height=78)
        result.grid(row=2, column=0, sticky='nsew', padx=15, pady=(0, 6))
        result.grid_propagate(False)
        result.grid_columnconfigure(0, weight=1)

        self.lbl_result_title = ctk.CTkLabel(result, text='ESTADO', font=('Segoe UI', 8, 'bold'), text_color=MUTED, anchor='w', height=15)
        self.lbl_result_title.grid(row=0, column=0, sticky='ew', padx=12, pady=(6, 0))

        self.lbl_value = ctk.CTkLabel(result, text='Sin analizar', font=('Segoe UI', 15, 'bold'), text_color=accent, anchor='w', height=23)
        self.lbl_value.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 0))

        self.lbl_detail = ctk.CTkLabel(
            result,
            text='Pulsa Analizar para obtener datos reales.',
            font=('Segoe UI', 8),
            text_color=MUTED,
            justify='left',
            anchor='w',
            wraplength=430,
            height=28,
        )
        self.lbl_detail.grid(row=2, column=0, sticky='ew', padx=12, pady=(0, 5))

        actions = ctk.CTkFrame(self, fg_color='transparent')
        actions.grid(row=3, column=0, sticky='ew', padx=15, pady=(0, 5))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        actions.grid_columnconfigure(2, weight=1)

        self.btn_analyze = None
        if analyze_command:
            self.btn_analyze = ctk.CTkButton(
                actions,
                text='Analizar',
                height=31,
                corner_radius=8,
                fg_color=theme_color('#17263a'),
                hover_color=theme_color(theme_color('#203650')),
                border_width=1,
                border_color=theme_color('#29435f'),
                text_color=TEXT,
                font=('Segoe UI', 9, 'bold'),
                command=analyze_command,
            )
            self.btn_analyze.grid(row=0, column=0, sticky='ew', padx=(0, 4))

        self.btn_action = ctk.CTkButton(
            actions,
            text=action_label,
            height=31,
            corner_radius=8,
            fg_color=action_color or accent,
            hover_color=action_color or accent,
            text_color='#ffffff',
            font=('Segoe UI', 9, 'bold'),
            command=action_command,
        )
        self.btn_action.grid(
            row=0,
            column=1 if analyze_command else 0,
            columnspan=1 if secondary_action_command else 2 if analyze_command else 3,
            sticky='ew',
            padx=4 if analyze_command else 0,
        )

        self.btn_secondary_action = None
        if secondary_action_command:
            self.btn_secondary_action = ctk.CTkButton(
                actions,
                text=secondary_action_label or 'Profunda',
                height=31,
                corner_radius=8,
                fg_color='#7c3aed',
                hover_color='#6d28d9',
                text_color='#ffffff',
                font=('Segoe UI', 9, 'bold'),
                command=secondary_action_command,
            )
            self.btn_secondary_action.grid(row=0, column=2, sticky='ew', padx=(4, 0))

        self.lbl_footer = ctk.CTkLabel(
            self,
            text=footer,
            font=('Segoe UI', 8),
            text_color=MUTED,
            wraplength=430,
            justify='left',
            anchor='w',
            height=17,
        )
        self.lbl_footer.grid(row=4, column=0, sticky='ew', padx=15, pady=(0, 8))

    def tune_for_width(self, width: int, narrow: bool):
        # 'width' es el ancho total de la página; cada tarjeta ocupa aprox. la mitad.
        # Los límites evitan saltos de línea innecesarios sin depender de un canvas.
        half = max(320, int(width * 0.46))
        desc_wrap = 300 if narrow else min(520, half)
        detail_wrap = 285 if narrow else min(500, half)
        footer_wrap = desc_wrap
        value_size = 14 if narrow else 15
        try:
            self.lbl_description.configure(wraplength=desc_wrap)
            self.lbl_detail.configure(wraplength=detail_wrap)
            self.lbl_footer.configure(wraplength=footer_wrap)
            self.lbl_value.configure(font=('Segoe UI', value_size, 'bold'))
        except Exception:
            pass


class ProfessionalCleaningCenterPanel(CleaningCenterPanel):
    """Centro de limpieza interno estable, sin canvas transitorio ni clipping."""

    def __init__(self, app):
        super().__init__(app)
        self._corepulse_cleaning_design_id = DESIGN_ID

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=12)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(header, fg_color='transparent')
        left.grid(row=0, column=0, sticky='w', padx=18, pady=9)
        ctk.CTkLabel(left, text='Limpieza de sistema', font=('Segoe UI', 19, 'bold'), height=24, text_color=TEXT).pack(anchor='w')
        ctk.CTkLabel(left, text='Herramientas independientes: analiza primero y ejecuta solo lo que necesites.', font=('Segoe UI', 9), text_color=TEXT_2, height=16).pack(anchor='w', pady=(3, 0))

        right = ctk.CTkFrame(header, fg_color='transparent')
        right.grid(row=0, column=1, sticky='e', padx=14, pady=8)
        ctk.CTkLabel(right, text='REAL / N/A', font=('Segoe UI', 8, 'bold'), text_color=GREEN, fg_color=theme_color('#10283a'), corner_radius=7, padx=9, pady=4).pack(side='left', padx=(0, 8))
        ctk.CTkButton(right, text='Volver al Dashboard', width=145, height=32, corner_radius=8, fg_color=theme_color('#17263a'), hover_color=theme_color(theme_color('#203650')), border_width=1, border_color=theme_color('#29435f'), text_color=TEXT, font=('Segoe UI', 9, 'bold'), command=self.close).pack(side='left')

    def _build_cards(self):
        # Se evita CTkScrollableFrame aquí. Durante una navegación rápida su
        # canvas interno podía quedar destruido mientras CustomTkinter terminaba
        # de configurarlo. El grid 2x2 cabe en los presets soportados por CorePulse
        # y mantiene alturas naturales, por lo que no recorta los estados.
        self.body = ctk.CTkFrame(self, fg_color='transparent', corner_radius=0)
        self.body.grid(row=1, column=0, sticky='nsew')
        self.body.grid_columnconfigure(0, weight=1, uniform='clean_pro')
        self.body.grid_columnconfigure(1, weight=1, uniform='clean_pro')
        self.body.grid_rowconfigure(0, weight=1, uniform='clean_rows')
        self.body.grid_rowconfigure(1, weight=1, uniform='clean_rows')
        self.body.grid_rowconfigure(2, weight=0)

        self.cache_card = ProfessionalCleaningToolCard(self.body, 'Limpiar Caché', '', PURPLE, 'Analiza únicamente temporales permitidos. Los archivos bloqueados o protegidos se omiten.', 'Limpiar caché', self.clean_cache, analyze_command=self.analyze_cache, footer='Requiere confirmación antes de eliminar.')
        self.ram_card = ProfessionalCleaningToolCard(self.body, 'Liberar RAM', '', BLUE, 'Mide RAM real antes/después. Modo normal es conservador; Profunda usa APIs de Windows con permisos de administrador.', 'Normal', self.optimize_ram, analyze_command=self.refresh_ram_card, footer='Profunda puede causar recargas temporales; nunca promete un 99% artificial.', secondary_action_label='Profunda', secondary_action_command=self.optimize_ram_deep)
        self.dup_card = ProfessionalCleaningToolCard(self.body, 'Archivos Duplicados', '', ORANGE, 'Selecciona una carpeta y verifica duplicados reales mediante tamaño + SHA-256.', 'Revisar resultados', self.review_duplicates, analyze_command=self.analyze_duplicates, footer='Solo informa. No elimina archivos personales automáticamente.', action_color='#b87916')
        self.storage_card = ProfessionalCleaningToolCard(self.body, 'Liberar Almacenamiento', '', GREEN, 'Consulta el uso real del volumen del sistema y presenta capacidad disponible.', 'Analizar almacenamiento', self.analyze_storage, footer='Análisis independiente de caché, RAM y duplicados.')
        self.tool_cards = [self.cache_card, self.ram_card, self.dup_card, self.storage_card]

        positions = (
            (self.cache_card, 0, 0),
            (self.ram_card, 0, 1),
            (self.dup_card, 1, 0),
            (self.storage_card, 1, 1),
        )
        for card, row, col in positions:
            card.tune_for_width(1100, False)
            card.grid(
                row=row,
                column=col,
                sticky='nsew',
                padx=(0 if col == 0 else 6, 6 if col == 0 else 0),
                pady=(0 if row == 0 else 5, 5 if row == 0 else 0),
            )

        self.safety = ctk.CTkFrame(self.body, fg_color=theme_color('#0d2130'), border_width=1, border_color='#17435a', corner_radius=10, height=34)
        self.safety.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(5, 0))
        self.safety.grid_propagate(False)
        self.safety.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.safety, text='CONTROL DE SEGURIDAD', font=('Segoe UI', 8, 'bold'), text_color=CYAN, height=16).grid(row=0, column=0, sticky='w', padx=(12, 10), pady=5)
        self.safety_description = ctk.CTkLabel(self.safety, text='CorePulse mide primero. Sin evidencia válida muestra N/A y no inventa resultados.', font=('Segoe UI', 8), text_color=TEXT_2, anchor='w', height=16)
        self.safety_description.grid(row=0, column=1, sticky='ew', pady=5)
        self.badges = ctk.CTkFrame(self.safety, fg_color='transparent')
        self.badges.grid(row=0, column=2, sticky='e', padx=10)
        for label in ('Confirmación', 'Medición real', 'Acciones separadas'):
            ctk.CTkLabel(self.badges, text=label, font=('Segoe UI', 7, 'bold'), text_color=theme_color('#bcd0e2'), fg_color=theme_color(theme_color('#163047')), corner_radius=6, padx=6, pady=2).pack(side='left', padx=2)

        # Solo ajustamos wraps una vez cuando Tk ya conoce el ancho. No se
        # reconstruyen tarjetas durante <Configure>, evitando reflows y carreras.
        self.after(80, self._tune_cards_once)

    def _tune_cards_once(self):
        if self._closed:
            return
        try:
            width = max(900, int(self.winfo_width()))
        except Exception:
            width = 1100
        for card in getattr(self, 'tool_cards', []):
            try:
                card.tune_for_width(width, False)
            except Exception:
                pass
        try:
            if width < 980:
                self.badges.grid_remove()
            else:
                self.badges.grid()
        except Exception:
            pass

    def close(self):
        """Vuelve al Dashboard completo; no deja el host interno vacío."""
        self._closed = True
        try:
            self.app.cleaning_center_panel = None
        except Exception:
            pass
        try:
            from gui.internal_navigation import show_dashboard
            show_dashboard(self.app)
        except Exception:
            try:
                self.destroy()
            except Exception:
                pass

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=2, column=0, sticky='ew', pady=(3, 0))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, text='CorePulse Cleaning Engine · Acciones independientes · Datos reales / N/A', font=('Segoe UI', 8), text_color=MUTED, height=16).grid(row=0, column=0, sticky='w', padx=3)
        self.lbl_last_action = ctk.CTkLabel(footer, text='Sin acciones ejecutadas', font=('Segoe UI', 8), text_color=MUTED, height=16)
        self.lbl_last_action.grid(row=0, column=1, sticky='e', padx=3)


def show_cleaning_center(app):
    from gui.internal_navigation import activate_internal_page, commit_internal_page, abort_internal_page
    host, reused = activate_internal_page(app, 'cleanup')
    existing = getattr(app, 'cleaning_center_panel', None)
    try:
        if reused and existing is not None and existing.winfo_exists():
            existing.lift()
            return existing
    except Exception:
        pass

    panel = None
    try:
        panel = ProfessionalCleaningCenterPanel(app)
        if not commit_internal_page(app, 'cleanup', host, panel):
            raise RuntimeError('La navegación de limpieza fue invalidada antes del commit.')
        return panel
    except Exception:
        abort_internal_page(app, 'cleanup', host, panel)
        raise

