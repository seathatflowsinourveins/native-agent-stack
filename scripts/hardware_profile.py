#!/usr/bin/env python3
"""Measure the current host and recommend hardware-dependent layer tiers.

Stdlib only. Read-only: this script never installs, starts, or configures
anything; it inspects /proc, sysctl, and (optionally) nvidia-smi output and
emits a JSON report. Tier thresholds come from the declarative
adoption/hardware-profiles.json so the arithmetic used for measured hosts and
projected/labelled hosts stays in one place.

Covers, per docs/native-token-workflow.md and AGENTS.md:
  - workflow concurrency cap: agent-lab's min(16, CPUs - 2) rule
    (CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS sizing).
  - local generation model tier, by GPU VRAM (Linux/WSL with an NVIDIA GPU)
    or unified memory (macOS Apple Silicon).
  - embedding / semantic-RAG fit (SocratiCode, Qdrant, vLLM) at this host's
    memory tier.
  - ecosystem-bounded-run memory limits (the guarded heavy-job wrapper).

Evidence class: native_proven for values this script itself measures on the
host it runs on (cores, /proc/meminfo, nvidia-smi, sysctl); source_review /
synthetic for anything read from a config file it did not generate (e.g. a
.wslconfig memory value) or supplied via --profiles for hosts not present.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILES_PATH = ROOT / "adoption" / "hardware-profiles.json"


def _load_profiles(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_meminfo_total_kib(text: str) -> int | None:
    match = re.search(r"^MemTotal:\s+(\d+)\s*kB", text, re.MULTILINE)
    return int(match.group(1)) if match else None


def detect_wsl(release_text: str) -> bool:
    return "microsoft" in release_text.lower() or "wsl" in release_text.lower()


def _find_wslconfig() -> Path | None:
    """Best-effort, read-only search for the Windows-side .wslconfig.

    WSL exposes the Windows filesystem at /mnt/<drive>; USERPROFILE/WSLENV
    are not reliably forwarded, so this checks the conventional mount points
    without following symlinks outside them or invoking any Windows binary.
    """
    for drive in ("c", "C"):
        users_dir = Path(f"/mnt/{drive}/Users")
        if not users_dir.is_dir():
            continue
        try:
            entries = sorted(users_dir.iterdir())
        except OSError:
            continue
        for entry in entries:
            candidate = entry / ".wslconfig"
            if candidate.is_file():
                return candidate
    return None


def _parse_wslconfig_memory_gb(text: str) -> float | None:
    match = re.search(r"^\s*memory\s*=\s*([0-9.]+)\s*GB", text, re.IGNORECASE | re.MULTILINE)
    if match:
        return float(match.group(1))
    match = re.search(r"^\s*memory\s*=\s*([0-9.]+)\s*MB", text, re.IGNORECASE | re.MULTILINE)
    if match:
        return float(match.group(1)) / 1024.0
    return None


def _run(cmd: list[str]) -> str | None:
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    try:
        result = subprocess.run(
            [exe, *cmd[1:]], capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def detect_nvidia_gpu() -> dict | None:
    output = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if not output:
        return None
    line = output.strip().splitlines()[0] if output.strip() else ""
    if not line:
        return None
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 2:
        return None
    name, mem_mib = parts[0], parts[1]
    try:
        vram_mib = float(re.sub(r"[^0-9.]", "", mem_mib))
    except ValueError:
        return None
    return {"name": name, "vram_gb": round(vram_mib / 1024.0, 1), "evidence_class": "native_proven"}


def measure_linux(profiles: dict) -> dict:
    cores = os.cpu_count() or 1
    meminfo_path = Path("/proc/meminfo")
    ram_gb = None
    if meminfo_path.is_file():
        kib = _read_meminfo_total_kib(meminfo_path.read_text(encoding="utf-8"))
        if kib is not None:
            ram_gb = round(kib / (1024.0 * 1024.0), 1)

    version_text = ""
    version_path = Path("/proc/version")
    if version_path.is_file():
        version_text = version_path.read_text(encoding="utf-8")
    is_wsl = detect_wsl(version_text) or detect_wsl(platform.release())

    wsl_config_memory_gb = None
    wsl_config_source = None
    if is_wsl:
        wslconfig = _find_wslconfig()
        if wslconfig is not None:
            try:
                text = wslconfig.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            wsl_config_memory_gb = _parse_wslconfig_memory_gb(text)
            wsl_config_source = str(wslconfig)

    gpu = detect_nvidia_gpu()

    effective_ram_gb = wsl_config_memory_gb if (is_wsl and wsl_config_memory_gb) else ram_gb

    return {
        "platform": "wsl" if is_wsl else "linux",
        "cores": cores,
        "ram_gb_proc_meminfo": ram_gb,
        "is_wsl": is_wsl,
        "wslconfig_memory_gb": wsl_config_memory_gb,
        "wslconfig_source": wsl_config_source,
        "effective_ram_gb": effective_ram_gb,
        "gpu": gpu,
        "evidence_class": "native_proven",
    }


def measure_macos(profiles: dict) -> dict:
    ncpu = _run(["sysctl", "-n", "hw.ncpu"])
    memsize = _run(["sysctl", "-n", "hw.memsize"])
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    cores = int(ncpu.strip()) if ncpu and ncpu.strip().isdigit() else (os.cpu_count() or 1)
    ram_gb = None
    if memsize and memsize.strip().isdigit():
        ram_gb = round(int(memsize.strip()) / (1024.0 ** 3), 1)
    is_arm64 = platform.machine() in ("arm64", "aarch64")

    return {
        "platform": "macos",
        "cores": cores,
        "effective_ram_gb": ram_gb,
        "cpu_brand": brand.strip() if brand else None,
        "arm64": is_arm64,
        "unified_memory_gb": ram_gb if is_arm64 else None,
        "evidence_class": "native_proven",
    }


def _pick_tier(tiers: list[dict], value: float | None, key: str) -> dict | None:
    """Pick the highest tier whose min_<key> threshold value satisfies."""
    if value is None:
        return None
    eligible = [t for t in tiers if value >= t.get(f"min_{key}", 0)]
    if not eligible:
        return None
    return max(eligible, key=lambda t: t.get(f"min_{key}", 0))


def recommend(measured: dict, profiles: dict) -> dict:
    cores = measured.get("cores") or 1
    concurrency_rule = profiles["layers"]["workflow_concurrency"]
    cap = concurrency_rule["cap_default"]
    concurrency = min(cap, max(1, cores - concurrency_rule["reserved_cores"]))

    ram_gb = measured.get("effective_ram_gb")
    vram_gb = None
    gpu = measured.get("gpu")
    if gpu:
        vram_gb = gpu.get("vram_gb")
    elif measured.get("unified_memory_gb") is not None:
        vram_gb = measured.get("unified_memory_gb")

    gen_tiers = profiles["layers"]["local_generation_model"]["tiers"]
    gen_tier = _pick_tier(gen_tiers, vram_gb, "vram_gb")

    rag_tiers = profiles["layers"]["embedding_semantic_rag"]["tiers"]
    rag_tier = _pick_tier(rag_tiers, ram_gb, "ram_gb")

    bounded_run_rule = profiles["layers"]["ecosystem_bounded_run"]
    bounded_run_mem_gb = None
    if ram_gb is not None:
        bounded_run_mem_gb = round(
            max(bounded_run_rule["floor_gb"], ram_gb * bounded_run_rule["fraction"]), 1
        )
        bounded_run_mem_gb = min(bounded_run_mem_gb, bounded_run_rule["ceiling_gb"])

    return {
        "workflow_concurrency_cap": concurrency,
        "local_generation_model_tier": gen_tier["name"] if gen_tier else "cpu-only",
        "embedding_semantic_rag_tier": rag_tier["name"] if rag_tier else "unsupported",
        "ecosystem_bounded_run_memory_gb": bounded_run_mem_gb,
    }


def build_report(profiles: dict) -> dict:
    system = platform.system()
    if system == "Darwin":
        measured = measure_macos(profiles)
    elif system == "Linux":
        measured = measure_linux(profiles)
    else:
        measured = {
            "platform": system.lower(),
            "cores": os.cpu_count() or 1,
            "effective_ram_gb": None,
            "evidence_class": "native_proven",
        }
    recommendation = recommend(measured, profiles)
    return {
        "schema": "hardware-profile-report-v1",
        "profiles_source": profiles.get("$schema_id", "adoption/hardware-profiles.json"),
        "measured": measured,
        "recommended": recommendation,
        "limits": [
            "Presence/threshold measurement only; no model, service, or GPU workload is actually run.",
            "nvidia-smi absence yields gpu=null even when a GPU is present but the driver/tool is unavailable.",
            ".wslconfig detection is a best-effort read of /mnt/<drive>/Users/*/.wslconfig; a non-default "
            "Windows user profile path or drive letter is not searched.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES_PATH,
                         help="Path to the declarative hardware-profiles.json")
    parser.add_argument("--out", type=Path, default=None, help="Write JSON here instead of stdout")
    args = parser.parse_args(argv)

    profiles = _load_profiles(args.profiles)
    report = build_report(profiles)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
