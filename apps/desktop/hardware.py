import csv
import io
import json
import os
import platform
import re
import subprocess
import time
from collections import deque
from datetime import datetime, timezone

import psutil


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nvidia_metrics():
    if platform.system() != "Windows":
        return {}
    query = (
        "name,temperature.gpu,utilization.gpu,memory.used,memory.total,"
        "clocks.gr,fan.speed,power.draw,power.limit"
    )
    try:
        r = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2.5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0 or not r.stdout.strip():
            return {}
        row = next(csv.reader(io.StringIO(r.stdout.strip())))
        keys = ["name", "temperature_c", "utilization_percent", "memory_used_mb",
                "memory_total_mb", "clock_mhz", "fan_percent", "power_w", "power_limit_w"]
        data = {}
        for key, raw in zip(keys, row):
            value = raw.strip()
            data[key] = value if key == "name" else _num(value)
        # Never expose an obviously invalid power reading. A laptop GPU should
        # remain below its reported power limit; if the driver reports nonsense,
        # use None rather than displaying a false value.
        limit = data.get("power_limit_w")
        power = data.get("power_w")
        if power is not None and (power < 0 or (power > 250.0) or (limit and power > max(150.0, limit * 1.5))):
            data["power_w"] = None
            data["power_status"] = "invalid_driver_value"
        else:
            data["power_status"] = "valid" if power is not None else "unavailable"
        return {"gpu": data}
    except Exception:
        return {}


def _hardware_monitor_sensors():
    """Optional CPU/GPU temperature/fan sensors from LibreHardwareMonitor/OpenHardwareMonitor."""
    if platform.system() != "Windows":
        return {}
    ps = r'''$items=@(); $ns=@('root\LibreHardwareMonitor','root\OpenHardwareMonitor'); foreach($n in $ns){ try { $items=Get-CimInstance -Namespace $n -ClassName Sensor -ErrorAction Stop; if($items){ break } } catch {} }; $items | Where-Object { $_.SensorType -in @('Temperature','Fan','Clock','Load') } | Select-Object Name,SensorType,Value,Parent | ConvertTo-Json -Compress'''
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=3.5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0 or not r.stdout.strip():
            return {}
        raw = json.loads(r.stdout.strip())
        rows = raw if isinstance(raw, list) else [raw]
        result = {}
        temps = []
        fans = []
        for row in rows:
            name = str(row.get("Name") or "")
            kind = str(row.get("SensorType") or "")
            value = _num(row.get("Value"))
            if value is None:
                continue
            lname = name.lower()
            if kind.lower() == "temperature":
                temps.append((lname, value, name))
            elif kind.lower() == "fan":
                fans.append((lname, value, name))
        preferred_temp = [x for x in temps if any(k in x[0] for k in ("package", "cpu", "tdie", "tctl"))]
        if preferred_temp:
            result["cpu_temperature_c"] = round(preferred_temp[0][1], 1)
        elif temps:
            result["cpu_temperature_c"] = round(temps[0][1], 1)
        preferred_fan = [x for x in fans if any(k in x[0] for k in ("cpu", "processor"))]
        if preferred_fan:
            result["cpu_fan_rpm"] = round(preferred_fan[0][1], 0)
        elif fans:
            result["cpu_fan_rpm"] = round(fans[0][1], 0)
        return result
    except Exception:
        return {}


_prev_net = None
_prev_disk = None
_prev_sample_time = None


def _rate(now_value, previous_value, elapsed):
    if previous_value is None or elapsed <= 0:
        return None
    return max(0.0, (now_value - previous_value) / elapsed)


IDLE_PROCESS_NAMES = {"system idle process", "idle", "idle.exe"}
KERNEL_PROCESS_NAMES = {"system", "registry", "memory compression"}

def _top_processes(limit=6):
    """Return normalized process metadata only; never exposes command lines or paths.

    Windows/psutil process CPU can be expressed per logical core, so a multi-core
    process may exceed 100%. PatternSeeker normalizes it to whole-machine capacity
    and excludes Windows idle/kernel pseudo-processes from the ranking.
    """
    rows = []
    logical = max(1, psutil.cpu_count(logical=True) or 1)
    try:
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = proc.info
                pid = int(info.get("pid") or 0)
                name = (info.get("name") or "unknown")[:80]
                normalized_name = name.lower().strip()
                if pid in {0, 4} or normalized_name in IDLE_PROCESS_NAMES:
                    continue
                raw_cpu = max(0.0, float(info.get("cpu_percent") or 0))
                cpu_percent = min(100.0, raw_cpu / logical)
                mem = info.get("memory_info")
                rows.append({
                    "pid": pid,
                    "name": name,
                    "cpu_percent": round(cpu_percent, 1),
                    "memory_mb": round((mem.rss if mem else 0) / (1024 ** 2), 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError):
                continue
        rows.sort(key=lambda x: (x["cpu_percent"], x["memory_mb"]), reverse=True)
    except Exception:
        return []
    return rows[:limit]


def collect_system_metrics():
    global _prev_net, _prev_disk, _prev_sample_time

    sample_time = time.time()
    cpu_percent = psutil.cpu_percent(interval=None)
    freq = psutil.cpu_freq()
    vm = psutil.virtual_memory()
    disk_path = os.environ.get("SystemDrive", "C:") + "\\"
    disk = psutil.disk_usage(disk_path)
    battery = psutil.sensors_battery()
    net = psutil.net_io_counters()
    disk_io = psutil.disk_io_counters()
    proc = psutil.Process(os.getpid())
    elapsed = sample_time - _prev_sample_time if _prev_sample_time else None

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu": {
            "usage_percent": round(cpu_percent, 1),
            "clock_mhz": round(freq.current, 0) if freq else None,
            "min_clock_mhz": round(freq.min, 0) if freq and freq.min else None,
            "max_clock_mhz": round(freq.max, 0) if freq and freq.max else None,
            "cores_physical": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
        },
        "memory": {
            "usage_percent": round(vm.percent, 1),
            "used_gb": round(vm.used / (1024 ** 3), 2),
            "available_gb": round(vm.available / (1024 ** 3), 2),
            "total_gb": round(vm.total / (1024 ** 3), 2),
            "cached_gb": round(getattr(vm, "cached", 0) / (1024 ** 3), 2),
        },
        "disk": {
            "usage_percent": round(disk.percent, 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "read_mb_s": round(_rate(disk_io.read_bytes, _prev_disk[0] if _prev_disk else None, elapsed) / (1024 ** 2), 2) if disk_io and _rate(disk_io.read_bytes, _prev_disk[0] if _prev_disk else None, elapsed) is not None else None,
            "write_mb_s": round(_rate(disk_io.write_bytes, _prev_disk[1] if _prev_disk else None, elapsed) / (1024 ** 2), 2) if disk_io and _rate(disk_io.write_bytes, _prev_disk[1] if _prev_disk else None, elapsed) is not None else None,
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_received": net.bytes_recv,
            "sent_mb": round(net.bytes_sent / (1024 ** 2), 1),
            "received_mb": round(net.bytes_recv / (1024 ** 2), 1),
            "upload_mb_s": round(_rate(net.bytes_sent, _prev_net[0] if _prev_net else None, elapsed) / (1024 ** 2), 3) if _rate(net.bytes_sent, _prev_net[0] if _prev_net else None, elapsed) is not None else None,
            "download_mb_s": round(_rate(net.bytes_recv, _prev_net[1] if _prev_net else None, elapsed) / (1024 ** 2), 3) if _rate(net.bytes_recv, _prev_net[1] if _prev_net else None, elapsed) is not None else None,
        },
        "process": {
            "pid": proc.pid,
            "cpu_percent": round(proc.cpu_percent(interval=None), 1),
            "memory_mb": round(proc.memory_info().rss / (1024 ** 2), 1),
            "threads": proc.num_threads(),
        },
        "system": {
            "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
            "boot_time": datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc).isoformat(),
        },
        "top_processes": _top_processes(6),
    }
    if battery:
        metrics["battery"] = {"percent": round(battery.percent, 1), "plugged": bool(battery.power_plugged)}

    metrics.update(_nvidia_metrics())
    metrics.update(_hardware_monitor_sensors())
    if metrics.get("gpu") and metrics["gpu"].get("fan_percent") is None:
        metrics["gpu"]["fan_percent"] = None

    _prev_net = (net.bytes_sent, net.bytes_recv)
    _prev_disk = (disk_io.read_bytes, disk_io.write_bytes) if disk_io else None
    _prev_sample_time = sample_time
    return metrics
