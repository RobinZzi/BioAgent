"""远程环境发现解析测试（mock SSH client）。"""
import json

from app.env.remote_discovery import discover_remote


class FakeChannel:
    def __init__(self, code=0):
        self.code = code

    def recv_exit_status(self):
        return self.code


class FakeOut:
    def __init__(self, text, code=0):
        self.text = text
        self.channel = FakeChannel(code)

    def read(self):
        return self.text.encode()


class FakeErr:
    def __init__(self, code=0):
        self.channel = FakeChannel(code)

    def read(self):
        return b""


class FakeClient:
    def __init__(self, cli_present=("star", "samtools", "sbatch"), tools=None):
        self.cli_present = cli_present
        self.tools = tools or {
            "scanpy": True, "anndata": True, "leidenalg": True, "pandas": True,
            "numpy": True, "matplotlib": True, "scipy": True, "h5py": True,
            "seaborn": True, "scvi-tools": False,
        }

    def exec_command(self, cmd, timeout=60):
        cmd = cmd.strip()
        if cmd.startswith("uname"):
            return None, FakeOut("Linux\nx86_64\n32"), FakeErr()
        if "python3 --version" in cmd:
            return None, FakeOut("Python 3.11.8\n"), FakeErr()
        if "R --version" in cmd:
            return None, FakeOut("R version 4.3.2\n"), FakeErr()
        if "importlib.util" in cmd:
            return None, FakeOut(json.dumps(self.tools) + "\n"), FakeErr()
        if cmd.startswith("command -v"):
            cli = cmd.split()[-1]
            if cli in self.cli_present:
                return None, FakeOut(f"/usr/bin/{cli}\n"), FakeErr()
            return None, FakeOut("", code=1), FakeErr(code=1)  # 找不到 → 非 0
        return None, FakeOut(""), FakeErr()


def test_discover_remote_basic():
    m = discover_remote(FakeClient())
    assert m.system.os == "linux"
    assert m.system.cpu_cores == 32
    assert any(r.id == "runtime_py3" for r in m.runtimes)
    assert any(r.id == "runtime_R" for r in m.runtimes)
    assert m.tool_status("scanpy") == "healthy"
    assert m.tool_status("scvi-tools") == "missing"
    assert m.compute.scheduler == "slurm"


def test_discover_remote_no_tools():
    m = discover_remote(FakeClient(tools={k: False for k in [
        "scanpy", "anndata", "leidenalg", "pandas", "numpy", "matplotlib",
        "scipy", "h5py", "seaborn", "scvi-tools"]}, cli_present=()))
    assert m.tool_status("scanpy") == "missing"
    assert m.compute.scheduler is None


def test_discover_remote_bash_tools():
    m = discover_remote(FakeClient(cli_present=("star", "samtools", "cutadapt", "featureCounts", "sbatch")))
    assert m.tool_status("star") == "healthy"
    assert m.tool_status("cutadapt") == "healthy"
    assert m.tool_status("featureCounts") == "healthy"
