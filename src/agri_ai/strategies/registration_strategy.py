"""
作業記録登録戦略インターフェース

責務分離によるStrategy パターン実装
各登録戦略を独立したクラスとして実装し、テスタビリティを向上
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from ..agents.models.work_log_extraction import ExtractedWorkInfo, WorkLogValidationResult

logger = logging.getLogger(__name__)


class RegistrationStrategy(ABC):
    """
    作業記録登録戦略の抽象基底クラス
    
    各戦略は独立して実行できる責務を持つ
    """
    
    @abstractmethod
    async def execute(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        戦略実行メソッド
        
        Args:
            extracted_info: 抽出された作業情報
            validation_result: 検証結果
            message: 元のメッセージ
            user_id: ユーザーID
            
        Returns:
            Dict: 戦略実行結果
        """
        pass
    
    @abstractmethod
    def can_handle(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult
    ) -> bool:
        """
        この戦略で処理可能かどうかを判定
        
        Args:
            extracted_info: 抽出された作業情報
            validation_result: 検証結果
            
        Returns:
            bool: 処理可能な場合True
        """
        pass
    
    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """戦略名を返す"""
        pass


class RegistrationStrategyContext:
    """
    登録戦略のコンテキストクラス
    
    複数の戦略から適切なものを選択して実行
    """
    
    def __init__(self, strategies: list[RegistrationStrategy]):
        self.strategies = strategies
    
    async def execute_best_strategy(
        self,
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        最適な戦略を選択して実行
        
        Args:
            extracted_info: 抽出された作業情報
            validation_result: 検証結果
            message: 元のメッセージ
            user_id: ユーザーID
            
        Returns:
            Dict: 実行結果
        """
        for strategy in self.strategies:
            if strategy.can_handle(extracted_info, validation_result):
                logger.info(f"戦略選択: {strategy.strategy_name}")
                return await strategy.execute(extracted_info, validation_result, message, user_id)
        
        # 該当する戦略がない場合はデフォルト戦略（確認フロー）
        logger.warning("適用可能な戦略が見つかりません。デフォルト戦略を使用します。")
        default_strategy = self.strategies[-1]  # 最後を確認フロー戦略とする
        return await default_strategy.execute(extracted_info, validation_result, message, user_id)