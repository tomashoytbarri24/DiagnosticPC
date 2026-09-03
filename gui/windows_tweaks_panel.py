"""Vista interna de Tweaks de Windows 11 de CorePulse."""
from __future__ import annotations
from core.theme_manager import color as theme_color

import threading
import copy
import customtkinter as ctk
from tkinter import messagebox

from core.windows_tweaks import (
    CATEGORY_ORDER, PRESETS, apply_many, catalog, create_restore_point, detect_all,
    environment_info, has_saved_original, preset_ids, restart_explorer,
    selected_metadata, undo_many,
)
from core.before_after import capture_metrics, save_snapshot
from core.battery_health import collect_battery_health
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost

BG = theme_color('#06111f'); CARD = theme_color('#0d1828'); CARD_2 = theme_color('#0a1524'); BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb'); TEXT_2 = theme_color('#b8c4d4'); MUTED = theme_color('#7f91a8'); CYAN = '#14b8ff'
GREEN = '#1fd18b'; AMBER = '#f59e0b'; RED = '#ff5d6c'; CRITICAL = '#ff334d'; FONT = 'Segoe UI'
RISK_COLORS = {'Bajo': GREEN, 'Medio': AMBER, 'Alto': RED, 'Crítico': CRITICAL}


class WindowsTweaksPanel:
    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._busy = False
        self.items = catalog()
        self.vars = {}
        self.status_labels = {}
        self.undo_labels = {}
        self.restore_point_var = ctk.BooleanVar(value=False)
        self._build()
        self.refresh_status()

    def widget(self):
        return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(15, 7))
        ctk.CTkButton(
            header, text='Volver al resumen', width=145, height=31, fg_color='transparent',
            hover_color=theme_color(theme_color('#102840')), border_width=1, border_color=theme_color(theme_color('#214765')), text_color=TEXT_2,
            font=(FONT, 9, 'bold'), corner_radius=8, command=lambda: show_dashboard(self.app),
        ).pack(side='left')
        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        ctk.CTkLabel(titles, text='Tweaks de Windows 11', font=(FONT, 19, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(
            titles, text=f'{len(self.items)} ajustes · reversibles, clasificados por riesgo y sin scripts remotos',
            font=(FONT, 10), text_color=TEXT_2, anchor='w',
        ).pack(anchor='w', pady=(1, 0))
        self.lbl_environment = ctk.CTkLabel(header, text='Comprobando Windows…', font=(FONT, 9, 'bold'), text_color=MUTED)
        self.lbl_environment.pack(side='right')

        info = ctk.CTkFrame(self.frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=11)
        info.pack(fill='x', padx=18, pady=(0, 8))
        self.lbl_info = ctk.CTkLabel(
            info,
            text='Registro: CorePulse restaura el valor exacto anterior. Acciones de sistema: la reversión definida se indica por separado. Alto/Crítico nunca entra en presets.',
            font=(FONT, 9), text_color=TEXT_2, anchor='w', justify='left',
        )
        self.lbl_info.pack(side='left', fill='x', expand=True, padx=12, pady=9)
        self.lbl_selected = ctk.CTkLabel(info, text='0 seleccionados', font=(FONT, 9, 'bold'), text_color=CYAN)
        self.lbl_selected.pack(side='right', padx=12)

        presets = ctk.CTkFrame(self.frame, fg_color='transparent')
        presets.pack(fill='x', padx=18, pady=(0, 8))
        ctk.CTkLabel(presets, text='PRESETS', font=(FONT, 9, 'bold'), text_color=MUTED).pack(side='left', padx=(0, 8))
        for key in ('recommended', 'minimal', 'privacy', 'gaming', 'performance', 'advanced'):
            width = 102 if key in ('recommended', 'performance', 'advanced') else 88
            ctk.CTkButton(
                presets, text=PRESETS[key], width=width, height=28, corner_radius=7,
                fg_color=theme_color('#0d2942'), hover_color=theme_color('#164f7d'), border_width=1, border_color=theme_color('#1d5278'),
                text_color=theme_color('#75d2f7'), font=(FONT, 8, 'bold'), command=lambda k=key: self._select_preset(k),
            ).pack(side='left', padx=3)
        ctk.CTkButton(
            presets, text='Limpiar', width=72, height=28, corner_radius=7, fg_color='transparent',
            hover_color=theme_color(theme_color('#102840')), border_width=1, border_color=BORDER, text_color=TEXT_2,
            font=(FONT, 8, 'bold'), command=self._clear_selection,
        ).pack(side='left', padx=3)
        ctk.CTkButton(
            presets, text='Detectar aplicados', width=118, height=28, corner_radius=7, fg_color='transparent',
            hover_color=theme_color(theme_color('#102840')), border_width=1, border_color=BORDER, text_color=TEXT_2,
            font=(FONT, 8, 'bold'), command=self.refresh_status,
        ).pack(side='right')

        self.body_scroll = StableScrollHost(self.frame, fg_color=BG)
        self.body_scroll.pack(fill='both', expand=True, padx=13, pady=(0, 6))
        self.body = self.body_scroll.content
        grouped = {}
        for item in self.items:
            grouped.setdefault(item['category'], []).append(item)
        for category in CATEGORY_ORDER:
            rows = grouped.get(category, [])
            if rows:
                self._build_category(category, rows)

        action = ctk.CTkFrame(self.frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10)
        action.pack(fill='x', padx=18, pady=(0, 13))
        left = ctk.CTkFrame(action, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True, padx=10, pady=8)
        self.chk_restore = ctk.CTkCheckBox(
            left, text='Crear punto de restauración antes de aplicar (requiere administrador)',
            variable=self.restore_point_var, font=(FONT, 8), text_color=MUTED, fg_color=CYAN,
            hover_color=theme_color('#0d8fc7'), border_color=theme_color('#31516d'),
        )
        self.chk_restore.pack(anchor='w')
        self.lbl_result = ctk.CTkLabel(left, text='Listo para seleccionar ajustes.', font=(FONT, 8), text_color=MUTED, anchor='w')
        self.lbl_result.pack(anchor='w', pady=(3, 0))
        buttons = ctk.CTkFrame(action, fg_color='transparent')
        buttons.pack(side='right', padx=10, pady=8)
        self.btn_restart = ctk.CTkButton(
            buttons, text='Reiniciar Explorador', width=124, height=31, fg_color='transparent', hover_color=theme_color(theme_color('#102840')),
            border_width=1, border_color=BORDER, text_color=TEXT_2, font=(FONT, 8, 'bold'), command=self._restart_explorer,
        )
        self.btn_restart.pack(side='left', padx=4)
        self.btn_undo = ctk.CTkButton(
            buttons, text='Deshacer seleccionados', width=145, height=31, fg_color=theme_color('#2b1d26'), hover_color=theme_color(theme_color('#412530')),
            border_width=1, border_color=theme_color(theme_color('#693343')), text_color='#ff9bab', font=(FONT, 8, 'bold'), command=lambda: self._run_batch('undo'),
        )
        self.btn_undo.pack(side='left', padx=4)
        self.btn_apply = ctk.CTkButton(
            buttons, text='Aplicar seleccionados', width=140, height=31, fg_color=theme_color('#0d5c45'), hover_color=theme_color('#11765a'),
            border_width=1, border_color=theme_color(theme_color('#178967')), text_color='#b8ffdf', font=(FONT, 8, 'bold'), command=lambda: self._run_batch('apply'),
        )
        self.btn_apply.pack(side='left', padx=4)
        self._update_selected_count()

    def _build_category(self, title, rows):
        is_security = title == 'Seguridad avanzada'
        card_border = theme_color('#5a2630') if is_security else BORDER
        card = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=card_border, corner_radius=11)
        card.pack(fill='x', padx=5, pady=(0, 8))
        heading = f'{title.upper()} · NO INCLUIDO EN PRESETS' if is_security else title.upper()
        ctk.CTkLabel(card, text=heading, font=(FONT, 10, 'bold'), text_color=RED if is_security else TEXT_2).pack(anchor='w', padx=13, pady=(10, 5))
        if is_security:
            ctk.CTkLabel(
                card,
                text='Estos cambios reducen protecciones de Windows. Úsalos sólo si entiendes el impacto y tienes una alternativa de seguridad/recuperación.',
                font=(FONT, 8), text_color='#d9959f', anchor='w', justify='left', wraplength=1120,
            ).pack(anchor='w', padx=13, pady=(0, 6))
        for item in rows:
            self._build_row(card, item)

    def _build_row(self, card, item):
        risk = item.get('risk', 'Bajo')
        row_border = theme_color('#4d2530') if risk == 'Crítico' else theme_color('#152a41')
        row = ctk.CTkFrame(card, fg_color=CARD_2, border_width=1, border_color=row_border, corner_radius=8)
        row.pack(fill='x', padx=9, pady=4)
        var = ctk.BooleanVar(value=False)
        self.vars[item['id']] = var
        check = ctk.CTkCheckBox(
            row, text='', width=24, variable=var, fg_color=CYAN, hover_color=theme_color('#0d8fc7'),
            border_color=theme_color('#31516d'), command=self._update_selected_count,
        )
        check.pack(side='left', padx=(10, 4), pady=10)
        text = ctk.CTkFrame(row, fg_color='transparent')
        text.pack(side='left', fill='x', expand=True, pady=7)
        ctk.CTkLabel(text, text=item['title'], font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(
            text, text=item['description'], font=(FONT, 8), text_color=MUTED,
            anchor='w', justify='left', wraplength=760,
        ).pack(anchor='w', pady=(1, 0))
        if item.get('note'):
            ctk.CTkLabel(
                text, text=item['note'], font=(FONT, 7), text_color=theme_color('#9da9b9'),
                anchor='w', justify='left', wraplength=760,
            ).pack(anchor='w', pady=(2, 0))

        meta = ctk.CTkFrame(row, fg_color='transparent')
        meta.pack(side='right', padx=10, pady=7)
        flags = []
        if item.get('requires_admin'):
            flags.append('ADMIN')
        if item.get('requires_restart'):
            flags.append('REINICIO')
        elif item.get('requires_explorer'):
            flags.append('EXPLORER')
        tag = f"RIESGO {risk.upper()}"
        if flags:
            tag += ' · ' + ' · '.join(flags)
        ctk.CTkLabel(meta, text=tag, font=(FONT, 7, 'bold'), text_color=RISK_COLORS.get(risk, AMBER)).pack(anchor='e')
        status = ctk.CTkLabel(meta, text='Comprobando…', font=(FONT, 8, 'bold'), text_color=MUTED)
        status.pack(anchor='e', pady=(2, 0))
        self.status_labels[item['id']] = status
        undo = ctk.CTkLabel(meta, text='', font=(FONT, 7), text_color=MUTED)
        undo.pack(anchor='e')
        self.undo_labels[item['id']] = undo
        self._bind_row_hover(row)

    def _bind_row_hover(self, row):
        """Hace que una opción completa reaccione al puntero, no sólo el checkbox."""
        normal = CARD_2
        hover = theme_color('#0e1d2f')
        pending = {'after': None}

        def inside():
            try:
                x, y = row.winfo_pointerxy()
                node = row.winfo_containing(x, y)
                while node is not None:
                    if node is row:
                        return True
                    node = getattr(node, 'master', None)
            except Exception:
                pass
            return False

        def enter(_event=None):
            aid = pending.get('after')
            if aid:
                try:
                    row.after_cancel(aid)
                except Exception:
                    pass
                pending['after'] = None
            try:
                row.configure(fg_color=hover)
            except Exception:
                pass

        def finish_leave():
            pending['after'] = None
            if not inside():
                try:
                    row.configure(fg_color=normal)
                except Exception:
                    pass

        def leave(_event=None):
            try:
                pending['after'] = row.after(12, finish_leave)
            except Exception:
                finish_leave()

        def bind_tree(node):
            try:
                node.bind('<Enter>', enter, add='+')
                node.bind('<Leave>', leave, add='+')
            except Exception:
                pass
            try:
                for child in node.winfo_children():
                    bind_tree(child)
            except Exception:
                pass
        bind_tree(row)

    def _selected_ids(self):
        return [item['id'] for item in self.items if self.vars.get(item['id']) is not None and self.vars[item['id']].get()]

    def _update_selected_count(self):
        if not hasattr(self, 'lbl_selected'):
            return
        ids = self._selected_ids()
        meta = selected_metadata(ids)
        suffix = ''
        if meta['critical']:
            suffix = f" · {len(meta['critical'])} críticos"
        elif meta['high_risk']:
            suffix = f" · {len(meta['high_risk'])} alto riesgo"
        self.lbl_selected.configure(text=f'{len(ids)} seleccionados{suffix}', text_color=RED if meta['high_risk'] else CYAN)

    def _select_preset(self, key):
        selected = set(preset_ids(key))
        for tweak_id, var in self.vars.items():
            var.set(tweak_id in selected)
        self._update_selected_count()

    def _clear_selection(self):
        for var in self.vars.values():
            var.set(False)
        self._update_selected_count()

    def refresh_status(self):
        if self._busy:
            return
        env = environment_info()
        if env['supported']:
            self.lbl_environment.configure(
                text=f"Windows 11 build {env.get('build') or 'N/A'} · Admin: {'Sí' if env['admin'] else 'No'}",
                text_color=GREEN if env['admin'] else AMBER,
            )
            self.btn_apply.configure(state='normal')
            self.btn_undo.configure(state='normal')
        else:
            self.lbl_environment.configure(text='Disponible sólo en Windows 11', text_color=AMBER)
            self.btn_apply.configure(state='disabled')
            self.btn_undo.configure(state='disabled')

        def worker():
            statuses = detect_all() if env['supported'] else {}

            def finish():
                if not self._alive:
                    return
                mapping = {
                    'applied': ('APLICADO', GREEN),
                    'partial': ('PARCIAL', AMBER),
                    'not_applied': ('NO APLICADO', MUTED),
                    'unavailable': ('NO DISPONIBLE', MUTED),
                    'action': ('ACCIÓN DISPONIBLE', MUTED),
                }
                for item in self.items:
                    status = statuses.get(item['id'], {}).get('status', 'unavailable')
                    text, color = mapping.get(status, ('DESCONOCIDO', MUTED))
                    self.status_labels[item['id']].configure(text=text, text_color=color)
                    if has_saved_original(item['id']):
                        undo_text = 'Deshacer exacto disponible' if item.get('undo_mode') == 'exact' else 'Reversión disponible'
                    else:
                        undo_text = ''
                    self.undo_labels[item['id']].configure(text=undo_text)

            def schedule_finish():
                if not self._alive:
                    return
                host = getattr(self, 'body_scroll', None)
                if host is not None:
                    host.defer_until_idle(finish)
                else:
                    finish()
            try:
                self.frame.after(0, schedule_finish)
            except Exception:
                pass

        threading.Thread(target=worker, name='CorePulseTweaksDetect', daemon=True).start()

    def _set_busy(self, busy, text=None):
        self._busy = bool(busy)
        state = 'disabled' if busy else 'normal'
        for btn in (self.btn_apply, self.btn_undo, self.btn_restart):
            try:
                btn.configure(state=state)
            except Exception:
                pass
        if text:
            self.lbl_result.configure(text=text, text_color=CYAN if busy else MUTED)

    def _confirm_high_risk(self, ids, meta):
        high = meta['high_risk']
        if not high:
            return True
        names = '\n'.join(f"• {row['title']} ({row['risk']})" for row in high[:8])
        if len(high) > 8:
            names += f"\n• … y {len(high) - 8} más"
        text = (
            'Has seleccionado cambios de ALTO IMPACTO.\n\n'
            f'{names}\n\n'
            'Pueden reducir seguridad, quitar componentes o alterar Windows Update. '
            'No forman parte de ningún preset automático.\n\n¿Quieres continuar?'
        )
        if not messagebox.askyesno('CorePulse · Confirmación de alto impacto', text, parent=self.app):
            return False
        if meta['critical']:
            text2 = (
                'CONFIRMACIÓN CRÍTICA\n\n'
                'La selección incluye cambios de seguridad como Defender, SmartScreen o UAC. '
                'El sistema puede quedar con menos protección.\n\n'
                'CorePulse recomienda crear un punto de restauración y disponer de otra protección.\n\n'
                '¿Confirmas nuevamente que deseas aplicar estos cambios?'
            )
            if not messagebox.askyesno('CorePulse · Riesgo crítico', text2, parent=self.app):
                return False
        return True

    def _run_batch(self, action):
        ids = self._selected_ids()
        if not ids:
            self.lbl_result.configure(text='Selecciona al menos un tweak.', text_color=AMBER)
            return
        env = environment_info()
        if not env['supported']:
            self.lbl_result.configure(text='Esta función requiere Windows 11.', text_color=RED)
            return
        meta = selected_metadata(ids)
        if meta['requires_admin'] and not env['admin']:
            self.lbl_result.configure(text='La selección incluye ajustes que requieren ejecutar CorePulse como administrador.', text_color=RED)
            messagebox.showwarning(
                'CorePulse · Administrador requerido',
                'Uno o más tweaks seleccionados modifican políticas, seguridad o componentes del sistema.\n\nCierra CorePulse y ejecútalo como administrador para aplicarlos.',
                parent=self.app,
            )
            return
        if action == 'apply' and not self._confirm_high_risk(ids, meta):
            return

        verb = 'aplicar' if action == 'apply' else 'deshacer'
        extra = ''
        if meta['requires_restart']:
            extra += '\n\nAlgunos cambios requerirán reiniciar Windows.'
        if not messagebox.askyesno(
            'CorePulse · Tweaks de Windows 11',
            f'¿Quieres {verb} {len(ids)} tweak(s) seleccionados?\n\n'
            'CorePulse registra el valor previo de los cambios de Registro. Las acciones externas indican su método de reversión.' + extra,
            parent=self.app,
        ):
            return

        self._set_busy(True, 'Aplicando cambios…' if action == 'apply' else 'Restaurando cambios…')
        use_restore = action == 'apply' and (bool(self.restore_point_var.get()) or bool(meta.get('high_risk')))
        tele_before = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {}) if action == 'apply' else {}
        disks_before = copy.deepcopy(getattr(self.app, 'latest_disks', []) or []) if action == 'apply' else []

        def worker():
            if action == 'apply':
                try:
                    batt_before = collect_battery_health(tele_before)
                    save_snapshot(capture_metrics(tele_before, disks_before, batt_before, label='before_tweaks'), slot='before')
                except Exception:
                    pass
            restore_result = None
            if use_restore:
                restore_result = create_restore_point()
            results = apply_many(ids) if action == 'apply' else undo_many(ids)
            ok = sum(1 for row in results if row.get('success'))
            failed = len(results) - ok
            explorer = any(row.get('success') and row.get('requires_explorer') for row in results)
            restart = any(row.get('success') and row.get('requires_restart') for row in results)

            def finish():
                if not self._alive:
                    return
                self._set_busy(False)
                parts = [f'{ok} correctos', f'{failed} con error']
                if restore_result is not None:
                    parts.append('punto de restauración creado' if restore_result.get('success') else 'punto de restauración no creado')
                if explorer:
                    parts.append('reinicio de Explorador recomendado')
                if restart:
                    parts.append('reinicio de Windows requerido/recomendado')
                self.lbl_result.configure(text=' · '.join(parts), text_color=GREEN if failed == 0 else AMBER)
                if action == 'apply' and failed == 0 and not explorer and not restart:
                    try:
                        tele_after = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
                        disks_after = copy.deepcopy(getattr(self.app, 'latest_disks', []) or [])
                        def capture_after_worker():
                            try:
                                batt_after = collect_battery_health(tele_after)
                                save_snapshot(capture_metrics(tele_after, disks_after, batt_after, label='after_tweaks_immediate'), slot='after')
                            except Exception:
                                pass
                        threading.Thread(target=capture_after_worker, name='CorePulseTweaksAfterSnapshot', daemon=True).start()
                    except Exception:
                        pass
                self.refresh_status()

            try:
                self.frame.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=worker, name='CorePulseTweaksWorker', daemon=True).start()

    def _restart_explorer(self):
        if not messagebox.askyesno(
            'CorePulse · Reiniciar Explorador',
            'Se cerrará y volverá a abrir explorer.exe. Las ventanas del Explorador pueden cerrarse.\n\n¿Continuar?',
            parent=self.app,
        ):
            return
        result = restart_explorer()
        self.lbl_result.configure(text=result.get('message') or 'Operación finalizada.', text_color=GREEN if result.get('success') else RED)

    def refresh(self):
        self.refresh_status()

    def destroy(self):
        self._alive = False
        try:
            self.frame.destroy()
        except Exception:
            pass
