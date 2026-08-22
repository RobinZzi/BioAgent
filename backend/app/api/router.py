"""BioAgent REST API（v0.1）。见 docs/TECHNICAL_DESIGN.md §7。"""
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..capabilities.definitions import CAPABILITIES_BY_ID, get_capability, list_capabilities
from ..db import SessionLocal, get_db
from ..env.discovery import discover_local
from ..env.manifest import Manifest
from ..services.auth import get_current_user
from ..models import (
    AnalysisEvent, Artifact, ArtifactKind, ComputeEnvironment, Conversation,
    Dataset, DatasetType, EnvStatus, EnvType, EventLink, EventRelation,
    EventStatus, Message, MessageRole, Project, User, new_id, utcnow,
)
from ..schemas import (
    ArtifactOut, CapabilityOut, ConversationOut, DagOut, DatasetOut,
    DatasetPatch, DatasetRegister, EnvironmentOut, EventOut, IntentRequest,
    IntentResponse, MessageOut, MessageResult, MessageSend, ProjectCreate,
    ProjectDetail, ProjectOut, RegisterRemoteBody, RegisterSSHBody, RerunBody,
    ResolveOut, SetEnvironmentBody,
)
from ..services import agent as agent_svc
from ..services import dag as dag_svc
from ..services.execution import project_dir
from ..config import settings

router = APIRouter(prefix="/api")


# ================================================================ 工具函数

def _project_out(p: Project, db: Session) -> ProjectOut:
    server_name = server_host = None
    if p.server_id:
        env = db.get(ComputeEnvironment, p.server_id)
        if env is not None:
            server_name = env.name
            server_host = env.ssh_host or env.connector_url or None
    return ProjectOut(
        id=p.id, name=p.name, description=p.description,
        data_source=p.data_source.value if hasattr(p.data_source, "value") else p.data_source,
        compute_location=p.compute_location.value if hasattr(p.compute_location, "value") else p.compute_location,
        workdir=p.workdir, server_id=p.server_id,
        server_name=server_name, server_host=server_host,
        created_at=p.created_at,
        n_conversations=len(p.conversations),
        n_datasets=len(p.datasets),
        n_events=len(p.events),
    )


def _conversation_out(c: Conversation) -> ConversationOut:
    return ConversationOut(
        id=c.id, project_id=c.project_id, title=c.title,
        current_dataset_id=c.current_dataset_id, current_phase=c.current_phase,
        active_environment_id=c.active_environment_id, active_runtime_id=c.active_runtime_id,
        analysis_state=c.analysis_state or {}, created_at=c.created_at,
    )


def _dataset_out(d: Dataset) -> DatasetOut:
    return DatasetOut(
        id=d.id, name=d.name,
        dtype=d.dtype.value if hasattr(d.dtype, "value") else d.dtype,
        format=d.format, location=d.location,
        phase=d.phase, parent_dataset_id=d.parent_dataset_id,
        source_event_id=d.source_event_id, metadata=d.metadata_ or {},
        created_at=d.created_at,
    )


def _env_out(e: ComputeEnvironment) -> EnvironmentOut:
    return EnvironmentOut(
        id=e.id, project_id=e.project_id, name=e.name,
        env_type=e.env_type.value if hasattr(e.env_type, "value") else e.env_type,
        manifest=e.manifest or {}, status=e.status.value if hasattr(e.status, "value") else e.status,
        connector_url=e.connector_url,
        ssh_host=e.ssh_host, ssh_port=e.ssh_port, ssh_user=e.ssh_user,
        ssh_has_password=bool(e.ssh_password), ssh_key_path=e.ssh_key_path,
        discovered_at=e.discovered_at,
    )


def _artifact_out(a: Artifact) -> ArtifactOut:
    return ArtifactOut(
        id=a.id, event_id=a.event_id, kind=a.kind.value if hasattr(a.kind, "value") else a.kind,
        name=a.name, path=a.path, mime=a.mime, size_bytes=a.size_bytes, created_at=a.created_at,
    )


def _event_out(ev: AnalysisEvent, db: Session) -> EventOut:
    arts = db.query(Artifact).filter(Artifact.event_id == ev.id).all()
    return EventOut(
        id=ev.id, project_id=ev.project_id, conversation_id=ev.conversation_id,
        message_id=ev.message_id, capability_id=ev.capability_id,
        implementation=ev.implementation, runtime_id=ev.runtime_id,
        environment_id=ev.environment_id, inputs=ev.inputs or {}, parameters=ev.parameters or {},
        status=ev.status.value if hasattr(ev.status, "value") else ev.status,
        error=ev.error, started_at=ev.started_at, finished_at=ev.finished_at,
        output=ev.output or {}, metrics=ev.metrics or {}, log_path=ev.log_path,
        artifacts=[_artifact_out(a) for a in arts], created_at=ev.created_at,
    )


def _get_project(db: Session, project_id: str, user: User | None = None) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, f"项目不存在: {project_id}")
    if user is not None and p.owner_id is not None and p.owner_id != user.id:
        raise HTTPException(403, "无权访问该项目")
    return p


def _get_conversation(db: Session, conv_id: str) -> Conversation:
    c = db.get(Conversation, conv_id)
    if c is None:
        raise HTTPException(404, f"对话不存在: {conv_id}")
    return c


def _get_event(db: Session, event_id: str) -> AnalysisEvent:
    e = db.get(AnalysisEvent, event_id)
    if e is None:
        raise HTTPException(404, f"分析事件不存在: {event_id}")
    return e


# ================================================================ 健康检查

@router.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.version}


# ================================================================ Auth

class AuthBody(BaseModel):
    username: str
    password: str


@router.post("/auth/register")
def register(body: AuthBody, db: Session = Depends(get_db)):
    from ..services.auth import hash_password, new_token
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "用户名已存在")
    is_first = db.query(User).count() == 0
    user = User(id=new_id("usr"), username=body.username,
                password_hash=hash_password(body.password),
                name=body.username, is_admin=is_first)
    db.add(user)
    db.flush()
    if is_first:
        # 首个用户接管所有未归属项目
        db.query(Project).filter(Project.owner_id.is_(None)).update({Project.owner_id: user.id})
    user.token = new_token()
    db.commit()
    db.refresh(user)
    return {"token": user.token, "username": user.username, "is_admin": user.is_admin}


@router.post("/auth/login")
def login(body: AuthBody, db: Session = Depends(get_db)):
    from ..services.auth import new_token, verify_password
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    user.token = new_token()
    db.commit()
    return {"token": user.token, "username": user.username, "is_admin": user.is_admin}


@router.get("/auth/me")
def me(user: User | None = Depends(get_current_user)):
    if user is None:
        return {"username": None, "is_admin": False, "standalone": True}
    return {"username": user.username, "is_admin": user.is_admin, "standalone": False}


# ================================================================ Projects

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    q = db.query(Project)
    if user is not None:
        q = q.filter(Project.owner_id == user.id)
    projects = q.order_by(Project.created_at.desc()).all()
    return [_project_out(p, db) for p in projects]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db),
                   user: User | None = Depends(get_current_user)):
    workdir = body.workdir.strip() or None
    server_id = body.server_id.strip() or None
    # 本地项目工作区：确保目录存在（可创建）
    if body.data_source == "local" and workdir:
        try:
            Path(workdir).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(400, f"无法创建工作区目录: {e}")
    p = Project(id=new_id("proj"), owner_id=user.id if user else None, name=body.name, description=body.description,
                data_source=body.data_source, compute_location=body.compute_location,
                workdir=workdir, server_id=server_id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _project_out(p, db)


class ProjectPatch(BaseModel):
    name: str | None = None
    workdir: str | None = None   # 重定位工作区（本地绝对路径 / 服务器目录名）


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def patch_project(project_id: str, body: ProjectPatch, db: Session = Depends(get_db),
                  user: User | None = Depends(get_current_user)):
    """重命名项目 / 重定位工作区。"""
    p = _get_project(db, project_id, user)
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "项目名不能为空")
        p.name = body.name.strip()
    if body.workdir is not None:
        wd = body.workdir.strip()
        if p.data_source == "local" and wd:
            try:
                Path(wd).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise HTTPException(400, f"无法创建工作区目录: {e}")
        p.workdir = wd or None
    db.commit()
    db.refresh(p)
    return _project_out(p, db)


@router.get("/fs/list")
def fs_list(path: str = "/", db: Session = Depends(get_db)):
    """目录浏览（用于本地项目工作区选择）。"""
    import os
    base = Path(path).expanduser()
    if not base.is_dir():
        return {"path": str(base), "parent": str(base.parent), "dirs": []}
    dirs = []
    try:
        for entry in sorted(base.iterdir()):
            try:
                if entry.is_dir() and not entry.name.startswith("."):
                    dirs.append(entry.name)
            except OSError:
                continue
    except OSError:
        pass
    return {"path": str(base), "parent": str(base.parent), "dirs": dirs}


class BatchDeleteBody(BaseModel):
    project_ids: list[str]
    delete_files: bool = True   # 是否删除项目目录（含 log / 已生成图片 / 产物文件）


@router.post("/projects/batch-delete")
def batch_delete_projects(body: BatchDeleteBody, db: Session = Depends(get_db),
                          user: User | None = Depends(get_current_user)):
    """批量删除项目。delete_files=True 时连带删除项目目录（log/图片/产物）；
    False 时仅删除数据库记录，文件保留。"""
    import shutil

    deleted = []
    for pid in body.project_ids:
        p = db.get(Project, pid)
        if p is None or (user is not None and p.owner_id != user.id):
            continue
        if p is None:
            continue
        pdir = project_dir(pid)
        db.delete(p)
        if body.delete_files and pdir.exists():
            shutil.rmtree(pdir, ignore_errors=True)
        deleted.append(pid)
    db.commit()
    return {"deleted": deleted, "deleted_files": body.delete_files}


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def project_detail(project_id: str, db: Session = Depends(get_db),
                   user: User | None = Depends(get_current_user)):
    p = _get_project(db, project_id, user)
    convs = db.query(Conversation).filter(Conversation.project_id == project_id).all()
    dss = db.query(Dataset).filter(Dataset.project_id == project_id).order_by(
        Dataset.created_at.asc()).all()
    envs = db.query(ComputeEnvironment).filter(
        ComputeEnvironment.project_id == project_id).all()
    return ProjectDetail(
        project=_project_out(p, db),
        conversations=[_conversation_out(c) for c in convs],
        datasets=[_dataset_out(d) for d in dss],
        environments=[_env_out(e) for e in envs],
        dag=dag_svc.build_dag(db, project_id),
    )


# ================================================================ Conversations

@router.post("/projects/{project_id}/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(project_id: str, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    c = Conversation(id=new_id("conv"), project_id=p.id, title=p.name + " 分析")
    db.add(c)
    db.commit()
    db.refresh(c)
    return _conversation_out(c)


@router.get("/conversations/{conv_id}", response_model=dict)
def conversation_detail(conv_id: str, db: Session = Depends(get_db)):
    c = _get_conversation(db, conv_id)
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(
        Message.created_at.asc()).all()
    events = db.query(AnalysisEvent).filter(AnalysisEvent.conversation_id == conv_id).order_by(
        AnalysisEvent.created_at.asc()).all()
    return {
        "conversation": _conversation_out(c),
        "messages": [MessageOut(id=m.id, role=m.role.value if hasattr(m.role, "value") else m.role,
                                content=m.content, triggered_event_ids=m.triggered_event_ids or [],
                                created_at=m.created_at).model_dump() for m in msgs],
        "events": [_event_out(e, db) for e in events],
    }


@router.post("/conversations/{conv_id}/messages", response_model=MessageResult)
def send_message(conv_id: str, body: MessageSend, db: Session = Depends(get_db)):
    c = _get_conversation(db, conv_id)

    if not body.wait:
        # 异步：用户消息与占位助手消息立即可见，线程执行并回填
        user_msg = Message(conversation_id=c.id, role=MessageRole.user, content=body.content)
        placeholder = Message(conversation_id=c.id, role=MessageRole.assistant,
                              content="分析执行中…（事件状态见历史面板）")
        db.add(user_msg)
        db.add(placeholder)
        db.commit()

        def _run():
            s = SessionLocal()
            try:
                conv = s.get(Conversation, c.id)
                agent_svc.handle_message(s, conv, body.content,
                                         user_msg=user_msg, assistant_msg=placeholder)
            finally:
                s.close()

        threading.Thread(target=_run, daemon=True).start()
        return MessageResult(
            user_message=MessageOut(id=user_msg.id, role="user", content=user_msg.content,
                                    triggered_event_ids=[], created_at=user_msg.created_at),
            assistant_message=MessageOut(id=placeholder.id, role="assistant",
                                         content=placeholder.content, triggered_event_ids=[],
                                         created_at=placeholder.created_at),
            events=[])

    result = agent_svc.handle_message(db, c, body.content)
    return MessageResult(
        user_message=MessageOut(id=result["user_message"].id, role="user",
                                content=result["user_message"].content,
                                triggered_event_ids=result["user_message"].triggered_event_ids or [],
                                created_at=result["user_message"].created_at),
        assistant_message=MessageOut(id=result["assistant_message"].id, role="assistant",
                                     content=result["assistant_message"].content,
                                     triggered_event_ids=[],
                                     created_at=result["assistant_message"].created_at),
        events=[_event_out(e, db) for e in result["events"]],
    )


# ================================================================ Datasets

@router.get("/projects/{project_id}/datasets", response_model=list[DatasetOut])
def list_datasets(project_id: str, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    dss = db.query(Dataset).filter(Dataset.project_id == project_id).order_by(
        Dataset.created_at.asc()).all()
    return [_dataset_out(d) for d in dss]


@router.post("/projects/{project_id}/datasets", response_model=DatasetOut, status_code=201)
def register_dataset(project_id: str, body: DatasetRegister, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    location = body.location
    if not location:
        # 生成 mock 占位文件
        pd = project_dir(project_id) / "datasets"
        pd.mkdir(parents=True, exist_ok=True)
        loc = pd / body.name
        loc.write_bytes(b"\x89HDF placeholder (registered mock)")
        (pd / (body.name + ".meta.json")).write_text(
            '{"mock": true, "registered": true}', encoding="utf-8")
        location = str(loc)
    meta = dict(body.metadata or {})
    if body.dtype == "fastq" and "data_type" not in meta:
        from ..services.data_type import detect_fastq_type
        meta["data_type"] = detect_fastq_type(body.name)
    d = Dataset(id=new_id("ds"), project_id=p.id, name=body.name, dtype=DatasetType(body.dtype),
                format=body.format, location=location, phase=body.phase,
                metadata_=meta)
    db.add(d)
    db.commit()
    db.refresh(d)
    return _dataset_out(d)


@router.patch("/datasets/{dataset_id}", response_model=DatasetOut)
def patch_dataset(dataset_id: str, body: DatasetPatch, db: Session = Depends(get_db)):
    """重命名数据集 / 打标签。"""
    d = db.get(Dataset, dataset_id)
    if d is None:
        raise HTTPException(404, f"数据集不存在: {dataset_id}")
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "数据集名不能为空")
        d.name = body.name.strip()
    if body.tags is not None:
        meta = dict(d.metadata_ or {})
        meta["tags"] = body.tags
        d.metadata_ = meta
    db.commit()
    db.refresh(d)
    return _dataset_out(d)


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """删除数据集记录（不删除原始文件）。先断开子数据集的版本链引用。"""
    d = db.get(Dataset, dataset_id)
    if d is None:
        raise HTTPException(404, f"数据集不存在: {dataset_id}")
    # 断开引用本数据集的子数据集（避免外键冲突）
    db.query(Dataset).filter(Dataset.parent_dataset_id == dataset_id).update(
        {Dataset.parent_dataset_id: None})
    db.delete(d)
    db.commit()
    return {"deleted": dataset_id}


@router.get("/projects/{project_id}/files")
def project_files(project_id: str, path: str = "", db: Session = Depends(get_db)):
    """工作区文件浏览（本地项目）。path 相对工作区目录。"""
    from ..services.execution import project_dir
    p = _get_project(db, project_id)
    base = Path(p.workdir) if p.workdir else project_dir(project_id)
    if not base.is_dir():
        return {"path": str(base), "is_dir": False, "dirs": [], "files": []}
    target = (base / path).resolve() if path else base
    if not str(target).startswith(str(base)):
        raise HTTPException(400, "路径越界")
    if not target.is_dir():
        return {"path": str(target), "is_dir": False, "dirs": [], "files": []}
    dirs, files = [], []
    try:
        for e in sorted(target.iterdir()):
            if e.name.startswith("."):
                continue
            try:
                if e.is_dir():
                    dirs.append(e.name)
                elif e.is_file():
                    files.append({"name": e.name, "size": e.stat().st_size})
            except OSError:
                continue
    except OSError:
        pass
    return {"path": str(target), "is_dir": True, "dirs": dirs, "files": files}

@router.post("/projects/{project_id}/environments/discover", response_model=EnvironmentOut)
def discover_environment(project_id: str, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    manifest = discover_local(timeout=settings.discovery_timeout)
    env = (
        db.query(ComputeEnvironment)
        .filter(ComputeEnvironment.project_id == project_id,
                ComputeEnvironment.env_type == EnvType.local)
        .first()
    )
    if env is None:
        env = ComputeEnvironment(id=new_id("env"), project_id=p.id, name="本机环境",
                                 env_type=EnvType.local)
        db.add(env)
    env.manifest = manifest.model_dump()
    env.status = EnvStatus.healthy if manifest.runtimes else EnvStatus.unreachable
    env.discovered_at = utcnow()
    db.commit()
    db.refresh(env)
    return _env_out(env)


@router.get("/projects/{project_id}/environments", response_model=list[EnvironmentOut])
def list_environments(project_id: str, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    envs = db.query(ComputeEnvironment).filter(
        ComputeEnvironment.project_id == project_id).all()
    return [_env_out(e) for e in envs]


@router.get("/servers", response_model=list[EnvironmentOut])
def list_servers(db: Session = Depends(get_db)):
    """所有已链接的远程服务器环境（新建项目时选择）。"""
    envs = (db.query(ComputeEnvironment)
            .filter(ComputeEnvironment.env_type == EnvType.remote)
            .order_by(ComputeEnvironment.discovered_at.desc()).all())
    return [_env_out(e) for e in envs]


@router.post("/environments/{env_id}/rediscover", response_model=EnvironmentOut)
def rediscover_environment(env_id: str, db: Session = Depends(get_db)):
    env = db.get(ComputeEnvironment, env_id)
    if env is None:
        raise HTTPException(404, f"环境不存在: {env_id}")
    manifest = discover_local(timeout=settings.discovery_timeout)
    env.manifest = manifest.model_dump()
    env.status = EnvStatus.healthy if manifest.runtimes else EnvStatus.unreachable
    env.discovered_at = utcnow()
    db.commit()
    db.refresh(env)
    return _env_out(env)


# ---------------------------------------------------------------- 远程环境（Local Connector）

@router.post("/projects/{project_id}/environments/register-remote", response_model=EnvironmentOut)
def register_remote_environment(project_id: str, body: RegisterRemoteBody,
                                db: Session = Depends(get_db)):
    """注册远程 Connector：握手 /discover 获取远程 Manifest。
    后端只保存 connector_url + 共享令牌，不持有任何 SSH 凭据。"""
    p = _get_project(db, project_id)
    from ..executor.remote import LocalConnectorExecutor
    probe = LocalConnectorExecutor(Path("."), body.connector_url, body.token)
    manifest_dict, err = probe.discover()
    if err or manifest_dict is None:
        raise HTTPException(400, f"无法连接 Connector ({body.connector_url}): {err}")
    env = ComputeEnvironment(
        id=new_id("env"), project_id=p.id, name=body.name, env_type=EnvType.remote,
        manifest=manifest_dict,
        status=EnvStatus.healthy if manifest_dict.get("runtimes") else EnvStatus.degraded,
        connector_url=body.connector_url, connector_token=body.token,
        discovered_at=utcnow())
    db.add(env)
    db.commit()
    db.refresh(env)
    return _env_out(env)


@router.post("/projects/{project_id}/environments/register-ssh", response_model=EnvironmentOut)
def register_ssh_environment(project_id: str, body: RegisterSSHBody,
                             db: Session = Depends(get_db)):
    """注册 SSH 直连环境（方案 B：后端直连）。密码加密存储，接口不回显明文。
    注册时连接并执行远程工具发现，生成 Manifest。"""
    p = _get_project(db, project_id)
    from ..utils.crypto import encrypt
    ok, detail, manifest = _ssh_probe(body.host, body.port, body.user,
                                      body.password, body.key_path)
    env = ComputeEnvironment(
        id=new_id("env"), project_id=p.id, name=body.name, env_type=EnvType.remote,
        ssh_host=body.host, ssh_port=body.port, ssh_user=body.user,
        ssh_password=encrypt(body.password) if body.password else None,
        ssh_key_path=body.key_path or None,
        manifest=manifest or {},
        status=EnvStatus.healthy if ok else EnvStatus.unreachable,
        discovered_at=utcnow())
    db.add(env)
    db.commit()
    db.refresh(env)
    return _env_out(env)


@router.post("/environments/register-remote", response_model=EnvironmentOut)
def register_remote_global(body: RegisterRemoteBody, db: Session = Depends(get_db)):
    """注册全局 Connector（新建项目时添加服务器，无需项目）。"""
    from ..executor.remote import LocalConnectorExecutor
    probe = LocalConnectorExecutor(Path("."), body.connector_url, body.token)
    manifest_dict, err = probe.discover()
    if err or manifest_dict is None:
        raise HTTPException(400, f"无法连接 Connector ({body.connector_url}): {err}")
    env = ComputeEnvironment(
        id=new_id("env"), project_id=None, name=body.name, env_type=EnvType.remote,
        manifest=manifest_dict,
        status=EnvStatus.healthy if manifest_dict.get("runtimes") else EnvStatus.degraded,
        connector_url=body.connector_url, connector_token=body.token,
        discovered_at=utcnow())
    db.add(env)
    db.commit()
    db.refresh(env)
    return _env_out(env)


@router.post("/environments/register-ssh", response_model=EnvironmentOut)
def register_ssh_global(body: RegisterSSHBody, db: Session = Depends(get_db)):
    """注册全局 SSH 服务器（新建项目时添加服务器，无需项目）。"""
    from ..utils.crypto import encrypt
    ok, detail, manifest = _ssh_probe(body.host, body.port, body.user,
                                      body.password, body.key_path)
    env = ComputeEnvironment(
        id=new_id("env"), project_id=None, name=body.name, env_type=EnvType.remote,
        ssh_host=body.host, ssh_port=body.port, ssh_user=body.user,
        ssh_password=encrypt(body.password) if body.password else None,
        ssh_key_path=body.key_path or None,
        manifest=manifest or {},
        status=EnvStatus.healthy if ok else EnvStatus.unreachable,
        discovered_at=utcnow())
    db.add(env)
    db.commit()
    db.refresh(env)
    return _env_out(env)


def _ssh_connect(host: str, port: int, user: str, password: str, key_path: str):
    """建立 SSH 连接，返回 (client, error)。client 失败时为 None。"""
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = dict(hostname=host, port=port, username=user, timeout=20, banner_timeout=20)
    if key_path:
        kw["key_filename"] = key_path
    elif password:
        kw["password"] = password
    else:
        kw["allow_agent"] = True
    try:
        client.connect(**kw)
        return client, None
    except Exception as e:  # noqa: BLE001
        client.close()
        return None, str(e)


def _ssh_probe(host: str, port: int, user: str, password: str, key_path: str):
    """连接 + 远程工具发现。返回 (ok, detail, manifest_dict|None)。"""
    client, err = _ssh_connect(host, port, user, password, key_path)
    if client is None:
        return False, err, None
    try:
        from ..env.remote_discovery import discover_remote
        manifest = discover_remote(client)
        return True, "连接成功", manifest.model_dump()
    except Exception as e:  # noqa: BLE001
        return False, f"连接成功但发现失败：{e}", None
    finally:
        client.close()


def _test_ssh(host: str, port: int, user: str, password: str, key_path: str) -> tuple[bool, str]:
    client, err = _ssh_connect(host, port, user, password, key_path)
    if client is not None:
        client.close()
        return True, "连接成功"
    return False, err


@router.post("/environments/{env_id}/test")
def test_environment(env_id: str, db: Session = Depends(get_db)):
    env = db.get(ComputeEnvironment, env_id)
    if env is None:
        raise HTTPException(404, f"环境不存在: {env_id}")
    if env.env_type == EnvType.remote and env.connector_url:
        from ..executor.remote import LocalConnectorExecutor
        ok, detail = LocalConnectorExecutor.test_connection(
            env.connector_url, env.connector_token or "")
        return {"ok": ok, "detail": detail, "env_type": "connector"}
    if env.env_type == EnvType.remote and env.ssh_host:
        from ..utils.crypto import decrypt
        ok, detail, manifest = _ssh_probe(env.ssh_host, env.ssh_port, env.ssh_user or "",
                                          decrypt(env.ssh_password or ""), env.ssh_key_path or "")
        env.status = EnvStatus.healthy if ok else EnvStatus.unreachable
        if manifest:
            env.manifest = manifest
        env.discovered_at = utcnow()
        db.commit()
        return {"ok": ok, "detail": detail, "env_type": "ssh",
                "manifest_runtimes": len((manifest or {}).get("runtimes", [])),
                "manifest_tools": len((manifest or {}).get("tools", []))}
    return {"ok": True, "detail": "本地环境（直接执行）", "env_type": "local"}


@router.post("/conversations/{conv_id}/set-environment", response_model=ConversationOut)
def set_conversation_environment(conv_id: str, body: SetEnvironmentBody,
                                 db: Session = Depends(get_db)):
    c = _get_conversation(db, conv_id)
    env = db.get(ComputeEnvironment, body.environment_id)
    if env is None:
        raise HTTPException(404, f"环境不存在: {body.environment_id}")
    c.active_environment_id = env.id
    c.active_runtime_id = None
    db.commit()
    db.refresh(c)
    return _conversation_out(c)


# ---------------------------------------------------------------- Agent（v0.2 LLM）

@router.get("/agent/status")
def agent_status():
    from ..services import llm as llm_svc
    return llm_svc.llm_status()


@router.get("/settings")
def get_settings():
    """运行时工作模式 / Agent 模式配置（不返回 api_key 明文）。"""
    from ..services import llm as llm_svc
    return {
        "executor_mode": settings.executor_mode,
        "llm_mode": settings.llm_mode,
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "version": settings.version,
        "auth_enabled": settings.auth_enabled,
        "agent_status": llm_svc.llm_status(),
    }


class SettingsPatch(BaseModel):
    executor_mode: str | None = None   # mock | auto | local
    llm_mode: str | None = None        # off | echo | real
    llm_api_key: str | None = None     # None=不改动，空串=清除，否则保存
    llm_base_url: str | None = None
    llm_model: str | None = None


@router.patch("/settings")
def patch_settings(body: SettingsPatch):
    """运行时切换工作模式 / Agent 模式 / LLM 配置。"""
    if body.executor_mode is not None:
        if body.executor_mode not in ("mock", "auto", "local"):
            raise HTTPException(400, "executor_mode 必须是 mock/auto/local")
        settings.executor_mode = body.executor_mode

    # LLM 配置持久化（写入本地文件，重启后仍生效）
    if body.llm_api_key is not None or body.llm_base_url or body.llm_model:
        settings.save_llm_config(
            api_key=body.llm_api_key,
            base_url=body.llm_base_url or None,
            model=body.llm_model or None,
        )
        if body.llm_api_key is not None:
            settings.llm_api_key = body.llm_api_key
        if body.llm_base_url:
            settings.llm_base_url = body.llm_base_url
        if body.llm_model:
            settings.llm_model = body.llm_model

    if body.llm_mode is not None:
        if body.llm_mode not in ("off", "echo", "real"):
            raise HTTPException(400, "llm_mode 必须是 off/echo/real")
        if body.llm_mode == "real" and not settings.llm_api_key:
            raise HTTPException(400, "real 模式需要先配置 API Key")
        settings.llm_mode = body.llm_mode
    return get_settings()


@router.post("/agent/intent", response_model=IntentResponse)
def agent_intent(body: IntentRequest, db: Session = Depends(get_db)):
    """意图解析调试（dry-run）：LLM → 规则引擎 → none。"""
    from ..services import llm as llm_svc
    ctx = {}
    if body.conversation_id:
        conv = _get_conversation(db, body.conversation_id)
        datasets = db.query(Dataset).filter(
            Dataset.project_id == conv.project_id).order_by(
            Dataset.created_at.desc()).all()
        ctx = llm_svc.build_context(conv, datasets)

    if llm_svc.enabled():
        res = llm_svc.parse_intent_llm(body.content, ctx)
        if res is not None:
            if res.capability_id:
                return IntentResponse(source=res.source, capability_id=res.capability_id,
                                      parameters=res.parameters, note=res.note)
            # LLM 判定无法识别 → 规则兜底
            r = agent_svc.parse_intent(body.content)
            if r:
                return IntentResponse(source="rules", capability_id=r[0],
                                      parameters=r[1], note=r[2])
            return IntentResponse(source="none", note=res.note)

    r = agent_svc.parse_intent(body.content)
    if r:
        return IntentResponse(source="rules", capability_id=r[0], parameters=r[1], note=r[2])
    return IntentResponse(source="none", note="无法识别该请求")


# ================================================================ Capabilities

@router.get("/capabilities", response_model=list[CapabilityOut])
def capabilities(domain: str | None = None):
    return [CapabilityOut(**c) for c in list_capabilities(domain)]


@router.get("/capabilities/resolve", response_model=ResolveOut)
def resolve_capability(capability_id: str, environment_id: str | None = None,
                       db: Session = Depends(get_db)):
    cap = get_capability(capability_id)
    if cap is None:
        raise HTTPException(404, f"能力不存在: {capability_id}")
    manifest: Manifest | None = None
    if environment_id:
        env = db.get(ComputeEnvironment, environment_id)
        if env and env.manifest:
            manifest = Manifest(**env.manifest)
    results = []
    for impl in cap["implementations"]:
        tools = impl.get("tools", [])
        runtime_id = None
        reason = ""
        available = False
        if manifest is None:
            reason = "未发现环境（先执行环境发现）"
        else:
            for t in manifest.tools:
                if t.tool_id in tools and t.status == "healthy" and t.runtime_id:
                    runtime_id = t.runtime_id
                    available = True
                    break
            if not available:
                missing = [t for t in tools if manifest.tool_status(t) != "healthy"]
                reason = f"缺少工具: {', '.join(missing)}"
        results.append({"id": impl["id"], "language": impl["language"],
                        "available": available, "runtime_id": runtime_id, "reason": reason})
    return ResolveOut(capability_id=capability_id, implementations=results)


@router.get("/capabilities/{capability_id}", response_model=CapabilityOut)
def capability_detail(capability_id: str):
    c = get_capability(capability_id)
    if c is None:
        raise HTTPException(404, f"能力不存在: {capability_id}")
    return CapabilityOut(**c)


# ================================================================ Events

@router.get("/events/{event_id}", response_model=EventOut)
def event_detail(event_id: str, db: Session = Depends(get_db)):
    return _event_out(_get_event(db, event_id), db)


@router.get("/events/{event_id}/logs")
def event_logs(event_id: str):
    ev = None
    db = SessionLocal()
    try:
        ev = _get_event(db, event_id)
        if ev.log_path and Path(ev.log_path).exists():
            return {"event_id": event_id, "logs": Path(ev.log_path).read_text(encoding="utf-8")}
        return {"event_id": event_id, "logs": ""}
    finally:
        db.close()


@router.post("/events/{event_id}/rerun", response_model=EventOut)
def rerun_event(event_id: str, body: RerunBody, db: Session = Depends(get_db)):
    original = _get_event(db, event_id)
    conv = db.get(Conversation, original.conversation_id)
    if conv is None:
        raise HTTPException(400, "原事件没有关联对话，无法重跑")
    try:
        ev = agent_svc.rerun_event(db, conv, original, body.parameters)
    except agent_svc.PlanError as e:
        raise HTTPException(400, str(e))
    return _event_out(ev, db)


@router.post("/events/{event_id}/diagnose")
def diagnose_event(event_id: str, db: Session = Depends(get_db)):
    """失败诊断：分析失败原因 + 参数修正建议（错误恢复循环）。"""
    ev = _get_event(db, event_id)
    from ..services.diagnostics import diagnose_failure
    return diagnose_failure(ev)


@router.post("/events/{event_id}/rstudio")
def rstudio_handoff(event_id: str, db: Session = Depends(get_db)):
    """生成 RStudio 手动交接包（analysis.R + prior 加载器 + MANIFEST + README）。

    仅支持 R 类 implementation 的事件。生成后返回包信息;产物由用户在
    RStudio 中运行,之后通过「导入结果」端点注册回 BioAgent。
    """
    ev = _get_event(db, event_id)
    impl = ev.implementation or ""
    from ..services import rstudio as rs
    if impl not in rs._R_IMPLS:
        raise HTTPException(400,
            f"当前事件 implementation={impl} 不是 R 类能力,无法生成 RStudio 交接包")
    project = db.get(Project, ev.project_id)
    if project is None:
        raise HTTPException(404, f"项目不存在: {ev.project_id}")
    info = rs.build_package(db, ev, project)
    return info


@router.get("/events/{event_id}/rstudio/zip")
def rstudio_zip(event_id: str, db: Session = Depends(get_db)):
    """下载 RStudio 交接包为 zip(便于在本地 RStudio 桌面运行)。"""
    ev = _get_event(db, event_id)
    impl = ev.implementation or ""
    from ..services import rstudio as rs
    if impl not in rs._R_IMPLS:
        raise HTTPException(400, "该事件不是 R 类能力,没有交接包")
    project = db.get(Project, ev.project_id)
    info = rs.build_package(db, ev, project)
    dest = Path(info["package_dir"]) / "rstudio_handoff.zip"
    rs.write_zip(info, dest)
    return FileResponse(dest, media_type="application/zip",
                        filename=f"rstudio_handoff_{event_id}.zip")


class RStudioImportBody(BaseModel):
    """导入结果:从交接包输出目录扫描并注册,或显式传产物路径。"""
    output_dir: str = ""          # 要扫描的目录(默认事件 rstudio_output)
    name: str = ""                # 结果数据集名(可选,默认取产物名)
    dtype: str = ""               # 结果 dtype(scrna/bulk_rna;留空则按格式推断)
    phase: str = ""               # 结果阶段(留空用能力契约的 resulting_phase)


@router.post("/events/{event_id}/rstudio/import")
def rstudio_import(event_id: str, body: RStudioImportBody,
                   db: Session = Depends(get_db)):
    """导入 RStudio 手动分析产物,注册为新 Dataset/Artifact 并延续 DAG 链路。

    手动分析成功后,用户在界面上触发「导入结果」。产物写入事件目录的
    rstudio_output/,这里扫描并注册,并建立 DAG 链路,使下游能力可以消费这些产物。
    """
    ev = _get_event(db, event_id)
    if ev.status in (EventStatus.succeeded, EventStatus.failed) and not body.output_dir:
        # 允许对已成功/失败事件导入新的手动结果(以 event 的 rstudio_output 为准)
        pass
    project = db.get(Project, ev.project_id)
    from ..services import rstudio as rs
    from ..services.execution import project_dir

    evdir = project_dir(project.id) / "events" / ev.id
    out_dir = Path(body.output_dir) if body.output_dir else (evdir / "rstudio_output")

    files = rs.scan_outputs(out_dir)
    if not files:
        raise HTTPException(400, f"未在 {out_dir} 找到可用产物文件(csv/h5ad/png/pdf/html/bam)")

    cap = get_capability(ev.capability_id)
    resulting_phase = (cap or {}).get("resulting_phase") or body.phase or "raw"
    input_dataset_id = (ev.inputs or {}).get("dataset")
    input_dataset = db.get(Dataset, input_dataset_id) if input_dataset_id else None

    artifact_ids: list[str] = []
    dataset_ids: list[str] = []
    for p in files:
        suffix = p.suffix.lstrip(".").lower()
        art_kind = {"csv": ArtifactKind.csv, "png": ArtifactKind.figure,
                    "pdf": ArtifactKind.pdf, "html": ArtifactKind.report,
                    "h5ad": ArtifactKind.h5ad, "bam": ArtifactKind.bam}.get(suffix)
        if art_kind is None:
            art_kind = ArtifactKind.other
        art = Artifact(id=new_id("art"), project_id=project.id, event_id=ev.id,
                       kind=art_kind, name=p.name, path=str(p),
                       mime=_mime_of(p.name), size_bytes=p.stat().st_size if p.exists() else 0)
        db.add(art)
        artifact_ids.append(art.id)

        # 数据集:仅对 csv/h5ad 注册(它们可被下游能力消费)
        if suffix in ("csv", "h5ad"):
            dtype = body.dtype or ("scrna" if suffix == "h5ad" else "bulk_rna")
            ds_name = body.name or p.stem or p.name
            # 避免与现有同名冲突
            base_name = ds_name; i = 2
            while db.query(Dataset).filter(Dataset.project_id == project.id,
                                           Dataset.name == ds_name).first():
                ds_name = f"{base_name}_{i}"; i += 1
            d = Dataset(id=new_id("ds"), project_id=project.id, name=ds_name,
                        dtype=DatasetType(dtype), format="h5ad" if suffix == "h5ad" else "csv",
                        location=str(p), phase=resulting_phase,
                        parent_dataset_id=input_dataset.id if input_dataset else None,
                        source_event_id=ev.id,
                        metadata_={"phase": resulting_phase, "imported_from": "rstudio"})
            db.add(d)
            dataset_ids.append(d.id)
            db.flush()

    ev.output = {"datasets": dataset_ids, "artifacts": artifact_ids}
    ev.status = EventStatus.succeeded
    ev.finished_at = ev.finished_at or utcnow()
    ev.metrics = {**ev.metrics, "imported_from_rstudio": True, "output_dir": str(out_dir)}
    db.add(ev)

    # DAG 边:输入数据集的产生事件 → 本事件(depends_on)
    if input_dataset and input_dataset.source_event_id and input_dataset.source_event_id != ev.id:
        if not db.query(EventLink).filter_by(
                parent_event_id=input_dataset.source_event_id,
                child_event_id=ev.id).first():
            db.add(EventLink(id=new_id("link"),
                             parent_event_id=input_dataset.source_event_id,
                             child_event_id=ev.id, relation=EventRelation.depends_on))
    db.commit()

    return {
        "event_id": event_id, "imported": True,
        "datasets": dataset_ids, "artifacts": artifact_ids,
        "files": [str(p) for p in files],
    }


def _mime_of(name: str) -> str:
    s = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {"csv": "text/csv", "png": "image/png", "pdf": "application/pdf",
            "html": "text/html", "h5ad": "application/x-hdf5",
            "bam": "application/octet-stream", "tsv": "text/tab-separated-values",
            "txt": "text/plain"}.get(s, "application/octet-stream")


@router.get("/events/{event_id}/stream")
def event_stream(event_id: str, token: str = "", db: Session = Depends(get_db)):
    """SSE 实时日志流：推送事件执行日志（增量），事件结束推送 done。"""
    import time

    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(401, "未认证")
    ev = _get_event(db, event_id)
    path = ev.log_path

    def generate():
        offset = 0
        while True:
            if path and Path(path).exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        f.seek(offset)
                        new = f.read()
                        offset += len(new)
                    for line in new.splitlines():
                        if line.strip():
                            yield f"data: {line}\n\n"
                except OSError:
                    pass
            s = SessionLocal()
            e = s.get(AnalysisEvent, event_id)
            finished = e is not None and e.status in ("succeeded", "failed", "cancelled")
            s.close()
            if finished:
                if path and Path(path).exists():
                    try:
                        with open(path, encoding="utf-8") as f:
                            f.seek(offset)
                            tail = f.read()
                        if tail.strip():
                            for line in tail.splitlines():
                                if line.strip():
                                    yield f"data: {line}\n\n"
                    except OSError:
                        pass
                yield "event: done\ndata: {}\n\n"
                break
            time.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/projects/{project_id}/dag", response_model=DagOut)
def project_dag(project_id: str, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    return dag_svc.build_dag(db, project_id)


# ================================================================ Artifacts

@router.get("/projects/{project_id}/artifacts", response_model=list[ArtifactOut])
def project_artifacts(project_id: str, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    arts = db.query(Artifact).filter(Artifact.project_id == project_id).order_by(
        Artifact.created_at.desc()).all()
    return [_artifact_out(a) for a in arts]


@router.get("/projects/{project_id}/report")
def project_report(project_id: str, db: Session = Depends(get_db)):
    """生成并返回项目分析报告 HTML（动态生成）。"""
    p = _get_project(db, project_id)
    from ..services.report import render_report_to_file
    path = render_report_to_file(db, p)
    return FileResponse(path, media_type="text/html", filename=path.name)


@router.get("/artifacts/{artifact_id}/content")
def artifact_content(artifact_id: str):
    db = SessionLocal()
    try:
        art = db.get(Artifact, artifact_id)
        if art is None:
            raise HTTPException(404, f"产物不存在: {artifact_id}")
        p = Path(art.path)
        if not p.exists():
            raise HTTPException(404, f"产物文件不存在: {art.path}")
        return FileResponse(p, media_type=art.mime, filename=art.name)
    finally:
        db.close()
