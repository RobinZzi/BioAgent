"""Local Connector Executor：通过 Connector 协议在远程执行。

安全模型（见 docs §10）：后端/Agent 不持有任何 SSH 凭据。Connector 运行在
持有用户身份（SSH Key / 凭据）的机器上，只接受结构化 Task + 共享令牌。
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

from .base import BaseExecutor, ExecutionResult, TaskSpec


class LocalConnectorExecutor(BaseExecutor):
    """把 Task 通过 HTTP 协议提交给 Connector，轮询/同步返回结构化结果。"""

    def __init__(self, project_dir: Path, connector_url: str, token: str):
        super().__init__(project_dir)
        self.connector_url = connector_url.rstrip("/")
        self.token = token

    def execute(self, task: TaskSpec, capability: dict) -> ExecutionResult:
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
            return ExecutionResult.from_dict(body)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:400]
            return ExecutionResult(ok=False, error={
                "stage": "connector", "type": "HTTPError",
                "message": f"Connector 返回 {e.code}: {detail}", "log_tail": []})
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(ok=False, error={
                "stage": "connector", "type": type(e).__name__,
                "message": f"无法连接 Connector: {e}", "log_tail": []})

    # ------------------------------------------------------------ 协议调用

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
