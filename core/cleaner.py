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

def get_temp_directories():
    """Retorna las rutas de carpetas temporales para Windows o Linux."""
    temp_dirs = [tempfile.gettempdir()]
    if IS_WINDOWS:
        win_temp = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Temp')
        if os.path.exists(win_temp):
            temp_dirs.append(win_temp)
    else:  # Linux
        for extra in ['/var/tmp', '/tmp']:
            if os.path.exists(extra):
                temp_dirs.append(extra)
    return list(set(temp_dirs))

def calculate_cleanable_space_mb():
    """Calcula el espacio total estimado en MB que se puede liberar."""
    total_bytes = 0
    for folder in get_temp_directories():
        for root, _, files in os.walk(folder):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_bytes += os.path.getsize(file_path)
                except Exception:
                    continue
    return round(total_bytes / (1024**2), 2)

def clean_temp_files():
    """Elimina archivos temporales omitiendo los que estén en uso."""
    freed_bytes = 0
    deleted_files_count = 0
    
    for folder in get_temp_directories():
        for root, dirs, files in os.walk(folder, topdown=False):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    os.remove(file_path)
                    freed_bytes += size
                    deleted_files_count += 1
                except Exception:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except Exception:
                    pass
                    
    return {
        "freed_mb": round(freed_bytes / (1024**2), 2),
        "deleted_files": deleted_files_count
    }

def empty_recycle_bin():
    """Vacía la papelera de reciclaje según el sistema operativo."""
    try:
        if IS_WINDOWS:
            flags = 7  # SILENT | NOPROGRESSBAR | NOCONFIRMATION
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return result == 0
        else:  # Linux (XDG Trash Standard)
            trash_path = os.path.expanduser('~/.local/share/Trash/files')
            if os.path.exists(trash_path):
                for item in os.listdir(trash_path):
                    p = os.path.join(trash_path, item)
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    else:
                        os.remove(p)
            return True
    except Exception:
        return False

def flush_dns_cache():
    """Vacía la caché DNS del sistema."""
    try:
        if IS_WINDOWS:
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, check=True, creationflags=0x08000000)
        else:  # Linux (resolvectl o systemd-resolve)
            try:
                subprocess.run(["resolvectl", "flush-caches"], check=True)
            except Exception:
                subprocess.run(["systemd-resolve", "--flush-caches"], check=True)
        return True
    except Exception:
        return False

def optimize_ram_memory():
    """Optimiza el uso de memoria en Windows o Linux."""
    if IS_WINDOWS:
        for proc in psutil.process_iter(['pid']):
            try:
                pid = proc.info['pid']
                if pid == 0: continue
                handle = ctypes.windll.kernel32.OpenProcess(0x0500, False, pid)
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                continue
    else:  # Linux: forzar escritura en disco para liberar buffers
        try:
            subprocess.run(["sync"], check=True)
        except Exception:
            pass
    return True

def calculate_file_hash(file_path, chunk_size=65536):
    """Calcula hash MD5 por partes para no saturar memoria RAM."""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def find_duplicate_files(target_dir, status_callback=None):
    """Búsqueda de archivos duplicados de doble fase (tamaño -> MD5)."""
    size_groups = {}
    for root, _, files in os.walk(target_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                size = os.path.getsize(file_path)
                if size > 0:
                    size_groups.setdefault(size, []).append(file_path)
            except Exception:
                continue

    potential_duplicates = {size: paths for size, paths in size_groups.items() if len(paths) > 1}
    duplicates_by_hash = {}
    total_groups = len(potential_duplicates)
    processed_groups = 0

    for size, paths in potential_duplicates.items():
        processed_groups += 1
        if status_callback:
            status_callback(f"Analizando coincidencias ({processed_groups}/{total_groups})...")
            
        for path in paths:
            file_hash = calculate_file_hash(path)
            if file_hash:
                duplicates_by_hash.setdefault((file_hash, size), []).append(path)

    return {key: paths for key, paths in duplicates_by_hash.items() if len(paths) > 1}

def delete_duplicate_file(file_path):
    """Elimina el archivo duplicado seleccionado."""
    try:
        os.remove(file_path)
        return True
    except Exception:
        return False