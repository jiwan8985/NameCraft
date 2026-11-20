"""Read-only hardware assessment for installed Ollama models."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

GIB = 1024 ** 3


def _memory() -> tuple[int | None, int | None]:
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                    (name, ctypes.c_ulonglong)
                    for name in ("total", "available", "page", "page_available",
                                 "virtual", "virtual_available", "extended_available")
                ]

            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                return memory.total, memory.available
        elif platform.system() == "Darwin":
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                                    timeout=2, check=True)
            return int(result.stdout), None
        else:
            values = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, _, value = line.partition(":")
                if key in {"MemTotal", "MemAvailable"}:
                    values[key] = int(value.split()[0]) * 1024
            return values.get("MemTotal"), values.get("MemAvailable")
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None, None


def _gpus() -> list[dict]:
    executable = shutil.which("nvidia-smi")
    if not executable and os.name == "nt":
        candidate = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        return []
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        devices = []
        for line in result.stdout.splitlines():
            name, total, free = line.rsplit(",", 2)
            devices.append({"name": name.strip(), "total_bytes": int(total) * 1024 ** 2,
                            "available_bytes": int(free) * 1024 ** 2})
        return devices
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def hardware_snapshot() -> dict:
    total, available = _memory()
    return {"logical_cpus": os.cpu_count(), "ram_total_bytes": total,
            "ram_available_bytes": available, "gpus": _gpus()}


def recommend_installed(models: list[dict], hardware: dict) -> list[dict]:
    """Order candidates by estimated fit and suitability for natural-language writing."""
    free_vram = max((gpu["available_bytes"] for gpu in hardware["gpus"]), default=0)
    ram = hardware["ram_available_bytes"]
    if ram is None and hardware["ram_total_bytes"] is not None:
        ram = int(hardware["ram_total_bytes"] * .60)

    rows = []
    for model in models:
        name, size = model.get("name"), model.get("size")
        if not name or not model.get("can_generate") or model.get("is_remote") or not isinstance(size, int) or size <= 0:
            continue
        memory = size + max(GIB, size // 3)
        if memory <= free_vram:
            fit = "gpu"
        elif ram is None:
            fit = "unknown"
        else:
            fit = "ram" if memory <= ram else "tight"
        coding = any(word in name.lower().split(":")[0] for word in ("coder", "codellama", "starcoder", "granite-code"))
        rows.append({"name": name, "size_bytes": size, "estimated_memory_bytes": memory,
                     "fit": fit, "coding": coding})

    order = {"gpu": 0, "ram": 1, "unknown": 2, "tight": 3}
    return sorted(rows, key=lambda row: (order[row["fit"]], row["coding"], row["size_bytes"], row["name"]))
