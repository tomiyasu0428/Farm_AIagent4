import logging
from typing import Dict, Any, List
from .state import AgriAgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import os

# 読み取り専用ツールのインポート
from ..langchain_tools.field_info_tool import FieldInfoTool
from ..langchain_tools.work_log_search_agent_tool import WorkLogSearchAgentTool
from ..langchain_tools.field_agent_tool import FieldAgentTool
from ..agents.field_agent import FieldAgent
from ..agents.work_log_search_agent import WorkLogSearchAgent
from ..core.config import settings

logger = logging.getLogger(__name__)


class ReadAgent:
    """
    データベースからの読み取り専用クエリを担当するエージェント。
    LLMが自然言語で適切なツールを選択・実行し、柔軟な対応を行う。
    """

    def __init__(self):
        """ReadAgentの初期化 - LLMベースのツール選択システム"""
        logger.info("ReadAgent初期化開始")
        
        try:
            # LLMの初期化
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.1,
                google_api_key=settings.google_ai.api_key
            )
            
            # 専門エージェントの初期化
            self.field_agent = FieldAgent()
            self.work_log_search_agent = WorkLogSearchAgent()
            
            # 読み取り専用ツールをLangChainツールとして準備
            self.tools = [
                FieldInfoTool(),
                FieldAgentTool(self.field_agent),
                WorkLogSearchAgentTool(),
                # 他の読み取りツールも必要に応じて追加
            ]
            
            # LangChainエージェントの作成
            self._create_agent()
            
            logger.info(f"ReadAgent初期化完了 - {len(self.tools)}個のツールを搭載")
            
        except Exception as e:
            logger.error(f"ReadAgent初期化エラー: {e}")
            raise

    def _create_agent(self):
        """LLMベースのエージェントを作成"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3
        )
    
    def _get_system_prompt(self) -> str:
        """ReadAgent用のシステムプロンプト"""
        return """
あなたは農業管理システムの「ReadAgent」です。
データベースからの読み取り専用クエリを担当し、ユーザーの質問に対して適切なツールを選択して回答します。

利用可能なツール:
1. field_info_tool: 圃場の基本情報（名前、面積、作物など）を取得
2. field_agent_tool: 圃場に関する詳細な分析や複雑な質問に対応
3. work_log_search_agent_tool: 過去の作業記録を検索・分析

ユーザーの質問を理解し、最も適切なツールを使用して正確で有用な情報を提供してください。

回答は以下の点を心がけてください:
- 簡潔で分かりやすい日本語で回答
- 農業従事者にとって実用的な情報を提供
- 必要に応じて具体的なデータや数値を含める
- エラーが発生した場合は分かりやすく説明

自然言語の柔軟性を活かして、ユーザーの意図を的確に理解し、最適なツールを選択してください。
"""
    
    async def run(self, state: AgriAgentState) -> Dict[str, Any]:
        """
        ReadAgentの実行ロジック - LLMが適切なツールを選択・実行
        """
        logger.info("--- READ AGENT 実行開始 (LLMベース) ---")
        
        try:
            # メッセージから最新のユーザー入力を取得
            messages = state.get('messages', [])
            if not messages:
                state['final_response'] = "メッセージが見つかりません"
                return state
                
            latest_message = messages[-1] if messages else ""
            user_query = latest_message.get('content', '') if isinstance(latest_message, dict) else str(latest_message)
            
            logger.info(f"ReadAgent処理クエリ: {user_query}")
            
            # LLMエージェントによる実行
            result = self.agent_executor.invoke({"input": user_query})
            
            # 結果の取得
            if isinstance(result, dict) and "output" in result:
                response = result["output"]
            else:
                response = str(result)
            
            state['final_response'] = f"🔍 ReadAgent検索結果:\n\n{response}"
            
            # 中間ステップの記録
            state['intermediate_steps'] = state.get('intermediate_steps', []) + [
                "ReadAgent: LLMがツールを選択・実行"
            ]
            
            logger.info("ReadAgent実行完了")
            
        except Exception as e:
            logger.error(f"ReadAgent実行エラー: {e}")
            state['final_response'] = f"ReadAgentでエラーが発生しました: {str(e)}"
            
        return state
    
    def get_available_tools(self) -> List[str]:
        """
        利用可能なツールのリストを取得
        
        Returns:
            ツール名のリスト
        """
        return [tool.name for tool in self.tools]


logger.info("ReadAgent (LLMベース) の実装が完了しました。")