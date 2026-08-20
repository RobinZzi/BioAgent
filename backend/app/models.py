"""BioAgent 核心数据模型（见 docs/TECHNICAL_DESIGN.md §2）。

关系约定：
  Project 1—n Conversation（一条分析线索）
  Conversation 1—n Message
  Message 1—n AnalysisEvent（triggered_event_ids 标注）
  AnalysisEvent 1—n Artifact
  AnalysisEvent 1—n EventLink（DAG 边：depends_on / re_run / fork）
  Dataset 自引用版本链（parent_dataset_id），source_event_id 指向产生它的事件
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- enums

class DataSource(str, enum.Enum):
    local = "local"
    remote = "remote"


class ComputeLocation(str, enum.Enum):
    local = "local"
    remote = "remote"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class DatasetType(str, enum.Enum):
    scrna = "scrna"
    bulk_rna = "bulk_rna"
    fastq = "fastq"
    other = "other"


class EnvType(str, enum.Enum):
    local = "local"
    remote = "remote"


class EnvStatus(str, enum.Enum):
    unknown = "unknown"
    healthy = "healthy"
    degraded = "degraded"
    unreachable = "unreachable"


class EventStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class EventRelation(str, enum.Enum):
    depends_on = "depends_on"
    re_run = "re_run"
    fork = "fork"


class ArtifactKind(str, enum.Enum):
    figure = "figure"
    csv = "csv"
    pdf = "pdf"
    html = "html"
    h5ad = "h5ad"
    log = "log"
    report = "report"
    bam = "bam"
    other = "other"


# ---------------------------------------------------------------- tables

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("usr"))
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("proj"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    data_source: Mapped[str] = mapped_column(SAEnum(DataSource), default=DataSource.local)
    compute_location: Mapped[str] = mapped_column(SAEnum(ComputeLocation), default=ComputeLocation.local)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    environments: Mapped[list["ComputeEnvironment"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    events: Mapped[list["AnalysisEvent"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("conv"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="分析对话")
    # ---- 上下文指针（评审结论：指针式上下文，不复制分析结果）----
    current_dataset_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_phase: Mapped[str] = mapped_column(String(40), default="raw")
    active_environment_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active_runtime_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    analysis_state: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    events: Mapped[list["AnalysisEvent"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("msg"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(SAEnum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    triggered_event_ids: Mapped[list] = mapped_column(JSON, default=list)  # 触发的 AnalysisEvent id 列表
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ds"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    dtype: Mapped[str] = mapped_column(SAEnum(DatasetType), default=DatasetType.scrna)
    format: Mapped[str] = mapped_column(String(40), default="h5ad")
    location: Mapped[str] = mapped_column(Text)          # 不可变文件路径（引用语义）
    phase: Mapped[str] = mapped_column(String(40), default="raw")   # raw/qc/normalized/...
    parent_dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)  # 版本链
    source_event_id: Mapped[str | None] = mapped_column(String(40), nullable=True)    # 产生它的事件
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    schema_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="datasets")
    parent: Mapped["Dataset | None"] = relationship(remote_side="Dataset.id")


class ComputeEnvironment(Base):
    __tablename__ = "environments"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("env"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)  # None = 全局
    name: Mapped[str] = mapped_column(String(200), default="本机环境")
    env_type: Mapped[str] = mapped_column(SAEnum(EnvType), default=EnvType.local)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(SAEnum(EnvStatus), default=EnvStatus.unknown)
    # 远程环境（Local Connector 协议）：连接信息 + 共享令牌（非 SSH 凭据）
    connector_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    connector_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 远程环境（SSH 直连）：账号/密码/密钥（密码加密存储，接口不回显）
    ssh_host: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_port: Mapped[int] = mapped_column(default=22)
    ssh_user: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_password: Mapped[str | None] = mapped_column(Text, nullable=True)  # 加密
    ssh_key_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project | None] = relationship(back_populates="environments")


class AnalysisEvent(Base):
    __tablename__ = "analysis_events"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ev"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(40), nullable=True)  # 触发它的对话消息
    capability_id: Mapped[str] = mapped_column(String(80))
    implementation: Mapped[str] = mapped_column(String(40), default="mock")
    runtime_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    environment_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)       # {"dataset": "ds_xxx"}
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(SAEnum(EventStatus), default=EventStatus.queued)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 结构化错误
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    output: Mapped[dict] = mapped_column(JSON, default=dict)        # {"datasets": [...], "artifacts": [...]}
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    schema_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="events")
    conversation: Mapped[Conversation | None] = relationship(back_populates="events")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    out_links: Mapped[list["EventLink"]] = relationship(
        foreign_keys="EventLink.parent_event_id", back_populates="parent", cascade="all, delete-orphan")
    in_links: Mapped[list["EventLink"]] = relationship(
        foreign_keys="EventLink.child_event_id", back_populates="child")


class EventLink(Base):
    """Analysis DAG 的边。"""
    __tablename__ = "event_links"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("link"))
    parent_event_id: Mapped[str] = mapped_column(ForeignKey("analysis_events.id"), index=True)
    child_event_id: Mapped[str] = mapped_column(ForeignKey("analysis_events.id"), index=True)
    relation: Mapped[str] = mapped_column(SAEnum(EventRelation), default=EventRelation.depends_on)

    parent: Mapped[AnalysisEvent] = relationship(foreign_keys=[parent_event_id], back_populates="out_links")
    child: Mapped[AnalysisEvent] = relationship(foreign_keys=[child_event_id], back_populates="in_links")


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("art"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("analysis_events.id"), index=True)
    kind: Mapped[str] = mapped_column(SAEnum(ArtifactKind))
    name: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship()
    event: Mapped[AnalysisEvent] = relationship(back_populates="artifacts")
