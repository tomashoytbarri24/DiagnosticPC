"""Implementa las acciones funcionales del centro de limpieza y mantenimiento."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import hashlib
import os
import shutil
import threading
import time
from pathlib import Path
import customtkinter as ctk
import psutil
from tkinter import filedialog, messagebox
from core.ram_optimizer import optimize_ram_safely, optimize_ram_deep, is_administrator
from core.version import VERSION_LABEL
BG_MAIN = theme_color('#0b0f19')
BG_CARD = theme_color('#151c2c')
BG_CARD_2 = theme_color(theme_color('#111827'))
BORDER = theme_color('#26344f')
TEXT = theme_color('#f8fafc')
TEXT_DIM = theme_color('#94a3b8')
PURPLE = '#8b5cf6'
BLUE = theme_color('#1687ea')
CYAN = '#38bdf8'
GREEN = '#10b981'
ORANGE = '#f59e0b'

def _fmt_bytes(value):
    try:
        n = float(value)
    except Exception:
        return 'N/A'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if abs(n) < 1024 or unit == 'TB':
            return f'{n:.2f} {unit}' if unit in ('GB', 'TB') else f'{n:.1f} {unit}'
        n /= 1024.0

def _safe_temp_roots():
    roots = []
    for raw in (os.environ.get('TEMP'), os.environ.get('TMP'), str(Path.home() / 'AppData' / 'Local' / 'Temp')):
        if not raw:
            continue
        try:
            p = Path(raw).expanduser().resolve()
        except Exception:
            continue
        if p.exists() and p not in roots:
            roots.append(p)
    return roots

def _scan_tree_size(roots):
    total = 0
    files = 0
    errors = 0
    for root in roots:
        try:
            root = Path(root).resolve()
        except Exception:
            continue
        if not root.exists():
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                p = Path(dirpath) / name
                try:
                    if p.is_symlink():
                        continue
                    total += p.stat().st_size
                    files += 1
                except (PermissionError, OSError):
                    errors += 1
    return {'bytes': total, 'files': files, 'errors': errors}

def _delete_allowed_temp_files():
    roots = _safe_temp_roots()
    before = _scan_tree_size(roots)
    deleted_bytes = 0
    deleted_files = 0
    skipped = 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            for name in filenames:
                p = Path(dirpath) / name
                try:
                    if p.is_symlink():
                        skipped += 1
                        continue
                    size = p.stat().st_size
                    p.unlink()
                    deleted_bytes += size
                    deleted_files += 1
                except (PermissionError, OSError):
                    skipped += 1
            for name in dirnames:
                p = Path(dirpath) / name
                try:
                    p.rmdir()
                except (PermissionError, OSError):
                    pass
    return {'before': before, 'deleted_bytes': deleted_bytes, 'deleted_files': deleted_files, 'skipped': skipped, 'after': _scan_tree_size(roots)}

def _sha256(path, block=1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(block)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def scan_duplicates(folder):
    folder = Path(folder).resolve()
    by_size = {}
    scanned = 0
    errors = 0
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                if p.is_symlink():
                    continue
                size = p.stat().st_size
                if size <= 0:
                    continue
                by_size.setdefault(size, []).append(p)
                scanned += 1
            except (PermissionError, OSError):
                errors += 1
    groups = []
    wasted = 0
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash = {}
        for p in paths:
            try:
                by_hash.setdefault(_sha256(p), []).append(p)
            except (PermissionError, OSError):
                errors += 1
        for digest, dupes in by_hash.items():
            if len(dupes) > 1:
                dupes = sorted(dupes, key=lambda x: str(x).lower())
                groups.append({'size': size, 'hash': digest, 'files': [str(x) for x in dupes]})
                wasted += size * (len(dupes) - 1)
    return {'folder': str(folder), 'scanned_files': scanned, 'errors': errors, 'groups': groups, 'duplicate_files': sum((max(0, len(g['files']) - 1) for g in groups)), 'wasted_bytes': wasted}

class CleaningToolCard(ctk.CTkFrame):

    def __init__(self, parent, title, icon, accent, description, action_label, action_command, analyze_command=None, footer='', action_color=None):
        super().__init__(parent, fg_color=BG_CARD, border_width=1, border_color=BORDER, corner_radius=12)
        self.accent = accent
        self.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(self, fg_color='transparent')
        head.grid(row=0, column=0, sticky='ew', padx=15, pady=(16, 3))
        ctk.CTkLabel(head, text=icon, font=('Segoe UI Emoji', 21), text_color=accent).pack(side='left', padx=(0, 8))
        ctk.CTkLabel(head, text=title, font=('Segoe UI', 16, 'bold'), text_color=TEXT).pack(side='left')
        ctk.CTkLabel(self, text=description, font=('Segoe UI', 9), text_color=TEXT_DIM, justify='left', anchor='w', wraplength=240).grid(row=1, column=0, sticky='ew', padx=15, pady=(0, 12))
        result = ctk.CTkFrame(self, fg_color=BG_CARD_2, border_width=1, border_color=theme_color('#202d44'), corner_radius=9)
        result.grid(row=2, column=0, sticky='ew', padx=15, pady=(0, 12))
        self.lbl_result_title = ctk.CTkLabel(result, text='ESTADO', font=('Segoe UI', 9, 'bold'), text_color=TEXT_DIM)
        self.lbl_result_title.pack(anchor='w', padx=12, pady=(10, 2))
        self.lbl_value = ctk.CTkLabel(result, text='Sin analizar', font=('Segoe UI', 20, 'bold'), text_color=accent)
        self.lbl_value.pack(anchor='w', padx=12)
        self.lbl_detail = ctk.CTkLabel(result, text='Pulsa Analizar para obtener datos reales.', font=('Segoe UI', 8), text_color=TEXT_DIM, justify='left', anchor='w', wraplength=230)
        self.lbl_detail.pack(anchor='w', padx=12, pady=(2, 10))
        self.btn_analyze = None
        if analyze_command:
            self.btn_analyze = ctk.CTkButton(self, text='Analizar', height=32, corner_radius=7, fg_color='#334155', hover_color='#475569', font=('Segoe UI', 9, 'bold'), command=analyze_command)
            self.btn_analyze.grid(row=3, column=0, sticky='ew', padx=15, pady=(0, 7))
        self.btn_action = ctk.CTkButton(self, text=action_label, height=34, corner_radius=7, fg_color=action_color or accent, hover_color=action_color or accent, font=('Segoe UI', 9, 'bold'), command=action_command)
        self.btn_action.grid(row=4, column=0, sticky='ew', padx=15, pady=(0, 8))
        ctk.CTkLabel(self, text=footer, font=('Segoe UI', 8), text_color=TEXT_DIM, wraplength=230, justify='center').grid(row=5, column=0, sticky='ew', padx=15, pady=(0, 14))

    def set_result(self, value, detail='', color=None, title=None):
        if title:
            self.lbl_result_title.configure(text=title)
        self.lbl_value.configure(text=value, text_color=color or self.accent)
        self.lbl_detail.configure(text=detail)

    def set_busy(self, busy=True, text=None):
        state = 'disabled' if busy else 'normal'
        if self.btn_analyze:
            self.btn_analyze.configure(state=state)
        self.btn_action.configure(state=state)
        secondary = getattr(self, 'btn_secondary_action', None)
        if secondary is not None:
            secondary.configure(state=state)
        if text:
            self.lbl_detail.configure(text=text)

class CleaningCenterPanel(ctk.CTkFrame):

    def __init__(self, app):
        parent = getattr(app, '_internal_page_build_host', None) or getattr(app, '_internal_page_host', None) or getattr(app, 'main_content', app)
        super().__init__(parent, fg_color=BG_MAIN, corner_radius=0)
        self.app = app
        self.cache_scan = None
        self.duplicate_scan = None
        self._closed = False
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_cards()
        self._build_footer()
        self.after(100, self.refresh_ram_card)

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG_CARD, border_width=1, border_color=BORDER, corner_radius=10)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        header.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(header, fg_color='transparent')
        left.grid(row=0, column=0, sticky='w', padx=18, pady=12)
        ctk.CTkLabel(left, text='LIMPIEZA DE SISTEMA', font=('Segoe UI', 19, 'bold'), text_color=TEXT).pack(anchor='w')
        ctk.CTkLabel(left, text='Herramientas avanzadas para optimizar y liberar recursos de forma segura.', font=('Segoe UI', 9), text_color=TEXT_DIM).pack(anchor='w', pady=(2, 0))
        ctk.CTkButton(header, text='← Volver al Dashboard', width=155, height=32, corner_radius=7, fg_color=theme_color('#26354d'), hover_color=theme_color(theme_color('#334867')), command=self.close).grid(row=0, column=1, padx=14, pady=12)

    def _build_cards(self):
        """Construye la operación `build_cards` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
        self.body = ctk.CTkFrame(self, fg_color='transparent', corner_radius=0)
        self.body.grid(row=1, column=0, sticky='nsew')
        self.cache_card = CleaningToolCard(self.body, 'Limpiar Caché', '🧹', PURPLE, 'Elimina temporales permitidos y mide el espacio real.', 'Limpiar Ahora', self.clean_cache, analyze_command=self.analyze_cache, footer='Confirmación antes de eliminar.')
        self.ram_card = CleaningToolCard(self.body, 'Liberar RAM', '⚙', BLUE, 'Optimiza memoria reclamable y mide antes/después.', 'Liberar RAM Segura', self.optimize_ram, analyze_command=self.refresh_ram_card, footer='No modifica procesos externos.')
        self.dup_card = CleaningToolCard(self.body, 'Archivos Duplicados', '📄', ORANGE, 'Busca duplicados reales por SHA-256 en la carpeta elegida.', 'Revisar Resultados', self.review_duplicates, analyze_command=self.analyze_duplicates, footer='No elimina archivos automáticamente.', action_color='#c9810b')
        self.storage_card = CleaningToolCard(self.body, 'Liberar Almacenamiento', '▱', GREEN, 'Muestra uso real del disco y rutas seguras disponibles.', 'Analizar Almacenamiento', self.analyze_storage, footer='Protege carpetas personales.')
        self.tool_cards = [self.cache_card, self.ram_card, self.dup_card, self.storage_card]
        self.safety = ctk.CTkFrame(self.body, fg_color=BG_CARD, border_width=1, border_color=BORDER, corner_radius=10, height=62)
        self.safety.grid_propagate(False)
        self.safety.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.safety, text='🛡', font=('Segoe UI Emoji', 19), text_color=CYAN).grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=5)
        ctk.CTkLabel(self.safety, text='100% CONTROLADO POR EVIDENCIA', font=('Segoe UI', 9, 'bold'), text_color=TEXT).grid(row=0, column=1, sticky='w', pady=(6, 0))
        self.safety_description = ctk.CTkLabel(self.safety, text='Datos reales o N/A hasta obtener una medición válida.', font=('Segoe UI', 8), text_color=TEXT_DIM, anchor='w')
        self.safety_description.grid(row=1, column=1, sticky='ew', pady=(0, 6))
        self.badges = ctk.CTkFrame(self.safety, fg_color='transparent')
        self.badges.grid(row=0, column=2, rowspan=2, sticky='e', padx=7)
        for label in ('Análisis Seguro', 'Confirmación', 'Medición Real', 'Datos / N/A'):
            ctk.CTkLabel(self.badges, text=label, font=('Segoe UI', 7, 'bold'), text_color=theme_color('#cbd5e1'), fg_color=theme_color('#1f2a3d'), corner_radius=6, padx=4, pady=2).pack(side='left', padx=2)
        self._cleaning_layout_columns = None
        self._cleaning_layout_after_id = None
        self._last_layout_width = None
        self.bind('<Configure>', self._schedule_compact_layout, add='+')
        self.after(60, self._initialize_compact_layout)

    def _initialize_compact_layout(self):
        if self._closed:
            return
        try:
            width = max(1, int(self.winfo_width()))
        except Exception:
            width = 900
        self._apply_compact_layout(width)

    def _schedule_compact_layout(self, event=None):
        if self._closed:
            return
        if getattr(self.app, 'is_resizing', False):
            return
        if event is not None and getattr(event, 'widget', self) is not self:
            return
        try:
            width = int(self.winfo_width())
        except Exception:
            return
        if width <= 1:
            return
        if self._last_layout_width is not None and abs(width - self._last_layout_width) < 20:
            return
        if self._cleaning_layout_after_id is not None:
            try:
                self.after_cancel(self._cleaning_layout_after_id)
            except Exception:
                pass
        self._cleaning_layout_after_id = self.after(100, lambda w=width: self._apply_compact_layout(w))

    def _desired_compact_columns(self, width):
        return 4 if width >= 820 else 2

    def _compact_labels(self, card, columns):
        wrap = 180 if columns == 4 else 320
        stack = list(card.winfo_children())
        while stack:
            widget = stack.pop()
            if isinstance(widget, ctk.CTkLabel):
                try:
                    widget.configure(wraplength=wrap)
                except Exception:
                    pass
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass

    def _apply_compact_layout(self, width):
        self._cleaning_layout_after_id = None
        if self._closed:
            return
        columns = self._desired_compact_columns(width)
        if columns == self._cleaning_layout_columns:
            self._last_layout_width = width
            return
        self._cleaning_layout_columns = columns
        self._last_layout_width = width
        for col in range(4):
            self.body.grid_columnconfigure(col, weight=0, uniform='')
        for col in range(columns):
            self.body.grid_columnconfigure(col, weight=1, uniform=f'clean_{columns}')
        for card in self.tool_cards:
            card.grid_forget()
        for idx, card in enumerate(self.tool_cards):
            row, col = divmod(idx, columns)
            card.grid(row=row, column=col, sticky='nsew', padx=(0 if col == 0 else 4, 0 if col == columns - 1 else 4), pady=(2, 6))
            self._compact_labels(card, columns)
        rows = (len(self.tool_cards) + columns - 1) // columns
        self.safety.grid_forget()
        self.safety.grid(row=rows, column=0, columnspan=columns, sticky='ew', pady=(5, 0))
        if columns == 4 and width >= 980:
            self.badges.grid()
        else:
            self.badges.grid_remove()

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=2, column=0, sticky='ew', pady=(7, 0))
        ctk.CTkLabel(footer, text=f'CorePulse Engine {VERSION_LABEL} • Monitoreo activo • Datos reales / N/A', font=('Segoe UI', 8), text_color=TEXT_DIM).pack(side='left', padx=4)
        self.lbl_last_action = ctk.CTkLabel(footer, text='Sin acciones ejecutadas', font=('Segoe UI', 8), text_color=TEXT_DIM)
        self.lbl_last_action.pack(side='right', padx=4)

    def close(self):
        self._closed = True
        if getattr(self, '_cleaning_layout_after_id', None) is not None:
            try:
                self.after_cancel(self._cleaning_layout_after_id)
            except Exception:
                pass
            self._cleaning_layout_after_id = None
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

    def _thread(self, target, done, fail):

        def worker():
            try:
                result = target()
                if not self._closed:
                    self.after(0, lambda: done(result))
            except Exception as exc:
                if not self._closed:
                    self.after(0, lambda: fail(exc))
        threading.Thread(target=worker, daemon=True).start()

    def refresh_ram_card(self):
        vm = psutil.virtual_memory()
        self.ram_card.set_result(f'{vm.percent:.1f}% en uso', f'Disponible: {_fmt_bytes(vm.available)} • Total: {_fmt_bytes(vm.total)}', color=GREEN if vm.percent < 80 else ORANGE, title='ESTADO ACTUAL')

    def optimize_ram(self):
        if not messagebox.askyesno('CorePulse - RAM segura', 'No se cerrarán aplicaciones ni se modificarán working sets ajenos.\n\n¿Continuar?', parent=self.app):
            return
        self.ram_card.set_busy(True, 'Midiendo y optimizando memoria...')
        self._thread(lambda: optimize_ram_safely(settle_seconds=0.35, snapshot_samples=3, run_registered_cache_clearers=True), self._ram_done, self._ram_fail)

    def _ram_done(self, result):
        self.ram_card.set_busy(False)
        before = result.get('before') or {}
        after = result.get('after') or {}
        recovered = float(result.get('measured_recovered_mb') or 0)
        self.ram_card.set_result(f'{recovered:.2f} MB', f"Antes: {float(before.get('used_percent') or 0):.1f}% • Después: {float(after.get('used_percent') or 0):.1f}%\nProcesos externos modificados: 0", color=GREEN, title='RECUPERADO MEDIDO')
        self.lbl_last_action.configure(text=f"RAM: {recovered:.2f} MB • {time.strftime('%H:%M:%S')}")

    def _ram_fail(self, exc):
        self.ram_card.set_busy(False)
        messagebox.showerror('CorePulse - RAM', str(exc), parent=self.app)

    def optimize_ram_deep(self):
        if not is_administrator():
            messagebox.showwarning('CorePulse - RAM profunda', 'La liberación profunda requiere ejecutar CorePulse como administrador.', parent=self.app)
            return
        if not messagebox.askyesno('CorePulse - RAM profunda', 'Esta acción recorta working sets accesibles y solicita a Windows purgar memoria standby.\nPuede provocar recargas o micro-stutter temporal en aplicaciones abiertas.\n\nCorePulse medirá el resultado real antes/después y no promete un porcentaje fijo.\n\n¿Continuar?', parent=self.app):
            return
        self.ram_card.set_busy(True, 'Ejecutando liberación profunda de Windows...')
        self._thread(lambda: optimize_ram_deep(settle_seconds=0.9, snapshot_samples=4, purge_standby=True), self._ram_deep_done, self._ram_fail)

    def _ram_deep_done(self, result):
        self.ram_card.set_busy(False)
        if not result.get('success'):
            messagebox.showwarning('CorePulse - RAM profunda', str(result.get('message') or 'No se pudo ejecutar.'), parent=self.app)
            self.refresh_ram_card()
            return
        before = result.get('before') or {}
        after = result.get('after') or {}
        recovered = float(result.get('measured_recovered_mb') or 0)
        self.ram_card.set_result(f'{recovered / 1024.0:.2f} GB', f"Antes: {float(before.get('used_percent') or 0):.1f}% • Después: {float(after.get('used_percent') or 0):.1f}%\nWorking sets recortados: {int(result.get('working_sets_trimmed') or 0)} • Standby: {('sí' if result.get('standby_purge_success') else 'no/N/A')}", color=GREEN, title='LIBERACIÓN PROFUNDA MEDIDA')
        self.lbl_last_action.configure(text=f"RAM profunda: {recovered:.1f} MB • {time.strftime('%H:%M:%S')}")

    def analyze_cache(self):
        self.cache_card.set_busy(True, 'Analizando temporales permitidos...')
        self._thread(lambda: _scan_tree_size(_safe_temp_roots()), self._cache_done, self._cache_fail)

    def _cache_done(self, result):
        self.cache_scan = result
        self.cache_card.set_busy(False)
        self.cache_card.set_result(_fmt_bytes(result['bytes']), f"{result['files']:,} archivos • {result['errors']} omitidos/error", color=PURPLE, title='ELEMENTOS ENCONTRADOS')

    def _cache_fail(self, exc):
        self.cache_card.set_busy(False)
        messagebox.showerror('CorePulse - Caché', str(exc), parent=self.app)

    def clean_cache(self):
        if not messagebox.askyesno('CorePulse - Limpiar Caché', 'Se borrarán solo archivos TEMP permitidos. Los bloqueados se omitirán.\n\n¿Continuar?', parent=self.app):
            return
        self.cache_card.set_busy(True, 'Eliminando temporales permitidos...')
        self._thread(_delete_allowed_temp_files, self._cache_clean_done, self._cache_fail)

    def _cache_clean_done(self, result):
        self.cache_card.set_busy(False)
        freed = result['deleted_bytes']
        self.cache_card.set_result(_fmt_bytes(freed), f"{result['deleted_files']:,} eliminados • {result['skipped']} omitidos", color=GREEN, title='ESPACIO LIBERADO MEDIDO')
        self.lbl_last_action.configure(text=f"Caché: {_fmt_bytes(freed)} • {time.strftime('%H:%M:%S')}")

    def analyze_duplicates(self):
        folder = filedialog.askdirectory(title='Selecciona carpeta para analizar duplicados', parent=self.app)
        if not folder:
            return
        self.dup_card.set_busy(True, 'Calculando hashes SHA-256...')
        self._thread(lambda: scan_duplicates(folder), self._duplicates_done, self._duplicates_fail)

    def _duplicates_done(self, result):
        self.duplicate_scan = result
        self.dup_card.set_busy(False)
        self.dup_card.set_result(_fmt_bytes(result['wasted_bytes']), f"{result['duplicate_files']:,} copias verificadas • {len(result['groups'])} grupos • {result['scanned_files']:,} analizados", color=ORANGE, title='DUPLICADOS VERIFICADOS')

    def _duplicates_fail(self, exc):
        self.dup_card.set_busy(False)
        messagebox.showerror('CorePulse - Duplicados', str(exc), parent=self.app)

    def review_duplicates(self):
        if not self.duplicate_scan:
            messagebox.showinfo('CorePulse - Duplicados', 'Primero pulsa Analizar.', parent=self.app)
            return
        result = self.duplicate_scan
        lines = []
        for idx, group in enumerate(result['groups'][:10], 1):
            lines.append(f"Grupo {idx}: {_fmt_bytes(group['size'])} × {len(group['files'])}")
            for p in group['files'][:2]:
                lines.append(f'  • {p}')
            if len(group['files']) > 2:
                lines.append(f"  • ... +{len(group['files']) - 2} más")
        messagebox.showinfo('CorePulse - Duplicados verificados', f"Carpeta: {result['folder']}\nCopias duplicadas: {result['duplicate_files']}\nEspacio duplicado: {_fmt_bytes(result['wasted_bytes'])}\n\n" + ('\n'.join(lines) if lines else 'No se encontraron duplicados.') + '\n\nEsta versión no borra automáticamente archivos personales.', parent=self.app)

    def analyze_storage(self):
        try:
            root = Path(os.environ.get('SystemDrive', 'C:') + '\\')
            usage = shutil.disk_usage(root)
            used = usage.total - usage.free
            pct = used / usage.total * 100 if usage.total else 0
            self.storage_card.set_result(f'{pct:.1f}% usado', f'Libre: {_fmt_bytes(usage.free)} • Total: {_fmt_bytes(usage.total)}', color=GREEN if pct < 85 else ORANGE, title='ALMACENAMIENTO REAL')
        except Exception as exc:
            messagebox.showerror('CorePulse - Almacenamiento', str(exc), parent=self.app)

def show_cleaning_center(app):
    existing = getattr(app, 'cleaning_center_panel', None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return existing
    except Exception:
        pass
    panel = CleaningCenterPanel(app)
    app.cleaning_center_panel = panel
    return panel
