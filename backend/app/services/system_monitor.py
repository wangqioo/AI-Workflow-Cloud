"""System monitoring service.

Ported from v0.7.5 system_monitor_server.py (port 8085).
Cloud mode: reports server stats. Edge mode: tegrastats/psutil.
"""

from __future__ import annotations

import os
import platform
import time


def _read_proc_stat() -> dict:
    """Read CPU stats from /proc/stat (Linux only)."""
    try:
        with open("/proc/stat") as f:
            lines = f.readlines()
        cpu_line = lines[0].split()
        # user, nice, system, idle, iowait, irq, softirq, steal
        vals = [int(v) for v in cpu_line[1:8]]
        total = sum(vals)
        idle = vals[3] + vals[4]
        return {"total": total, "idle": idle, "usage_pct": round((1 - idle / max(total, 1)) * 100, 1)}
    except Exception:
        return {"total": 0, "idle": 0, "usage_pct": 0}


def _read_meminfo() -> dict:
    """Read memory stats from /proc/meminfo (Linux only)."""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])

        total_kb = info.get("MemTotal", 0)
        avail_kb = info.get("MemAvailable", info.get("MemFree", 0))
        used_kb = total_kb - avail_kb

        return {
            "total_mb": round(total_kb / 1024, 1),
            "used_mb": round(used_kb / 1024, 1),
            "available_mb": round(avail_kb / 1024, 1),
            "percent": round(used_kb / max(total_kb, 1) * 100, 1),
        }
    except Exception:
        return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}


def _read_disk() -> dict:
    """Read disk usage via os.statvfs."""
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        used = total - free
        return {
            "total_gb": round(total / 1024**3, 1),
            "used_gb": round(used / 1024**3, 1),
            "free_gb": round(free / 1024**3, 1),
            "percent": round(used / max(total, 1) * 100, 1),
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}


def _read_uptime() -> float:
    """Read system uptime in seconds."""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0


def _read_load() -> dict:
    """Read load average."""
    try:
        load1, load5, load15 = os.getloadavg()
        return {"1min": round(load1, 2), "5min": round(load5, 2), "15min": round(load15, 2)}
    except Exception:
        return {"1min": 0, "5min": 0, "15min": 0}


def _read_temperature() -> dict:
    """Read thermal sensors (Linux)."""
    temps = {}
    try:
        thermal_dir = "/sys/class/thermal"
        if os.path.isdir(thermal_dir):
            for zone in os.listdir(thermal_dir):
                if zone.startswith("thermal_zone"):
                    temp_file = os.path.join(thermal_dir, zone, "temp")
                    type_file = os.path.join(thermal_dir, zone, "type")
                    if os.path.exists(temp_file):
                        with open(temp_file) as f:
                            temp_c = int(f.read().strip()) / 1000
                        name = zone
                        if os.path.exists(type_file):
                            with open(type_file) as f:
                                name = f.read().strip()
                        temps[name] = round(temp_c, 1)
    except Exception:
        pass
    return temps


async def get_system_status() -> dict:
    """Get comprehensive system status."""
    return {
        "cpu": _read_proc_stat(),
        "memory": _read_meminfo(),
        "disk": _read_disk(),
        "load": _read_load(),
        "temperature": _read_temperature(),
        "uptime_seconds": round(_read_uptime()),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "hostname": platform.node(),
        },
        "timestamp": time.time(),
    }


async def get_quick_stats() -> dict:
    """Quick summary for dashboard widgets."""
    cpu = _read_proc_stat()
    mem = _read_meminfo()
    disk = _read_disk()
    return {
        "cpu_percent": cpu["usage_pct"],
        "memory_percent": mem["percent"],
        "disk_percent": disk["percent"],
        "uptime": round(_read_uptime()),
    }
