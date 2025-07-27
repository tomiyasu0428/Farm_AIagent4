"""
戦略ファクトリー

登録戦略の生成と管理を担当
DIコンテナと連携して適切な戦略インスタンスを提供
"""

import logging
from typing import List

from .registration_strategy import RegistrationStrategy, RegistrationStrategyContext
from .auto_registration_strategy import AutoRegistrationStrategy
from .intelligent_strategy import IntelligentStrategy
from .confirmation_strategy import ConfirmationStrategy, EnhancedConfirmationStrategy
from ..providers.service_provider import IServiceProvider
from ..dependencies.database import DatabaseConnection

logger = logging.getLogger(__name__)


class RegistrationStrategyFactory:
    """
    登録戦略ファクトリークラス
    
    責務:
    - 戦略インスタンスの生成
    - 戦略の優先順位管理
    - DIコンテナとの連携
    """
    
    def __init__(self, service_provider: IServiceProvider, db_connection: DatabaseConnection):
        self.service_provider = service_provider
        self.db_connection = db_connection
    
    def create_strategy_context(self) -> RegistrationStrategyContext:
        """
        戦略コンテキストを作成
        
        戦略の優先順位:
        1. 自動登録戦略 (高信頼度)
        2. 知的判断戦略 (グレーゾーン)
        3. 拡張確認フロー戦略 (中程度の信頼度)
        4. 確認フロー戦略 (フォールバック)
        
        Returns:
            RegistrationStrategyContext: 設定済みコンテキスト
        """
        strategies = self._create_ordered_strategies()
        return RegistrationStrategyContext(strategies)
    
    def _create_ordered_strategies(self) -> List[RegistrationStrategy]:
        """
        優先順位付きの戦略リストを作成
        """
        strategies = []
        
        # 1. 自動登録戦略 (最高優先度)
        strategies.append(AutoRegistrationStrategy(self.db_connection))
        
        # 2. 知的判断戦略 (グレーゾーン処理)
        strategies.append(IntelligentStrategy(self.service_provider))
        
        # 3. 拡張確認フロー戦略 (中程度の信頼度)
        strategies.append(EnhancedConfirmationStrategy(self.service_provider))
        
        # 4. 基本確認フロー戦略 (フォールバック)
        strategies.append(ConfirmationStrategy(self.service_provider))
        
        logger.info(f"戦略リスト作成完了: {len(strategies)}個の戦略を登録")
        return strategies
    
    def create_auto_registration_strategy(self) -> AutoRegistrationStrategy:
        """自動登録戦略の個別作成"""
        return AutoRegistrationStrategy(self.db_connection)
    
    def create_intelligent_strategy(self) -> IntelligentStrategy:
        """知的判断戦略の個別作成"""
        return IntelligentStrategy(self.service_provider)
    
    def create_confirmation_strategy(self) -> ConfirmationStrategy:
        """確認フロー戦略の個別作成"""
        return ConfirmationStrategy(self.service_provider)
    
    def create_enhanced_confirmation_strategy(self) -> EnhancedConfirmationStrategy:
        """拡張確認フロー戦略の個別作成"""
        return EnhancedConfirmationStrategy(self.service_provider)
    
    def get_strategy_names(self) -> List[str]:
        """利用可能な戦略名のリストを取得"""
        strategies = self._create_ordered_strategies()
        return [strategy.strategy_name for strategy in strategies]
    
    def create_custom_strategy_context(self, strategy_names: List[str]) -> RegistrationStrategyContext:
        """
        カスタム戦略コンテキストを作成
        
        Args:
            strategy_names: 使用する戦略名のリスト（優先順位順）
            
        Returns:
            RegistrationStrategyContext: カスタム設定コンテキスト
        """
        strategy_map = {
            "自動登録戦略": lambda: AutoRegistrationStrategy(self.db_connection),
            "知的判断戦略": lambda: IntelligentStrategy(self.service_provider),
            "拡張確認フロー戦略": lambda: EnhancedConfirmationStrategy(self.service_provider),
            "確認フロー戦略": lambda: ConfirmationStrategy(self.service_provider)
        }
        
        strategies = []
        for name in strategy_names:
            if name in strategy_map:
                strategies.append(strategy_map[name]())
            else:
                logger.warning(f"未知の戦略名: {name}")
        
        if not strategies:
            # フォールバック: デフォルト戦略
            logger.warning("有効な戦略が指定されませんでした。デフォルト戦略を使用します。")
            strategies = self._create_ordered_strategies()
        
        return RegistrationStrategyContext(strategies)