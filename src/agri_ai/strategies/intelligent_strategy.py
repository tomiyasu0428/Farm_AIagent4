"""
知的判断戦略

LLMによる文脈分析を活用した高度な登録判断を担当
グレーゾーンの処理において機械学習的判断を行う戦略
"""

import logging
from typing import Dict, Any

from .registration_strategy import RegistrationStrategy
from ..agents.models.work_log_extraction import ExtractedWorkInfo, WorkLogValidationResult
from ..providers.service_provider import IServiceProvider

logger = logging.getLogger(__name__)


class IntelligentStrategy(RegistrationStrategy):
    """
    知的判断戦略
    
    LLMによる文脈分析結果に基づいて、
    自動登録または確認フローを動的に決定する戦略
    """
    
    def __init__(self, service_provider: IServiceProvider):
        self.service_provider = service_provider
    
    @property
    def strategy_name(self) -> str:
        return "知的判断戦略"
    
    def can_handle(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult
    ) -> bool:
        """
        知的判断が必要かどうかを判定
        
        条件:
        - 信頼度が中程度 (0.4-0.8)
        - 検証が部分的に成功
        - 文脈分析が有効と判断される場合
        """
        confidence = extracted_info.confidence_score or 0.0
        missing_count = len(validation_result.missing_info)
        
        # グレーゾーンで知的判断を使用
        return (
            0.4 <= confidence < 0.8 and 
            1 <= missing_count <= 2 and
            validation_result.is_valid  # 基本検証は通過している
        )
    
    async def execute(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        知的判断戦略実行
        """
        try:
            # LLM文脈分析を実行
            intelligent_decision_service = self.service_provider.get_intelligent_decision_service()
            
            # ユーザー履歴取得
            user_history = await intelligent_decision_service.get_user_recent_history(user_id)
            
            # 文脈分析実行
            context_analysis = await intelligent_decision_service.analyze_context(
                message, extracted_info, validation_result, user_history
            )
            
            logger.info(f"LLM分析完了: 推奨アクション={context_analysis.recommended_action}")
            
            # 分析結果に基づく戦略選択
            return await self._execute_based_on_analysis(
                context_analysis, extracted_info, validation_result, message, user_id
            )
            
        except Exception as e:
            logger.error(f"知的判断戦略エラー: {e}")
            # エラー時はフォールバック（確認フロー）
            from .confirmation_strategy import ConfirmationStrategy
            fallback_strategy = ConfirmationStrategy(self.service_provider)
            return await fallback_strategy.execute(extracted_info, validation_result, message, user_id)
    
    async def _execute_based_on_analysis(
        self,
        context_analysis,
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        LLM分析結果に基づく戦略実行
        """
        action = context_analysis.recommended_action
        
        if action == "auto_register_urgent":
            logger.info("LLM判断: 緊急自動登録")
            return await self._execute_urgent_registration(
                extracted_info, validation_result, message, user_id, context_analysis
            )
            
        elif action == "auto_register_inferred":
            logger.info("LLM判断: 推測自動登録")
            return await self._execute_inferred_registration(
                extracted_info, validation_result, message, user_id, context_analysis
            )
            
        elif action == "confirm_with_suggestions":
            logger.info("LLM判断: 提案付き確認")
            return await self._execute_enhanced_confirmation(
                extracted_info, validation_result, message, user_id, context_analysis
            )
        
        else:
            # デフォルトは通常確認フロー
            logger.info("LLM判断: 通常確認フロー")
            from .confirmation_strategy import ConfirmationStrategy
            fallback_strategy = ConfirmationStrategy(self.service_provider)
            return await fallback_strategy.execute(extracted_info, validation_result, message, user_id)
    
    async def _execute_urgent_registration(
        self,
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str,
        context_analysis
    ) -> Dict[str, Any]:
        """緊急自動登録の実行"""
        from .auto_registration_strategy import AutoRegistrationStrategy
        from ..dependencies.database import DatabaseConnection
        
        # 自動登録戦略を使用
        auto_strategy = AutoRegistrationStrategy(DatabaseConnection())
        result = await auto_strategy.execute(extracted_info, validation_result, message, user_id)
        
        # 知的判断の情報を追加
        result['intelligent_analysis'] = {
            'urgency_level': context_analysis.urgency_level,
            'reasoning': context_analysis.reasoning[:150],
            'confidence': context_analysis.confidence
        }
        result['strategy_used'] = f"{self.strategy_name} → 緊急自動登録"
        
        return result
    
    async def _execute_inferred_registration(
        self,
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str,
        context_analysis
    ) -> Dict[str, Any]:
        """推測情報を適用した自動登録"""
        # 推測情報をextracted_infoに適用
        if context_analysis.missing_info_inference:
            extracted_info = self._apply_llm_inferences(
                extracted_info, context_analysis.missing_info_inference
            )
        
        # 自動登録戦略を使用
        from .auto_registration_strategy import AutoRegistrationStrategy
        from ..dependencies.database import DatabaseConnection
        
        auto_strategy = AutoRegistrationStrategy(DatabaseConnection())
        result = await auto_strategy.execute(extracted_info, validation_result, message, user_id)
        
        # 推測情報の詳細を追加
        result['intelligent_analysis'] = {
            'inferred_data': context_analysis.missing_info_inference,
            'reasoning': context_analysis.reasoning[:150],
            'confidence': context_analysis.confidence
        }
        result['strategy_used'] = f"{self.strategy_name} → 推測自動登録"
        
        return result
    
    async def _execute_enhanced_confirmation(
        self,
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str,
        context_analysis
    ) -> Dict[str, Any]:
        """拡張確認フローの実行"""
        from .confirmation_strategy import EnhancedConfirmationStrategy
        
        enhanced_strategy = EnhancedConfirmationStrategy(self.service_provider)
        return await enhanced_strategy.execute(extracted_info, validation_result, message, user_id)
    
    def _apply_llm_inferences(
        self, 
        extracted_info: ExtractedWorkInfo, 
        inferences: Dict[str, Any]
    ) -> ExtractedWorkInfo:
        """
        LLMの推測情報をExtractedWorkInfoに適用
        """
        updated_data = extracted_info.dict()
        
        # 推測可能な情報を適用
        for key, value in inferences.items():
            if key in updated_data and not updated_data[key]:
                updated_data[key] = value
                logger.info(f"LLM推測適用: {key}={value}")
        
        return ExtractedWorkInfo(**updated_data)  # type: ignore