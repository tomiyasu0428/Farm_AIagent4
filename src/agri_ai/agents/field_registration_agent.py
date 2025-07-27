"""
FieldRegistrationAgent: 圃場登録専門エージェント

AIエージェント構築のポイントに基づく設計:
- 単一責任: 圃場登録のみに特化
- KV-Cache最適化: 固定システムプロンプト
- MasterAgentの複雑化回避: 専門エージェント分離
"""

import logging
from typing import Any, Dict, List, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from ..langchain_tools.field_registration_tool import FieldRegistrationTool
from ..core.config import settings

logger = logging.getLogger(__name__)


class FieldRegistrationAgent:
    """
    圃場登録専門エージェント
    
    責任範囲:
    - 新しい圃場の登録・追加
    - エリア別圃場管理
    - 圃場コードの自動生成
    - 登録データの検証
    """
    
    def __init__(self):
        """FieldRegistrationAgentの初期化"""
        self.config = settings
        self.llm = self._setup_llm()
        self.tools = self._setup_tools()
        self.agent_executor = self._create_agent()
        
    def _setup_llm(self) -> ChatGoogleGenerativeAI:
        """LLMの設定"""
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=self.config.google_ai.api_key,
            temperature=0.1,
            max_tokens=2048,
            timeout=30
        )
    
    def _setup_tools(self) -> List[Any]:
        """ツールの設定 - 登録専用ツール"""
        return [
            FieldRegistrationTool(),   # 圃場登録・追加専用
        ]
    
    def _create_system_prompt(self) -> str:
        """
        KV-Cache最適化された固定システムプロンプト
        AIエージェント構築のポイント: プロンプト構造の安定化
        """
        return """あなたは圃場登録の専門家「FieldRegistrationAgent」です。

## 専門領域
新しい圃場の登録・追加処理のみを担当します。

## 主要機能
### 圃場登録・追加 ⭐
- 自然言語での圃場登録処理
- エリア別圃場管理（豊糠、豊緑など）
- 面積・土壌・エリア情報の同時登録
- 圃場コードの自動生成
- 登録データの検証・確認

## 対応する登録パターン
1. 基本登録: 「新田を0.8haで豊糠エリアに登録」
2. 詳細登録: 「橋向こう④を1.5ha、土壌タイプ：砂質で豊糠エリアに登録」
3. 簡易登録: 「学校前を豊緑エリアに追加」

## 応答方針
1. 登録要求を正確に解析する
2. 不足情報があれば質問で補完する
3. 登録完了時は詳細な確認情報を表示する
4. エラー時は具体的な解決策を提示する
5. 圃場情報検索などの専門外要求は対応範囲外と伝える

## 利用可能ツール
- field_registration: 新しい圃場の登録・追加

新しい圃場の登録について、何でもお手伝いします！"""

    def _create_agent(self) -> AgentExecutor:
        """エージェントの作成"""
        # プロンプトテンプレートの作成（KV-Cache最適化）
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._create_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # ツール呼び出しエージェントの作成
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # エージェント実行器の作成
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=3,
            early_stopping_method="generate",
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    
    async def process_query(self, query: str, chat_history: Optional[List] = None) -> Dict[str, Any]:
        """
        圃場登録クエリの処理
        
        Args:
            query: ユーザーからの登録依頼
            chat_history: 会話履歴（オプション）
            
        Returns:
            処理結果辞書
        """
        try:
            logger.info(f"FieldRegistrationAgent処理開始: {query}")
            
            # 登録関連かどうかの事前チェック
            if not self._is_registration_query(query):
                return {
                    "success": False,
                    "response": "申し訳ございませんが、圃場の登録・追加以外のご質問には対応できません。圃場の登録や新しい圃場の追加についてお聞きください。",
                    "agent_type": "field_registration_agent",
                    "query_type": "out_of_scope"
                }
            
            # エージェント実行
            result = await self.agent_executor.ainvoke({
                "input": query,
                "chat_history": chat_history or []
            })
            
            return {
                "success": True,
                "response": result["output"],
                "agent_type": "field_registration_agent",
                "query_type": "field_registration",
                "intermediate_steps": result.get("intermediate_steps", [])
            }
            
        except Exception as e:
            logger.error(f"FieldRegistrationAgent処理エラー: {e}")
            return {
                "success": False,
                "response": f"圃場登録中にエラーが発生しました: {str(e)}",
                "agent_type": "field_registration_agent",
                "error": str(e)
            }
    
    def _is_registration_query(self, query: str) -> bool:
        """
        圃場登録関連クエリかどうかの判定
        
        Args:
            query: ユーザークエリ
            
        Returns:
            登録関連かどうか
        """
        registration_keywords = [
            # 登録・追加関連キーワード
            "登録", "追加", "新しい", "作成", "新規",
            "入力", "設定", "データ入力",
            
            # エリア関連
            "エリア", "地区", "豊糠", "豊緑",
            
            # 圃場関連（登録文脈で）
            "圃場", "ハウス", "畑", "田", "フィールド",
            
            # 具体的圃場名（登録される可能性のある名前）
            "橋向こう", "登山道前", "橋前", "田んぼあと",
            "若菜横", "学校裏", "相田さん向かい", "フォレスト",
            "学校前", "新田", "若菜裏"
        ]
        
        # 登録を示唆するパターンもチェック
        registration_patterns = [
            "を.*登録", "を.*追加", "を.*作成",
            "ha.*登録", "ヘクタール.*登録",
            "エリアに.*登録", "エリアに.*追加"
        ]
        
        # キーワードマッチ
        keyword_match = any(keyword in query for keyword in registration_keywords)
        
        # パターンマッチ
        import re
        pattern_match = any(re.search(pattern, query) for pattern in registration_patterns)
        
        return keyword_match or pattern_match
    
    def get_capabilities(self) -> Dict[str, Any]:
        """エージェントの能力情報を返す"""
        return {
            "agent_name": "FieldRegistrationAgent",
            "specialization": "圃場登録・追加",
            "tools": ["field_registration"],
            "supported_queries": [
                "新しい圃場の登録",
                "エリア別圃場追加",
                "面積・土壌情報付き登録",
                "圃場コード自動生成"
            ],
            "sample_queries": [
                "新田を0.8haで豊糠エリアに登録",
                "橋向こう④を1.5haで豊糠エリアに登録",
                "学校前を豊緑エリアに追加",
                "フォレストを2.0ha、土壌：砂質で豊糠エリアに登録"
            ],
            "architecture_benefit": "MasterAgentの複雑化回避"
        }


# 使用例とテスト用の関数
async def test_field_registration_agent():
    """FieldRegistrationAgentのテスト実行"""
    agent = FieldRegistrationAgent()
    
    test_queries = [
        "新田を0.8haで豊糠エリアに登録",
        "橋向こう④を1.5haで豊糠エリアに登録して",
        "学校前を豊緑エリアに追加したい",
        "第1ハウスの状況を教えて"  # 対応範囲外のテスト
    ]
    
    for query in test_queries:
        print(f"\n--- テスト: {query} ---")
        result = await agent.process_query(query)
        print(f"成功: {result['success']}")
        print(f"応答: {result['response']}")
        print(f"タイプ: {result.get('query_type', 'unknown')}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_field_registration_agent())