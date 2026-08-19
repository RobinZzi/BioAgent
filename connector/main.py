"""BioAgent Local Connector（v0.1）

协议（结构化，非自由 shell）：
  GET  /health    —— 连通性检查
  GET  /discover  —— 远程 Environment Discovery → Manifest
  POST /execute   —— 执行结构化 Task → ExecutionResult JSON

鉴权：请求头 X-Connector-Token == 环境变量 CONNECTOR_TOKEN（未设置=仅本机演示）。

启动：
  CONNECTOR_TOKEN=xxx CONNECTOR_EXECUTOR_MODE=auto \
    backend/.venv/bin/uvicorn connector.main:app --port 8765
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import Depends, FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.capabilities.definitions import get_capability  # noqa: E402
from app.env.discovery import discover_local  # noqa: E402
from app.executor.base import ExecutionResult, TaskSpec  # noqa: E402

from .auth import require_token  # noqa: E402
from .runtime import get_connector_executor  # noqa: E402

app = FastAPI(title="BioAgent Connector", version="0.1.0")

_CONNECTOR_WORK = Path(os.environ.get("CONNECTOR_WORKDIR",
                                      str(ROOT / "connector" / "work")))
_CONNECTOR_WORK.mkdir(parents=True, exist_ok=True)


class ExecuteRequest(BaseModel):
    task: dict


@app.get("/health")
def health(_=Depends(require_token)):
    import platform
    return {
        "ok": True,
        "app": "bioagent-connector",
        "version": "0.1.0",
        "mode": os.environ.get("CONNECTOR_EXECUTOR_MODE", "auto"),
        "host": platform.node(),
    }


@app.get("/discover")
def discover(_=Depends(require_token)):
    manifest = discover_local(timeout=float(os.environ.get("CONNECTOR_DISCOVER_TIMEOUT", "30")))
    return manifest.model_dump()


@app.post("/execute")
def execute(body: ExecuteRequest, _=Depends(require_token)):
    task = TaskSpec(**body.task)
    capability = get_capability(task.capability_id)
    if capability is None:
        return ExecutionResult(ok=False, error={
            "stage": "resolve", "type": "UnknownCapability",
            "message": f"Connector 无法识别能力 {task.capability_id}",
            "log_tail": []}).to_dict()

    # 执行目录映射到 Connector 本地工作区（远端文件系统不可见时后端需做路径映射，见文档）
    job_dir = _CONNECTOR_WORK / task.task_id
    job_dir.mkdir(parents=True, exist_ok=True)

    from .slurm import _cached_manifest
    manifest = _cached_manifest()
    executor = get_connector_executor(job_dir.parent.parent, manifest, task, capability)

    # 替换输出目录为 Connector 本地工作区
    task.output_dir = str(job_dir)
    if task.input_dataset_path and not Path(task.input_dataset_path).exists():
        task.input_dataset_path = None  # 远端路径不可达：由 Connector 侧数据映射处理

    result = executor.execute(task, capability)
    return result.to_dict()
