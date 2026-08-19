"""Environment Manifest 的 Pydantic 模型（标准化输出契约）。"""
from pydantic import BaseModel, Field


class SystemInfo(BaseModel):
    os: str = "unknown"
    arch: str = "unknown"
    cpu_cores: int | None = None
    memory_gb: float | None = None
    gpu: str | None = None


class ComputeInfo(BaseModel):
    scheduler: str | None = None      # slurm / pbs / null
    notes: list[str] = Field(default_factory=list)


class RuntimeInfo(BaseModel):
    id: str
    type: str                          # python / conda / r / shell
    name: str
    version: str | None = None
    path: str | None = None


class ToolInfo(BaseModel):
    tool_id: str
    runtime_id: str | None = None      # None = 系统级工具
    version: str | None = None
    status: str = "unknown"            # healthy / missing / unknown
    language: str = "python"           # python / r / bash


class Manifest(BaseModel):
    environment_id: str = "env_local"
    environment_type: str = "local"
    system: SystemInfo = Field(default_factory=SystemInfo)
    compute: ComputeInfo = Field(default_factory=ComputeInfo)
    runtimes: list[RuntimeInfo] = Field(default_factory=list)
    tools: list[ToolInfo] = Field(default_factory=list)
    schema_version: int = 1

    def tool_status(self, tool_id: str) -> str:
        for t in self.tools:
            if t.tool_id == tool_id:
                return t.status
        return "missing"

    def runtime_has_tools(self, runtime_id: str, tools: list[str]) -> bool:
        return all(self.tool_status(t) == "healthy" for t in tools)
