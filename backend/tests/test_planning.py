"""前置链规划与执行衔接测试（内存 SQLite + mock 执行器）。"""
import pytest

from app.capabilities.definitions import PREREQ
from app.db import SessionLocal, init_db, Base, engine
from app.models import Conversation, Dataset, DatasetType, Project, new_id
from app.services.agent import _needed_chain, find_dataset, plan_capability


@pytest.fixture()
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


def test_needed_chain_scrna():
    """从 raw 说「聚类」→ 链应包含 QC→标准化→PCA→邻接→聚类。"""
    chain = _needed_chain("scrna.clustering", "raw")
    assert chain == ["scrna.qc", "scrna.normalization", "scrna.pca",
                     "scrna.neighbors", "scrna.clustering"]


def test_needed_chain_partial():
    """从 normalized 说「聚类」→ 只补 PCA→邻接→聚类。"""
    chain = _needed_chain("scrna.clustering", "normalized")
    assert chain == ["scrna.pca", "scrna.neighbors", "scrna.clustering"]


def test_needed_chain_fastq():
    """从 raw fastq 说「比对」→ 链应包含裁切→比对（fastqc 不自动跑）。"""
    chain = _needed_chain("bulk_rna.alignment", "raw")
    assert "bulk_rna.trimming" in chain and "bulk_rna.alignment" in chain
    assert "bulk_rna.fastqc" not in chain


def test_find_dataset(db_session):
    p = Project(id=new_id("proj"), name="t")
    db_session.add(p)
    db_session.flush()
    ds = Dataset(id=new_id("ds"), project_id=p.id, name="x.fastq.gz",
                 dtype=DatasetType.fastq, format="fastq.gz", phase="raw", location="/tmp/x")
    db_session.add(ds)
    db_session.commit()

    found = find_dataset(db_session, p.id, "fastq", "raw")
    assert found is not None and found.id == ds.id
    assert find_dataset(db_session, p.id, "fastq", "trimmed") is None


def test_plan_capability_direct(db_session):
    """当前阶段满足要求 → 直接执行目标能力。"""
    p = Project(id=new_id("proj"), name="t")
    db_session.add(p)
    db_session.flush()
    ds = Dataset(id=new_id("ds"), project_id=p.id, name="x.h5ad",
                 dtype=DatasetType.scrna, format="h5ad", phase="raw", location="/tmp/x")
    db_session.add(ds)
    conv = Conversation(id=new_id("conv"), project_id=p.id, current_phase="raw")
    db_session.add(conv)
    db_session.commit()

    steps = plan_capability(db_session, conv, "scrna.inspect", {})
    assert len(steps) == 1 and steps[0]["capability_id"] == "scrna.inspect"
    assert steps[0]["dataset_id"] == ds.id


def test_plan_capability_chain(db_session):
    """缺少前置 → 自动补链。"""
    p = Project(id=new_id("proj"), name="t")
    db_session.add(p)
    db_session.flush()
    ds = Dataset(id=new_id("ds"), project_id=p.id, name="x.h5ad",
                 dtype=DatasetType.scrna, format="h5ad", phase="raw", location="/tmp/x")
    db_session.add(ds)
    conv = Conversation(id=new_id("conv"), project_id=p.id, current_phase="raw")
    db_session.add(conv)
    db_session.commit()

    steps = plan_capability(db_session, conv, "scrna.clustering", {"resolution": 1.0})
    ids = [s["capability_id"] for s in steps]
    assert ids[-1] == "scrna.clustering"
    assert ids[0] == "scrna.qc"
    # 用户参数应落在最后一步（聚类）
    assert steps[-1]["params"]["resolution"] == 1.0
