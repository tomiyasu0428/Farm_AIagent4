import logging
from typing import Dict, Any, List
from .state import AgriAgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import os

# 書き込み専用ツールのインポート
from ..langchain_tools.work_log_registration_agent_tool import WorkLogRegistrationAgentTool
# from ..langchain_tools.field_registration_agent_tool import FieldRegistrationAgentTool  # 一時的にコメントアウト
from ..agents.work_log_registration_agent import WorkLogRegistrationAgent
# from ..agents.field_registration_agent import FieldRegistrationAgent  # 一時的にコメントアウト
from ..core.config import settings

logger = logging.getLogger(__name__)


class WriteAgent:
    """
    データベースへの書き込み専用クエリを担当するエージェント。
    LLMが自然言語で適切な登録・更新ツールを選択・実行し、柔軟な対応を行う。
    """

    def __init__(self):
        """WriteAgentの初期化 - LLMベースのツール選択システム"""
        logger.info("WriteAgent初期化開始")
        
        try:
            # LLMの初期化
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.1,
                google_api_key=settings.google_ai.api_key
            )
            
            # 専門エージェントの初期化
            self.work_log_registration_agent = WorkLogRegistrationAgent()
            # self.field_registration_agent = FieldRegistrationAgent()  # 一時的にコメントアウト
            
            # 書き込み専用ツールをLangChainツールとして準備
            self.tools = [
                WorkLogRegistrationAgentTool(),
                # FieldRegistrationAgentTool(self.field_registration_agent),  # 一時的にコメントアウト
                # 他の書き込みツールも必要に応じて追加
            ]
            
            # LangChainエージェントの作成
            self._create_agent()
            
            logger.info(f"WriteAgent初期化完了 - {len(self.tools)}個のツールを搭載")
            
        except Exception as e:
            logger.error(f"WriteAgent初期化エラー: {e}")
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
        """WriteAgent用のシステムプロンプト"""
        return """
あなたは農業管理システムの「WriteAgent」です。
データベースへの書き込み専用クエリを担当し、ユーザーの作業報告や新規登録要求に対して適切なツールを選択して処理します。

利用可能なツール:
1. work_log_registration_agent_tool: 作業記録の登録・保存（「昨日トマトに薬を撒いた」など）

ユーザーの入力を理解し、最も適切なツールを使用してデータを正確に登録・保存してください。

処理は以下の点を心がけてください:
- 自然言語の作業報告を構造化データに変換
- 農業従事者にとって使いやすい登録フロー
- 必要に応じて不足情報の確認を求める
- エラーが発生した場合は分かりやすく説明
- 確認フローを通じてユーザーの意図を正確に把握

自然言語の柔軟性を活かして、ユーザーの作業報告や登録要求の意図を的確に理解し、最適なツールを選択してください。
登録・保存処理では、データの正確性と整合性を最優先に考慮してください。
"""
    
    async def run(self, state: AgriAgentState) -> Dict[str, Any]:
        """
        WriteAgentの実行ロジック - LLMが適切なツールを選択・実行
        """
        logger.info("--- WRITE AGENT 実行開始 (LLMベース) ---")
        
        try:
            # メッセージから最新のユーザー入力を取得
            messages = state.get('messages', [])
            if not messages:
                state['final_response'] = "メッセージが見つかりません"
                return state
                
            latest_message = messages[-1] if messages else ""
            user_query = latest_message.get('content', '') if isinstance(latest_message, dict) else str(latest_message)
            
            logger.info(f"WriteAgent処理クエリ: {user_query}")
            
            # LLMエージェントによる実行
            result = self.agent_executor.invoke({"input": user_query})
            
            # 結果の取得
            if isinstance(result, dict) and "output" in result:
                response = result["output"]
            else:
                response = str(result)
            
            state['final_response'] = f"✍️ WriteAgent処理結果:\n\n{response}"
            
            # 中間ステップの記録
            state['intermediate_steps'] = state.get('intermediate_steps', []) + [
                "WriteAgent: LLMがツールを選択・実行"
            ]
            
            logger.info("WriteAgent実行完了")
            
        except Exception as e:
            logger.error(f"WriteAgent実行エラー: {e}")
            state['final_response'] = f"WriteAgentでエラーが発生しました: {str(e)}"
            
        return state
    
    def get_available_tools(self) -> List[str]:
        """
        利用可能なツールのリストを取得
        
        Returns:
            ツール名のリスト
        """
        return [tool.name for tool in self.tools]


logger.info("WriteAgent (LLMベース) の実装が完了しました。")