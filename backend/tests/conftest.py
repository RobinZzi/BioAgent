"""pytest 全局配置：测试使用独立临时数据库，避免污染开发数据。"""
import os
import tempfile

# 必须在导入 app 模块前设置，使 engine 指向临时数据库
_TMP_DATA = tempfile.mkdtemp(prefix="bioagent_test_")
os.environ["BIOAGENT_DATA_DIR"] = _TMP_DATA
os.environ["BIOAGENT_EXECUTOR_MODE"] = "mock"
