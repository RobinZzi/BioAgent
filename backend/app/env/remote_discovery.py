"""远程环境发现：通过 SSH 在远程服务器上探测 runtimes / tools / compute。

复用 env.manifest 的 Manifest 模型，输出与本地发现一致的标准 Manifest，
使 Capability Resolver 能针对远程环境正确判断实现可用性。
"""
import json

from .manifest import ComputeInfo, Manifest, RuntimeInfo, SystemInfo, ToolInfo

# python 模块 → 规范 tool_id
PY_TOOL_MODULES = {
    "scanpy": "scanpy", "anndata": "anndata", "leidenalg": "leidenalg",
    "pandas": "pandas", "numpy": "numpy", "matplotlib": "matplotlib",
    "scipy": "scipy", "h5py": "h5py", "seaborn": "seaborn",
    "scvi-tools": "scvi-tools",
}

# 系统级 CLI 工具（command -v 探测）
CLI_TOOLS = ["star", "samtools", "salmon", "kallisto", "fastqc", "cutadapt", "featureCounts", "cellranger", "sbatch"]


def _run(client, cmd: str, timeout: int = 60) -> tuple[bool, str]:
    """在远程执行命令，返回 (ok, stdout)。"""
    try:
        _in, out, err = client.exec_command(cmd, timeout=timeout)
        code = out.channel.recv_exit_status()
        text = (out.read().decode("utf-8", "replace") + "\n" +
                err.read().decode("utf-8", "replace")).strip()
        return code == 0, text
    except Exception:  # noqa: BLE001
        return False, ""


def discover_remote(client) -> Manifest:
    """在已连接的 paramiko client 上执行探测，返回标准 Manifest。"""
    manifest = Manifest(environment_id="env_remote_ssh", environment_type="remote")

    # ---- System Discovery ----
    ok, out = _run(client, "uname -s; uname -m; nproc 2>/dev/null || echo unknown")
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    os_name = lines[0] if len(lines) > 0 else "unknown"
    arch = lines[1] if len(lines) > 1 else "unknown"
    cores = None
    if len(lines) > 2 and lines[2].isdigit():
        cores = int(lines[2])
    manifest.system = SystemInfo(os=os_name.lower(), arch=arch, cpu_cores=cores)

    # ---- Runtime Discovery ----
    ok, pyver = _run(client, "python3 --version 2>&1 || python --version 2>&1")
    if ok and pyver:
        manifest.runtimes.append(RuntimeInfo(
            id="runtime_py3", type="python", name="python3",
            version=pyver.splitlines()[0].strip(), path="python3"))
    ok, rver = _run(client, "R --version 2>&1 | head -1")
    if ok and rver:
        manifest.runtimes.append(RuntimeInfo(
            id="runtime_R", type="r", name="R",
            version=rver.splitlines()[0].strip(), path="R"))

    # ---- Tool Discovery（默认 python3 的模块）----
    mods = list(PY_TOOL_MODULES.keys())
    probe = ("python3 -c \"import importlib.util,sys,json;"
             "print(json.dumps({m: importlib.util.find_spec(m) is not None for m in sys.argv[1:]}))\" " +
             " ".join(mods))
    ok, out = _run(client, probe, timeout=120)
    if ok and out:
        try:
            found = json.loads(out.strip().splitlines()[-1])
            for mod, present in found.items():
                if present:
                    manifest.tools.append(ToolInfo(
                        tool_id=PY_TOOL_MODULES[mod], runtime_id="runtime_py3",
                        version=None, status="healthy", language="python"))
        except Exception:  # noqa: BLE001
            pass

    # ---- CLI 工具 + 调度器 ----
    scheduler = None
    for cli in CLI_TOOLS:
        ok, _ = _run(client, f"command -v {cli}", timeout=15)
        if ok:
            if cli == "sbatch":
                scheduler = "slurm"
            else:
                manifest.tools.append(ToolInfo(
                    tool_id=cli, runtime_id=None, version=None,
                    status="healthy", language="bash"))
    manifest.compute = ComputeInfo(scheduler=scheduler, notes=["remote discovery via SSH"])

    return manifest
