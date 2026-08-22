// 能力名双语映射（供多个组件共用）
import type { Lang } from './i18n'

const CAP_ZH: Record<string, string> = {
  'scrna.import_10x': '10x 下机导入', 'scrna.import_mtx': '10x 矩阵导入',
  'scrna.inspect': '数据检查', 'scrna.qc': '细胞 QC', 'scrna.normalization': '标准化',
  'scrna.hvg': '高变基因', 'scrna.pca': 'PCA', 'scrna.neighbors': '邻接图',
  'scrna.umap': 'UMAP', 'scrna.clustering': '聚类', 'scrna.marker_genes': '标记基因',
  'scrna.annotation': '细胞注释',
  'bulk_rna.inspect': '数据检查', 'bulk_rna.qc': 'QC', 'bulk_rna.normalization': '标准化',
  'bulk_rna.fastqc': 'FastQC', 'bulk_rna.trimming': '去接头裁切',
  'bulk_rna.alignment': '序列比对', 'bulk_rna.quantification': '基因定量',
  'bulk_rna.differential_expression': '差异表达', 'bulk_rna.volcano': '火山图',
  'bulk_rna.heatmap': '热图', 'bulk_rna.go_enrichment': 'GO 富集', 'bulk_rna.gsea': 'GSEA',
  'scatac.qc': 'ATAC 质控', 'scatac.clustering': 'ATAC 聚类',
  'spatial.qc': '空间质控', 'spatial.clustering': '空间聚类',
  'methylation.qc': '甲基化质控', 'methylation.differential': '差异甲基化',
  'variant.calling': '变异检测', 'variant.annotation': '变异注释',
}

const CAP_EN: Record<string, string> = {
  'scrna.import_10x': '10x Import', 'scrna.import_mtx': '10x Matrix Import',
  'scrna.inspect': 'Inspect', 'scrna.qc': 'Cell QC', 'scrna.normalization': 'Normalize',
  'scrna.hvg': 'HVG', 'scrna.pca': 'PCA', 'scrna.neighbors': 'Neighbors',
  'scrna.umap': 'UMAP', 'scrna.clustering': 'Cluster', 'scrna.marker_genes': 'Markers',
  'scrna.annotation': 'Annotate',
  'bulk_rna.inspect': 'Inspect', 'bulk_rna.qc': 'QC', 'bulk_rna.normalization': 'Normalize',
  'bulk_rna.fastqc': 'FastQC', 'bulk_rna.trimming': 'Trim',
  'bulk_rna.alignment': 'Align', 'bulk_rna.quantification': 'Quantify',
  'bulk_rna.differential_expression': 'DE', 'bulk_rna.volcano': 'Volcano',
  'bulk_rna.heatmap': 'Heatmap', 'bulk_rna.go_enrichment': 'GO', 'bulk_rna.gsea': 'GSEA',
  'scatac.qc': 'ATAC QC', 'scatac.clustering': 'ATAC Cluster',
  'spatial.qc': 'Spatial QC', 'spatial.clustering': 'Spatial Cluster',
  'methylation.qc': 'Methylation QC', 'methylation.differential': 'Differential Methylation',
  'variant.calling': 'Variant Calling', 'variant.annotation': 'Variant Annotation',
}

export function capLabel(id: string, lang: Lang): string {
  const map = lang === 'en' ? CAP_EN : CAP_ZH
  return map[id] ?? id
}
