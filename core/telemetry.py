import psutil
import pythoncom
import wmi

def get_system_chassis_and_bios():
    """
    Detecta el tipo de chasis (Laptop vs Torre), versión de BIOS y Placa Base.
    """
    is_laptop = False
    chassis_label = "Torre / Desktop"
    bios_info = "Desconocida"
    board_info = "Desconocida"

    try:
        pythoncom.CoInitialize()
        c = wmi.WMI()

        # 1. Informacion de BIOS
        bios_list = c.Win32_BIOS()
        if bios_list:
            b = bios_list[0]
            bios_vendor = b.Manufacturer.strip() if b.Manufacturer else ""
            bios_ver = b.SMBIOSBIOSVersion.strip() if b.SMBIOSBIOSVersion else ""
            bios_info = f"{bios_vendor} {bios_ver}".strip()

        # 2. Informacion de Placa Base
        board_list = c.Win32_BaseBoard()
        if board_list:
            mb = board_list[0]
            mb_vendor = mb.Manufacturer.strip() if mb.Manufacturer else ""
            mb_model = mb.Product.strip() if mb.Product else ""
            board_info = f"{mb_vendor} {mb_model}".strip()

        # 3. Detección Laptop vs Torre (PCSystemType, Batería y Chasis)
        cs_list = c.Win32_ComputerSystem()
        if cs_list:
            pc_type = getattr(cs_list[0], 'PCSystemType', 0)
            if pc_type in [2, 8]:  # 2 = Mobile, 8 = Laptop
                is_laptop = True

        if psutil.sensors_battery() is not None:
            is_laptop = True

        enclosure = c.Win32_SystemEnclosure()
        if enclosure and hasattr(enclosure[0], 'ChassisTypes'):
            chassis_types = enclosure[0].ChassisTypes or []
            if any(t in chassis_types for t in [8, 9, 10, 14, 30, 31, 32]):
                is_laptop = True

        if is_laptop:
            chassis_label = "Laptop / Notebook"

    except Exception:
        pass

    return is_laptop, chassis_label, bios_info, board_info


def get_hardware_names():
    cpu_name = "Procesador"
    gpu_name = "Gráfica"
    try:
        pythoncom.CoInitialize()
        w = wmi.WMI()

        cpus = w.Win32_Processor()
        if cpus:
            cpu_name = cpus[0].Name.strip()

        gpus = w.Win32_VideoController()
        if gpus:
            gpu_list = [g.Name.strip() for g in gpus if g.Name]
            nvidia_gpus = [g for g in gpu_list if "nvidia" in g.lower()]
            amd_gpus = [g for g in gpu_list if "radeon" in g.lower() or "amd" in g.lower()]

            if nvidia_gpus:
                gpu_name = nvidia_gpus[0]
            elif amd_gpus:
                gpu_name = amd_gpus[0]
            elif gpu_list:
                gpu_name = gpu_list[0]
    except Exception:
        pass
    return cpu_name, gpu_name


CPU_MODEL_NAME, GPU_MODEL_NAME = get_hardware_names()
LAST_VALID_GPU_TEMP = 38.0


def get_system_telemetry():
    global LAST_VALID_GPU_TEMP

    cpu_usage = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    cpu_temp = 45.0
    gpu_temp = LAST_VALID_GPU_TEMP
    gpu_usage = 0.0

    try:
        pythoncom.CoInitialize()
        w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
        sensors = w.Sensor()

        for s in sensors:
            if s.SensorType == 'Temperature':
                if 'cpu' in s.Name.lower() or 'core' in s.Name.lower():
                    if s.Value and s.Value > 0:
                        cpu_temp = round(float(s.Value), 1)
                elif 'gpu' in s.Name.lower() or 'nvidia' in s.Name.lower():
                    if s.Value and s.Value > 0:
                        gpu_temp = round(float(s.Value), 1)
                        LAST_VALID_GPU_TEMP = gpu_temp

            elif s.SensorType == 'Load' and ('gpu' in s.Name.lower() or 'nvidia' in s.Name.lower()):
                if s.Value is not None:
                    gpu_usage = round(float(s.Value), 1)
    except Exception:
        pass

    is_laptop, chassis_label, bios_info, board_info = get_system_chassis_and_bios()

    # Si en el nombre del GPU/CPU ya figura Laptop/Mobile, forzar flag
    if "laptop" in GPU_MODEL_NAME.lower() or "mobile" in CPU_MODEL_NAME.lower():
        is_laptop = True
        chassis_label = "Laptop / Notebook"

    return {
        "cpu_usage": round(cpu_usage, 1),
        "cpu_temp": cpu_temp,
        "cpu_name": CPU_MODEL_NAME,
        "ram_usage": round(ram.percent, 1),
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "gpu_usage": gpu_usage,
        "gpu_temp": gpu_temp,
        "gpu_name": GPU_MODEL_NAME,
        "is_laptop": is_laptop,
        "chassis_label": chassis_label,
        "bios_info": bios_info,
        "board_info": board_info
    }


def get_all_disks_data():
    """
    Corrige la asignación de letras y uso real de almacenamiento mediante
    asociación robusta de particiones psutil + WMI S.M.A.R.T.
    """
    disks = []
    try:
        pythoncom.CoInitialize()
        c = wmi.WMI()

        # 1. Mapear uso de particiones lógicas activas
        logic_partitions = {}
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                letter = part.mountpoint.replace("\\", "").replace("/", "")
                logic_partitions[letter] = {
                    "total": usage.total,
                    "used": usage.used,
                    "percent": usage.percent
                }
            except Exception:
                pass

        # 2. Mapear unidades físicas mediante WMI
        partitions_map = {}
        try:
            for dp in c.Win32_DiskDriveToDiskPartition():
                drive_ref = dp.Antecedent.split("=")[-1].replace('"', '').strip()
                part_ref = dp.Dependent.split("=")[-1].replace('"', '').strip()

                for lp in c.Win32_LogicalDiskToPartition():
                    lp_part_ref = lp.Antecedent.split("=")[-1].replace('"', '').strip()
                    if part_ref == lp_part_ref:
                        log_drive = lp.Dependent.split("=")[-1].replace('"', '').strip()
                        partitions_map.setdefault(drive_ref, []).append(log_drive)
        except Exception:
            pass

        # 3. Mapear salud S.M.A.R.T. física
        smart_failures = {}
        try:
            wmi_smart = wmi.WMI(namespace="root\\wmi")
            for status in wmi_smart.MSStorageDriver_FailurePredictStatus():
                smart_failures[status.InstanceName.strip().upper()] = status.PredictFailure
        except Exception:
            pass

        for i, disk in enumerate(c.Win32_DiskDrive()):
            disk_id = disk.DeviceID.replace('\\\\.\\', '').strip()
            
            # Extraer letras asignadas o buscar por índice
            assigned = partitions_map.get(disk.DeviceID, [])
            if not assigned:
                assigned = partitions_map.get(disk_id, [])

            # Si no se encuentra mapeo por ID estricto, asignar letras de respaldo según disponibilidad
            if not assigned and logic_partitions:
                keys = list(logic_partitions.keys())
                if i < len(keys):
                    assigned = [keys[i]]

            mount_str = ", ".join(assigned) if assigned else "Partición de Sistema"

            total_bytes = int(disk.Size) if disk.Size else 0
            used_bytes = 0

            for letter in assigned:
                clean_let = letter.replace(":", "") + ":"
                if clean_let in logic_partitions:
                    used_bytes += logic_partitions[clean_let]["used"]

            if total_bytes == 0 and assigned:
                for letter in assigned:
                    clean_let = letter.replace(":", "") + ":"
                    if clean_let in logic_partitions:
                        total_bytes += logic_partitions[clean_let]["total"]

            total_gb = round(total_bytes / (1024**3), 2)
            used_gb = round(used_bytes / (1024**3), 2)
            used_percent = round((used_bytes / total_bytes * 100), 1) if total_bytes > 0 else 0.0

            # Evaluación de Salud S.M.A.R.T.
            health_score = 100
            model_upper = (disk.Model or "").upper()
            
            # Buscar concordancia de fallo S.M.A.R.T.
            is_failing = False
            for p_name, predict_fail in smart_failures.items():
                if disk.PNPDeviceID and disk.PNPDeviceID.upper() in p_name:
                    if predict_fail:
                        is_failing = True

            disk_status = str(disk.Status).upper() if disk.Status else "OK"
            if is_failing or disk_status in ["ERROR", "PRED FAIL"]:
                health_score = 30
            elif disk_status == "DEGRADED":
                health_score = 65

            disks.append({
                "index": i,
                "model": disk.Model.strip() if disk.Model else f"Disco Físico {i}",
                "mount_points": mount_str,
                "total_gb": total_gb,
                "used_percent": used_percent,
                "used_gb": used_gb,
                "used_mb": int(used_bytes / (1024**2)),
                "used_kb": int(used_bytes / 1024),
                "health": health_score
            })
    except Exception:
        pass

    # Respaldo con psutil si WMI falla
    if not disks:
        try:
            for i, p in enumerate(psutil.disk_partitions(all=False)):
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    disks.append({
                        "index": i,
                        "model": "Unidad de Almacenamiento Principal",
                        "mount_points": p.mountpoint.replace("\\", ""),
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_percent": round(usage.percent, 1),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "used_mb": int(usage.used / (1024**2)),
                        "used_kb": int(usage.used / 1024),
                        "health": 100
                    })
                except Exception:
                    pass
        except Exception:
            pass

    return disks


def calculate_preliminary_score(cpu_u, ram_u, cpu_t, gpu_t, disks):
    score = 100.0
    if cpu_u > 85: score -= 15
    if ram_u > 90: score -= 15
    if cpu_t > 80: score -= 10
    if gpu_t > 85: score -= 10

    for d in disks:
        if d["health"] < 100:
            score -= (100 - d["health"]) * 0.2
        if d["used_percent"] > 90:
            score -= 10

    return max(0.0, round(score, 1))