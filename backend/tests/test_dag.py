"""Analysis DAG 构建测试。"""
from app.db import SessionLocal, init_db
from app.models import (
    AnalysisEvent, Conversation, EventLink, EventRelation, EventStatus,
    Project, new_id,
)
from app.services.dag import build_dag


def _setup():
    init_db()
    db = SessionLocal()
    p = Project(id=new_id("proj"), name="dag-test")
    db.add(p)
    c = Conversation(id=new_id("conv"), project_id=p.id)
    db.add(c)
    db.flush()
    evs = []
    for i, cap in enumerate(["scrna.qc", "scrna.normalization", "scrna.clustering"]):
        ev = AnalysisEvent(id=new_id("ev"), project_id=p.id, conversation_id=c.id,
                           capability_id=cap, status=EventStatus.succeeded,
                           parameters={}, inputs={}, output={}, metrics={})
        db.add(ev)
        evs.append(ev)
    db.flush()
    # qc → normalization → clustering
    db.add(EventLink(id=new_id("link"), parent_event_id=evs[0].id,
                     child_event_id=evs[1].id, relation=EventRelation.depends_on))
    db.add(EventLink(id=new_id("link"), parent_event_id=evs[1].id,
                     child_event_id=evs[2].id, relation=EventRelation.depends_on))
    db.commit()
    ids = [e.id for e in evs]
    db.close()
    return ids


def test_build_dag_edges_and_depth():
    ids = _setup()
    init_db()
    db = SessionLocal()
    p = db.query(Project).filter(Project.name == "dag-test").first()
    dag = build_dag(db, p.id)
    db.close()

    assert len(dag["nodes"]) == 3
    assert len(dag["edges"]) == 2
    assert dag["depth"][ids[0]] == 0
    assert dag["depth"][ids[1]] == 1
    assert dag["depth"][ids[2]] == 2
    # 边方向：parent(上游) → child(下游)
    assert (ids[0], ids[1]) in [(e["source"], e["target"]) for e in dag["edges"]]
