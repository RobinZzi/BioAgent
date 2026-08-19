"""BioAgent 应用配置。"""
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

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "projects").mkdir(parents=True, exist_ok=True)


settings = Settings()
