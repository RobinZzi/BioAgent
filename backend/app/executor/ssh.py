"""SSH Executor：后端直连远程服务器执行（用户选择方案 B）。

安全说明：这是「后端直连」模式，SSH 凭据加密存储于本地数据库、接口不回显。
架构上更推荐 Local Connector 模式（凭据本地化），本模式为简化接入提供。

流程：渲染脚本 → SSH 连接 → 上传脚本+输入数据 → 远程执行 → 下载产物 → 结构化结果。
"""
import shutil
from pathlib import Path

from . import templates
from .base import ArtifactOut, BaseExecutor, DatasetOut, ExecutionResult, TaskSpec

# 远程默认解释器（远程环境的具体 runtime 由服务器自身决定）
_DEFAULT_PYTHON = "python3"
_DEFAULT_R = "Rscript"
_DEFAULT_BASH = "bash"


class SSHExecutor(BaseExecutor):
    def __init__(self, project_dir: Path, host: str, port: int, user: str,
                 password: str | None = None, key_path: str | None = None):
        super().__init__(project_dir)
        self.host = host
        self.port = int(port or 22)
        self.user = user
        self.password = password
        self.key_path = key_path

    # ------------------------------------------------------------ 执行

    def execute(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        import paramiko

        outdir = Path(task.output_dir)
        outdir.mkdir(parents=True, exist_ok=True)
        remote_base = f"/tmp/bioagent/{task.task_id}"
        remote_out = f"{remote_base}/out"

        # 1. 渲染脚本
        try:
            script_name, script_text, run_cmd = self._render(task, capability, remote_base, remote_out)
        except ValueError as e:
            return ExecutionResult(ok=False, error={
                "stage": "render", "type": "UnsupportedImplementation",
                "message": str(e), "log_tail": []})

        local_script = outdir / script_name
        local_script.write_text(script_text, encoding="utf-8")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            connect_kwargs = dict(hostname=self.host, port=self.port, username=self.user,
                                  timeout=30, banner_timeout=30)
            if self.key_path:
                connect_kwargs["key_filename"] = self.key_path
            elif self.password:
                connect_kwargs["password"] = self.password
            else:
                connect_kwargs["allow_agent"] = True
            client.connect(**connect_kwargs)
        except Exception as e:  # noqa: BLE001
            client.close()
            return ExecutionResult(ok=False, error={
                "stage": "connect", "type": "SSHConnectError",
                "message": f"无法连接 {self.user}@{self.host}:{self.port} — {e}",
                "log_tail": []})

        try:
            sftp = client.open_sftp()
            # 2. 建目录 + 上传
            self._mkdir(sftp, remote_out)
            sftp.put(str(local_script), f"{remote_base}/{script_name}")
            input_remote = None
            if task.input_dataset_path and Path(task.input_dataset_path).exists():
                input_name = Path(task.input_dataset_path).name
                input_remote = f"{remote_base}/{input_name}"
                sftp.put(task.input_dataset_path, input_remote)
            sftp.close()

            # 3. 远程执行（用远程路径替换脚本里的本地占位）
            cmd = run_cmd(input_remote)
            stdin, stdout, stderr = client.exec_command(f"bash -lc {_q(cmd)}", timeout=7200)
            exit_code = stdout.channel.recv_exit_status()
            out_text = stdout.read().decode("utf-8", "replace")
            err_text = stderr.read().decode("utf-8", "replace")
            log_tail = (out_text + err_text).strip().splitlines()[-25:]

            if exit_code != 0:
                return ExecutionResult(ok=False, error={
                    "stage": "execute", "type": "RemoteScriptError",
                    "message": f"远程执行退出码 {exit_code}（{self.host}）",
                    "log_tail": log_tail}, log_lines=log_tail)

            # 4. 下载产物
            artifacts, datasets, warnings = self._download(sftp_client_fn=lambda: client.open_sftp(),
                                                            remote_out=remote_out, outdir=outdir)
            return ExecutionResult(ok=True,
                                   metrics={"host": self.host, "remote_dir": remote_out,
                                            "warnings": warnings},
                                   artifacts=artifacts, datasets=datasets,
                                   log_lines=log_tail)
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(ok=False, error={
                "stage": "transfer", "type": type(e).__name__,
                "message": f"远程传输/执行异常：{e}", "log_tail": []})
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------ helpers

    def _render(self, task: TaskSpec, capability: dict, remote_base: str, remote_out: str):
        impl = task.implementation
        inp = task.input_dataset_path or ""
        if impl == "scanpy":
            text = templates.render_scanpy_script(
                task.capability_id, task.parameters, inp, f"{remote_out}/output.h5ad", remote_out)
            return "run_scanpy.py", text, lambda rin: f"{_DEFAULT_PYTHON} {remote_base}/run_scanpy.py"
        if impl in ("DESeq2", "edgeR"):
            text = templates.render_deseq2_script(
                task.parameters, inp, f"{remote_out}/deseq2_results.csv", remote_out)
            return "run_deseq2.R", text, lambda rin: f"{_DEFAULT_R} {remote_base}/run_deseq2.R"
        if impl == "star":
            text = templates.render_star_bash(task.parameters, inp, remote_out)
            return "run_star.sh", text, lambda rin: f"{_DEFAULT_BASH} {remote_base}/run_star.sh"
        raise ValueError(f"SSH 执行器暂不支持 implementation={impl}")

    def _mkdir(self, sftp, path: str) -> None:
        parts = path.strip("/").split("/")
        cur = ""
        for p in parts:
            cur += "/" + p
            try:
                sftp.stat(cur)
            except IOError:
                try:
                    sftp.mkdir(cur)
                except IOError:
                    pass

    def _download(self, sftp_client_fn, remote_out: str, outdir: Path):
        import paramiko
        sftp = sftp_client_fn()
        artifacts: list[ArtifactOut] = []
        datasets: list[DatasetOut] = []
        warnings: list[str] = []
        try:
            names = sftp.listdir(remote_out)
        except IOError:
            sftp.close()
            return artifacts, datasets, ["远程输出目录为空或不存在"]
        for name in names:
            rp = f"{remote_out}/{name}"
            try:
                if sftp.stat(rp).st_mode & 0o170000 == 0o40000:  # 目录，跳过
                    continue
            except IOError:
                continue
            lp = outdir / name
            try:
                sftp.get(rp, str(lp))
            except IOError:
                warnings.append(f"下载失败: {name}")
                continue
            suffix = Path(name).suffix.lstrip(".").lower()
            if suffix == "h5ad":
                datasets.append(DatasetOut(name=name, dtype="scrna", format="h5ad",
                                           phase="raw", location=str(lp)))
                artifacts.append(ArtifactOut(kind="h5ad", name=name, path=str(lp),
                                             mime="application/x-hdf5"))
            elif suffix in ("png", "pdf"):
                artifacts.append(ArtifactOut(kind="figure", name=name, path=str(lp),
                                             mime="image/png"))
            elif suffix == "csv":
                artifacts.append(ArtifactOut(kind="csv", name=name, path=str(lp),
                                             mime="text/csv"))
            elif suffix == "html":
                artifacts.append(ArtifactOut(kind="report", name=name, path=str(lp),
                                             mime="text/html"))
            elif suffix == "bam":
                artifacts.append(ArtifactOut(kind="bam", name=name, path=str(lp),
                                             mime="application/octet-stream"))
        sftp.close()
        if not artifacts:
            warnings.append("远程未产生可识别的产物文件")
        return artifacts, datasets, warnings


def _q(cmd: str) -> str:
    import shlex
    return shlex.quote(cmd)
