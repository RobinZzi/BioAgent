"""Slurm Executor（Connector 侧）。

把结构化 Task 包装为 sbatch 作业：渲染任务体脚本（python/R/bash 模板）→
构造 sbatch 头（参数白名单：threads；partition/mem 来自环境配置）→ 提交 →
轮询 sacct/squeue → 收集产物。任何失败返回结构化错误。
"""
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.executor.base import ArtifactOut, BaseExecutor, DatasetOut, ExecutionResult, TaskSpec  # noqa: E402
from app.executor import templates  # noqa: E402

_POLL_INTERVAL = float(os.environ.get("CONNECTOR_SLURM_POLL", "5"))
_TIMEOUT = float(os.environ.get("CONNECTOR_SLURM_TIMEOUT", "3600"))
_PARTITION = os.environ.get("CONNECTOR_SLURM_PARTITION", "")
_MEM_GB = os.environ.get("CONNECTOR_SLURM_MEM_GB", "8")

_TERMINAL_FAIL = {"FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY", "DEADLINE"}


class SlurmExecutor(BaseExecutor):
    def execute(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        if shutil.which("sbatch") is None:
            return ExecutionResult(ok=False, error={
                "stage": "submit", "type": "SchedulerUnavailable",
                "message": "Connector 上未找到 sbatch，无法提交 Slurm 作业（请安装 Slurm 或改用 local/mock 模式）",
                "log_tail": []})

        outdir = Path(task.output_dir)
        outdir.mkdir(parents=True, exist_ok=True)

        # 1. 渲染任务体
        try:
            body_path, run_cmd = self._render_body(task, capability, outdir)
        except ValueError as e:
            return ExecutionResult(ok=False, error={
                "stage": "render", "type": "UnsupportedImplementation",
                "message": str(e), "log_tail": []})

        # 2. 构造并提交 sbatch
        script = self._sbatch_script(task, outdir, run_cmd)
        script_path = outdir / "job.sbatch"
        script_path.write_text(script, encoding="utf-8")
        r = subprocess.run(["sbatch", str(script_path)], capture_output=True,
                           text=True, timeout=30)
        if r.returncode != 0:
            return ExecutionResult(ok=False, error={
                "stage": "submit", "type": "SbatchError",
                "message": f"sbatch 提交失败: {(r.stderr or r.stdout).strip()[:300]}",
                "log_tail": (r.stderr or r.stdout).strip().splitlines()[-10:]})
        m = re.search(r"Submitted batch job (\d+)", r.stdout)
        if not m:
            return ExecutionResult(ok=False, error={
                "stage": "submit", "type": "ParseError",
                "message": f"无法解析 sbatch 输出: {r.stdout[:200]}", "log_tail": []})
        job_id = m.group(1)

        # 3. 轮询
        deadline = time.monotonic() + _TIMEOUT
        state = "PENDING"
        while time.monotonic() < deadline:
            state = self._job_state(job_id)
            if state in ("COMPLETED", "COMPLETING"):
                break
            if state in _TERMINAL_FAIL:
                err_log = self._read_err(outdir, job_id)
                return ExecutionResult(ok=False, error={
                    "stage": "slurm", "type": "JobFailed",
                    "message": f"Slurm 作业 {job_id} 失败（state={state}）",
                    "log_tail": err_log})
            time.sleep(_POLL_INTERVAL)
        if state not in ("COMPLETED", "COMPLETING"):
            return ExecutionResult(ok=False, error={
                "stage": "slurm", "type": "Timeout",
                "message": f"Slurm 作业 {job_id} 轮询超时", "log_tail": []})

        # 4. 收集产物
        artifacts, datasets, warnings = self._collect_outputs(outdir)
        return ExecutionResult(
            ok=True, metrics={"scheduler": "slurm", "job_id": job_id,
                              "warnings": warnings},
            artifacts=artifacts, datasets=datasets,
            log_lines=[f"[slurm] job {job_id} completed (state={state})"])

    # ------------------------------------------------------------ helpers

    def _render_body(self, task: TaskSpec, capability: dict, outdir: Path) -> tuple[Path, str]:
        impl = task.implementation
        params = task.parameters
        inp = task.input_dataset_path or ""
        if impl == "scanpy":
            p = outdir / "run_scanpy.py"
            p.write_text(templates.render_scanpy_script(
                task.capability_id, params, inp, str(outdir / "output.h5ad"), str(outdir)),
                encoding="utf-8")
            py = self._runtime_python(task.runtime_id) or "python3"
            return p, f"{py} {p.name}"
        if impl in ("DESeq2", "edgeR"):
            p = outdir / "run_deseq2.R"
            p.write_text(templates.render_deseq2_script(
                params, inp, str(outdir / "deseq2_results.csv"), str(outdir)),
                encoding="utf-8")
            return p, f"Rscript {p.name}"
        if impl == "star":
            p = outdir / "run_star.sh"
            p.write_text(templates.render_star_bash(params, inp, str(outdir)), encoding="utf-8")
            return p, f"bash {p.name}"
        raise ValueError(f"Slurm 执行器暂不支持 implementation={impl}")

    def _runtime_python(self, runtime_id: str | None) -> str | None:
        from app.env.manifest import Manifest
        import json
        cached = _cached_manifest()
        if not cached or not runtime_id:
            return None
        for rt in cached.runtimes:
            if rt.id == runtime_id:
                if rt.type in ("python", "venv"):
                    return rt.path
                if rt.type == "conda" and rt.path:
                    return str(Path(rt.path) / "bin" / "python")
        return None

    def _sbatch_script(self, task: TaskSpec, outdir: Path, run_cmd: str) -> str:
        threads = int(task.parameters.get("threads", 1))
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=bioagent-{task.task_id[:12]}",
            f"#SBATCH --output={outdir}/slurm-%j.out",
            f"#SBATCH --error={outdir}/slurm-%j.err",
            f"#SBATCH --cpus-per-task={threads}",
            f"#SBATCH --mem={_MEM_GB}G",
        ]
        if _PARTITION:
            lines.append(f"#SBATCH --partition={_PARTITION}")
        lines += ["", f"cd {outdir}", run_cmd]
        return "\n".join(lines) + "\n"

    def _job_state(self, job_id: str) -> str:
        try:
            r = subprocess.run(["sacct", "-j", job_id, "-n", "-P", "-o", "State"],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()[-1].split("|")[0].strip().upper()
        except Exception:  # noqa: BLE001
            pass
        try:
            r = subprocess.run(["squeue", "-j", job_id, "-h", "-o", "%T"],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()[-1].upper()
        except Exception:  # noqa: BLE001
            pass
        return "UNKNOWN"

    def _read_err(self, outdir: Path, job_id: str) -> list[str]:
        for name in (f"slurm-{job_id}.err", f"slurm-{job_id}.out"):
            p = outdir / name
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-20:]
        return []

    def _collect_outputs(self, outdir: Path) -> tuple[list[ArtifactOut], list[DatasetOut], list[str]]:
        artifacts: list[ArtifactOut] = []
        datasets: list[DatasetOut] = []
        warnings: list[str] = []
        for p in sorted(outdir.iterdir()):
            if not p.is_file() or p.suffix in (".sbatch", ".sh", ".py", ".R"):
                continue
            suffix = p.suffix.lstrip(".").lower()
            if suffix == "h5ad":
                datasets.append(DatasetOut(name=p.name, dtype="scrna", format="h5ad",
                                           phase="raw", location=str(p)))
                artifacts.append(ArtifactOut(kind="h5ad", name=p.name, path=str(p),
                                             mime="application/x-hdf5"))
            elif suffix in ("png", "pdf"):
                artifacts.append(ArtifactOut(kind="figure", name=p.name, path=str(p),
                                             mime="image/png"))
            elif suffix == "csv":
                artifacts.append(ArtifactOut(kind="csv", name=p.name, path=str(p),
                                             mime="text/csv"))
            elif suffix == "html":
                artifacts.append(ArtifactOut(kind="report", name=p.name, path=str(p),
                                             mime="text/html"))
            elif suffix == "bam":
                artifacts.append(ArtifactOut(kind="bam", name=p.name, path=str(p),
                                             mime="application/octet-stream"))
        if not artifacts:
            warnings.append("输出目录中没有检测到产物文件")
        return artifacts, datasets, warnings


def _cached_manifest():
    """Connector 侧缓存的 Manifest（首次 /execute 时发现，TTL 120s）。"""
    import time as _t
    from app.env.discovery import discover_local
    from app.env.manifest import Manifest

    now = _t.monotonic()
    if _cached_manifest._data is not None and now - _cached_manifest._ts < 120:
        return _cached_manifest._data
    try:
        m = discover_local(timeout=float(os.environ.get("CONNECTOR_DISCOVER_TIMEOUT", "30")))
        _cached_manifest._data = m
        _cached_manifest._ts = now
        return m
    except Exception:  # noqa: BLE001
        return None


_cached_manifest._data = None
_cached_manifest._ts = 0.0
