"""Local Connector Executor：通过 Connector 协议在远程执行。

安全模型（见 docs §10）：后端/Agent 不持有任何 SSH 凭据。Connector 运行在
持有用户身份（SSH Key / 凭据）的机器上，只接受结构化 Task + 共享令牌。

数据映射：执行前把本地产物文件上传到 Connector（/upload），执行后从
Connector 下载产物（/artifacts），使两端无需共享文件系统。
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

from .base import BaseExecutor, ExecutionResult, TaskSpec

_BOUNDARY = "----BioAgentXBoundary"


class LocalConnectorExecutor(BaseExecutor):
    """把 Task 通过 HTTP 协议提交给 Connector，同步返回结构化结果。"""

    def __init__(self, project_dir: Path, connector_url: str, token: str):
        super().__init__(project_dir)
        self.connector_url = connector_url.rstrip("/")
        self.token = token

    def execute(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        # 1. 上传输入文件到 Connector（跨机数据映射）
        remote_input = task.input_dataset_path
        if remote_input and Path(remote_input).exists() and Path(remote_input).is_file():
            name = Path(remote_input).name
            if not self._upload(task.task_id, name, remote_input):
                return ExecutionResult(ok=False, error={
                    "stage": "upload", "type": "UploadError",
                    "message": f"上传输入文件 {name} 到 Connector 失败", "log_tail": []})
        # 2. 提交执行
        try:
            payload = json.dumps({"task": task.__dict__}).encode("utf-8")
            req = urllib.request.Request(
                self.connector_url + "/execute",
                data=payload,
                headers={"Content-Type": "application/json",
                         "X-Connector-Token": self.token},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=7200) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:400]
            return ExecutionResult(ok=False, error={
                "stage": "connector", "type": "HTTPError",
                "message": f"Connector 返回 {e.code}: {detail}", "log_tail": []})
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(ok=False, error={
                "stage": "connector", "type": type(e).__name__,
                "message": f"无法连接 Connector: {e}", "log_tail": []})

        result = ExecutionResult.from_dict(body)
        # 3. 下载产物到本地 event 目录（远端产物回传）
        task_dir = Path(task.output_dir)
        task_dir.mkdir(parents=True, exist_ok=True)
        for art in result.artifacts:
            if not Path(art.path).exists():
                dest = task_dir / Path(art.path).name
                if self._download(task.task_id, Path(art.path).name, dest):
                    art.path = str(dest)
        for ds in result.datasets:
            if not Path(ds.location).exists():
                dest = task_dir / Path(ds.location).name
                if self._download(task.task_id, Path(ds.location).name, dest):
                    ds.location = str(dest)
        return result

    # ------------------------------------------------------------ 协议调用

    def _upload(self, task_id: str, filename: str, file_path: str) -> bool:
        try:
            body, ctype = self._multipart(file_path, filename)
            req = urllib.request.Request(
                self.connector_url + f"/upload/{task_id}/{filename}",
                data=body,
                headers={"Content-Type": ctype, "X-Connector-Token": self.token},
                method="POST")
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read().decode()).get("ok", False)
        except Exception:  # noqa: BLE001
            return False

    def _download(self, task_id: str, filename: str, dest: Path) -> bool:
        try:
            req = urllib.request.Request(
                self.connector_url + f"/artifacts/{task_id}/{filename}",
                headers={"X-Connector-Token": self.token}, method="GET")
            with urllib.request.urlopen(req, timeout=600) as resp:
                dest.write_bytes(resp.read())
            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _multipart(file_path: str, filename: str) -> tuple[bytes, str]:
        head = (f"--{_BOUNDARY}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n").encode()
        tail = f"\r\n--{_BOUNDARY}--\r\n".encode()
        return head + Path(file_path).read_bytes() + tail, f"multipart/form-data; boundary={_BOUNDARY}"

    def _get(self, path: str, timeout: float = 15.0) -> tuple[dict | None, str | None]:
        try:
            req = urllib.request.Request(
                self.connector_url + path,
                headers={"X-Connector-Token": self.token},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8")), None
        except Exception as e:  # noqa: BLE001
            return None, str(e)

    def discover(self) -> tuple[dict | None, str | None]:
        return self._get("/discover", timeout=60)

    def health(self) -> tuple[dict | None, str | None]:
        return self._get("/health", timeout=10)

    @staticmethod
    def test_connection(url: str, token: str) -> tuple[bool, str]:
        tmp = LocalConnectorExecutor(Path("."), url, token)
        data, err = tmp.health()
        if err:
            return False, f"连接失败: {err}"
        return data.get("ok", False), (data.get("detail") or "ok") if data else "ok"
