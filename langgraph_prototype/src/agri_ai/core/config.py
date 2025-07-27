"""
環境設定と設定値の管理
"""

import os
from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


class GoogleAISettings(BaseModel):
    """Google AI API設定"""

    api_key: str = ""
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.1
    timeout: int = 30


class LangSmithSettings(BaseModel):
    """LangSmith設定"""

    api_key: str = ""
    project_name: str = "agri-ai-project"
    endpoint: str = "https://api.smith.langchain.com"
    tracing_enabled: bool = False


class MongoDBSettings(BaseModel):
    """MongoDB設定"""

    connection_string: str = ""
    database_name: str = "agri_ai"
    max_pool_size: int = 50
    min_pool_size: int = 5
    connect_timeout: int = 10000
    server_selection_timeout: int = 5000


class LINEBotSettings(BaseModel):
    """LINE Bot設定"""

    channel_access_token: str = ""
    channel_secret: str = ""
    webhook_url: Optional[str] = None


class GoogleCloudSettings(BaseModel):
    """Google Cloud設定"""

    project_id: Optional[str] = None
    credentials_path: Optional[str] = None


class AppSettings(BaseModel):
    """アプリケーション設定"""

    environment: str = "development"
    debug: bool = True
    max_concurrent_requests: int = 100
    log_level: str = "INFO"


class Settings(BaseSettings):
    """統合設定クラス"""

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "allow"}

    def __init__(self, **kwargs):
        # 環境変数ファイルを読み込み
        load_dotenv()
        super().__init__(**kwargs)
        self._validate_env_file()

        # 各設定グループを初期化（環境変数から読み込み）
        self.google_ai = GoogleAISettings(
            api_key=os.environ.get("GOOGLE_API_KEY", ""),
            model_name=os.environ.get("GOOGLE_AI_MODEL", "gemini-2.5-flash"),
            temperature=float(os.environ.get("GOOGLE_AI_TEMPERATURE", "0.1")),
            timeout=int(os.environ.get("AI_RESPONSE_TIMEOUT", "30")),
        )
        self.langsmith = LangSmithSettings(
            api_key=os.environ.get("LANGSMITH_API_KEY", ""),
            project_name=os.environ.get("LANGSMITH_PROJECT", "agri-ai-project"),
            endpoint=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
            tracing_enabled=os.environ.get("LANGSMITH_TRACING", "false").lower() == "true",
        )
        self.mongodb = MongoDBSettings(
            connection_string=os.environ.get("MONGODB_CONNECTION_STRING", ""),
            database_name=os.environ.get("MONGODB_DATABASE_NAME", "agri_ai"),
            max_pool_size=int(os.environ.get("MONGODB_MAX_POOL_SIZE", "50")),
            min_pool_size=int(os.environ.get("MONGODB_MIN_POOL_SIZE", "5")),
            connect_timeout=int(os.environ.get("MONGODB_CONNECT_TIMEOUT", "10000")),
            server_selection_timeout=int(os.environ.get("MONGODB_SERVER_SELECTION_TIMEOUT", "5000")),
        )
        self.line_bot = LINEBotSettings(
            channel_access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
            channel_secret=os.environ.get("LINE_CHANNEL_SECRET", ""),
            webhook_url=os.environ.get("LINE_WEBHOOK_URL"),
        )
        self.google_cloud = GoogleCloudSettings(
            project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
            credentials_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        )
        self.app = AppSettings(
            environment=os.environ.get("ENVIRONMENT", "development"),
            debug=os.environ.get("DEBUG", "true").lower() == "true",
            max_concurrent_requests=int(os.environ.get("MAX_CONCURRENT_REQUESTS", "100")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )

    def _validate_env_file(self):
        """環境設定ファイルの検証"""
        env_file = ".env"
        if not os.path.exists(env_file):
            raise FileNotFoundError(
                f"環境設定ファイル '{env_file}' が見つかりません。"
                f"'.env.example' を '{env_file}' にコピーして適切な値を設定してください。"
            )



# グローバル設定インスタンス
settings = Settings()


def setup_logging():
    """アプリケーション全体のロギング設定"""
    import logging
    import logging.config

    log_level = settings.app.log_level.upper()

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
        "loggers": {
            "uvicorn": {"handlers": ["console"], "level": log_level, "propagate": False},
            "fastapi": {"handlers": ["console"], "level": log_level, "propagate": False},
            "linebot": {"handlers": ["console"], "level": log_level, "propagate": False},
            "src": {"handlers": ["console"], "level": log_level, "propagate": True},
        },
    }

    logging.config.dictConfig(logging_config)

    logging.config.dictConfig(logging_config)
