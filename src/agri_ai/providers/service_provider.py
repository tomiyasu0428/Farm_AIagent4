"""
サービス・プロバイダー

依存性注入(DI)のためのコンテナクラス
サービス間の密結合を解決し、テスタビリティを向上させる
"""

import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from ..dependencies.database import DatabaseConnection
from ..services.master_data_resolver import MasterDataResolver

logger = logging.getLogger(__name__)


class IServiceProvider(ABC):
    """サービスプロバイダーのインターフェース"""
    
    @abstractmethod
    def get_work_log_extractor(self):
        """WorkLogExtractor インスタンスを取得"""
        pass
    
    @abstractmethod 
    def get_work_log_validator(self):
        """WorkLogValidator インスタンスを取得"""
        pass
    
    @abstractmethod
    def get_work_log_confirmation_service(self):
        """WorkLogConfirmationService インスタンスを取得"""
        pass
    
    @abstractmethod
    def get_intelligent_decision_service(self):
        """IntelligentDecisionService インスタンスを取得"""
        pass
    
    @abstractmethod
    def get_master_data_resolver(self):
        """MasterDataResolver インスタンスを取得"""
        pass


class ServiceProvider(IServiceProvider):
    """
    実装クラス
    
    遅延ロードによりインスタンス作成コストを最小化
    設定ベースのカスタマイズ対応
    """
    
    def __init__(self, db_connection: Optional[DatabaseConnection] = None):
        # 基盤サービス
        self._db_connection = db_connection or DatabaseConnection()
        
        # キャッシュ用インスタンス変数（遅延ロード）
        self._work_log_extractor = None
        self._work_log_validator = None
        self._work_log_confirmation_service = None
        self._intelligent_decision_service = None
        self._master_data_resolver = None
        
        # 設定（将来的な拡張用）
        self._config = {}
    
    def get_work_log_extractor(self):
        """WorkLogExtractor インスタンスを取得（遅延ロード）"""
        if self._work_log_extractor is None:
            from ..services.work_log_extractor import WorkLogExtractor
            self._work_log_extractor = WorkLogExtractor()
            logger.debug("WorkLogExtractor インスタンス作成")
        
        return self._work_log_extractor
    
    def get_work_log_validator(self):
        """WorkLogValidator インスタンスを取得（遅延ロード）"""
        if self._work_log_validator is None:
            from ..services.work_log_validator import WorkLogValidator
            self._work_log_validator = WorkLogValidator(self._db_connection)
            logger.debug("WorkLogValidator インスタンス作成")
        
        return self._work_log_validator
    
    def get_work_log_confirmation_service(self):
        """WorkLogConfirmationService インスタンスを取得（遅延ロード）"""
        if self._work_log_confirmation_service is None:
            from ..services.work_log_confirmation import WorkLogConfirmationService
            self._work_log_confirmation_service = WorkLogConfirmationService()
            logger.debug("WorkLogConfirmationService インスタンス作成")
        
        return self._work_log_confirmation_service
    
    def get_intelligent_decision_service(self):
        """IntelligentDecisionService インスタンスを取得（遅延ロード）"""
        if self._intelligent_decision_service is None:
            from ..services.intelligent_decision_service import IntelligentDecisionService
            self._intelligent_decision_service = IntelligentDecisionService()
            logger.debug("IntelligentDecisionService インスタンス作成")
        
        return self._intelligent_decision_service
    
    def get_master_data_resolver(self):
        """MasterDataResolver インスタンスを取得（遅延ロード）"""
        if self._master_data_resolver is None:
            self._master_data_resolver = MasterDataResolver(self._db_connection)
            logger.debug("MasterDataResolver インスタンス作成")
        
        return self._master_data_resolver
    
    def configure(self, config: Dict[str, Any]):
        """設定を更新（将来的な拡張用）"""
        self._config.update(config)
        logger.info(f"ServiceProvider設定更新: {list(config.keys())}")
    
    def reset_cache(self):
        """インスタンスキャッシュをリセット（テスト用）"""
        self._work_log_extractor = None
        self._work_log_validator = None
        self._work_log_confirmation_service = None
        self._intelligent_decision_service = None
        self._master_data_resolver = None
        logger.debug("ServiceProvider キャッシュリセット")


class MockServiceProvider(IServiceProvider):
    """
    テスト用のモック・サービス・プロバイダー
    
    各サービスをモックオブジェクトに差し替え可能
    """
    
    def __init__(self):
        self.mock_extractor = None
        self.mock_validator = None
        self.mock_confirmation_service = None
        self.mock_intelligent_decision_service = None
        self.mock_master_data_resolver = None
    
    def get_work_log_extractor(self):
        return self.mock_extractor
    
    def get_work_log_validator(self):
        return self.mock_validator
    
    def get_work_log_confirmation_service(self):
        return self.mock_confirmation_service
    
    def get_intelligent_decision_service(self):
        return self.mock_intelligent_decision_service
    
    def get_master_data_resolver(self):
        return self.mock_master_data_resolver
    
    def set_mock_extractor(self, mock):
        """テスト用: WorkLogExtractor のモックを設定"""
        self.mock_extractor = mock
    
    def set_mock_validator(self, mock):
        """テスト用: WorkLogValidator のモックを設定"""
        self.mock_validator = mock
    
    def set_mock_confirmation_service(self, mock):
        """テスト用: WorkLogConfirmationService のモックを設定"""
        self.mock_confirmation_service = mock
    
    def set_mock_intelligent_decision_service(self, mock):
        """テスト用: IntelligentDecisionService のモックを設定"""
        self.mock_intelligent_decision_service = mock
    
    def set_mock_master_data_resolver(self, mock):
        """テスト用: MasterDataResolver のモックを設定"""
        self.mock_master_data_resolver = mock


# デフォルトのサービスプロバイダーインスタンス
_default_provider: Optional[IServiceProvider] = None


def get_service_provider() -> IServiceProvider:
    """デフォルトのサービスプロバイダーを取得"""
    global _default_provider
    
    if _default_provider is None:
        _default_provider = ServiceProvider()
        logger.info("デフォルトServiceProvider初期化")
    
    return _default_provider


def set_service_provider(provider: IServiceProvider):
    """サービスプロバイダーを差し替え（主にテスト用）"""
    global _default_provider
    _default_provider = provider
    logger.info(f"ServiceProvider差し替え: {type(provider).__name__}")