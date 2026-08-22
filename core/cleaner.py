# core/cleaner.py

import os
import shutil
import tempfile
import platform
import subprocess
import hashlib
import psutil

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import ctypes


# ============================================================================
# RUTAS DE ARCHIVOS TEMPORALES
# ============================================================================

def get_temp_directories():
    """Retorna las rutas de carpetas temporales según el sistema operativo."""
    temp_dirs = [tempfile.gettempdir()]
    
    if IS_WINDOWS:
        win_temp = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Temp')
        if os.path.exists(win_temp):
            temp_dirs.append(win_temp)
    else:  # Linux / Unix
        user_home = os.path.expanduser('~')
        extra_dirs = ['/var/tmp', '/tmp', os.path.join(user_home, '.cache')]
        for extra in extra_dirs:
            if os.path.exists(extra):
                temp_dirs.append(extra)
                
    return list(set(temp_dirs))


# ============================================================================
# LIMPIEZA DE TEMPORALES Y ESPACIO
# ============================================================================

def calculate_cleanable_space_mb():
    """Calcula el espacio total estimado en MB que se puede liberar en temporales."""
    total_bytes = 0
    for folder in get_temp_directories():
        for root, _, files in os.walk(folder):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path) and not os.path.islink(file_path):
                        total_bytes += os.path.getsize(file_path)
                except Exception:
                    continue
    return round(total_bytes / (1024 ** 2), 2)


def clean_temp_files():
    """Elimina archivos temporales omitiendo los que estén bloqueados o en uso."""
    freed_bytes = 0
    deleted_files_count = 0
    
    for folder in get_temp_directories():
        for root, dirs, files in os.walk(folder, topdown=False):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    if not os.path.islink(file_path):
                        size = os.path.getsize(file_path)
                        os.remove(file_path)
                        freed_bytes += size
                        deleted_files_count += 1
                except Exception:
                    pass
            for d in dirs:
                try:
                    dir_path = os.path.join(root, d)
                    if not os.path.islink(dir_path):
                        os.rmdir(dir_path)
                except Exception:
                    pass
                    
    return {
        "freed_mb": round(freed_bytes / (1024 ** 2), 2),
        "deleted_files": deleted_files_count
    }


def empty_recycle_bin():
    """Vacía la papelera de reciclaje en Windows (WinAPI) o Linux (XDG Trash)."""
    try:
        if IS_WINDOWS:
            # Flags: SHERB_NOCONFIRMATION (0x1) | SHERB_NOPROGRESSUI (0x2) | SHERB_NOSOUND (0x4)
            flags = 7
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return result == 0
        else:  # Linux (Estándar XDG Trash)
            trash_path = os.path.expanduser('~/.local/share/Trash/files')
            trash_info = os.path.expanduser('~/.local/share/Trash/info')
            
            for t_path in (trash_path, trash_info):
                if os.path.exists(t_path):
                    for item in os.listdir(t_path):
                        p = os.path.join(t_path, item)
                        try:
                            if os.path.isdir(p) and not os.path.islink(p):
                                shutil.rmtree(p)
                            else:
                                os.remove(p)
                        except Exception:
                            continue
            return True
    except Exception:
        return False


# ============================================================================
# OPTIMIZACIÓN DE SISTEMA Y RED
# ============================================================================

def flush_dns_cache():
    """Vacía la caché DNS del sistema operativo."""
    try:
        if IS_WINDOWS:
            creationflags = 0x08000000  # CREATE_NO_WINDOW
            subprocess.run(
                ["ipconfig", "/flushdns"],
                capture_output=True,
                check=True,
                creationflags=creationflags
            )
        else:  # Linux
            try:
                subprocess.run(["resolvectl", "flush-caches"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                subprocess.run(["systemd-resolve", "--flush-caches"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def optimize_ram_memory():
    """Reduce el Working Set de los procesos (Windows) o fuerza sync de buffers (Linux)."""
    if IS_WINDOWS:
        for proc in psutil.process_iter(['pid']):
            try:
                pid = proc.info['pid']
                if pid == 0:
                    continue
                # PROCESS_SET_QUOTA (0x0100) | PROCESS_VM_WRITE (0x0020)
                handle = ctypes.windll.kernel32.OpenProcess(0x0500, False, pid)
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                continue
    else:  # Linux
        try:
            subprocess.run(["sync"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    return True


# ============================================================================
# DETECCIÓN DE ARCHIVOS DUPLICADOS
# ============================================================================

def calculate_file_hash(file_path, chunk_size=65536):
    """Calcula hash MD5 por fragmentos de 64KB para proteger el uso de RAM."""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


def find_duplicate_files(target_dir, status_callback=None):
    """Búsqueda optimizada de archivos duplicados (Fase 1: Tamaño -> Fase 2: MD5)."""
    if not os.path.exists(target_dir):
        return {}

    size_groups = {}
    
    # Fase 1: Agrupar por tamaño
    for root, _, files in os.walk(target_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                if not os.path.islink(file_path):
                    size = os.path.getsize(file_path)
                    if size > 0:
                        size_groups.setdefault(size, []).append(file_path)
            except Exception:
                continue

    potential_duplicates = {size: paths for size, paths in size_groups.items() if len(paths) > 1}
    duplicates_by_hash = {}
    total_groups = len(potential_duplicates)
    processed_groups = 0

    # Fase 2: Verificar Hash MD5 solo de coincidencias
    for size, paths in potential_duplicates.items():
        processed_groups += 1
        if status_callback:
            try:
                status_callback(f"Analizando coincidencias ({processed_groups}/{total_groups})...")
            except Exception:
                pass
            
        for path in paths:
            file_hash = calculate_file_hash(path)
            if file_hash:
                duplicates_by_hash.setdefault((file_hash, size), []).append(path)

    return {key: paths for key, paths in duplicates_by_hash.items() if len(paths) > 1}


def delete_duplicate_file(file_path):
    """Elimina de forma segura el archivo duplicado indicado."""
    try:
        if os.path.exists(file_path) and not os.path.islink(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False