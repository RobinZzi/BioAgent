"""API 响应 Schema（Pydantic）。"""
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- 通用

class Msg(BaseModel):
    detail: str


# ---------------------------------------------------------------- Project

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    data_source: str = "local"      # local / remote（本地项目 / 服务器端项目）
    compute_location: str = "local"  # local / remote
    workdir: str = ""               # 工作区路径（本地绝对路径 / 服务器目录名）
    server_id: str = ""             # 服务器端项目关联的服务器环境


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str = ""
    data_source: str
    compute_location: str
    workdir: str | None = None
    server_id: str | None = None
    server_name: str | None = None
    server_host: str | None = None
    created_at: datetime | None = None
    n_conversations: int = 0
    n_datasets: int = 0
    n_events: int = 0


class DatasetOut(BaseModel):
    id: str
    name: str
    dtype: str
    format: str
    location: str
    phase: str
    parent_dataset_id: str | None = None
    source_event_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime | None = None


# ---------------------------------------------------------------- Conversation

class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: str
    current_dataset_id: str | None = None
    current_phase: str = "raw"
    active_environment_id: str | None = None
    active_runtime_id: str | None = None
    analysis_state: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    triggered_event_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class MessageSend(BaseModel):
    content: str
    wait: bool = True     # true=同步执行完再返回；false=后台执行，轮询事件状态


class MessageResult(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    events: list["EventOut"] = Field(default_factory=list)


# ---------------------------------------------------------------- Environment

class EnvironmentOut(BaseModel):
    id: str
    project_id: str | None = None
    name: str
    env_type: str
    manifest: dict = Field(default_factory=dict)
    status: str
    connector_url: str | None = None
    ssh_host: str | None = None
    ssh_port: int | None = None
    ssh_user: str | None = None
    ssh_has_password: bool = False     # 只回显是否配置密码，不回显明文
    ssh_key_path: str | None = None
    discovered_at: datetime | None = None


# ---------------------------------------------------------------- Capability

class ParameterSpec(BaseModel):
    type: str
    default: object | None = None
    enum: list | None = None
    minimum: float | None = None
    maximum: float | None = None
    description: str = ""


class ImplementationOut(BaseModel):
    id: str
    language: str
    runtime_hint: str
    tools: list[str]
    default: bool = False


class CapabilityOut(BaseModel):
    capability_id: str
    name: str
    domain: str
    dataset_dtype: str
    requires_phase: str
    resulting_phase: str | None = None
    produces_dataset: bool
    parameters: dict[str, ParameterSpec]
    implementations: list[ImplementationOut]
    description: str = ""
    keywords: list[str] = Field(default_factory=list)


class ResolveOut(BaseModel):
    capability_id: str
    implementations: list[dict]      # [{id, language, available, runtime_id, reason}]


# ---------------------------------------------------------------- Event / DAG

class ArtifactOut(BaseModel):
    id: str
    event_id: str
    kind: str
    name: str
    path: str
    mime: str
    size_bytes: int = 0
    created_at: datetime | None = None


class EventOut(BaseModel):
    id: str
    project_id: str
    conversation_id: str | None = None
    message_id: str | None = None
    capability_id: str
    implementation: str
    runtime_id: str | None = None
    environment_id: str | None = None
    inputs: dict = Field(default_factory=dict)
    parameters: dict = Field(default_factory=dict)
    status: str
    error: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    log_path: str | None = None
    artifacts: list[ArtifactOut] = Field(default_factory=list)
    created_at: datetime | None = None


class DagNode(BaseModel):
    id: str
    capability_id: str
    implementation: str
    status: str
    parameters: dict = Field(default_factory=dict)
    message_id: str | None = None
    output: dict = Field(default_factory=dict)
    error: dict | None = None
    created_at: str | None = None


class DagEdge(BaseModel):
    source: str
    target: str
    relation: str


class DagOut(BaseModel):
    nodes: list[DagNode]
    edges: list[DagEdge]
    depth: dict[str, int]


class ProjectDetail(BaseModel):
    project: ProjectOut
    conversations: list[ConversationOut] = Field(default_factory=list)
    datasets: list[DatasetOut] = Field(default_factory=list)
    environments: list[EnvironmentOut] = Field(default_factory=list)
    dag: DagOut | None = None


class RerunBody(BaseModel):
    parameters: dict = Field(default_factory=dict)


class DatasetRegister(BaseModel):
    name: str
    dtype: str = "scrna"          # scrna / bulk_rna / fastq
    format: str = "h5ad"          # h5ad / csv / fastq / 10x
    location: str = ""            # 本地路径；留空则生成 mock 占位
    phase: str = "raw"
    metadata: dict = Field(default_factory=dict)


class DatasetPatch(BaseModel):
    name: str | None = None
    tags: list[str] | None = None


# ---------------------------------------------------------------- Agent / Remote

class IntentRequest(BaseModel):
    content: str
    conversation_id: str | None = None


class IntentResponse(BaseModel):
    source: str                    # llm / rules / none
    capability_id: str | None = None
    parameters: dict = Field(default_factory=dict)
    note: str = ""


class RegisterRemoteBody(BaseModel):
    name: str
    connector_url: str             # 如 http://127.0.0.1:8765
    token: str                     # Connector 共享令牌（非 SSH 凭据）


class RegisterSSHBody(BaseModel):
    name: str
    host: str
    port: int = 22
    user: str
    password: str = ""             # 密码或留空用密钥/agent
    key_path: str = ""             # 本机私钥路径（可选）


class SetEnvironmentBody(BaseModel):
    environment_id: str


MessageResult.model_rebuild()
