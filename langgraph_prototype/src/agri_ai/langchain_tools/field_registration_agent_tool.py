"""
FieldRegistrationAgentTool: FieldRegistrationAgent専用呼び出しツール

MasterAgentからFieldRegistrationAgentを呼び出すためのカスタムツール
AIエージェント構築のポイント: 専門エージェント分離によるMasterAgent複雑化回避
"""

import logging
from typing import Any, Dict, Optional

from .base_tool import AgriAIBaseTool

logger = logging.getLogger(__name__)


class FieldRegistrationAgentTool(AgriAIBaseTool):
    """FieldRegistrationAgent専門エージェント呼び出しツール"""

    name: str = "field_registration_agent_tool"
    description: str = (
        "新しい圃場の登録・追加が必要な場合に、FieldRegistrationAgent専門エージェントを呼び出します。"
        "圃場の新規登録、エリア別追加、面積・土壌情報の設定など、圃場登録に関する処理に使用してください。"
        "使用例: '新田を0.8haで豊糠エリアに登録', '橋向こう④を1.5haで登録', '学校前を豊緑エリアに追加'"
    )

    def __init__(self, field_registration_agent):
        """
        FieldRegistrationAgentToolの初期化
        
        Args:
            field_registration_agent: FieldRegistrationAgentのインスタンス
        """
        super().__init__()
        # Pydanticモデルの制約を回避するため_で始める
        self._field_registration_agent = field_registration_agent

    async def _execute(self, query: str) -> Dict[str, Any]:
        """FieldRegistrationAgentの実行"""
        try:
            logger.info(f"FieldRegistrationAgentTool実行開始: {query}")
            
            # FieldRegistrationAgentに登録依頼を委譲
            result = await self._field_registration_agent.process_query(query)
            
            if result["success"]:
                return {
                    "status": "success",
                    "response": result["response"],
                    "agent_type": result["agent_type"],
                    "query_type": result.get("query_type", "field_registration"),
                    "intermediate_steps": result.get("intermediate_steps", [])
                }
            else:
                return {
                    "status": "error", 
                    "error": result.get("response", "FieldRegistrationAgentでエラーが発生しました"),
                    "agent_type": result["agent_type"]
                }
                
        except Exception as e:
            logger.error(f"FieldRegistrationAgentTool実行エラー: {e}")
            return {
                "status": "error",
                "error": f"FieldRegistrationAgent呼び出し中にエラーが発生しました: {str(e)}"
            }

    def _format_result(self, result: Dict[str, Any]) -> str:
        """結果のフォーマット"""
        if result.get("status") == "error":
            return f"❌ {result.get('error', '不明なエラー')}"
        
        response = result.get("response", "結果なし")
        agent_type = result.get("agent_type", "unknown")
        
        formatted_lines = [
            f"🏡 {agent_type}からの登録結果:",
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
    
    def is_registration_related(self, query: str) -> bool:
        """
        クエリが圃場登録関連かどうかの判定
        
        Args:
            query: ユーザークエリ
            
        Returns:
            登録関連かどうか
        """
        registration_keywords = [
            # 登録・追加キーワード
            "登録", "追加", "新しい", "作成", "新規",
            "入力", "設定", "データ入力",
            "を.*登録", "を.*追加", "を.*作成",
            
            # エリア関連
            "エリア", "地区", "豊糠", "豊緑",
            
            # 圃場関連（登録文脈で）
            "圃場", "ハウス", "畑", "田", "フィールド",
            
            # 具体的圃場名
            "橋向こう", "登山道前", "橋前", "田んぼあと",
            "若菜横", "学校裏", "相田さん向かい", "フォレスト",
            "学校前", "新田", "若菜裏"
        ]
        
        return any(keyword in query for keyword in registration_keywords)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """ツールの能力情報"""
        return {
            "tool_name": "FieldRegistrationAgentTool",
            "purpose": "圃場登録専門エージェントの呼び出し",
            "agent_type": "field_registration_agent",
            "supported_queries": [
                "新しい圃場の登録",
                "エリア別圃場追加",
                "面積・土壌情報付き登録",
                "圃場コードの自動生成"
            ],
            "integration_level": "deep",  # 深い統合レベル
            "cache_optimized": True,  # KV-Cache最適化対応
            "architecture_benefit": "MasterAgent複雑化回避"
        }