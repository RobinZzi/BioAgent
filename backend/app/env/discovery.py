"""本地环境发现（Environment Discovery）。

流程：Connection Check → System Discovery → Runtime Discovery
      → Tool Discovery → Compute Discovery → Health Check

原则：任何单点探测失败不中断，标记 unknown 并继续；最终总 status 为
healthy / degraded，绝不抛异常。见 docs/TECHNICAL_DESIGN.md §4。
"""
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from .manifest import ComputeInfo, Manifest, RuntimeInfo, SystemInfo, ToolInfo

# conda 环境内可识别的生信工具（包名 → 规范 tool_id）
CONDA_TOOL_NAMES = {
    "scanpy": "scanpy",
    "anndata": "anndata",
    "leidenalg": "leidenalg",
    "scvi-tools": "scvi-tools",
    "scvi": "scvi-tools",
    "scrublet": "scrublet",
    "harmonypy": "harmonypy",
    "scanorama": "scanorama",
    "pandas": "pandas",
    "numpy": "numpy",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "h5py": "h5py",
    "seaborn": "seaborn",
}

# 系统级 CLI 工具（which 探测）
CLI_TOOLS = {
    "star": ("star", "bash"),
    "samtools": ("samtools", "bash"),
    "salmon": ("salmon", "bash"),
    "kallisto": ("kallisto", "bash"),
    "fastqc": ("fastqc", "bash"),
    "cutadapt": ("cutadapt", "bash"),
    "featureCounts": ("featureCounts", "bash"),
    "cellranger": ("cellranger", "bash"),
}

_SCHEDULERS = {"sbatch": "slurm", "qsub": "pbs"}


def _run(cmd: list[str], timeout: float = 20.0) -> tuple[bool, str]:
    """执行探测命令，永不抛异常。"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return True, r.stdout
        return False, (r.stderr or r.stdout)[:500]
    except FileNotFoundError:
        return False, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"timeout: {cmd[0]}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:300]


def _memory_gb() -> float | None:
    try:
        if sys.platform == "darwin":
            ok, out = _run(["sysctl", "-n", "hw.memsize"], 5)
            return round(int(out.strip()) / (1024**3), 1) if ok else None
        if sys.platform.startswith("linux"):
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / (1024**2), 1)
        return None
    except Exception:  # noqa: BLE001
        return None


def _gpu() -> str | None:
    if sys.platform.startswith("linux") and Path("/usr/bin/nvidia-smi").exists():
        ok, out = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], 5)
        if ok:
            return out.strip().splitlines()[0]
    return None


def _conda_envs() -> list[dict]:
    """返回 [{name, path}]，失败返回 []。"""
    ok, out = _run(["conda", "env", "list", "--json"], 30)
    if not ok:
        return []
    try:
        data = json.loads(out)
        envs = data.get("envs", [])
        return [{"name": os.path.basename(p) if p != data.get("root_prefix") else "base",
                 "path": p} for p in envs]
    except Exception:  # noqa: BLE001
        return []


def _conda_packages(env_name: str, timeout: float = 30.0) -> set[str]:
    ok, out = _run(["conda", "list", "-n", env_name, "--json"], timeout)
    if not ok:
        return set()
    try:
        pkgs = json.loads(out)
        return {p.get("name", "").lower() for p in pkgs}
    except Exception:  # noqa: BLE001
        return set()


def _which(name: str) -> str | None:
    ok, out = _run(["which", name], 5)
    return out.strip() if ok else None


def _python_version(path: str) -> str | None:
    ok, out = _run([path, "--version"], 10)
    if ok:
        m = re.search(r"Python (\S+)", out)
        return m.group(1) if m else None
    return None


def discover_local(timeout: float = 25.0) -> Manifest:
    """执行本地环境发现，返回 Manifest。"""
    manifest = Manifest(environment_id="env_local", environment_type="local")

    # ---- System Discovery ----
    manifest.system = SystemInfo(
        os=platform.system().lower(),
        arch=platform.machine(),
        cpu_cores=os.cpu_count(),
        memory_gb=_memory_gb(),
        gpu=_gpu(),
    )

    # ---- Compute Discovery ----
    compute_notes: list[str] = []
    scheduler = None
    for cmd, sched in _SCHEDULERS.items():
        if _which(cmd):
            scheduler = sched
            break
    if scheduler:
        compute_notes.append(f"detected scheduler: {scheduler}")
    manifest.compute = ComputeInfo(scheduler=scheduler, notes=compute_notes)

    # ---- Runtime Discovery ----
    python_path = _which("python3") or _which("python")
    if python_path:
        manifest.runtimes.append(RuntimeInfo(
            id="runtime_base", type="python", name="base-python",
            version=_python_version(python_path), path=python_path))

    r_path = _which("R")
    if r_path:
        ok, out = _run([r_path, "--version"], 10)
        ver = None
        if ok:
            m = re.search(r"version (\S+)", out)
            ver = m.group(1) if m else None
        manifest.runtimes.append(RuntimeInfo(
            id="runtime_R", type="r", name="R", version=ver, path=r_path))

    # conda 环境（限速：最多扫描 6 个环境）
    conda_envs = _conda_envs()[:6]
    if conda_envs:
        manifest.runtimes.append(RuntimeInfo(
            id="runtime_conda", type="conda", name="conda",
            version=None, path=_which("conda")))

    # ---- Tool Discovery（conda 包 + 系统 CLI + 项目内 venv）----
    for env in conda_envs:
        pkgs = _conda_packages(env["name"], timeout)
        runtime_id = f"conda:{env['name']}"
        for pkg, tool_id in CONDA_TOOL_NAMES.items():
            if pkg in pkgs and not any(t.tool_id == tool_id and t.runtime_id == runtime_id for t in manifest.tools):
                manifest.tools.append(ToolInfo(
                    tool_id=tool_id, runtime_id=runtime_id, version=None,
                    status="healthy", language="python"))
        manifest.runtimes.append(RuntimeInfo(
            id=runtime_id, type="conda", name=env["name"],
            version=None, path=env["path"]))

    # backend 目录下的 Python venv（如 .venv311，用 importlib.find_spec 探测工具）
    from ..config import BACKEND_DIR
    for vd in sorted(BACKEND_DIR.glob(".venv*")):
        py = vd / "bin" / "python"
        if not py.exists():
            continue
        runtime_id = f"venv:{vd.name}"
        ver = _python_version(str(py))
        manifest.runtimes.append(RuntimeInfo(
            id=runtime_id, type="venv", name=vd.name, version=ver, path=str(py)))
        probe = ("import importlib.util,sys,json;"
                 "print(json.dumps({m: importlib.util.find_spec(m) is not None for m in sys.argv[1:]}))")
        ok, out = _run([str(py), "-c", probe] + list(CONDA_TOOL_NAMES.keys()), timeout=20)
        if ok:
            try:
                found = json.loads(out.strip().splitlines()[-1])
                for tool_id, present in found.items():
                    if present:
                        manifest.tools.append(ToolInfo(
                            tool_id=tool_id, runtime_id=runtime_id, version=None,
                            status="healthy", language="python"))
            except Exception:  # noqa: BLE001
                pass

    for cli, (tool_id, lang) in CLI_TOOLS.items():
        p = _which(cli)
        if p:
            manifest.tools.append(ToolInfo(
                tool_id=tool_id, runtime_id=None, version=None,
                status="healthy", language=lang))

    # R 包探测（可选深度检查，保持快速默认不执行）
    # ---- Health Check ----
    if manifest.runtimes:
        manifest_status = "degraded" if not manifest.tools else "healthy"
    else:
        manifest_status = "degraded"
    manifest.compute.notes.append(f"runtimes={len(manifest.runtimes)}, tools={len(manifest.tools)}")
    return manifest
