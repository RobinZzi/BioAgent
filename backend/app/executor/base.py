"""Executor 协议。

核心原则：Executor 只接受结构化 Task（capability_id + implementation +
runtime_id + inputs + parameters），绝不接受自由 shell。安全边界是协议
白名单，不是 OS 沙箱。见 docs/TECHNICAL_DESIGN.md §5、§11。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaskSpec:
    """结构化任务（Executor 唯一接受的输入）。"""
    task_id: str
    capability_id: str
    implementation: str
    runtime_id: str | None
    inputs: dict
    parameters: dict
    input_dataset_path: str | None
    output_dir: str
    environment_id: str | None = None
    seed: int | None = None          # 随机种子（可复现性：leiden/umap 等）


@dataclass
class ArtifactOut:
    kind: str
    name: str
    path: str
    mime: str = "application/octet-stream"


@dataclass
class DatasetOut:
    name: str
    dtype: str
    format: str
    phase: str
    location: str
    metadata: dict = field(default_factory=dict)


class ExecutionResult:
    """执行结果。支持 to_dict / from_dict（远程 Connector 协议传输用）。"""

    def __init__(self, ok: bool, error: dict | None = None, metrics: dict | None = None,
                 datasets: list | None = None, artifacts: list | None = None,
                 log_lines: list | None = None):
        self.ok = ok
        self.error = error
        self.metrics = metrics or {}
        self.datasets = datasets or []
        self.artifacts = artifacts or []
        self.log_lines = log_lines or []

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "error": self.error,
            "metrics": self.metrics,
            "datasets": [d.__dict__ for d in self.datasets],
            "artifacts": [a.__dict__ for a in self.artifacts],
            "log_lines": self.log_lines,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionResult":
        return cls(
            ok=data.get("ok", False),
            error=data.get("error"),
            metrics=data.get("metrics") or {},
            datasets=[DatasetOut(**d) for d in data.get("datasets") or []],
            artifacts=[ArtifactOut(**a) for a in data.get("artifacts") or []],
            log_lines=data.get("log_lines") or [],
        )


class BaseExecutor(ABC):
    """执行器基类。子类必须实现 execute()。"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)

    @abstractmethod
    def execute(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        """执行任务，返回结构化结果。永不抛异常（失败时 ok=False + error）。"""
