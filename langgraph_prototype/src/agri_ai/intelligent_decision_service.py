"""
知的判断サービス

必要なときのみLLMを呼び出して柔軟な判断を行う
固定フローをベースに、特定条件でLLMの知的判断を追加
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..core.config import settings
from ..agents.models.work_log_extraction import ExtractedWorkInfo, WorkLogValidationResult

logger = logging.getLogger(__name__)


class ContextAnalysis(BaseModel):
    """LLMによる文脈分析結果"""
    
    should_override: bool = Field(description="固定フローを上書きすべきか")
    recommended_action: str = Field(description="推奨アクション")
    confidence: float = Field(description="判断の信頼度")
    reasoning: str = Field(description="判断理由")
    urgency_level: str = Field(description="緊急度レベル: low/medium/high/critical")
    missing_info_inference: Optional[Dict[str, Any]] = Field(description="推測可能な不足情報")


class IntelligentDecisionService:
    """知的判断サービス"""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.google_ai.model_name,
            google_api_key=settings.google_ai.api_key,
            temperature=0.2,  # 判断の一貫性を保つため低め
            timeout=settings.google_ai.timeout
        )
        
        # LLM呼び出し条件の閾値
        self.CONFIDENCE_BOUNDARY_LOWER = 0.4  # これ以下は確実に確認が必要
        self.CONFIDENCE_BOUNDARY_UPPER = 0.8  # これ以上は確実に自動登録
        self.VALIDATION_FAILURE_THRESHOLD = 2  # 検証失敗項目数
    
    async def should_use_intelligent_decision(
        self, 
        message: str,
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult
    ) -> bool:
        """
        LLMによる知的判断が必要かどうかを判定
        
        Returns:
            bool: LLM判断が必要な場合True
        """
        # 1. グレーゾーン信頼度（固定フローでは判断困難）
        confidence = extracted_info.confidence_score or 0.0
        if self.CONFIDENCE_BOUNDARY_LOWER < confidence < self.CONFIDENCE_BOUNDARY_UPPER:
            logger.info(f"グレーゾーン信頼度検出: {confidence:.2f}")
            return True
        
        # 2. 緊急性キーワード検出
        urgent_keywords = [
            "病気", "枯れ", "枯死", "緊急", "至急", "急いで", "すぐに",
            "異常", "変色", "しおれ", "倒伏", "害虫大発生"
        ]
        if any(keyword in message for keyword in urgent_keywords):
            logger.info("緊急性キーワード検出")
            return True
        
        # 3. 複数の検証失敗（文脈で解決可能な可能性）
        validation_failures = 0
        if not validation_result.field_validation.get("is_valid", True):
            validation_failures += 1
        if not validation_result.crop_validation.get("is_valid", True):
            validation_failures += 1
        if any(not m.get("is_valid", True) for m in validation_result.material_validation):
            validation_failures += 1
            
        if validation_failures >= self.VALIDATION_FAILURE_THRESHOLD:
            logger.info(f"複数検証失敗検出: {validation_failures}項目")
            return True
        
        # 4. 文脈的推測が可能そうなケース
        contextual_clues = [
            "いつもの", "例の", "前回と同じ", "昨日と同じ場所",
            "ハウス", "温室", "ビニールハウス"  # 圃場と作物の関連性推測可能
        ]
        if any(clue in message for clue in contextual_clues):
            logger.info("文脈推測手がかり検出")
            return True
        
        return False
    
    async def analyze_context(
        self,
        message: str,
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        user_history: Optional[List[Dict]] = None
    ) -> ContextAnalysis:
        """
        LLMによる文脈分析と知的判断
        
        Args:
            message: 元のメッセージ
            extracted_info: 抽出された情報
            validation_result: 検証結果
            user_history: ユーザーの過去の作業記録
            
        Returns:
            ContextAnalysis: 分析結果と推奨アクション
        """
        try:
            # システムプロンプト
            system_prompt = """
あなたは農業作業記録の専門家です。以下の情報を分析して、適切な判断を行ってください：

【判断の観点】
1. 緊急性：作物の健康に関わる緊急事態か？
2. 文脈推測：明らかに推測可能な不足情報はあるか？
3. ユーザーパターン：過去の記録から推測できることはあるか？
4. リスク評価：間違った登録をするリスクはどの程度か？

【推奨アクション】
- "auto_register_urgent": 緊急性が高く即座に登録すべき
- "auto_register_inferred": 文脈から推測して自動登録可能
- "confirm_with_suggestions": 確認が必要だが推測情報を提示
- "require_confirmation": 通常の確認フローが必要
- "request_more_info": より詳細な情報が必要

【緊急度レベル】
- critical: 作物の生死に関わる（病気、害虫大発生など）
- high: 迅速な対応が必要（異常発見など）
- medium: 通常より重要（初回作業など）
- low: 通常レベル

慎重に判断し、農業の専門知識を活用してください。
"""
            
            # ユーザーメッセージの構築
            user_prompt_parts = [
                f"【作業報告メッセージ】\n{message}",
                f"\n【抽出された情報】",
                f"- 作業日: {extracted_info.work_date}",
                f"- 圃場名: {extracted_info.field_name}",
                f"- 作物名: {extracted_info.crop_name}",
                f"- 作業分類: {extracted_info.work_category}",
                f"- 使用資材: {extracted_info.materials}",
                f"- 使用量: {extracted_info.quantity} {extracted_info.unit}",
                f"- 抽出信頼度: {extracted_info.confidence_score}",
                f"\n【検証結果】",
                f"- 全体検証: {'成功' if validation_result.is_valid else '失敗'}",
                f"- 不足情報: {validation_result.missing_info}",
                f"- 提案事項: {validation_result.suggestions}"
            ]
            
            # ユーザー履歴があれば追加
            if user_history:
                recent_logs = user_history[-5:]  # 直近5件
                history_summary = []
                for log in recent_logs:
                    summary = f"  - {log.get('work_date', '不明')}: {log.get('category', '不明')} ({log.get('extracted_data', {}).get('field_name', '不明')})"
                    history_summary.append(summary)
                
                user_prompt_parts.extend([
                    f"\n【ユーザーの最近の作業履歴】",
                    *history_summary
                ])
            
            user_prompt = "\n".join(user_prompt_parts)
            user_prompt += "\n\n上記の情報を総合的に分析し、適切な判断を行ってください。"
            
            # LLMに問い合わせ
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # レスポンスを解析してContextAnalysisに変換
            return self._parse_llm_response(response.content, extracted_info, validation_result)
            
        except Exception as e:
            logger.error(f"LLM文脈分析エラー: {e}")
            # エラー時は安全側に倒して確認フローを選択
            return ContextAnalysis(
                should_override=False,
                recommended_action="require_confirmation",
                confidence=0.0,
                reasoning=f"LLM分析エラーのため安全側の判断: {str(e)}",
                urgency_level="low"
            )
    
    def _parse_llm_response(
        self, 
        llm_response: str, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult
    ) -> ContextAnalysis:
        """
        LLMレスポンスを解析してContextAnalysisに変換
        
        Args:
            llm_response: LLMからの応答テキスト
            extracted_info: 抽出情報
            validation_result: 検証結果
            
        Returns:
            ContextAnalysis: 構造化された分析結果
        """
        # 簡易的なキーワードベース解析（本格実装時はより高度な解析を実装）
        response_lower = llm_response.lower()
        
        # 推奨アクションの判定
        if "auto_register_urgent" in response_lower or ("緊急" in response_lower and "自動" in response_lower):
            recommended_action = "auto_register_urgent"
            should_override = True
            confidence = 0.8
        elif "auto_register_inferred" in response_lower or ("推測" in response_lower and "自動" in response_lower):
            recommended_action = "auto_register_inferred"
            should_override = True
            confidence = 0.7
        elif "confirm_with_suggestions" in response_lower or "提案" in response_lower:
            recommended_action = "confirm_with_suggestions"
            should_override = True
            confidence = 0.6
        elif "request_more_info" in response_lower or "詳細" in response_lower:
            recommended_action = "request_more_info"
            should_override = True
            confidence = 0.5
        else:
            recommended_action = "require_confirmation"
            should_override = False
            confidence = 0.3
        
        # 緊急度の判定
        if "critical" in response_lower or "生死" in response_lower:
            urgency_level = "critical"
        elif "high" in response_lower or "緊急" in response_lower:
            urgency_level = "high"
        elif "medium" in response_lower:
            urgency_level = "medium"
        else:
            urgency_level = "low"
        
        # 推測情報の抽出（簡易版）
        missing_info_inference = None
        if "推測" in response_lower and validation_result.missing_info:
            missing_info_inference = {}
            # より高度な推測ロジックは後で実装
        
        return ContextAnalysis(
            should_override=should_override,
            recommended_action=recommended_action,
            confidence=confidence,
            reasoning=llm_response[:500],  # 理由の抜粋
            urgency_level=urgency_level,
            missing_info_inference=missing_info_inference
        )
    
    async def get_user_recent_history(self, user_id: str, limit: int = 5) -> List[Dict]:
        """
        ユーザーの最近の作業履歴を取得
        
        Args:
            user_id: ユーザーID
            limit: 取得件数
            
        Returns:
            List[Dict]: 最近の作業記録リスト
        """
        try:
            # TODO: 実際のデータベースからの履歴取得実装
            # 現在はモック実装（開発完了時に実装）
            mock_history = [
                {
                    'work_date': '2025-07-25',
                    'category': '防除',
                    'extracted_data': {
                        'field_name': 'トマトハウス',
                        'crop_name': 'トマト',
                        'material_names': ['ダコニール1000']
                    }
                },
                {
                    'work_date': '2025-07-24', 
                    'category': '施肥',
                    'extracted_data': {
                        'field_name': 'トマトハウス',
                        'crop_name': 'トマト'
                    }
                }
            ]
            return mock_history[:limit]
        except Exception as e:
            logger.error(f"ユーザー履歴取得エラー: {e}")
            return []