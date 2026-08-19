"""Seed 演示数据：跑通 MVP 最小纵向切片（mock 模式）。

链路：创建 Project → 注册数据集 → 环境发现 → 对话消息
      （检查 → QC → 聚类(链式) → 换分辨率重跑 → 注释）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.env.discovery import discover_local  # noqa: E402
from app.models import (  # noqa: E402
    ComputeEnvironment, Conversation, Dataset, DatasetType, EnvStatus,
    EnvType, Message, MessageRole, Project, new_id, utcnow,
)
from app.services import agent as agent_svc  # noqa: E402


def main() -> None:
    settings.executor_mode = os.environ.get("BIOAGENT_EXECUTOR_MODE", "mock")
    init_db()
    db = SessionLocal()
    try:
        # 已存在则跳过
        if db.query(Project).filter(Project.name == "HCC Single-cell Analysis").first():
            print("演示项目已存在，跳过 seed。")
            return

        print(f"执行器模式: {settings.executor_mode}")
        project = Project(id=new_id("proj"), name="HCC Single-cell Analysis",
                          description="HCC 单细胞数据分析（演示）",
                          data_source="local", compute_location="local")
        db.add(project)
        db.flush()

        # 注册原始数据集（mock 占位）
        raw = Dataset(id=new_id("ds"), project_id=project.id, name="HCC_raw.h5ad",
                      dtype=DatasetType.scrna, format="h5ad", phase="raw",
                      location=str(Path(settings.data_dir) / "projects" / project.id
                                   / "datasets" / "HCC_raw.h5ad"),
                      metadata_={"n_cells_mock": 12000, "note": "10x 3' v3 建库"})
        db.add(raw)

        # 环境发现（真实探测本机）
        print("正在环境发现…")
        manifest = discover_local(timeout=30)
        env = ComputeEnvironment(id=new_id("env"), project_id=project.id,
                                 name="本机环境", env_type=EnvType.local,
                                 manifest=manifest.model_dump(),
                                 status=EnvStatus.healthy if manifest.runtimes else EnvStatus.degraded,
                                 discovered_at=utcnow())
        db.add(env)

        conversation = Conversation(id=new_id("conv"), project_id=project.id,
                                    title="HCC 主分析流程",
                                    active_environment_id=env.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        print("本机 manifest:",
              f"{len(manifest.runtimes)} runtimes, {len(manifest.tools)} tools")
        for t in manifest.tools:
            print(f"  tool {t.tool_id} @ {t.runtime_id} [{t.status}]")

        # 对话消息（同步执行，模拟完整分析）
        messages = [
            "帮我看看这个数据质量",
            "QC",
            "聚类，分辨率 0.5",
            "换个分辨率 1.0 重新聚类",
            "注释细胞类型",
        ]
        for text in messages:
            print(f"\n>>> {text}")
            result = agent_svc.handle_message(db, conversation, text)
            for ev in result["events"]:
                st = ev.status.value if hasattr(ev.status, "value") else ev.status
                print(f"    {ev.capability_id}: {st} (impl={ev.implementation})")
            print("   assistant:", result["assistant_message"].content.splitlines()[0])

        db.refresh(conversation)
        print("\n上下文指针:", conversation.current_dataset_id,
              "phase:", conversation.current_phase)
        print("Seed 完成。启动后端: backend/.venv/bin/uvicorn app.main:app --port 8000")
    finally:
        db.close()


if __name__ == "__main__":
    main()
