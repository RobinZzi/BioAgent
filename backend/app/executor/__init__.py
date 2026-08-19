"""Executor 工厂：按配置与 manifest 选择 mock / local。

EXECUTOR_MODE:
  mock —— 始终用 MockExecutor（开发/演示/CI）
  local —— 始终用 LocalExecutor（工具缺失即失败）
  auto —— 逐个探测候选 runtime（优先 preferred），第一个 import 探测通过的
          走真实执行，全部失败回退 mock（记录原因）

运行时探测（Health Check）：manifest 显示工具存在不代表可导入（如 py3.8
scanpy 兼容问题）。auto 模式对 python 工具做 `import` 探测、对 R 包做
`requireNamespace` 探测，结果带 TTL 缓存。
"""
import time
from pathlib import Path

from ..capabilities.definitions import get_capability
from ..config import settings
from ..env.manifest import Manifest
from .base import BaseExecutor
from .local import LocalExecutor
from .mock import MockExecutor

_PY_MODULES = {
    "scanpy": "scanpy", "anndata": "anndata", "leidenalg": "leidenalg",
    "pandas": "pandas", "numpy": "numpy", "matplotlib": "matplotlib",
    "scipy": "scipy", "h5py": "h5py", "seaborn": "seaborn", "scrublet": "scrublet",
}
_R_PACKAGES = {"Seurat", "DESeq2", "edgeR", "clusterProfiler"}

_PROBE_CACHE: dict[tuple, tuple[bool, float]] = {}
_PROBE_TTL = 300.0


def get_executor(project_dir: Path, manifest: Manifest | None, capability_id: str,
                 implementation: str,
                 preferred_runtime: str | None = None) -> tuple[BaseExecutor, str, str | None]:
    """返回 (executor, mode_note, effective_runtime_id)。

    auto 模式会实际探测候选 runtime 并把可用的 runtime id 返回给调用方，
    调用方应把它写回 task.runtime_id / event.runtime_id。
    """
    mode = settings.executor_mode
    if mode == "mock":
        return MockExecutor(project_dir), "mock (配置指定)", preferred_runtime
    if mode == "local":
        return LocalExecutor(project_dir, manifest or Manifest()), "local (配置指定)", preferred_runtime

    # auto：逐个探测候选 runtime
    capability = get_capability(capability_id)
    if manifest is not None and capability is not None:
        impl = next((i for i in capability["implementations"] if i["id"] == implementation), None)
        if impl is not None:
            candidates = _candidate_runtimes(manifest, impl, preferred_runtime)
            for runtime_id in candidates:
                ok, reason = _runtime_probe(manifest, runtime_id, impl.get("tools", []))
                if ok:
                    return LocalExecutor(project_dir, manifest), \
                        f"local (auto, runtime={runtime_id})", runtime_id
            if candidates:
                return MockExecutor(project_dir), \
                    f"mock (auto, 候选 runtime 均探测失败: {reason})", preferred_runtime
    return MockExecutor(project_dir), "mock (auto, 工具缺失或未发现环境)", preferred_runtime


def _candidate_runtimes(manifest: Manifest, impl: dict, preferred: str | None) -> list[str]:
    """候选 runtime：preferred 优先，其余按 manifest 工具顺序（含全部所需工具）。"""
    tools = impl.get("tools", [])
    ordered: list[str] = []
    for t in manifest.tools:
        if t.tool_id in tools and t.status == "healthy" and t.runtime_id:
            if t.runtime_id not in ordered:
                ordered.append(t.runtime_id)
    if preferred and preferred in ordered:
        ordered.remove(preferred)
        ordered.insert(0, preferred)
    # 过滤：必须覆盖全部所需工具
    result = []
    for rt in ordered:
        if all(any(t.tool_id == tool and t.runtime_id == rt and t.status == "healthy"
                   for t in manifest.tools) for tool in tools):
            result.append(rt)
    return result


def _runtime_python(manifest: Manifest, runtime_id: str) -> str | None:
    for rt in manifest.runtimes:
        if rt.id == runtime_id:
            if rt.type in ("python", "venv"):
                return rt.path
            if rt.type == "conda" and rt.path:
                return str(Path(rt.path) / "bin" / "python")
    return None


def _runtime_probe(manifest: Manifest, runtime_id: str, tools: list[str]) -> tuple[bool, str]:
    """探测 runtime 是否真的能加载所需工具。"""
    import subprocess

    py_mods = sorted({_PY_MODULES[t] for t in tools if t in _PY_MODULES})
    r_pkgs = sorted({t for t in tools if t in _R_PACKAGES})

    key = (runtime_id, tuple(py_mods), tuple(r_pkgs))
    cached = _PROBE_CACHE.get(key)
    if cached and time.monotonic() - cached[1] < _PROBE_TTL:
        return cached[0], ("cached" if cached[0] else "probe failed (cached)")

    ok, reason = False, "unknown"
    try:
        if py_mods:
            py = _runtime_python(manifest, runtime_id)
            if not py:
                reason = f"runtime {runtime_id} 无 python 路径"
            else:
                code = "import " + ",".join(py_mods)
                r = subprocess.run([py, "-c", code], capture_output=True,
                                   text=True, timeout=25)
                ok = r.returncode == 0
                reason = (r.stderr or r.stdout).strip().splitlines()[-1][:120] if not ok else ""
        elif r_pkgs:
            expr = "cat(all(sapply(c(%s), requireNamespace, quietly=TRUE)))" % (
                ",".join(f'"{p}"' for p in r_pkgs))
            r = subprocess.run(["Rscript", "-e", expr], capture_output=True,
                               text=True, timeout=40)
            ok = r.returncode == 0 and r.stdout.strip() == "TRUE"
            reason = "R 包缺失: " + ", ".join(r_pkgs) if not ok else ""
        else:
            # bash 工具已在发现阶段 which 验证
            ok, reason = True, ""
    except subprocess.TimeoutExpired:
        ok, reason = False, "探测超时"
    except Exception as e:  # noqa: BLE001
        ok, reason = False, str(e)[:120]

    _PROBE_CACHE[key] = (ok, time.monotonic())
    return ok, reason
