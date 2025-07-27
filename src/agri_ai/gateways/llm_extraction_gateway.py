"""
LLM抽出ゲートウェイ

LLM Function Callingの外部API通信を専門的に処理
I/Oとドメインロジックを分離し、テスタビリティを向上
"""

import logging
from typing import Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..core.config import settings
from ..utils.retry_decorator import gemini_retry

logger = logging.getLogger(__name__)


class ExtractWorkInfoTool(BaseModel):
    """LLM Function Calling用のツールスキーマ"""
    
    work_date: Optional[str] = Field(description="作業日（相対日付や具体的な日付）")
    field_name: Optional[str] = Field(description="圃場名")
    crop_name: Optional[str] = Field(description="作物名")
    work_category: Optional[str] = Field(description="作業分類（防除、施肥、収穫、栽培、管理）")
    materials: list[str] = Field(default=[], description="使用した資材・農薬名のリスト")
    quantity: Optional[float] = Field(description="使用量（数値）")
    unit: Optional[str] = Field(description="単位（L、kg、ml等）")
    work_count: Optional[int] = Field(description="作業回数")
    notes: Optional[str] = Field(description="特記事項やメモ")


class LLMExtractionGateway:
    """
    LLM呼び出し専用ゲートウェイクラス
    
    責務: 外部LLMサービスとの通信のみ
    - API呼び出し
    - エラーハンドリング
    - リトライ処理
    - レスポンス形式の正規化
    """
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.google_ai.model_name,
            google_api_key=settings.google_ai.api_key,
            temperature=0.1,  # 一貫性重視
            timeout=settings.google_ai.timeout
        )
        
        # Function Calling用のツール定義
        self.extract_tool = ExtractWorkInfoTool
        
        # LLMにツールをバインド
        self.llm_with_tools = self.llm.bind_tools([self.extract_tool])
    
    @gemini_retry
    async def call_function_calling(self, message: str) -> Dict[str, Any]:
        """
        LLM Function Callingを実行
        
        Args:
            message: 抽出対象のメッセージ
            
        Returns:
            Dict: 抽出された構造化データ
        """
        try:
            system_prompt = """
あなたは農業作業記録の情報抽出専門家です。
与えられたメッセージから作業に関する情報を正確に抽出してください。

抽出のポイント:
1. 日付は「昨日」「今日」「3日前」などの相対表現も正確に抽出
2. 圃場名は部分的な表記（「ハウス」「畑」）も含めて抽出
3. 資材名は商品名、一般名問わず可能な限り抽出
4. 使用量は数値と単位を分離して抽出
5. 不明な項目は無理に推測せず null で返す

確信が持てない情報は抽出しないでください。
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=message)
            ]
            
            # LLM呼び出し実行
            response = await self.llm_with_tools.ainvoke(messages)
            
            # ツール呼び出し結果の抽出
            if response.tool_calls:
                tool_call = response.tool_calls[0]
                return tool_call.get("args", {})
            else:
                logger.warning("LLMがFunction Callingを使用しませんでした")
                return {}
                
        except Exception as e:
            logger.error(f"LLM Function Calling エラー: {e}")
            raise
    
    async def call_simple_extraction(self, message: str) -> str:
        """
        シンプルなテキスト抽出（フォールバック用）
        
        Args:
            message: 抽出対象のメッセージ
            
        Returns:
            str: LLMからの生のレスポンス
        """
        try:
            simple_prompt = f"""
以下のメッセージから農業作業の情報を抽出し、
構造化されたテキストで返してください:

{message}

抽出項目:
- 作業日
- 圃場名
- 作物名
- 作業分類
- 使用資材
- 使用量
"""
            
            response = await self.llm.ainvoke([HumanMessage(content=simple_prompt)])
            return response.content
            
        except Exception as e:
            logger.error(f"シンプル抽出エラー: {e}")
            raise
    
    def get_model_info(self) -> Dict[str, str]:
        """使用中のモデル情報を取得"""
        return {
            "model_name": settings.google_ai.model_name,
            "temperature": str(self.llm.temperature),
            "timeout": str(settings.google_ai.timeout)
        }