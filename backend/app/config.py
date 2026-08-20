"""BioAgent 应用配置。"""
import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIOAGENT_")
    app_name: str = "BioAgent"
    version: str = "0.1.0"

    # 数据根目录（数据库 + 项目产物）
    data_dir: Path = BACKEND_DIR / "data"

    # 执行器模式: mock | auto | local
    #   mock  —— 不调用真实工具，预生成合理产物（开发/演示/CI）
    #   local —— 只走真实本机执行，工具缺失则失败
    #   auto  —— 优先真实执行，工具缺失时回退 mock（默认）
    executor_mode: str = "auto"

    # 发现超时（秒）
    discovery_timeout: float = 25.0

    # ---- LLM Agent（v0.2，OpenAI 兼容）----
    # 未配置 api_key 时自动回退规则引擎
    llm_mode: str = "off"          # off | echo | real
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout: float = 30.0

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'bioagent.db'}"

    @property
    def llm_config_path(self) -> Path:
        return self.data_dir / "llm_config.json"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "projects").mkdir(parents=True, exist_ok=True)

    def load_llm_config(self) -> None:
        """从本地配置文件加载 LLM 配置（环境变量优先，文件兜底）。"""
        try:
            if self.llm_config_path.exists():
                data = json.loads(self.llm_config_path.read_text(encoding="utf-8"))
                if not self.llm_api_key and data.get("api_key"):
                    self.llm_api_key = data["api_key"]
                if data.get("base_url"):
                    self.llm_base_url = data["base_url"]
                if data.get("model"):
                    self.llm_model = data["model"]
        except Exception:  # noqa: BLE001
            pass

    def save_llm_config(self, api_key: str | None = None,
                        base_url: str | None = None, model: str | None = None) -> None:
        """把 LLM 配置写入本地文件（api_key=None 表示不改动，空串表示清除）。"""
        self.ensure_dirs()
        data = {}
        if self.llm_config_path.exists():
            try:
                data = json.loads(self.llm_config_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                data = {}
        if api_key is not None:
            data["api_key"] = api_key
        if base_url:
            data["base_url"] = base_url
        if model:
            data["model"] = model
        self.llm_config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                        encoding="utf-8")


settings = Settings()
settings.load_llm_config()

