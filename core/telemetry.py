import os
import psutil
import platform
import subprocess
import json

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    try:
        import pythoncom
        import wmi
    except ImportError:
        pass

LAST_VALID_GPU_TEMP = 38.0


def get_system_chassis_and_bios():
    is_laptop = False
    chassis_label = "Torre / Desktop"
    bios_info = "Desconocida"
    board_info = "Desconocida"

    if IS_WINDOWS:
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()

            bios_list = c.Win32_BIOS()
            if bios_list:
                b = bios_list[0]
                bios_vendor = b.Manufacturer.strip() if b.Manufacturer else ""
                bios_ver = b.SMBIOSBIOSVersion.strip() if b.SMBIOSBIOSVersion else ""
                bios_info = f"{bios_vendor} {bios_ver}".strip()

            board_list = c.Win32_BaseBoard()
            if board_list:
                mb = board_list[0]
                mb_vendor = mb.Manufacturer.strip() if mb.Manufacturer else ""
                mb_model = mb.Product.strip() if mb.Product else ""
                board_info = f"{mb_vendor} {mb_model}".strip()

            cs_list = c.Win32_ComputerSystem()
            if cs_list:
                pc_type = getattr(cs_list[0], 'PCSystemType', 0)
                if pc_type in [2, 8]:
                    is_laptop = True

            if psutil.sensors_battery() is not None:
                is_laptop = True

            enclosure = c.Win32_SystemEnclosure()
            if enclosure and hasattr(enclosure[0], 'ChassisTypes'):
                chassis_types = enclosure[0].ChassisTypes or []
                if any(t in chassis_types for t in [8, 9, 10, 14, 30, 31, 32]):
                    is_laptop = True
        except Exception:
            pass
    else:
        try:
            if psutil.sensors_battery() is not None:
                is_laptop = True

            if os.path.exists("/sys/class/dmi/id/bios_version"):
                with open("/sys/class/dmi/id/bios_version", "r") as f:
                    bios_info = f.read().strip()

            if os.path.exists("/sys/class/dmi/id/board_name"):
                with open("/sys/class/dmi/id/board_name", "r") as f:
                    board_info = f.read().strip()

            if os.path.exists("/sys/class/dmi/id/chassis_type"):
                with open("/sys/class/dmi/id/chassis_type", "r") as f:
                    ctype = f.read().strip()
                    if ctype in ["8", "9", "10", "14", "30", "31", "32"]:
                        is_laptop = True
        except Exception:
            pass

    if is_laptop:
        chassis_label = "Laptop / Notebook"

    return is_laptop, chassis_label, bios_info, board_info


def get_hardware_names():
    cpu_name = "Procesador"
    gpu_name = "Gráfica"

    if IS_WINDOWS:
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
    else:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_name = line.split(":")[1].strip()
                        break
        except Exception:
            pass

        try:
            res = subprocess.check_output("lspci | grep -E 'VGA|3D'", shell=True).decode("utf-8")
            if "NVIDIA" in res:
                gpu_name = "NVIDIA GPU (" + res.split(":")[-1].strip() + ")"
            elif "AMD" in res or "Radeon" in res:
                gpu_name = "AMD Radeon GPU (" + res.split(":")[-1].strip() + ")"
            elif res.strip():
                gpu_name = res.split(":")[-1].strip()
        except Exception:
            pass

    return cpu_name, gpu_name


CPU_MODEL_NAME, GPU_MODEL_NAME = get_hardware_names()


def get_system_telemetry():
    global LAST_VALID_GPU_TEMP

    cpu_usage = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    cpu_temp = 45.0
    gpu_temp = LAST_VALID_GPU_TEMP
    gpu_usage = 0.0

    if IS_WINDOWS:
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
    else:
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for sensor_name in ['coretemp', 'k10temp', 'zenpower', 'cpu_thermal']:
                    if sensor_name in temps and len(temps[sensor_name]) > 0:
                        cpu_temp = round(temps[sensor_name][0].current, 1)
                        break

                for sensor_name in ['amdgpu', 'nvidia', 'nouveau']:
                    if sensor_name in temps and len(temps[sensor_name]) > 0:
                        gpu_temp = round(temps[sensor_name][0].current, 1)
                        LAST_VALID_GPU_TEMP = gpu_temp
                        break
        except Exception:
            pass

        try:
            res = subprocess.check_output(
                "nvidia-smi --query-gpu=utilization.gpu,temperature.gpu --format=csv,noheader,nounits",
                shell=True, timeout=1
            ).decode("utf-8").strip()
            if res:
                parts = res.split(",")
                gpu_usage = float(parts[0].strip())
                gpu_temp = float(parts[1].strip())
                LAST_VALID_GPU_TEMP = gpu_temp
        except Exception:
            pass

    is_laptop, chassis_label, bios_info, board_info = get_system_chassis_and_bios()

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


def _get_linux_smart_health(device_path):
    """Consulta de salud real SMART en Linux"""
    try:
        cmd = f"smartctl -H -j {device_path}"
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8')
        data = json.loads(res)
        
        # Si la prueba pasó
        if data.get("smart_status", {}).get("passed", True):
            # Buscar porcentaje de vida útil en NVMe si existe
            nvme_percentage = data.get("nvme_smart_health_information_log", {}).get("percentage_used")
            if nvme_percentage is not None:
                return max(0, 100 - int(nvme_percentage))
            return 100
        else:
            return 35
    except Exception:
        pass
    return 100


def get_all_disks_data():
    disks = []

    if IS_WINDOWS:
        try:
            pythoncom.CoInitialize()
            c = wmi.WMI()

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

            smart_failures = {}
            try:
                wmi_smart = wmi.WMI(namespace="root\\wmi")
                for status in wmi_smart.MSStorageDriver_FailurePredictStatus():
                    smart_failures[status.InstanceName.strip().upper()] = status.PredictFailure
            except Exception:
                pass

            for i, disk in enumerate(c.Win32_DiskDrive()):
                disk_id = disk.DeviceID.replace('\\\\.\\', '').strip()
                assigned = partitions_map.get(disk.DeviceID, [])
                if not assigned:
                    assigned = partitions_map.get(disk_id, [])

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

                health_score = 100
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

    else:
        # LÓGICA DINÁMICA LINUX (Detecta solo discos físicos dinámicamente)
        try:
            cmd = "lsblk -J -b -o NAME,MODEL,SIZE,TYPE,MOUNTPOINT,FSTYPE"
            res = subprocess.check_output(cmd, shell=True).decode('utf-8')
            blk_data = json.loads(res)

            idx = 0
            for dev in blk_data.get("blockdevices", []):
                # Filtrar solo DISCOS FISICOS (ignora loop, zram, etc)
                if dev.get("type") == "disk":
                    dev_name = dev.get("name")
                    dev_path = f"/dev/{dev_name}"
                    model = dev.get("model") or f"Disco Físico (/dev/{dev_name})"
                    total_bytes = int(dev.get("size", 0))
                    total_gb = round(total_bytes / (1024**3), 2)

                    # Calcular uso agregando particiones montadas de este disco
                    used_bytes = 0
                    mounts = []

                    def parse_children(children):
                        nonlocal used_bytes, mounts
                        for child in children:
                            mp = child.get("mountpoint")
                            if mp:
                                mounts.append(mp)
                                try:
                                    usage = psutil.disk_usage(mp)
                                    used_bytes += usage.used
                                except Exception:
                                    pass
                            if "children" in child:
                                parse_children(child["children"])

                    if "children" in dev:
                        parse_children(dev["children"])

                    used_gb = round(used_bytes / (1024**3), 2)
                    used_percent = round((used_bytes / total_bytes * 100), 1) if total_bytes > 0 else 0.0
                    mount_str = ", ".join(mounts) if mounts else "Sin montar / SWAP"

                    # Obtener Salud SMART Real
                    health_score = _get_linux_smart_health(dev_path)

                    disks.append({
                        "index": idx,
                        "model": model.strip(),
                        "mount_points": mount_str,
                        "total_gb": total_gb,
                        "used_percent": used_percent,
                        "used_gb": used_gb,
                        "used_mb": int(used_bytes / (1024**2)),
                        "used_kb": int(used_bytes / 1024),
                        "health": health_score
                    })
                    idx += 1
        except Exception:
            pass

    # Respaldo en caso de fallo crítico
    if not disks:
        try:
            for i, p in enumerate(psutil.disk_partitions(all=False)):
                if not p.mountpoint or 'loop' in p.device or p.fstype == '':
                    continue
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    disks.append({
                        "index": i,
                        "model": f"Disco ({p.device})",
                        "mount_points": p.mountpoint,
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