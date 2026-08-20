import json
import platform
import subprocess


# ============================================================
# CONFIGURACIÓN
# ============================================================

IS_WINDOWS = platform.system() == "Windows"


# ============================================================
# UTILIDADES
# ============================================================

def _safe_int(value, default=None):
    """
    Convierte un valor a entero de forma segura.
    """

    if value is None:
        return default

    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_float(value, default=None):
    """
    Convierte un valor a float de forma segura.
    """

    if value is None:
        return default

    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _normalize_value(value):
    """
    Normaliza valores provenientes de PowerShell.
    """

    if value is None:
        return None

    if isinstance(value, str):

        value = value.strip()

        if value == "":
            return None

        # Intentar convertir números
        try:
            if "." in value:
                return float(value)

            return int(value)

        except ValueError:
            return value

    return value


# ============================================================
# EJECUTAR POWERSHELL
# ============================================================

def _run_powershell(script):
    """
    Ejecuta PowerShell y devuelve stdout.

    Se utiliza powershell.exe porque CorePulse está pensado
    principalmente para Windows.
    """

    if not IS_WINDOWS:
        return None

    try:

        result = subprocess.run(

            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],

            capture_output=True,

            text=True,

            encoding="utf-8",

            errors="replace",

            timeout=15
        )

        if result.returncode != 0:

            print(
                "[STORAGE WARNING] PowerShell devolvió "
                f"código {result.returncode}"
            )

            if result.stderr:
                print(
                    f"[STORAGE WARNING] {result.stderr.strip()}"
                )

            return None

        return result.stdout.strip()

    except subprocess.TimeoutExpired:

        print(
            "[STORAGE ERROR] PowerShell tardó "
            "demasiado en responder."
        )

        return None

    except Exception as e:

        print(
            f"[STORAGE ERROR] Error ejecutando "
            f"PowerShell: {e}"
        )

        return None


# ============================================================
# OBTENER DATOS REALES DE STORAGE
# ============================================================

def get_windows_storage_health():
    """
    Obtiene información real de salud de los dispositivos
    de almacenamiento utilizando:

        Get-PhysicalDisk
        Get-StorageReliabilityCounter

    Devuelve una lista de diccionarios.
    """

    if not IS_WINDOWS:

        return []

    script = r"""
$ErrorActionPreference = 'SilentlyContinue'

$result = @()

$physicalDisks = Get-PhysicalDisk

foreach ($disk in $physicalDisks) {

    $counter = $null

    try {
        $counter = Get-StorageReliabilityCounter -PhysicalDisk $disk
    }
    catch {
        $counter = $null
    }

    $result += [PSCustomObject]@{

        DeviceId = $disk.DeviceId

        FriendlyName = $disk.FriendlyName

        Model = $disk.Model

        SerialNumber = $disk.SerialNumber

        MediaType = [string]$disk.MediaType

        BusType = [string]$disk.BusType

        OperationalStatus = [string]$disk.OperationalStatus

        HealthStatus = [string]$disk.HealthStatus

        Size = $disk.Size

        Temperature = if ($counter) {
            $counter.Temperature
        }
        else {
            $null
        }

        TemperatureMax = if ($counter) {
            $counter.TemperatureMax
        }
        else {
            $null
        }

        Wear = if ($counter) {
            $counter.Wear
        }
        else {
            $null
        }

        PowerOnHours = if ($counter) {
            $counter.PowerOnHours
        }
        else {
            $null
        }

        ReadErrorsCorrected = if ($counter) {
            $counter.ReadErrorsCorrected
        }
        else {
            $null
        }

        ReadErrorsTotal = if ($counter) {
            $counter.ReadErrorsTotal
        }
        else {
            $null
        }

        ReadErrorsUncorrected = if ($counter) {
            $counter.ReadErrorsUncorrected
        }
        else {
            $null
        }

        WriteErrorsCorrected = if ($counter) {
            $counter.WriteErrorsCorrected
        }
        else {
            $null
        }

        WriteErrorsTotal = if ($counter) {
            $counter.WriteErrorsTotal
        }
        else {
            $null
        }

        WriteErrorsUncorrected = if ($counter) {
            $counter.WriteErrorsUncorrected
        }
        else {
            $null
        }

        StartStopCycleCount = if ($counter) {
            $counter.StartStopCycleCount
        }
        else {
            $null
        }

        LoadUnloadCycleCount = if ($counter) {
            $counter.LoadUnloadCycleCount
        }
        else {
            $null
        }
    }
}

$result | ConvertTo-Json -Depth 5 -Compress
"""

    output = _run_powershell(script)

    if not output:
        return []

    try:

        data = json.loads(output)

    except json.JSONDecodeError as e:

        print(
            "[STORAGE ERROR] No se pudo interpretar "
            f"la respuesta de PowerShell: {e}"
        )

        return []

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return []

    normalized = []

    for item in data:

        if not isinstance(item, dict):
            continue

        normalized.append({
            key: _normalize_value(value)
            for key, value in item.items()
        })

    return normalized


# ============================================================
# CALCULAR SALUD
# ============================================================

def calculate_storage_health(data):
    """
    Calcula una representación normalizada del estado
    de la unidad.

    IMPORTANTE:
    No utiliza el espacio ocupado como indicador de salud.

    Si Windows proporciona Wear, se utiliza como indicador
    de desgaste.

    Si no existe Wear, se utiliza HealthStatus cuando está
    disponible.

    Si tampoco existe información suficiente, health=None.
    """

    if not isinstance(data, dict):
        return None

    health_status = str(
        data.get(
            "HealthStatus",
            ""
        ) or ""
    ).strip().lower()

    wear = _safe_float(
        data.get("Wear")
    )

    read_uncorrected = _safe_int(
        data.get("ReadErrorsUncorrected"),
        0
    )

    write_uncorrected = _safe_int(
        data.get("WriteErrorsUncorrected"),
        0
    )

    # --------------------------------------------------------
    # ERRORES NO CORREGIBLES
    # --------------------------------------------------------

    if (
        read_uncorrected is not None
        and read_uncorrected > 0
    ):

        return 0

    if (
        write_uncorrected is not None
        and write_uncorrected > 0
    ):

        return 0

    # --------------------------------------------------------
    # WEAR
    # --------------------------------------------------------

    if wear is not None:

        # Algunas unidades exponen Wear como porcentaje
        # utilizado. 0 = nuevo, 100 = completamente
        # desgastado.

        wear = max(
            0,
            min(
                100,
                wear
            )
        )

        return round(
            100 - wear,
            1
        )

    # --------------------------------------------------------
    # HEALTH STATUS
    # --------------------------------------------------------

    if health_status in (
        "healthy",
        "ok",
        "normal"
    ):

        return 100.0

    if health_status in (
        "warning",
        "degraded"
    ):

        return 60.0

    if health_status in (
        "unhealthy",
        "critical",
        "failed"
    ):

        return 0.0

    # --------------------------------------------------------
    # DESCONOCIDO
    # --------------------------------------------------------

    return None


# ============================================================
# NORMALIZAR PARA COREPulse
# ============================================================

def normalize_storage_data(raw_disks):
    """
    Convierte los datos de Windows a la estructura que
    utilizará CorePulse.
    """

    normalized = []

    for index, disk in enumerate(
        raw_disks,
        start=1
    ):

        if not isinstance(
            disk,
            dict
        ):
            continue

        health = calculate_storage_health(
            disk
        )

        temperature = _safe_float(
            disk.get("Temperature")
        )

        temperature_max = _safe_float(
            disk.get("TemperatureMax")
        )

        normalized.append({

            "index":
                index,

            "device_id":
                disk.get("DeviceId"),

            "model":
                disk.get("Model")
                or disk.get("FriendlyName")
                or "Unidad de almacenamiento",

            "friendly_name":
                disk.get("FriendlyName"),

            "serial":
                disk.get("SerialNumber"),

            "media_type":
                disk.get("MediaType"),

            "bus_type":
                disk.get("BusType"),

            "operational_status":
                disk.get("OperationalStatus"),

            "health_status":
                disk.get("HealthStatus"),

            "health":
                health,

            "temperature":
                temperature,

            "temperature_max":
                temperature_max,

            "wear":
                _safe_float(
                    disk.get("Wear")
                ),

            "power_on_hours":
                _safe_int(
                    disk.get("PowerOnHours")
                ),

            "read_errors_corrected":
                _safe_int(
                    disk.get(
                        "ReadErrorsCorrected"
                    ),
                    0
                ),

            "read_errors_total":
                _safe_int(
                    disk.get(
                        "ReadErrorsTotal"
                    ),
                    0
                ),

            "read_errors_uncorrected":
                _safe_int(
                    disk.get(
                        "ReadErrorsUncorrected"
                    ),
                    0
                ),

            "write_errors_corrected":
                _safe_int(
                    disk.get(
                        "WriteErrorsCorrected"
                    ),
                    0
                ),

            "write_errors_total":
                _safe_int(
                    disk.get(
                        "WriteErrorsTotal"
                    ),
                    0
                ),

            "write_errors_uncorrected":
                _safe_int(
                    disk.get(
                        "WriteErrorsUncorrected"
                    ),
                    0
                ),

            "start_stop_cycles":
                _safe_int(
                    disk.get(
                        "StartStopCycleCount"
                    )
                ),

            "load_unload_cycles":
                _safe_int(
                    disk.get(
                        "LoadUnloadCycleCount"
                    )
                ),

            # Estos campos pueden ser añadidos por
            # el módulo que obtiene espacio lógico.
            "used_gb":
                0,

            "total_gb":
                round(
                    (
                        _safe_int(
                            disk.get("Size"),
                            0
                        )
                        or 0
                    ) / (
                        1024 ** 3
                    ),
                    1
                ),

            "used_percent":
                0,
        })

    return normalized


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def get_storage_health():
    """
    Función pública utilizada por CorePulse.

    Devuelve los dispositivos de almacenamiento con sus
    métricas reales de confiabilidad.
    """

    if not IS_WINDOWS:

        print(
            "[STORAGE WARNING] La lectura nativa "
            "de StorageReliabilityCounter está "
            "implementada para Windows."
        )

        return []

    raw = get_windows_storage_health()

    if not raw:

        print(
            "[STORAGE WARNING] No se pudieron obtener "
            "datos de confiabilidad de las unidades."
        )

        return []

    normalized = normalize_storage_data(
        raw
    )

    print(
        f"[STORAGE INFO] Se detectaron "
        f"{len(normalized)} unidades."
    )

    for disk in normalized:

        print(
            "[STORAGE INFO] "
            f"{disk.get('model')} | "
            f"Salud: {disk.get('health')} | "
            f"Temperatura: {disk.get('temperature')}°C | "
            f"Wear: {disk.get('wear')}"
        )

    return normalized


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("COREPULSE - STORAGE HEALTH TEST")
    print("=" * 70)

    disks = get_storage_health()

    print()

    print(
        json.dumps(
            disks,
            indent=2,
            ensure_ascii=False
        )
    )
