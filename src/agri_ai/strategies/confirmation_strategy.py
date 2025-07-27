"""
確認フロー戦略

不完全または曖昧なデータの確認フローを担当
ユーザーとの対話によって情報を補完する戦略
"""

import logging
from typing import Dict, Any

from .registration_strategy import RegistrationStrategy
from ..agents.models.work_log_extraction import ExtractedWorkInfo, WorkLogValidationResult
from ..providers.service_provider import IServiceProvider

logger = logging.getLogger(__name__)


class ConfirmationStrategy(RegistrationStrategy):
    """
    確認フロー戦略
    
    不足情報の補完やユーザー確認が必要なケースを処理
    """
    
    def __init__(self, service_provider: IServiceProvider):
        self.service_provider = service_provider
    
    @property
    def strategy_name(self) -> str:
        return "確認フロー戦略"
    
    def can_handle(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult
    ) -> bool:
        """
        確認フローが必要かどうかを判定
        
        条件:
        - 信頼度が低い (0.6未満)
        - 検証に失敗している
        - 不足情報が多い (2個以上)
        - または、他の戦略で処理できない全てのケース
        """
        confidence = extracted_info.confidence_score or 0.0
        missing_count = len(validation_result.missing_info)
        
        # 低信頼度または多数の不足情報
        if confidence < 0.6 or missing_count >= 2:
            return True
        
        # 検証失敗
        if not validation_result.is_valid:
            return True
        
        # デフォルトで全てのケースを処理可能（フォールバック戦略）
        return True
    
    async def execute(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        確認フロー実行
        """
        try:
            # 確認メッセージとオプションを生成
            confirmation_service = self.service_provider.get_work_log_confirmation_service()
            confirmation_data = confirmation_service.generate_confirmation_message(
                extracted_info, validation_result
            )
            
            logger.info(f"確認フロー開始: 不足情報={len(validation_result.missing_info)}件")
            
            return {
                'success': True,
                'requires_confirmation': True,
                'confirmation_data': {
                    'message': confirmation_data.confirmation_message,
                    'options': confirmation_data.options,
                    'extracted_info': extracted_info.dict(),
                    'validation_result': validation_result.dict(),
                    'original_message': message,
                    'user_id': user_id
                },
                'confidence_score': extracted_info.confidence_score,
                'registration_type': 'confirmation_required',
                'strategy_used': self.strategy_name
            }
            
        except Exception as e:
            logger.error(f"確認フローエラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '確認処理中にエラーが発生しました。',
                'requires_confirmation': False,
                'strategy_used': self.strategy_name
            }


class EnhancedConfirmationStrategy(RegistrationStrategy):
    """
    拡張確認フロー戦略
    
    LLM分析結果を活用した高度な確認フロー
    """
    
    def __init__(self, service_provider: IServiceProvider):
        self.service_provider = service_provider
    
    @property
    def strategy_name(self) -> str:
        return "拡張確認フロー戦略"
    
    def can_handle(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult
    ) -> bool:
        """
        拡張確認フローが必要かどうかを判定
        
        条件:
        - 信頼度が中程度 (0.4-0.7)
        - 部分的な検証成功
        - LLM分析が有効と判断される場合
        """
        confidence = extracted_info.confidence_score or 0.0
        missing_count = len(validation_result.missing_info)
        
        # 中程度の信頼度で拡張フローを使用
        return (
            0.4 <= confidence < 0.7 and 
            missing_count <= 3 and
            validation_result.suggestions  # 提案情報がある場合
        )
    
    async def execute(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        拡張確認フロー実行
        """
        try:
            # LLM文脈分析
            intelligent_decision_service = self.service_provider.get_intelligent_decision_service()
            user_history = await intelligent_decision_service.get_user_recent_history(user_id)
            context_analysis = await intelligent_decision_service.analyze_context(
                message, extracted_info, validation_result, user_history
            )
            
            # 基本確認フロー
            confirmation_service = self.service_provider.get_work_log_confirmation_service()
            confirmation_data = confirmation_service.generate_confirmation_message(
                extracted_info, validation_result
            )
            
            logger.info(f"拡張確認フロー開始: LLM分析結果={context_analysis.recommended_action}")
            
            return {
                'success': True,
                'requires_confirmation': True,
                'confirmation_data': {
                    'message': confirmation_data.confirmation_message,
                    'options': confirmation_data.options,
                    'extracted_info': extracted_info.dict(),
                    'validation_result': validation_result.dict(),
                    'original_message': message,
                    'user_id': user_id,
                    'llm_analysis': {
                        'urgency_level': context_analysis.urgency_level,
                        'reasoning': context_analysis.reasoning[:200],  # 要約
                        'confidence': context_analysis.confidence,
                        'recommended_action': context_analysis.recommended_action
                    }
                },
                'confidence_score': extracted_info.confidence_score,
                'registration_type': 'enhanced_confirmation_required',
                'strategy_used': self.strategy_name
            }
            
        except Exception as e:
            logger.error(f"拡張確認フローエラー: {e}")
            # フォールバック: 通常の確認フロー
            basic_strategy = ConfirmationStrategy(self.service_provider)
            return await basic_strategy.execute(extracted_info, validation_result, message, user_id)