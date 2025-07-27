"""
統一設定管理システム

LegacyシステムとLangGraphシステム間で共有される設定を管理します。
型安全性とバリデーションを強化し、環境設定の一元化を実現します。
"""

import os
import logging
import logging.config
from typing import Optional, Literal
from pathlib import Path
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


class GoogleAISettings(BaseModel):
    """Google AI API設定"""

    api_key: str = Field(default="", description="Google AI API キー")
    model_name: str = Field(default="gemini-2.5-flash", description="使用するモデル名")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="生成温度")
    timeout: int = Field(default=30, gt=0, description="タイムアウト秒数")

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.startswith('AIza'):
            raise ValueError('Google AI API キーの形式が正しくありません')
        return v


class LangSmithSettings(BaseModel):
    """LangSmith設定"""

    api_key: str = Field(default="", description="LangSmith API キー")
    project_name: str = Field(default="farm-aiagent4", description="プロジェクト名")
    endpoint: str = Field(default="https://api.smith.langchain.com", description="エンドポイントURL")
    tracing_enabled: bool = Field(default=False, description="トレーシング有効化")

    @validator('api_key')
    def validate_api_key(cls, v):
        if v and not v.startswith('lsv2_'):
            raise ValueError('LangSmith API キーの形式が正しくありません')
        return v


class MongoDBSettings(BaseModel):
    """MongoDB設定"""

    connection_string: str = Field(default="", description="MongoDB接続文字列")
    database_name: str = Field(default="Agri-AI-Project", description="データベース名")
    max_pool_size: int = Field(default=50, gt=0, description="最大接続プールサイズ")
    min_pool_size: int = Field(default=5, ge=0, description="最小接続プールサイズ")
    connect_timeout: int = Field(default=10000, gt=0, description="接続タイムアウト(ms)")
    server_selection_timeout: int = Field(default=5000, gt=0, description="サーバー選択タイムアウト(ms)")

    @validator('connection_string')
    def validate_connection_string(cls, v):
        if v and not (v.startswith('mongodb://') or v.startswith('mongodb+srv://')):
            raise ValueError('MongoDB接続文字列の形式が正しくありません')
        return v

    @validator('min_pool_size')
    def validate_pool_sizes(cls, v, values):
        if 'max_pool_size' in values and v > values['max_pool_size']:
            raise ValueError('min_pool_sizeはmax_pool_sizeより小さくしてください')
        return v


class LINEBotSettings(BaseModel):
    """LINE Bot設定"""

    channel_access_token: str = Field(default="", description="チャンネルアクセストークン")
    channel_secret: str = Field(default="", description="チャンネルシークレット")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL")

    @validator('channel_access_token')
    def validate_access_token(cls, v):
        if v and len(v) < 10:
            raise ValueError('チャンネルアクセストークンが短すぎます')
        return v


class GoogleCloudSettings(BaseModel):
    """Google Cloud設定"""

    project_id: Optional[str] = Field(default=None, description="プロジェクトID")
    credentials_path: Optional[Path] = Field(default=None, description="認証情報ファイルパス")

    @validator('credentials_path', pre=True)
    def validate_credentials_path(cls, v):
        if v and isinstance(v, str) and v != "":
            path = Path(v)
            if not path.exists():
                # テスト環境では警告のみ
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f'認証情報ファイルが見つかりません: {v}')
                return None
            return path
        return v


class AppSettings(BaseModel):
    """アプリケーション設定"""

    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="実行環境"
    )
    debug: bool = Field(default=True, description="デバッグモード")
    max_concurrent_requests: int = Field(default=100, gt=0, description="最大同時リクエスト数")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="ログレベル"
    )


class SystemConstants(BaseModel):
    """システム定数（マジックナンバー排除）"""
    
    # タイムアウト設定
    DEFAULT_TIMEOUT_SECONDS: int = 30
    LLM_TIMEOUT_SECONDS: int = 60
    DATABASE_TIMEOUT_SECONDS: int = 10
    
    # 信頼度閾値
    HIGH_CONFIDENCE_THRESHOLD: float = 0.8
    MEDIUM_CONFIDENCE_THRESHOLD: float = 0.6
    LOW_CONFIDENCE_THRESHOLD: float = 0.4
    
    # 作業記録設定
    MAX_MISSING_INFO_FOR_AUTO_REGISTRATION: int = 3
    MIN_WORK_LOG_MESSAGE_LENGTH: int = 5
    
    # キャッシュ設定
    LLM_CACHE_TTL_SECONDS: int = 3600
    SESSION_CACHE_TTL_SECONDS: int = 7200
    
    # パフォーマンス設定
    MAX_BATCH_SIZE: int = 100
    CONNECTION_POOL_SIZE: int = 10


class UnifiedSettings(BaseSettings):
    """統合設定クラス - 型安全性とバリデーション強化版"""

    model_config = {
        "env_file": ".env", 
        "case_sensitive": False, 
        "extra": "allow",
        "validate_assignment": True
    }

    def __init__(self, env_file: Optional[str] = None, **kwargs):
        """
        設定の初期化
        
        Args:
            env_file: 環境設定ファイルパス（デフォルト: .env）
        """
        # 環境変数ファイルを読み込み
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
            
        super().__init__(**kwargs)
        self._validate_env_file(env_file or ".env")
        self._initialize_settings()

    def _validate_env_file(self, env_file: str):
        """環境設定ファイルの検証"""
        if not os.path.exists(env_file):
            raise FileNotFoundError(
                f"環境設定ファイル '{env_file}' が見つかりません。"
                f"'.env.example' を '{env_file}' にコピーして適切な値を設定してください。"
            )

    def _initialize_settings(self):
        """各設定グループを初期化"""
        self.google_ai = GoogleAISettings(
            api_key=os.environ.get("GOOGLE_API_KEY", ""),
            model_name=os.environ.get("GOOGLE_AI_MODEL", "gemini-2.5-flash"),
            temperature=float(os.environ.get("GOOGLE_AI_TEMPERATURE", "0.1")),
            timeout=int(os.environ.get("AI_RESPONSE_TIMEOUT", "30")),
        )
        
        self.langsmith = LangSmithSettings(
            api_key=os.environ.get("LANGSMITH_API_KEY", ""),
            project_name=os.environ.get("LANGSMITH_PROJECT", "farm-aiagent4"),
            endpoint=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
            tracing_enabled=os.environ.get("LANGSMITH_TRACING", "false").lower() == "true",
        )
        
        self.mongodb = MongoDBSettings(
            connection_string=os.environ.get("MONGODB_CONNECTION_STRING", ""),
            database_name=os.environ.get("MONGODB_DATABASE_NAME", "Agri-AI-Project"),
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
        
        self.constants = SystemConstants()

    def is_production(self) -> bool:
        """本番環境かどうかを判定"""
        return self.app.environment == "production"

    def is_development(self) -> bool:
        """開発環境かどうかを判定"""
        return self.app.environment == "development"

    def setup_logging(self):
        """アプリケーション全体のロギング設定"""
        log_level = self.app.log_level.upper()

        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "detailed" if self.is_development() else "default",
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
                "agri_ai": {"handlers": ["console"], "level": log_level, "propagate": True},
                "shared": {"handlers": ["console"], "level": log_level, "propagate": True},
            },
        }

        logging.config.dictConfig(logging_config)


# グローバル設定インスタンス
settings = UnifiedSettings()


def get_settings(env_file: Optional[str] = None) -> UnifiedSettings:
    """
    設定インスタンスを取得
    
    Args:
        env_file: 環境設定ファイルパス
        
    Returns:
        UnifiedSettings: 設定インスタンス
    """
    if env_file:
        return UnifiedSettings(env_file=env_file)
    return settings


def setup_logging():
    """アプリケーション全体のロギング設定（関数版）"""
    settings.setup_logging()


# 後方互換性のための別名
Settings = UnifiedSettings