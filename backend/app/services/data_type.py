"""fastq 数据类型自动识别（Bulk 下机 vs 10x 单细胞）。

基于文件名启发式：10x 特征（I1 索引文件、barcodes、matrix、S1_L00 命名）
→ 10x 单细胞；否则默认 Bulk RNA 下机。注册时自动标记到 dataset.metadata。
"""


def detect_fastq_type(name: str) -> str:
    """返回 '10x' 或 'bulk'。"""
    n = (name or "").lower()
    _10x_hints = ("i1", "barcode", "matrix", "s1_l00", "s2_l00", "s3_l00",
                  "s4_l00", "s5_l00", "s6_l00", "s7_l00", "s8_l00")
    if any(k in n for k in _10x_hints):
        return "10x"
    return "bulk"


def is_10x_fastq(dataset) -> bool:
    """从 dataset metadata 或文件名判断。"""
    meta = dataset.metadata_ or {}
    if meta.get("data_type"):
        return meta["data_type"] == "10x"
    return detect_fastq_type(dataset.name) == "10x"
