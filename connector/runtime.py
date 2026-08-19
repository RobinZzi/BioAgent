"""Connector 侧执行器选择：mock / local / slurm / auto。

复用 backend/app 的模板与发现逻辑（sys.path 注入），保持协议一致：
只接受结构化 Task，绝不接受自由 shell。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.env.manifest import Manifest  # noqa: E402
from app.executor.base import BaseExecutor, TaskSpec  # noqa: E402
from app.executor.local import LocalExecutor  # noqa: E402
from app.executor.mock import MockExecutor  # noqa: E402

from .slurm import SlurmExecutor  # noqa: E402

MODE = os.environ.get("CONNECTOR_EXECUTOR_MODE", "auto")


def get_connector_executor(project_dir: Path, manifest: Manifest | None,
                           task: TaskSpec, capability: dict) -> BaseExecutor:
    mode = MODE
    if mode == "mock":
        return MockExecutor(project_dir)
    if mode == "slurm":
        return SlurmExecutor(project_dir)
    if mode == "local":
        return LocalExecutor(project_dir, manifest or Manifest())
    # auto：Slurm 可用 → slurm；否则本地（含探测）；失败回退 mock
    if manifest is not None and manifest.compute.scheduler == "slurm":
        import shutil
        if shutil.which("sbatch"):
            return SlurmExecutor(project_dir)
    try:
        from app.executor import _candidate_runtimes, _runtime_probe
        impl = next((i for i in capability["implementations"]
                     if i["id"] == task.implementation), None)
        if manifest is not None and impl is not None:
            for runtime_id in _candidate_runtimes(manifest, impl, task.runtime_id):
                ok, _reason = _runtime_probe(manifest, runtime_id, impl.get("tools", []))
                if ok:
                    return LocalExecutor(project_dir, manifest)
    except Exception:  # noqa: BLE001
        pass
    return MockExecutor(project_dir)
