"""Local Executor：真实本机执行（scanpy / R / bash 模板）。

- 校验参数 → 按 implementation 模板生成脚本 → 在指定 runtime 中执行
- 工具缺失或脚本失败 → 返回结构化错误（stage / type / message / log_tail）
- 收集 output 目录中的产物文件注册为 Artifact / Dataset
"""
import subprocess
from pathlib import Path

from ..env.manifest import Manifest
from . import templates
from .base import ArtifactOut, BaseExecutor, DatasetOut, ExecutionResult, TaskSpec


def _mime(name: str) -> str:
    from ..executor.mock import _mime as _m
    return _m(name)


class LocalExecutor(BaseExecutor):
    """真实本机执行器。"""

    def __init__(self, project_dir: Path, manifest: Manifest):
        super().__init__(project_dir)
        self.manifest = manifest

    # ------------------------------------------------------------ helpers

    def _runtime_python(self, runtime_id: str | None) -> str | None:
        """从 manifest 解析 runtime 对应的 python 可执行文件。"""
        if not runtime_id:
            return None
        for rt in self.manifest.runtimes:
            if rt.id == runtime_id:
                if rt.type in ("python", "venv"):
                    return rt.path
                if rt.type == "conda" and rt.path:
                    return str(Path(rt.path) / "bin" / "python")
        return None

    def _proc_env(self) -> dict:
        """子进程环境：matplotlib 缓存指到项目数据目录（避免 HOME 沙箱问题）。"""
        import os
        from ..config import settings
        env = dict(os.environ)
        env["MPLCONFIGDIR"] = str(settings.data_dir / ".mplcache")
        env.setdefault("MPLBACKEND", "Agg")
        return env


    def _run_stream(self, cmd: list, log_path: Path, timeout: int, env=None):
        """Popen 流式执行：逐行读子进程输出并实时追加到 log 文件。
        返回 (returncode, log_lines, error)。"""
        import os
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, env=env or os.environ)
        lines: list[str] = []
        try:
            for line in p.stdout:
                lines.append(line.rstrip())
                with open(log_path, "a") as f:
                    f.write(line)
        except Exception:  # noqa: BLE001
            pass
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            return None, lines, "timeout"
        return p.returncode, lines, None

    def _collect_outputs(self, output_dir: Path) -> tuple[list[ArtifactOut], list[DatasetOut], list[str]]:
        artifacts: list[ArtifactOut] = []
        datasets: list[DatasetOut] = []
        warnings: list[str] = []
        for p in sorted(output_dir.iterdir()):
            if not p.is_file():
                continue
            suffix = p.suffix.lstrip(".").lower()
            if suffix == "h5ad":
                datasets.append(DatasetOut(name=p.name, dtype="scrna", format="h5ad",
                                           phase="raw", location=str(p)))
                artifacts.append(ArtifactOut(kind="h5ad", name=p.name, path=str(p),
                                             mime=_mime(p.name)))
            elif suffix in ("png", "pdf"):
                artifacts.append(ArtifactOut(kind="figure", name=p.name, path=str(p),
                                             mime=_mime(p.name)))
            elif suffix == "csv":
                artifacts.append(ArtifactOut(kind="csv", name=p.name, path=str(p),
                                             mime=_mime(p.name)))
            elif suffix == "html":
                artifacts.append(ArtifactOut(kind="report", name=p.name, path=str(p),
                                             mime=_mime(p.name)))
            elif suffix == "bam":
                artifacts.append(ArtifactOut(kind="bam", name=p.name, path=str(p),
                                             mime=_mime(p.name)))
        if not artifacts:
            warnings.append("输出目录中没有检测到产物文件")
        return artifacts, datasets, warnings

    # ------------------------------------------------------------ dispatcher

    def execute(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        impl = task.implementation
        if impl in ("scanpy", "celltypist"):
            return self._run_scanpy(task, capability)
        if impl in ("DESeq2", "edgeR", "seurat"):
            return self._run_r(task, capability)
        if impl in ("star", "fastqc", "cutadapt", "featureCounts", "cellranger"):
            return self._run_bash(task, capability)
        return ExecutionResult(ok=False, error={
            "stage": "resolve", "type": "UnsupportedImplementation",
            "message": f"本地执行器暂不支持 implementation={impl}",
            "log_tail": []})

    # ------------------------------------------------------------ scanpy

    def _run_scanpy(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        outdir = Path(task.output_dir)
        outdir.mkdir(parents=True, exist_ok=True)
        py = self._runtime_python(task.runtime_id)
        if not py:
            return ExecutionResult(ok=False, error={
                "stage": "resolve", "type": "RuntimeNotFound",
                "message": f"manifest 中找不到 runtime {task.runtime_id}，无法定位 python 解释器",
                "log_tail": []})

        if task.implementation == "celltypist":
            script = templates.render_celltypist_script(
                task.capability_id, task.parameters, task.input_dataset_path or "",
                str(outdir / "output.h5ad"), str(outdir), seed=task.seed or 42)
        elif task.implementation == "omics-python":
            script = templates.render_omics_python_script(
                task.capability_id, task.parameters, task.input_dataset_path or "",
                str(outdir / "output.h5ad"), str(outdir), seed=task.seed or 42)
        else:
            script = templates.render_scanpy_script(
                task.capability_id, task.parameters, task.input_dataset_path or "",
                str(outdir / "output.h5ad"), str(outdir), seed=task.seed or 42)
        script_path = outdir / "run_scanpy.py"
        script_path.write_text(script, encoding="utf-8")

        log_path = outdir / "execution.log"
        code, lines, err = self._run_stream([py, str(script_path)], log_path, 3600, env=self._proc_env())
        if err == "timeout":
            return ExecutionResult(ok=False, error={
                "stage": "execute", "type": "Timeout",
                "message": "scanpy 脚本执行超时（>3600s）", "log_tail": lines[-20:]}, log_lines=lines[-20:])
        log_tail = lines[-20:]
        if code != 0:
            return ExecutionResult(ok=False, error={
                "stage": "execute", "type": "ScriptError",
                "message": f"scanpy 脚本退出码 {code}",
                "log_tail": log_tail}, log_lines=log_tail)

        artifacts, datasets, warnings = self._collect_outputs(outdir)
        return ExecutionResult(
            ok=True, metrics={"impl": "scanpy", "warnings": warnings},
            artifacts=artifacts, datasets=datasets,
            log_lines=(r.stdout + r.stderr).splitlines()[-30:])

    # ------------------------------------------------------------ R

    def _run_r(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        outdir = Path(task.output_dir)
        outdir.mkdir(parents=True, exist_ok=True)
        rscript = "Rscript"
        script = templates.render_deseq2_script(
            task.parameters, task.input_dataset_path or "",
            str(outdir / "deseq2_results.csv"), str(outdir))
        script_path = outdir / "run_deseq2.R"
        script_path.write_text(script, encoding="utf-8")
        log_path = outdir / "execution.log"
        code, lines, err = self._run_stream([rscript, str(script_path)], log_path, 3600, env=self._proc_env())
        if err == "timeout":
            return ExecutionResult(ok=False, error={
                "stage": "execute", "type": "Timeout",
                "message": "R 脚本执行超时（>3600s）", "log_tail": []})
        log_tail = lines[-20:]
        if code != 0:
            return ExecutionResult(ok=False, error={
                "stage": "execute", "type": "ScriptError",
                "message": f"Rscript 退出码 {code}（检查是否安装 DESeq2）",
                "log_tail": log_tail})
        artifacts, datasets, warnings = self._collect_outputs(outdir)
        return ExecutionResult(ok=True, metrics={"impl": task.implementation},
                               artifacts=artifacts, datasets=datasets,
                               log_lines=lines[-30:])

    # ------------------------------------------------------------ bash

    def _run_bash(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        outdir = Path(task.output_dir)
        outdir.mkdir(parents=True, exist_ok=True)
        if task.implementation == "gatk":
            script = templates.render_gatk_bash(task.capability_id, task.parameters,
                                                task.input_dataset_path or "", str(outdir))
        else:
            script = templates.render_bash_script(task.implementation, task.parameters,
                                                  task.input_dataset_path or "", str(outdir))
        script_path = outdir / "run.sh"
        script_path.write_text(script, encoding="utf-8")
        log_path = outdir / "execution.log"
        code, lines, err = self._run_stream(["bash", str(script_path)], log_path, 7200, env=self._proc_env())
        if err == "timeout":
            return ExecutionResult(ok=False, error={
                "stage": "execute", "type": "Timeout",
                "message": "STAR 比对超时（>7200s）", "log_tail": []})
        log_tail = lines[-20:]
        if code != 0:
            return ExecutionResult(ok=False, error={
                "stage": "execute", "type": "ScriptError",
                "message": f"STAR 脚本退出码 {code}（检查 STAR/samtools 是否安装）",
                "log_tail": log_tail})
        artifacts, datasets, warnings = self._collect_outputs(outdir)
        return ExecutionResult(ok=True, metrics={"impl": "star"},
                               artifacts=artifacts, datasets=datasets,
                               log_lines=(r.stdout + r.stderr).splitlines()[-30:])
