"""Centro interno de restauración para Tweaks de CorePulse.

V0.10.2.33w
- no abre ventanas independientes;
- lista sólo snapshots reales persistentes;
- detecta cambios posteriores fuera de CorePulse;
- separa cambios activos de historial de auditoría;
- restaura por selección o todo el inventario usando el motor existente.
"""
from __future__ import annotations

from datetime import datetime
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from core.theme_manager import color as theme_color
from core.windows_tweaks import (
    rollback_inventory,
    saved_rollback_ids,
    selected_metadata,
    tweak_history,
    undo_all_saved,
    undo_many,
)
from gui.stable_scroll import StableScrollHost

FONT = 'Segoe UI'
BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD_2 = theme_color('#0a1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
CYAN = '#14b8ff'
GREEN = '#1fd18b'
AMBER = '#f59e0b'
RED = '#ff5d6c'

STATE_COLORS = {
    'applied': GREEN,
    'restored_externally': CYAN,
    'modified_externally': AMBER,
    'unavailable': MUTED,
}


class TweakRestoreCenter:
    """Vista embebida. No modifica la navegación global de CorePulse."""

    def __init__(self, app, host, *, on_close=None, on_changed=None):
        self.app = app
        self.host = host
        self.on_close = on_close
        self.on_changed = on_changed
        self._alive = True
        self._busy = False
        self._loading = False
        self._inventory = []
        self._history = []
        self._vars = {}
        self._check_labels = {}
        self._view = 'Cambios activos'
        self._build()
        self.refresh()

    def widget(self):
        return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)

        top = ctk.CTkFrame(self.frame, fg_color='transparent')
        top.pack(fill='x', padx=18, pady=(15, 9))
        titles = ctk.CTkFrame(top, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            titles, text='Centro de restauración', font=(FONT, 18, 'bold'),
            text_color=TEXT, anchor='w',
        ).pack(anchor='w')
        ctk.CTkLabel(
            titles,
            text='Snapshots exactos de CorePulse, detección de cambios externos e historial de rollback.',
            font=(FONT, 9), text_color=TEXT_2, anchor='w',
        ).pack(anchor='w', pady=(1, 0))
        ctk.CTkButton(
            top, text='Volver a ajustes', width=118, height=30, corner_radius=8,
            fg_color='transparent', hover_color=theme_color('#102840'),
            border_width=1, border_color=theme_color('#214765'), text_color=TEXT_2,
            font=(FONT, 8, 'bold'), command=self._close,
        ).pack(side='right', padx=(10, 0))

        summary = ctk.CTkFrame(self.frame, fg_color='transparent')
        summary.pack(fill='x', padx=18, pady=(0, 8))
        self.lbl_total = self._summary_card(summary, 'CON ROLLBACK', '—', CYAN)
        self.lbl_applied = self._summary_card(summary, 'APLICADOS', '—', GREEN)
        self.lbl_external = self._summary_card(summary, 'CAMBIO EXTERNO', '—', AMBER)
        self.lbl_history = self._summary_card(summary, 'EVENTOS', '—', TEXT_2, last=True)

        toolbar = ctk.CTkFrame(
            self.frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10,
        )
        toolbar.pack(fill='x', padx=18, pady=(0, 8))
        ctk.CTkLabel(toolbar, text='VISTA', font=(FONT, 8, 'bold'), text_color=MUTED).pack(side='left', padx=(11, 7), pady=8)
        self.view_var = ctk.StringVar(value='Cambios activos')
        self.view_menu = ctk.CTkOptionMenu(
            toolbar, values=['Cambios activos', 'Historial'], variable=self.view_var,
            command=self._switch_view, width=145, height=29, corner_radius=7,
            fg_color=theme_color('#0d2942'), button_color=theme_color('#164f7d'),
            button_hover_color=theme_color('#1d628f'), dropdown_fg_color=theme_color('#0d1828'),
            dropdown_hover_color=theme_color('#16324c'), text_color=theme_color('#9bddff'),
            font=(FONT, 8, 'bold'), dropdown_font=(FONT, 9),
        )
        self.view_menu.pack(side='left', pady=8)
        self.lbl_filter_info = ctk.CTkLabel(
            toolbar, text='Selecciona filas para restaurarlas.', font=(FONT, 8),
            text_color=MUTED, anchor='w',
        )
        self.lbl_filter_info.pack(side='left', fill='x', expand=True, padx=12)
        self.btn_refresh = ctk.CTkButton(
            toolbar, text='Actualizar', width=88, height=29, corner_radius=7,
            fg_color='transparent', hover_color=theme_color('#102840'),
            border_width=1, border_color=BORDER, text_color=TEXT_2,
            font=(FONT, 8, 'bold'), command=self.refresh,
        )
        self.btn_refresh.pack(side='right', padx=11, pady=8)

        self.scroll = StableScrollHost(self.frame, fg_color=BG)
        self.scroll.pack(fill='both', expand=True, padx=13, pady=(0, 6))
        self.body = self.scroll.content

        self.action_bar = ctk.CTkFrame(
            self.frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10,
        )
        self.action_bar.pack(fill='x', padx=18, pady=(0, 13))
        self.lbl_action = ctk.CTkLabel(
            self.action_bar, text='0 seleccionados', font=(FONT, 8),
            text_color=MUTED, anchor='w',
        )
        self.lbl_action.pack(side='left', fill='x', expand=True, padx=11, pady=9)
        self.btn_restore_all = ctk.CTkButton(
            self.action_bar, text='Restaurar TODO', width=116, height=31, corner_radius=7,
            fg_color=theme_color('#2b1d26'), hover_color=theme_color('#412530'),
            border_width=1, border_color=theme_color('#693343'), text_color='#ffb0bd',
            font=(FONT, 8, 'bold'), command=self._restore_all,
        )
        self.btn_restore_all.pack(side='right', padx=(5, 10), pady=8)
        self.btn_restore_selected = ctk.CTkButton(
            self.action_bar, text='Restaurar seleccionados', width=148, height=31, corner_radius=7,
            fg_color=theme_color('#0d5c45'), hover_color=theme_color('#11765a'),
            border_width=1, border_color=theme_color('#178967'), text_color='#b8ffdf',
            font=(FONT, 8, 'bold'), command=self._restore_selected,
        )
        self.btn_restore_selected.pack(side='right', padx=5, pady=8)
        self.btn_restore_selected.configure(state='disabled')
        self.btn_restore_all.configure(state='disabled')

    def _summary_card(self, parent, title, initial, accent, last=False):
        card = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10)
        card.pack(side='left', fill='x', expand=True, padx=(0, 0 if last else 6))
        ctk.CTkLabel(card, text=title, font=(FONT, 7, 'bold'), text_color=MUTED, anchor='w').pack(anchor='w', padx=11, pady=(7, 0))
        value = ctk.CTkLabel(card, text=initial, font=(FONT, 16, 'bold'), text_color=accent, anchor='w')
        value.pack(anchor='w', padx=11, pady=(0, 7))
        return value

    def _close(self):
        if self._busy:
            return
        if callable(self.on_close):
            self.on_close()

    def _switch_view(self, label):
        self._view = str(label or 'Cambios activos')
        self._render()

    def _set_busy(self, busy, text=''):
        self._busy = bool(busy)
        state = 'disabled' if busy else 'normal'
        for widget in (self.btn_refresh, self.view_menu):
            try:
                widget.configure(state=state)
            except Exception:
                pass
        if busy:
            self.btn_restore_selected.configure(state='disabled')
            self.btn_restore_all.configure(state='disabled')
        else:
            self._update_selection_ui()
        if text:
            self.lbl_filter_info.configure(text=text, text_color=CYAN if busy else MUTED)

    def refresh(self):
        if self._busy or self._loading or not self._alive:
            return
        self._loading = True
        self.lbl_filter_info.configure(text='Comprobando snapshots y estado actual…', text_color=CYAN)
        self.btn_refresh.configure(state='disabled')

        def worker():
            inventory = rollback_inventory()
            history = tweak_history(limit=300)
            summary = {
                'total': len(inventory),
                'applied': sum(1 for row in inventory if row.get('state') == 'applied'),
                'modified_externally': sum(1 for row in inventory if row.get('state') == 'modified_externally'),
                'restored_externally': sum(1 for row in inventory if row.get('state') == 'restored_externally'),
                'unavailable': sum(1 for row in inventory if row.get('state') == 'unavailable'),
                'history_events': len(history),
            }

            def finish():
                if not self._alive:
                    return
                self._loading = False
                self._inventory = inventory
                self._history = history
                self._update_summary(summary)
                self.btn_refresh.configure(state='normal')
                self._render()

            try:
                self.frame.after(0, finish)
            except Exception:
                self._loading = False

        threading.Thread(target=worker, name='CorePulseRestoreCenterDetect', daemon=True).start()

    def _update_summary(self, summary):
        self.lbl_total.configure(text=str(summary.get('total', 0)))
        self.lbl_applied.configure(text=str(summary.get('applied', 0)))
        self.lbl_external.configure(text=str(summary.get('modified_externally', 0)))
        self.lbl_history.configure(text=str(summary.get('history_events', 0)))

    def _clear_body(self):
        for child in tuple(self.body.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        self._vars.clear()
        self._check_labels.clear()

    def _render(self):
        if not self._alive:
            return
        self._clear_body()
        if self._view == 'Historial':
            self._render_history()
            self._set_action_visible(False)
        else:
            self._render_active()
            self._set_action_visible(True)
        try:
            self.scroll._schedule_geometry(1)
        except Exception:
            pass

    def _set_action_visible(self, visible):
        try:
            if visible:
                if not self.action_bar.winfo_manager():
                    self.action_bar.pack(fill='x', padx=18, pady=(0, 13))
            else:
                self.action_bar.pack_forget()
        except Exception:
            pass

    def _render_active(self):
        rows = list(self._inventory)
        if not rows:
            empty = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10)
            empty.pack(fill='x', padx=5, pady=8)
            ctk.CTkLabel(
                empty, text='✓ No hay cambios de Tweaks pendientes de restaurar',
                font=(FONT, 12, 'bold'), text_color=GREEN,
            ).pack(anchor='w', padx=14, pady=(12, 2))
            ctk.CTkLabel(
                empty,
                text='CorePulse no tiene snapshots activos. Los cambios ya revertidos siguen disponibles en Historial.',
                font=(FONT, 9), text_color=TEXT_2, anchor='w', justify='left',
            ).pack(anchor='w', padx=14, pady=(0, 12))
            self.lbl_filter_info.configure(text='Sin rollback pendiente.', text_color=MUTED)
            self._update_selection_ui()
            return

        external = sum(1 for row in rows if row.get('state') == 'modified_externally')
        if external:
            self.lbl_filter_info.configure(
                text=f'{len(rows)} rollback(s) activos · {external} con cambio externo detectado.', text_color=AMBER,
            )
        else:
            self.lbl_filter_info.configure(text=f'{len(rows)} rollback(s) activos.', text_color=MUTED)

        for row in rows:
            self._render_active_row(row)
        self._update_selection_ui()

    def _render_active_row(self, data):
        state = str(data.get('state') or 'unavailable')
        color = STATE_COLORS.get(state, MUTED)
        row_bg = CARD_2
        border = theme_color('#6e5421') if state == 'modified_externally' else BORDER
        row = tk.Frame(self.body, bg=row_bg, bd=0, highlightthickness=1, highlightbackground=border, highlightcolor=border)
        row.pack(fill='x', padx=5, pady=4)

        var = tk.BooleanVar(master=row, value=False)
        tweak_id = str(data.get('id') or '')
        self._vars[tweak_id] = var
        check = tk.Label(
            row, text='☐', width=2, font=('Segoe UI Symbol', 14, 'bold'),
            fg=theme_color('#5f7189'), bg=row_bg, anchor='center', cursor='hand2', bd=0,
        )
        check.pack(side='left', padx=(9, 4), pady=11)
        self._check_labels[tweak_id] = check

        text_box = tk.Frame(row, bg=row_bg, bd=0)
        text_box.pack(side='left', fill='x', expand=True, padx=(2, 8), pady=7)
        tk.Label(
            text_box, text=str(data.get('title') or tweak_id), font=(FONT, 9, 'bold'),
            fg=TEXT, bg=row_bg, anchor='w', bd=0,
        ).pack(anchor='w', fill='x')
        saved = self._format_time(data.get('saved_at'))
        meta = f"{data.get('category') or 'Tweak'} · snapshot {saved}"
        if data.get('requires_admin'):
            meta += ' · ADMIN'
        if data.get('requires_restart'):
            meta += ' · REINICIO'
        elif data.get('requires_explorer'):
            meta += ' · EXPLORER'
        tk.Label(text_box, text=meta, font=(FONT, 7), fg=MUTED, bg=row_bg, anchor='w', bd=0).pack(anchor='w', fill='x', pady=(1, 0))

        changes = list(data.get('changes') or [])
        if changes:
            parts = []
            for change in changes[:2]:
                location = str(change.get('location') or '')
                short_loc = location.split(' · ')[-1] or location
                parts.append(f"{short_loc}: {change.get('before')} → {change.get('applied')}")
            if len(changes) > 2:
                parts.append(f'+{len(changes)-2} valor(es)')
            tk.Label(
                text_box, text='Anterior → aplicado:  ' + '  |  '.join(parts),
                font=(FONT, 7), fg=theme_color('#9da9b9'), bg=row_bg,
                anchor='w', justify='left', bd=0,
            ).pack(anchor='w', fill='x', pady=(2, 0))

        state_box = tk.Frame(row, bg=row_bg, bd=0)
        state_box.pack(side='right', padx=10, pady=7)
        tk.Label(
            state_box, text=str(data.get('state_label') or state).upper(),
            font=(FONT, 7, 'bold'), fg=color, bg=row_bg, anchor='e', bd=0,
        ).pack(anchor='e')
        detail = str(data.get('detail') or '')
        if len(detail) > 92:
            detail = detail[:89] + '…'
        tk.Label(
            state_box, text=detail, font=(FONT, 7), fg=MUTED, bg=row_bg,
            anchor='e', justify='right', wraplength=360, bd=0,
        ).pack(anchor='e', pady=(2, 0))

        def toggle(_event=None, tid=tweak_id):
            v = self._vars.get(tid)
            if v is None:
                return 'break'
            v.set(not bool(v.get()))
            self._sync_check(tid)
            self._update_selection_ui()
            return 'break'

        for node in (row, check, text_box):
            try:
                node.bind('<Button-1>', toggle, add='+')
            except Exception:
                pass
        for child in text_box.winfo_children():
            try:
                child.bind('<Button-1>', toggle, add='+')
            except Exception:
                pass

    def _render_history(self):
        rows = list(self._history)
        self.lbl_filter_info.configure(text=f'{len(rows)} evento(s) recientes de Tweaks.', text_color=MUTED)
        if not rows:
            ctk.CTkLabel(
                self.body, text='Todavía no hay eventos de Tweaks registrados.',
                font=(FONT, 10), text_color=MUTED,
            ).pack(anchor='w', padx=12, pady=18)
            return
        for data in rows:
            success = bool(data.get('success'))
            action = str(data.get('action') or '')
            label = str(data.get('event_label') or action.upper())
            color = GREEN if success else RED
            if success and action == 'undo':
                color = CYAN
            row = tk.Frame(self.body, bg=CARD_2, bd=0, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
            row.pack(fill='x', padx=5, pady=4)
            left = tk.Frame(row, bg=CARD_2, bd=0)
            left.pack(side='left', fill='x', expand=True, padx=11, pady=8)
            tk.Label(left, text=str(data.get('title') or data.get('tweak_id') or 'Tweak'), font=(FONT, 9, 'bold'), fg=TEXT, bg=CARD_2, anchor='w', bd=0).pack(anchor='w')
            message = str(data.get('message') or '').replace('\n', ' ').strip()
            if len(message) > 170:
                message = message[:167] + '…'
            tk.Label(left, text=message or 'Sin detalle adicional.', font=(FONT, 7), fg=MUTED, bg=CARD_2, anchor='w', bd=0).pack(anchor='w', pady=(2, 0))
            right = tk.Frame(row, bg=CARD_2, bd=0)
            right.pack(side='right', padx=11, pady=8)
            tk.Label(right, text=label, font=(FONT, 7, 'bold'), fg=color, bg=CARD_2, anchor='e', bd=0).pack(anchor='e')
            tk.Label(right, text=self._format_time(data.get('timestamp')), font=(FONT, 7), fg=MUTED, bg=CARD_2, anchor='e', bd=0).pack(anchor='e', pady=(2, 0))

    @staticmethod
    def _format_time(value):
        try:
            if not value:
                return 'fecha N/A'
            return datetime.fromtimestamp(float(value)).strftime('%d-%m-%Y %H:%M')
        except Exception:
            return 'fecha N/A'

    def _sync_check(self, tweak_id):
        var = self._vars.get(tweak_id)
        label = self._check_labels.get(tweak_id)
        if var is None or label is None:
            return
        selected = bool(var.get())
        try:
            label.configure(text='☑' if selected else '☐', fg=CYAN if selected else theme_color('#5f7189'))
        except Exception:
            pass

    def _selected_ids(self):
        return [tid for tid, var in self._vars.items() if bool(var.get())]

    def _update_selection_ui(self):
        ids = self._selected_ids()
        active_count = len(self._inventory)
        try:
            self.lbl_action.configure(text=f'{len(ids)} seleccionados · {active_count} rollback(s) activos')
            self.btn_restore_selected.configure(state='normal' if ids and not self._busy else 'disabled')
            self.btn_restore_all.configure(state='normal' if active_count and not self._busy else 'disabled')
        except Exception:
            pass

    def _inventory_by_id(self):
        return {str(row.get('id')): row for row in self._inventory}

    def _restore_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        self._confirm_and_restore(ids, all_saved=False)

    def _restore_all(self):
        ids = list(saved_rollback_ids())
        if not ids:
            return
        self._confirm_and_restore(ids, all_saved=True)

    def _confirm_and_restore(self, ids, *, all_saved):
        ids = [str(x) for x in ids]
        inventory = self._inventory_by_id()
        external = [inventory[x] for x in ids if x in inventory and inventory[x].get('state') == 'modified_externally']
        meta = selected_metadata(ids)

        text = (
            f"CorePulse restaurará {len(ids)} tweak(s) al estado exacto capturado antes de aplicarlos.\n\n"
            'El snapshot sólo se eliminará después de una verificación correcta.'
        )
        if meta.get('requires_admin'):
            text += '\n\nWindows puede mostrar UAC para los cambios del sistema.'
        if external:
            names = '\n'.join(f"• {row.get('title')}" for row in external[:6])
            if len(external) > 6:
                names += f"\n• … y {len(external)-6} más"
            text += (
                '\n\n⚠ CAMBIO EXTERNO DETECTADO\n'
                'Estos ajustes fueron modificados después de que CorePulse guardó su snapshot:\n'
                f'{names}\n\n'
                'Restaurar reemplazará esos cambios posteriores por el estado original guardado.'
            )
        if not messagebox.askyesno(
            'CorePulse · Restaurar Tweaks', text + '\n\n¿Continuar?', parent=self.app,
        ):
            return

        self._set_busy(True, 'Restaurando y verificando snapshots…')

        def worker():
            results = undo_all_saved(auto_elevate=True) if all_saved else undo_many(ids, auto_elevate=True)
            ok = sum(1 for row in results if row.get('success'))
            failed = len(results) - ok

            def finish():
                if not self._alive:
                    return
                self._set_busy(False)
                if failed:
                    self.lbl_filter_info.configure(
                        text=f'{ok} restaurados · {failed} pendientes. Los snapshots fallidos se conservaron.',
                        text_color=RED,
                    )
                else:
                    self.lbl_filter_info.configure(
                        text=f'{ok} tweak(s) restaurados y verificados.', text_color=GREEN,
                    )
                if callable(self.on_changed):
                    try:
                        self.on_changed()
                    except Exception:
                        pass
                self.refresh()

            try:
                self.frame.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=worker, name='CorePulseRestoreCenterUndo', daemon=True).start()

    def destroy(self):
        self._alive = False
        try:
            self.frame.destroy()
        except Exception:
            pass
