from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "cfix-server"
    app_env: str = "dev"
    app_debug: bool = True
    api_v1_str: str = "/api/v1"
    cors_allow_origins: str = "http://127.0.0.1:8000,http://127.0.0.1:5173,http://localhost:5173"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_db: str = "cfix_db"

    jwt_secret: str = "change-this-secret"
    jwt_alg: str = "HS256"
    jwt_expire_min: int = 120

    # ===== LLM 配置 =====
    llm_provider: str = "qwen"
    llm_enable: bool = False
    llm_model: str = "qwen3-coder-next"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_timeout: int = 120
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    # true 时，如果真实模型不可用/返回非法结果，直接抛错，避免静默退回占位逻辑。
    llm_strict: bool = False
    # 真实调用失败后的自动重试次数。
    llm_retry_count: int = 2
    # 简单线性退避秒数。
    llm_retry_backoff_sec: float = 1.0
    # 是否清理 Qwen 可能返回的 <think>...</think>。
    llm_strip_think: bool = True

    # ===== 执行沙箱配置 =====
    sandbox_backend: str = "safe_exec"  # safe_exec / docker
    sandbox_timeout_sec: int = 8
    sandbox_image: str = "cfix-python-sandbox:latest"
    sandbox_work_root: str = "/tmp/cfix_sandbox"
    sandbox_memory: str = "256m"
    sandbox_cpus: float = 0.5
    sandbox_pids_limit: int = 64
    sandbox_read_only: bool = True
    sandbox_docker_bin: str = "docker"
    sandbox_keep_temp: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def cors_origins(self) -> list[str]:
        items = [item.strip() for item in str(self.cors_allow_origins or "").split(",") if item.strip()]
        return items or [
            "http://127.0.0.1:8000",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]

    @property
    def llm_ready(self) -> bool:
        """是否具备真实调用模型的最小条件。"""
        return bool(self.llm_enable and self.llm_api_key and self.llm_base_url and self.llm_model)

    @property
    def sandbox_use_docker(self) -> bool:
        return (self.sandbox_backend or "safe_exec").strip().lower() == "docker"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
