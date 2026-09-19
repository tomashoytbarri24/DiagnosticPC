"""Panel de Ajustes Linux de CorePulse."""
from __future__ import annotations

import customtkinter as ctk

from core.linux_tuning import collect_linux_tuning, set_power_profile
from core.theme_manager import role_color

FONT = 'Segoe UI'
BG = role_color('bg')
SURFACE = role_color('surface')
SURFACE2 = role_color('surface_2')
BORDER = role_color('border')
TEXT = role_color('text')
TEXT2 = role_color('text_2')
MUTED = role_color('muted')
ACCENT = role_color('accent')
ACCENT2 = role_color('accent_2')
GREEN = '#16d98b'
AMBER = '#f3b54a'


class LinuxTuningPanel:
    """Equivalente Linux seguro de la sección Tweaks de Windows."""

    PROFILE_LABELS = (
        ('Ahorro', 'power-saver'),
        ('Equilibrado', 'balanced'),
        ('Rendimiento', 'performance'),
    )

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._alive = True
        self._profile_buttons = {}
        self._profile_value = None
        self._last_info = {}
        self._verify_after = None

        self.root = ctk.CTkScrollableFrame(
            parent, fg_color=BG, corner_radius=0,
            scrollbar_fg_color=BG, scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT2,
        )
        self.root.pack(fill='both', expand=True)
        self._build()

    def widget(self):
        return self.root

    def set_active(self, active=True):
        self._alive = bool(active)

    def _card(self, title, subtitle=''):
        # Importante: las tarjetas viven dentro de ``body``. En V173 se
        # añadían accidentalmente a ``root``; cada refresh limpiaba ``body``
        # pero dejaba las tarjetas antiguas, por eso se repetían varias veces.
        card = ctk.CTkFrame(
            self.body, fg_color=SURFACE, border_width=1,
            border_color=BORDER, corner_radius=12,
        )
        card.pack(fill='x', padx=24, pady=6)
        ctk.CTkLabel(
            card, text=title, font=(FONT, 12, 'bold'),
            text_color=TEXT, anchor='w',
        ).pack(fill='x', padx=14, pady=(12, 2))
        if subtitle:
            ctk.CTkLabel(
                card, text=subtitle, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left', wraplength=980,
            ).pack(fill='x', padx=14, pady=(0, 9))
        return card

    def _kv(self, card, label, value, color=None):
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=3)
        ctk.CTkLabel(
            row, text=label, font=(FONT, 9), text_color=TEXT2, anchor='w',
        ).pack(side='left')
        value_label = ctk.CTkLabel(
            row, text=str(value), font=(FONT, 9, 'bold'),
            text_color=color or TEXT, anchor='e',
        )
        value_label.pack(side='right')
        return value_label

    def _build(self):
        header = ctk.CTkFrame(self.root, fg_color='transparent')
        header.pack(fill='x', padx=24, pady=(18, 8))
        ctk.CTkLabel(
            header, text='Ajustes Linux', font=(FONT, 24, 'bold'),
            text_color=TEXT, anchor='w',
        ).pack(side='left')
        ctk.CTkButton(
            header, text='Actualizar', width=100, height=32, corner_radius=8,
            fg_color=ACCENT2, hover_color=ACCENT, text_color=TEXT,
            font=(FONT, 9, 'bold'), command=self.refresh,
        ).pack(side='right')
        ctk.CTkLabel(
            self.root,
            text=(
                'Optimización segura y nativa. CorePulse sólo cambia el perfil '
                'energético mediante power-profiles-daemon; el resto se muestra '
                'como diagnóstico para evitar modificar el kernel o sysctl sin contexto.'
            ),
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left',
            wraplength=1120,
        ).pack(fill='x', padx=24, pady=(0, 8))
        self.body = ctk.CTkFrame(self.root, fg_color='transparent')
        self.body.pack(fill='both', expand=True)
        self.refresh()

    def _paint_profile(self, profile):
        """Actualiza visualmente la selección sin esperar una segunda consulta."""
        profile = str(profile or '').strip()
        if self._profile_value is not None:
            try:
                self._profile_value.configure(text=profile or 'No disponible')
            except Exception:
                pass
        for key, button in self._profile_buttons.items():
            try:
                active = key == profile
                button.configure(
                    fg_color=ACCENT2 if active else SURFACE2,
                    border_color=ACCENT if active else BORDER,
                    border_width=2 if active else 1,
                )
            except Exception:
                pass
        self._last_info['profile'] = profile or self._last_info.get('profile', '')

    def _render_body(self, info):
        for child in self.body.winfo_children():
            child.destroy()
        self._profile_buttons = {}
        self._profile_value = None
        self._last_info = dict(info or {})

        power = self._card(
            'Perfil de energía',
            'Usa la autoridad de power-profiles-daemon del sistema. No se crean perfiles duplicados ni configuraciones propias.',
        )
        self._profile_value = self._kv(
            power, 'Perfil activo', info.get('profile', 'No disponible'), ACCENT,
        )
        if info.get('powerprofilesctl'):
            actions = ctk.CTkFrame(power, fg_color='transparent')
            actions.pack(fill='x', padx=12, pady=(8, 12))
            actions.grid_columnconfigure((0, 1, 2), weight=1)
            available = set(info.get('profiles') or [])
            current = str(info.get('profile') or '')
            for col, (label, key) in enumerate(self.PROFILE_LABELS):
                active = current == key
                btn = ctk.CTkButton(
                    actions, text=label, height=34, corner_radius=8,
                    fg_color=ACCENT2 if active else SURFACE2,
                    hover_color=ACCENT, border_width=2 if active else 1,
                    border_color=ACCENT if active else BORDER,
                    text_color=TEXT, font=(FONT, 9, 'bold'),
                    state='normal' if not available or key in available else 'disabled',
                    command=lambda value=key: self._set_profile(value),
                )
                btn.grid(row=0, column=col, sticky='ew', padx=4)
                self._profile_buttons[key] = btn
        else:
            ctk.CTkLabel(
                power,
                text='powerprofilesctl no está instalado o tu distribución no lo utiliza.',
                font=(FONT, 8), text_color=AMBER, anchor='w',
            ).pack(fill='x', padx=14, pady=(4, 12))

        cpu = self._card(
            'CPU y planificador',
            'Información expuesta por el kernel. CorePulse no fuerza governors globales porque el control depende del driver, firmware y distribución.',
        )
        gov = ', '.join(info.get('governors') or []) or 'No expuesto por sysfs'
        self._kv(cpu, 'Governor actual', gov, GREEN if info.get('governors') else MUTED)

        memory = self._card(
            'Memoria',
            'Indicadores del sistema que ayudan a comprender la política de memoria sin aplicar cambios agresivos.',
        )
        self._kv(memory, 'vm.swappiness', info.get('swappiness', 'No disponible'))
        zram = ', '.join(info.get('zram') or []) or 'No detectado'
        self._kv(memory, 'zram', zram, GREEN if info.get('zram') else MUTED)

        gaming = self._card(
            'Rendimiento en juegos',
            'GameMode es la alternativa Linux más cercana a una optimización temporal de juegos cuando está instalada.',
        )
        self._kv(
            gaming, 'GameMode',
            'Disponible' if info.get('gamemode') else 'No detectado',
            GREEN if info.get('gamemode') else MUTED,
        )
        ctk.CTkLabel(
            gaming,
            text='CorePulse no instala ni activa GameMode automáticamente; sólo detecta si tu sistema ya lo ofrece.',
            font=(FONT, 8), text_color=MUTED, anchor='w', justify='left',
        ).pack(fill='x', padx=14, pady=(4, 12))

    def refresh(self):
        """Reconstruye una sola vez la vista usando el estado real del sistema."""
        if not self._alive:
            return
        info = collect_linux_tuning()
        self._render_body(info)

    def _verify_profile(self, requested):
        self._verify_after = None
        if not self._alive:
            return
        try:
            info = collect_linux_tuning()
            actual = str(info.get('profile') or requested)
            self._last_info.update(info)
            self._paint_profile(actual)
        except Exception:
            self._paint_profile(requested)

    def _set_profile(self, profile):
        current = str(self._last_info.get('profile') or '')
        if profile == current:
            return

        # Feedback optimista: power-profiles-daemon cambia rápido; el usuario no
        # debe esperar a una segunda lectura del daemon para ver el botón activo.
        self._paint_profile(profile)
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        ok, detail = set_power_profile(profile)
        if ok:
            try:
                if self._verify_after:
                    self.app.after_cancel(self._verify_after)
                self._verify_after = self.app.after(180, lambda: self._verify_profile(profile))
            except Exception:
                self._verify_profile(profile)
            return

        # Si el sistema rechaza el cambio se restaura el estado real y se avisa.
        try:
            self.refresh()
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showwarning('CorePulse · Ajustes Linux', str(detail), parent=self.app)
        except Exception:
            pass
