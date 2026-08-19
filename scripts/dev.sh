#!/usr/bin/env bash
# BioAgent 开发辅助脚本
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup() {
  echo "==> 创建后端虚拟环境 (Python 3.12)"
  export UV_CACHE_DIR="$ROOT/.uv-cache" UV_PYTHON_INSTALL_DIR="$ROOT/.uv-python"
  uv venv --python 3.12 "$ROOT/backend/.venv"
  echo "==> 安装后端依赖"
  uv pip install --python "$ROOT/backend/.venv/bin/python" \
    fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings matplotlib
  echo "==> 创建真实 scanpy 执行环境 (Python 3.11，可选)"
  if [ ! -d "$ROOT/backend/.venv311" ]; then
    uv venv --python 3.11 "$ROOT/backend/.venv311"
    uv pip install --python "$ROOT/backend/.venv311/bin/python" scanpy anndata leidenalg
  else
    echo "    .venv311 已存在，跳过"
  fi
  echo "==> 安装前端依赖"
  (cd "$ROOT/frontend" && npm install --no-audit --no-fund --cache "$ROOT/.npm-cache")
  echo "==> Seed 演示数据"
  (cd "$ROOT/backend" && .venv/bin/python "$ROOT/scripts/seed_demo.py")
  echo "完成。运行 bash scripts/dev.sh start"
}

start() {
  trap 'kill 0' EXIT
  echo "==> 启动后端 :8000"
  (cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
  echo "==> 启动前端 :5173"
  (cd "$ROOT/frontend" && npx vite --port 5173 --strictPort) &
  echo "==> 打开 http://localhost:5173 （后端文档 http://127.0.0.1:8000/docs）"
  wait
}

case "${1:-}" in
  setup) setup ;;
  start) start ;;
  *) echo "用法: $0 {setup|start}"; exit 1 ;;
esac
