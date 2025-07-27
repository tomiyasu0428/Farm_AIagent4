"""
FieldAgentTool: FieldAgent呼び出し用ツール

MasterAgentからFieldAgentを呼び出すためのカスタムツール
AIエージェント構築のポイント: ツール削除なし、マスキング手法
"""

import logging
from typing import Any, Dict, Optional

from .base_tool import AgriAIBaseTool

logger = logging.getLogger(__name__)


class FieldAgentTool(AgriAIBaseTool):
    """FieldAgent専門エージェント呼び出しツール"""

    name: str = "field_agent_tool"
    description: str = (
        "圃場情報の専門的な分析が必要な場合に、FieldAgent専門エージェントを呼び出します。"
        "圃場の名前、面積、作付け計画、現在の作物状況など、圃場に関する詳細な情報が必要な場合に使用してください。"
        "使用例: '第1ハウスの詳細情報', '全圃場の作付け状況', 'A畑の面積と土壌情報'"
    )

    def __init__(self, field_agent):
        """
        FieldAgentToolの初期化
        
        Args:
            field_agent: FieldAgentのインスタンス
        """
        super().__init__()
        # Pydanticモデルの制約を回避するため_で始める
        self._field_agent = field_agent

    async def _execute(self, query: str) -> Dict[str, Any]:
        """FieldAgentの実行"""
        try:
            logger.info(f"FieldAgentTool実行開始: {query}")
            
            # FieldAgentに問い合わせを委譲
            result = await self._field_agent.process_query(query)
            
            if result["success"]:
                return {
                    "status": "success",
                    "response": result["response"],
                    "agent_type": result["agent_type"],
                    "query_type": result.get("query_type", "field_info"),
                    "intermediate_steps": result.get("intermediate_steps", [])
                }
            else:
                return {
                    "status": "error", 
                    "error": result.get("response", "FieldAgentでエラーが発生しました"),
                    "agent_type": result["agent_type"]
                }
                
        except Exception as e:
            logger.error(f"FieldAgentTool実行エラー: {e}")
            return {
                "status": "error",
                "error": f"FieldAgent呼び出し中にエラーが発生しました: {str(e)}"
            }

    def _format_result(self, result: Dict[str, Any]) -> str:
        """結果のフォーマット"""
        if result.get("status") == "error":
            return f"❌ {result.get('error', '不明なエラー')}"
        
        response = result.get("response", "結果なし")
        agent_type = result.get("agent_type", "unknown")
        
        formatted_lines = [
            f"🤖 {agent_type}からの回答:",
            "",
            response
        ]
        
        # デバッグ情報（必要に応じて）
        if logger.isEnabledFor(logging.DEBUG):
            intermediate_steps = result.get("intermediate_steps", [])
            if intermediate_steps:
                formatted_lines.extend([
                    "",
                    "--- デバッグ情報 ---",
                    f"実行ステップ数: {len(intermediate_steps)}"
                ])
        
        return "\n".join(formatted_lines)

    async def _arun(self, query: str, **kwargs: Any) -> str:
        """非同期実行"""
        result = await self._execute(query)
        return self._format_result(result)
    
    def is_field_related(self, query: str) -> bool:
        """
        クエリが圃場関連かどうかの判定（登録・管理機能も含む）
        
        Args:
            query: ユーザークエリ
            
        Returns:
            圃場関連かどうか
        """
        field_keywords = [
            # 基本圃場キーワード
            "圃場", "ハウス", "畑", "田", "フィールド",
            "A畑", "B畑", "C畑", "第1", "第2", "第3",
            "面積", "土壌", "作付け", "栽培", "生育",
            "全圃場", "すべて", "一覧",
            
            # 登録・追加キーワード
            "登録", "追加", "新しい", "作成",
            "エリア", "地区", "豊糠", "豊緑",
            
            # 具体的圃場名
            "橋向こう", "登山道前", "橋前", "田んぼあと",
            "若菜横", "学校裏", "相田さん向かい", "フォレスト",
            "学校前", "新田", "若菜裏"
        ]
        
        return any(keyword in query for keyword in field_keywords)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """ツールの能力情報"""
        return {
            "tool_name": "FieldAgentTool",
            "purpose": "圃場情報専門エージェントの呼び出し",
            "agent_type": "field_agent",
            "supported_queries": [
                "圃場の基本情報確認",
                "現在の作付け状況照会",
                "作付け計画の確認",
                "圃場一覧の取得"
            ],
            "integration_level": "deep",  # 深い統合レベル
            "cache_optimized": True  # KV-Cache最適化対応
        }