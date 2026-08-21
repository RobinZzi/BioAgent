"""执行编排：AnalysisEvent 全生命周期。

queued → running → succeeded / failed
成功时：写产物（Artifact）、建输出数据集（Dataset 版本链）、建 DAG 边
（depends_on / re_run）、更新会话上下文指针。失败时：结构化错误入库。
可复现性：确定性随机种子 + 环境工具版本快照记录在事件 metrics。
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..capabilities.definitions import get_capability, validate_parameters
from ..config import settings
from ..env.manifest import Manifest
from ..executor import get_executor
from ..executor.base import TaskSpec
from ..executor.remote import LocalConnectorExecutor
from ..models import (
    AnalysisEvent, Artifact, ArtifactKind, ComputeEnvironment, Conversation,
    Dataset, DatasetType, EnvStatus, EnvType, EventLink, EventRelation,
    EventStatus, Project, new_id, utcnow,
)

_PHASE_LABEL = {
    "raw": "原始数据", "qc": "质控完成", "normalized": "已标准化",
    "pca": "PCA 完成", "neighbors": "邻接图完成", "umap": "UMAP 完成",
    "clustered": "已聚类", "annotated": "已注释", "marker_genes": "标记基因完成",
    "de": "差异表达完成", "aligned": "已比对",
}


def project_dir(project_id: str) -> Path:
    return settings.data_dir / "projects" / project_id


def load_manifest(db: Session, env_id: str | None) -> Manifest | None:
    if not env_id:
        return None
    env = db.get(ComputeEnvironment, env_id)
    if env and env.manifest:
        return Manifest(**env.manifest)
    return None


def _is_mock_dataset(ds: Dataset) -> bool:
    """mock 占位文件以 `\\x89HDF placeholder` 或 `\\x89HDF mock` 开头
    （真实 h5ad 以 `\\x89HDF\\r\\n` 开头）。"""
    if ds.metadata_ and ds.metadata_.get("mock"):
        return True
    try:
        with open(ds.location, "rb") as f:
            head = f.read(16)
        return head.startswith(b"\x89HDF placeholder") or head.startswith(b"\x89HDF mock")
    except OSError:
        return False


_TOOL_MODULES = {
    "scanpy": "scanpy", "anndata": "anndata", "leidenalg": "leidenalg",
    "pandas": "pandas", "numpy": "numpy", "matplotlib": "matplotlib",
    "scipy": "scipy", "h5py": "h5py", "seaborn": "seaborn",
}


def _capture_env_snapshot(manifest: Manifest | None, runtime_id: str | None) -> dict | None:
    """捕获运行环境工具版本快照（可复现性：记录实际使用的工具版本）。"""
    import json as _json
    import subprocess

    if manifest is None or not runtime_id:
        return None
    py = None
    for rt in manifest.runtimes:
        if rt.id == runtime_id:
            if rt.type in ("python", "venv"):
                py = rt.path
            elif rt.type == "conda" and rt.path:
                py = str(Path(rt.path) / "bin" / "python")
            break
    if not py or not Path(py).exists():
        return None
    mods = {t.tool_id: _TOOL_MODULES[t.tool_id] for t in manifest.tools
            if t.runtime_id == runtime_id and t.language == "python"
            and t.tool_id in _TOOL_MODULES}
    if not mods:
        return None
    code = ("import importlib.metadata as m,json,sys;"
            "r={};"
            "[r.update({x:(lambda: m.version(x))()}) if True else None for x in sys.argv[1:]];"
            "print(json.dumps(r))")
    try:
        r = subprocess.run([py, "-c", code] + list(mods.values()),
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        tools = _json.loads(r.stdout.strip().splitlines()[-1])
        return {"runtime_id": runtime_id, "python": py, "tools": tools}
    except Exception:  # noqa: BLE001
        return None


def resolve_implementation(db: Session, manifest: Manifest | None, capability: dict,
                           force_impl: str | None = None) -> tuple[str, str | None]:
    """选择 implementation + runtime_id。manifest 缺失时回退默认实现。"""
    impls = capability["implementations"]
    if not impls:
        return "mock", None
    chosen = None
    if force_impl:
        chosen = next((i for i in impls if i["id"] == force_impl), None)
    if chosen is None:
        chosen = next((i for i in impls if i.get("default")), impls[0])
    runtime_id = None
    if manifest is not None:
        for i in impls:
            if i["id"] != chosen["id"]:
                continue
            for t in manifest.tools:
                if t.tool_id in i.get("tools", []) and t.status == "healthy" and t.runtime_id:
                    runtime_id = t.runtime_id
                    break
            break
    return chosen["id"], runtime_id


def create_and_run_event(
    db: Session,
    project: Project,
    conversation: Conversation,
    capability_id: str,
    params: dict,
    input_dataset: Dataset | None,
    message_id: str | None = None,
    relation_parent_id: str | None = None,
    relation: EventRelation = EventRelation.depends_on,
    force_impl: str | None = None,
) -> AnalysisEvent:
    """创建并执行单个 AnalysisEvent。失败以 event.status=failed 返回，不抛异常。"""
    capability = get_capability(capability_id)
    if capability is None:
        raise ValueError(f"未知 capability: {capability_id}")

    validated, errors = validate_parameters(capability, params)
    if errors:
        raise ValueError("参数校验失败: " + "; ".join(errors))

    event = AnalysisEvent(
        id=new_id("ev"), project_id=project.id, conversation_id=conversation.id,
        message_id=message_id, capability_id=capability_id,
        inputs={"dataset": input_dataset.id if input_dataset else None},
        parameters=validated,
        environment_id=conversation.active_environment_id,
    )
    relation = EventRelation(relation) if not isinstance(relation, EventRelation) else relation

    # 环境解析：对话指定 → 项目最近环境（自动回退）
    env_id = conversation.active_environment_id
    if env_id is None:
        fallback_env = (db.query(ComputeEnvironment)
                        .filter(ComputeEnvironment.project_id == project.id)
                        .order_by(ComputeEnvironment.discovered_at.desc()).first())
        if fallback_env is not None:
            env_id = fallback_env.id
            conversation.active_environment_id = fallback_env.id
    event.environment_id = env_id
    db.add(event)
    db.flush()

    outdir = project_dir(project.id) / "events" / event.id
    outdir.mkdir(parents=True, exist_ok=True)

    # 状态机：queued → running
    event.status = EventStatus.running
    event.started_at = utcnow()
    db.flush()

    manifest = load_manifest(db, env_id)
    implementation, runtime_id = resolve_implementation(db, manifest, capability, force_impl)
    event.implementation = implementation
    event.runtime_id = runtime_id

    # ---- 可复现性：确定性随机种子 + 环境工具版本快照 ----
    seed = int(hashlib.md5(event.id.encode()).hexdigest()[:8], 16)
    event.metrics["seed"] = seed
    snapshot = _capture_env_snapshot(manifest, runtime_id)
    if snapshot:
        event.metrics["env_snapshot"] = snapshot

    task = TaskSpec(
        task_id=event.id, capability_id=capability_id, implementation=implementation,
        runtime_id=runtime_id, inputs=event.inputs, parameters=validated,
        input_dataset_path=input_dataset.location if input_dataset else None,
        output_dir=str(outdir), environment_id=env_id, seed=seed,
    )

    executor = None
    mode_note = ""
    env = (db.get(ComputeEnvironment, env_id) if env_id else None)
    if env is not None and env.env_type == EnvType.remote and env.connector_url:
        # 远程 Connector 执行（Agent 不持有凭据）
        executor = LocalConnectorExecutor(project_dir(project.id), env.connector_url,
                                          env.connector_token or "")
        mode_note = f"remote connector ({env.connector_url})"
    elif env is not None and env.env_type == EnvType.remote and env.ssh_host:
        # SSH 直连执行（用户选择方案 B：后端直连，密码加密存储）
        from ..executor.ssh import SSHExecutor
        from ..utils.crypto import decrypt
        executor = SSHExecutor(project_dir(project.id), env.ssh_host, env.ssh_port,
                               env.ssh_user or "", decrypt(env.ssh_password or ""),
                               env.ssh_key_path)
        mode_note = f"ssh ({env.ssh_user}@{env.ssh_host}:{env.ssh_port})"
    elif settings.executor_mode == "auto" and input_dataset is not None and _is_mock_dataset(input_dataset):
        # mock 占位数据 → 沿用 mock 执行（真实 scanpy 读不了占位文件）
        from ..executor.mock import MockExecutor
        executor = MockExecutor(project_dir(project.id))
        mode_note = "mock (auto, 输入数据集为 mock 占位；真实执行需要真实 h5ad)"
    else:
        executor, mode_note, eff_runtime = get_executor(
            project_dir(project.id), manifest, capability_id, implementation,
            preferred_runtime=runtime_id)
        if eff_runtime and eff_runtime != runtime_id:
            runtime_id = eff_runtime
            event.runtime_id = runtime_id
            task.runtime_id = runtime_id
    result = executor.execute(task, capability)
    result.metrics.setdefault("executor_mode", mode_note)

    # 执行日志落盘（executor 已实时写入则保留，否则写 result.log_lines）
    log_path = outdir / "execution.log"
    if not log_path.exists() or log_path.stat().st_size == 0:
        log_path.write_text("\n".join(result.log_lines or []) + "\n", encoding="utf-8")
    event.log_path = str(log_path)

    if not result.ok:
        event.status = EventStatus.failed
        event.error = result.error
        event.finished_at = utcnow()
        db.flush()
        _link(db, event, input_dataset, relation_parent_id, relation)
        db.commit()
        return event

    # ---- 成功：注册产物与数据集 ----
    artifact_ids: list[str] = []
    for a in result.artifacts:
        p = Path(a.path)
        art = Artifact(
            id=new_id("art"), project_id=project.id, event_id=event.id,
            kind=ArtifactKind(a.kind), name=a.name, path=str(p), mime=a.mime,
            size_bytes=p.stat().st_size if p.exists() else 0,
        )
        db.add(art)
        artifact_ids.append(art.id)

    dataset_ids: list[str] = []
    resulting_phase = capability.get("resulting_phase")
    for d in result.datasets:
        parent_id = input_dataset.id if input_dataset else None
        # 数据集阶段以 capability 契约为准（本地执行器不感知 resulting_phase）
        phase = resulting_phase or d.phase
        ds = Dataset(
            id=new_id("ds"), project_id=project.id, name=d.name,
            dtype=DatasetType(d.dtype), format=d.format, location=d.location,
            phase=phase, parent_dataset_id=parent_id,
            source_event_id=event.id, metadata_={**d.metadata, "phase": phase},
        )
        db.add(ds)
        dataset_ids.append(ds.id)

    db.flush()
    event.output = {"datasets": dataset_ids, "artifacts": artifact_ids}
    event.metrics = result.metrics
    event.status = EventStatus.succeeded
    event.finished_at = utcnow()

    # ---- DAG 边 ----
    _link(db, event, input_dataset, relation_parent_id, relation)

    # ---- 更新会话上下文指针（评审结论：指针式上下文）----
    if dataset_ids:
        newest = db.get(Dataset, dataset_ids[-1])
        conversation.current_dataset_id = newest.id
        conversation.current_phase = capability.get("resulting_phase") or newest.phase
        conversation.analysis_state = {
            "label": _PHASE_LABEL.get(conversation.current_phase, conversation.current_phase),
            "summary": _summarize(capability, result.metrics),
            "capability": capability_id,
        }

    db.commit()
    db.refresh(event)
    return event


def _link(db: Session, event: AnalysisEvent, input_dataset: Dataset | None,
          relation_parent_id: str | None, relation: EventRelation) -> None:
    # depends_on：输入数据集的产生事件 → 本事件
    if input_dataset and input_dataset.source_event_id and input_dataset.source_event_id != event.id:
        if not db.query(EventLink).filter_by(parent_event_id=input_dataset.source_event_id,
                                             child_event_id=event.id).first():
            db.add(EventLink(id=new_id("link"), parent_event_id=input_dataset.source_event_id,
                             child_event_id=event.id, relation=EventRelation.depends_on))
    # re_run / fork：显式父事件
    if relation_parent_id and relation_parent_id != event.id:
        if not db.query(EventLink).filter_by(parent_event_id=relation_parent_id,
                                             child_event_id=event.id).first():
            db.add(EventLink(id=new_id("link"), parent_event_id=relation_parent_id,
                             child_event_id=event.id, relation=relation))


def _summarize(capability: dict, metrics: dict) -> str:
    cap_id = capability["capability_id"]
    name = capability["name"]
    if cap_id == "scrna.clustering":
        return f"{name}完成：resolution={metrics.get('resolution')}，共 {metrics.get('n_clusters')} 个簇"
    if cap_id == "scrna.qc":
        return f"{name}完成：{metrics.get('cells_before')} → {metrics.get('cells_after')} 个细胞"
    if cap_id == "scrna.annotation":
        return f"{name}完成：{', '.join(metrics.get('cell_types', [])[:5])}"
    if cap_id == "bulk_rna.differential_expression":
        return f"{name}完成：上调 {metrics.get('n_up')} / 下调 {metrics.get('n_down')}"
    if cap_id == "scrna.inspect":
        return f"{name}完成：{metrics.get('n_cells')} 细胞 × {metrics.get('n_genes')} 基因"
    if metrics:
        return f"{name}完成"
    return f"{name}完成"
