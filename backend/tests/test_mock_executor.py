"""Mock 执行器产物生成测试。"""
import tempfile
from pathlib import Path

from app.executor.base import TaskSpec
from app.executor.mock import MockExecutor


def _run(cap_id: str, params: dict, input_path: str = "/tmp/in.h5ad"):
    ex = MockExecutor(Path(tempfile.mkdtemp()))
    task = TaskSpec(task_id="ev_test", capability_id=cap_id, implementation="mock",
                    runtime_id=None, inputs={}, parameters=params,
                    input_dataset_path=input_path,
                    output_dir=str(Path(tempfile.mkdtemp())))
    from app.capabilities.definitions import get_capability
    return ex.execute(task, get_capability(cap_id))


def test_clustering_mock():
    r = _run("scrna.clustering", {"resolution": 0.5})
    assert r.ok
    assert r.metrics["n_clusters"] >= 2
    assert any(a.kind == "figure" for a in r.artifacts)
    assert len(r.datasets) == 1 and r.datasets[0].phase == "clustered"


def test_quantification_mock():
    r = _run("bulk_rna.quantification", {"feature_type": "gene"}, input_path="/tmp/x.bam")
    assert r.ok
    assert any(a.name == "counts.csv" for a in r.artifacts)
    assert r.datasets and r.datasets[0].dtype == "bulk_rna" and r.datasets[0].phase == "raw"


def test_trimming_mock():
    r = _run("bulk_rna.trimming", {"min_length": 20}, input_path="/tmp/x.fastq.gz")
    assert r.ok
    assert r.datasets and r.datasets[0].phase == "trimmed"


def test_deterministic():
    """同一 task id 结果可复现。"""
    r1 = _run("scrna.clustering", {"resolution": 1.0})
    r2 = _run("scrna.clustering", {"resolution": 1.0})
    assert r1.metrics["n_clusters"] == r2.metrics["n_clusters"]
