"""Centraliza diálogos nativos de información, advertencia, error y selección de archivo."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
from tkinter import filedialog, messagebox
from core.version import VERSION_LABEL
VERSION = VERSION_LABEL

def _title(section):
    section = str(section or '').strip()
    return f'CorePulse · {section}' if section else 'CorePulse'

def info(parent, section, message):
    return messagebox.showinfo(_title(section), str(message), parent=parent)

def warning(parent, section, message):
    return messagebox.showwarning(_title(section), str(message), parent=parent)

def error(parent, section, message):
    return messagebox.showerror(_title(section), str(message), parent=parent)

def ask_yes_no(parent, section, message):
    return messagebox.askyesno(_title(section), str(message), parent=parent)

def ask_pdf_path(parent, initialfile):
    try:
        parent.lift()
        parent.focus_force()
        parent.update_idletasks()
    except Exception:
        pass
    return filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('Archivos PDF', '*.pdf')], initialfile=initialfile, title=_title('Guardar informe PDF'), parent=parent)


def ask_pdf_directory(parent):
    """Pide solo la carpeta de destino; CorePulse genera el nombre del informe."""
    try:
        parent.lift()
        parent.focus_force()
        parent.update_idletasks()
    except Exception:
        pass
    return filedialog.askdirectory(title=_title('Seleccionar carpeta para el informe'), mustexist=True, parent=parent)
