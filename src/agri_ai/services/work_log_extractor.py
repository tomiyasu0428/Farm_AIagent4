"""
作業記録情報抽出サービス (v2.0 - I/O分離版)

LLMのFunction Calling機能を活用した高精度な情報抽出
I/O（LLM通信）とドメインロジック（スコア計算）を分離
"""

import logging
from typing import Dict, Any, Optional
from langchain.tools import tool

from ..agents.models.work_log_extraction import ExtractedWorkInfo
from ..gateways.llm_extraction_gateway import LLMExtractionGateway
from ..domain.work_info_scorer import WorkInfoScorer

logger = logging.getLogger(__name__)


class WorkLogExtractor:
    """
    作業記録情報抽出クラス (リファクタリング版)

    責務:
    - LLMGatewayとScorerの統合
    - 抽出フローの調整
    - フォールバック処理
    """

    def __init__(
        self, gateway: Optional[LLMExtractionGateway] = None, scorer: Optional[WorkInfoScorer] = None
    ):
        # 依存性注入対応（テスト時にモック差し替え可能）
        self.gateway = gateway or LLMExtractionGateway()
        self.scorer = scorer or WorkInfoScorer()

    @tool("extract_work_info", return_direct=True)
    def extract_work_info_tool(self, work_message: str) -> ExtractedWorkInfo:
        """
        作業報告メッセージから構造化された情報を抽出するツール

        Args:
            work_message: ユーザーの作業報告メッセージ

        Returns:
            ExtractedWorkInfo: 抽出された作業情報
        """
        # このツールはLLMが呼び出すためのスキーマ定義として使用
        # 実際の処理はLLM経由で行われるため、ここではダミーの値を返す
        return ExtractedWorkInfo()  # type: ignore[call-arg]

    async def extract_work_information(self, message: str) -> ExtractedWorkInfo:
        """
        自然言語メッセージから作業情報を抽出 (I/O分離版)

        Args:
            message: ユーザーの自然言語報告

        Returns:
            ExtractedWorkInfo: 抽出された構造化情報
        """
        try:
            # Step 1: LLMGateway経由で構造化データを取得
            extracted_data = await self.gateway.call_function_calling(message)

            if not extracted_data:
                # Function Calling失敗時はフォールバック
                logger.warning("Function Calling結果が空です。フォールバック処理を実行します。")
                return await self._fallback_extraction(message)

            # Step 2: Scorer経由で信頼度スコアを計算
            confidence_score = self.scorer.calculate_confidence_score(extracted_data)
            extracted_data["confidence_score"] = confidence_score

            # Step 3: ExtractedWorkInfoオブジェクトを作成
            # Pydantic モデルに動的 Dict を渡すため型チェックを無視
            extracted_info = ExtractedWorkInfo(**extracted_data)  # type: ignore

            logger.info(f"作業情報抽出完了: 信頼度={confidence_score:.2f}")
            return extracted_info

        except Exception as e:
            logger.error(f"作業情報抽出エラー: {e}")
            # エラー時のフォールバック
            return await self._fallback_extraction(message)

    def _calculate_confidence_score(self, extracted_data: Dict[str, Any]) -> float:
        """
        (後方互換用) 信頼度スコア計算はScorerに委譲
        """
        return self.scorer.calculate_confidence_score(extracted_data)

    async def _fallback_extraction(self, message: str) -> ExtractedWorkInfo:
        """
        フォールバック用の基本抽出処理

        Args:
            message: 作業報告メッセージ

        Returns:
            ExtractedWorkInfo: 基本的な抽出結果
        """
        import re

        extracted = ExtractedWorkInfo()  # type: ignore

        # 基本的な正規表現による抽出
        # 日付パターン
        date_patterns = [
            (r"昨日|きのう", "昨日"),
            (r"一昨日|おととい", "一昨日"),
            (r"今日|きょう", "今日"),
            (r"(\d+)日前", r"\1日前"),
        ]

        for pattern, replacement in date_patterns:
            if re.search(pattern, message):
                extracted.work_date = replacement
                break

        # 作業分類キーワード
        if any(keyword in message for keyword in ["防除", "農薬", "散布", "殺菌", "殺虫"]):
            extracted.work_category = "防除"
        elif any(keyword in message for keyword in ["施肥", "肥料", "追肥", "元肥"]):
            extracted.work_category = "施肥"
        elif any(keyword in message for keyword in ["収穫", "収穫量", "出荷"]):
            extracted.work_category = "収穫"
        elif any(keyword in message for keyword in ["播種", "定植", "摘心", "誘引"]):
            extracted.work_category = "栽培"
        elif any(keyword in message for keyword in ["草刈り", "清掃", "点検"]):
            extracted.work_category = "管理"

        extracted.confidence_score = 0.3  # フォールバックなので低めの信頼度

        logger.warning("フォールバック抽出を実行しました")
        return extracted
