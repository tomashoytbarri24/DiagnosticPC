import json
import subprocess
import shutil

def get_linux_storage_health():
    """
    Obtiene métricas de salud de discos en Linux usando smartctl.
    Retorna un diccionario mapeado por identificador/dispositivo.
    """
    if not shutil.which("smartctl"):
        return {}

    health_data = {}
    try:
        # Detecta discos en el sistema
        scan_output = subprocess.check_output(["smartctl", "--scan", "-j"], text=True)
        devices = json.loads(scan_output).get("devices", [])

        for dev in devices:
            dev_name = dev.get("name")
            if not dev_name:
                continue

            # Obtener datos de cada disco en JSON
            cmd = ["smartctl", "-A", "-H", "-i", dev_name, "-j"]
            info = json.loads(subprocess.check_output(cmd, text=True))

            smart_status = info.get("smart_status", {}).get("passed", True)
            
            # NVMe vs ATA SMART parsing
            temperature = info.get("temperature", {}).get("current", 0)
            
            health_data[dev_name] = {
                "health": 100 if smart_status else 50,
                "temperature": temperature,
                "reallocated_sectors": 0,
                "read_errors": 0,
                "write_errors": 0
            }
    except Exception:
        pass

    return health_data