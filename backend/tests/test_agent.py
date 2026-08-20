"""Agent 意图解析测试。"""
import pytest

from app.services.agent import _extract_params, parse_intent


@pytest.mark.parametrize("text,cap", [
    ("聚类", "scrna.clustering"),
    ("聚类，分辨率 1.0", "scrna.clustering"),
    ("qc", "scrna.qc"),
    ("帮我看看数据质量", "scrna.qc"),
    ("注释细胞类型", "scrna.annotation"),
    ("umap", "scrna.umap"),
    ("差异表达", "bulk_rna.differential_expression"),
    ("去接头裁切", "bulk_rna.trimming"),
    ("比对", "bulk_rna.alignment"),
    ("定量", "bulk_rna.quantification"),
    ("fastqc", "bulk_rna.fastqc"),
    ("gsea", "bulk_rna.gsea"),
])
def test_intent_mapping(text, cap):
    r = parse_intent(text)
    assert r is not None and r[0] == cap, f"{text!r} 应解析为 {cap}，实际 {r}"


def test_intent_unknown():
    assert parse_intent("今天天气怎么样") is None


def test_param_extraction():
    params = _extract_params("聚类，分辨率 1.0")
    assert params.get("resolution") == 1.0
    params = _extract_params("聚类 res=2.0")
    assert params.get("resolution") == 2.0
    params = _extract_params("min_genes 300")
    assert params.get("min_genes") == 300
