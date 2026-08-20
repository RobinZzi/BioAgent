"""Capability 定义与参数校验测试。"""
import pytest

from app.capabilities.definitions import (
    CAPABILITIES, CAPABILITIES_BY_ID, PREREQ, get_capability,
    list_capabilities, phase_rank, validate_parameters,
)


def test_capability_catalog_complete():
    """能力目录完整：每个能力都有必填字段与实现。"""
    assert len(CAPABILITIES) >= 20
    for c in CAPABILITIES:
        assert c["capability_id"] in CAPABILITIES_BY_ID
        assert c["dataset_dtype"] in ("scrna", "bulk_rna", "fastq")
        assert c["requires_phase"]
        assert isinstance(c["implementations"], list)
        for impl in c["implementations"]:
            assert impl["id"] and impl["language"] in ("python", "r", "bash")


def test_prereq_references_valid():
    """前置依赖引用的能力必须存在。"""
    for cap_id, prereqs in PREREQ.items():
        assert cap_id in CAPABILITIES_BY_ID, f"{cap_id} 未定义"
        for p in prereqs:
            assert p in CAPABILITIES_BY_ID, f"{cap_id} 引用了未定义前置 {p}"


def test_fastq_pipeline_chain():
    """fastq 流水线前置链完整。"""
    assert PREREQ["bulk_rna.trimming"] == ["bulk_rna.fastqc"]
    assert PREREQ["bulk_rna.alignment"] == ["bulk_rna.trimming"]
    assert PREREQ["bulk_rna.quantification"] == ["bulk_rna.alignment"]


def test_validate_parameters_defaults():
    """参数校验：补默认值、拒绝越界值。"""
    cap = get_capability("scrna.clustering")
    validated, errs = validate_parameters(cap, {})
    assert not errs
    assert validated["resolution"] == 0.5

    validated, errs = validate_parameters(cap, {"resolution": 99})
    assert errs, "越界值应报错"

    validated, errs = validate_parameters(cap, {"resolution": 1.5})
    assert not errs and validated["resolution"] == 1.5


def test_phase_rank_ordering():
    """阶段序：链式推进的 rank 单调递增。"""
    # scRNA
    assert phase_rank("scrna", "raw") < phase_rank("scrna", "qc") < phase_rank("scrna", "normalized")
    assert phase_rank("scrna", "neighbors") < phase_rank("scrna", "clustered")
    # fastq
    assert phase_rank("bulk_rna", "raw") < phase_rank("bulk_rna", "trimmed") < phase_rank("bulk_rna", "aligned")
