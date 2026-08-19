"""Analysis DAG 构建：事件节点 + 依赖边（depends_on / re_run / fork）。"""
from sqlalchemy.orm import Session

from ..models import AnalysisEvent, EventLink, EventStatus


def build_dag(db: Session, project_id: str) -> dict:
    events = (
        db.query(AnalysisEvent)
        .filter(AnalysisEvent.project_id == project_id)
        .order_by(AnalysisEvent.created_at.asc())
        .all()
    )
    nodes = []
    for ev in events:
        nodes.append({
            "id": ev.id,
            "capability_id": ev.capability_id,
            "implementation": ev.implementation,
            "status": ev.status.value if isinstance(ev.status, EventStatus) else ev.status,
            "parameters": ev.parameters,
            "message_id": ev.message_id,
            "output": ev.output,
            "error": ev.error,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        })

    links = (
        db.query(EventLink)
        .join(AnalysisEvent, AnalysisEvent.id == EventLink.child_event_id)
        .filter(AnalysisEvent.project_id == project_id)
        .all()
    )
    edges = [{"source": l.parent_event_id, "target": l.child_event_id,
              "relation": l.relation.value if hasattr(l.relation, "value") else l.relation}
             for l in links]

    # 分层（BFS 深度，供前端纵向渲染）
    depth: dict[str, int] = {}
    children: dict[str, list[str]] = {}
    indegree: dict[str, int] = {n["id"]: 0 for n in nodes}
    for e in edges:
        children.setdefault(e["source"], []).append(e["target"])
        indegree[e["target"]] = indegree.get(e["target"], 0) + 1
    queue = [nid for nid, d in indegree.items() if d == 0]
    for nid in queue:
        depth[nid] = 0
    while queue:
        cur = queue.pop(0)
        for nxt in children.get(cur, []):
            depth[nxt] = max(depth.get(nxt, 0), depth[cur] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    return {"nodes": nodes, "edges": edges, "depth": depth}
