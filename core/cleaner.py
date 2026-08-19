import os
import shutil
import tempfile
import ctypes
import subprocess
import hashlib
import psutil

def get_temp_directories():
    """Retorna las rutas de las carpetas temporales de Windows."""
    temp_dirs = [
        tempfile.gettempdir(),  # C:\Users\<User>\AppData\Local\Temp
        os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Temp')
    ]
    return [d for d in temp_dirs if os.path.exists(d)]

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
    """
    Elimina archivos temporales acumulados. 
    Omite automáticamente aquellos archivos que estén en uso por procesos activos.
    """
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
                    pass  # Archivo en uso por el sistema o protegido
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
    """Vacía la Papelera de Reciclaje de Windows de forma silenciosa mediante WinAPI."""
    try:
        flags = 7  # Sin confirmación, sin barra de progreso y sin sonido
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        return result == 0
    except Exception:
        return False

def flush_dns_cache():
    """Ejecuta el vaciado de la caché DNS del sistema sin mostrar consola."""
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, check=True, creationflags=0x08000000)
        return True
    except Exception:
        return False

def optimize_ram_memory():
    """
    Limpieza profunda de RAM estilo Mem Reduct.
    Recorre todos los procesos activos y vacía sus Working Sets, además de purgar la Standby List.
    """
    cleaned_processes = 0

    for proc in psutil.process_iter(['pid']):
        try:
            pid = proc.info['pid']
            if pid == 0:
                continue
            
            handle = ctypes.windll.kernel32.OpenProcess(0x0500, False, pid)
            if handle:
                if ctypes.windll.psapi.EmptyWorkingSet(handle):
                    cleaned_processes += 1
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            continue

    try:
        command = ctypes.c_ulong(3)  # MemoryPurgeStandbyList
        ctypes.windll.ntdll.NtSetSystemInformation(80, ctypes.byref(command), ctypes.sizeof(command))
    except Exception:
        pass

    return True

def calculate_file_hash(file_path, chunk_size=65536):
    """Calcula el hash MD5 de un archivo por bloques para optimizar el uso de RAM."""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def find_duplicate_files(target_dir, status_callback=None):
    """
    Escanea un directorio buscando duplicados exactos mediante 2 fases:
    1. Agrupa por tamaño exacto de archivo.
    2. Calcula hash MD5 únicamente a los archivos que comparten tamaño.
    """
    size_groups = {}
    
    # Fase 1: Agrupar por peso
    for root, _, files in os.walk(target_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                size = os.path.getsize(file_path)
                if size > 0:  # Ignorar archivos vacíos
                    size_groups.setdefault(size, []).append(file_path)
            except Exception:
                continue

    potential_duplicates = {size: paths for size, paths in size_groups.items() if len(paths) > 1}
    
    duplicates_by_hash = {}
    total_groups = len(potential_duplicates)
    processed_groups = 0

    # Fase 2: Comprobación de huella MD5
    for size, paths in potential_duplicates.items():
        processed_groups += 1
        if status_callback:
            status_callback(f"Analizando coincidencias ({processed_groups}/{total_groups})...")
            
        for path in paths:
            file_hash = calculate_file_hash(path)
            if file_hash:
                duplicates_by_hash.setdefault((file_hash, size), []).append(path)

    # Retorna solo grupos con 2 o más copias idénticas
    return {key: paths for key, paths in duplicates_by_hash.items() if len(paths) > 1}

def delete_duplicate_file(file_path):
    """Elimina un archivo duplicado seleccionado."""
    try:
        os.remove(file_path)
        return True
    except Exception:
        return False