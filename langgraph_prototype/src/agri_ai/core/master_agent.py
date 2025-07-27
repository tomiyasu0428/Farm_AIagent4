"""
MasterAgent: 農業AI司令塔エージェント

AIエージェント構築のポイントに基づく設計:
- KV-Cache最適化: 固定システムプロンプト
- プラン共有: 処理の透明性確保
- 専門エージェント連携: FieldAgentなどの専門家を管理
"""

import os

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

from .config import settings
from .session_manager import SessionManager
from ..database.mongodb_client import mongodb_client
from ..services.query_analyzer import QueryAnalyzer

logger = logging.getLogger(__name__)


class MasterAgent:
    """
    農業AI司令塔エージェント

    役割:
    - ユーザー指示の解釈と分析
    - 適切な専門エージェントへのタスク委譲
    - 実行プランの作成と共有
    - 統合的な結果の提供
    """

    def __init__(self):
        self.llm = None
        self.agent_executor = None
        self.tools = []
        self.field_agent = None  # 圃場専門エージェント
        self.execution_plan = None  # 実行プラン
        self.query_analyzer = QueryAnalyzer()  # クエリ分析サービス
        self.session_manager = SessionManager()  # セッション管理
        
        # 初期化を実行
        self.initialize()

    def initialize(self):
        """エージェントの初期化"""
        # LangSmith トレーシングの設定
        if settings.langsmith.tracing_enabled:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = settings.langsmith.api_key
            os.environ["LANGCHAIN_PROJECT"] = settings.langsmith.project_name
            os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith.endpoint
            logger.info(
                f"LangSmith トレーシングが有効になりました。プロジェクト: {settings.langsmith.project_name}"
            )

        # データベース接続
        # MongoDB接続は非同期処理で実行
        import asyncio

        if not mongodb_client.is_connected:
            try:
                # 既存のイベントループを確認
                try:
                    loop = asyncio.get_running_loop()
                    # 既にイベントループが実行中の場合はタスクとしてスケジュール
                    task = loop.create_task(mongodb_client.connect())
                    # メッセージ処理前に接続完了を待つ
                    logger.info("MongoDB接続タスクをスケジュールしました")
                except RuntimeError:
                    # イベントループが実行されていない場合は同期実行
                    asyncio.run(mongodb_client.connect())
            except Exception as e:
                logger.error(f"MongoDB接続エラー: {e}")
                raise

        # 専門エージェントの初期化
        self._initialize_specialized_agents()

        # ツールの初期化
        self._initialize_tools()

        # LLMの初期化
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", temperature=0.1, google_api_key=settings.google_ai.api_key
        )

        # エージェントの作成
        self._initialize_agent()
        logger.info("農業AIエージェントの初期化が完了しました")

    def _initialize_specialized_agents(self):
        """専門エージェントの初期化"""
        from ..agents.field_agent import FieldAgent
        from ..agents.work_log_registration_agent import WorkLogRegistrationAgent
        from ..agents.work_log_search_agent import WorkLogSearchAgent

        self.field_agent = FieldAgent()
        self.work_log_registration_agent = WorkLogRegistrationAgent()
        self.work_log_search_agent = WorkLogSearchAgent()
        logger.info("専門エージェント初期化完了")

    def _initialize_tools(self):
        """ツールの初期化（AIエージェント構築のポイント: ツール削除なし）"""
        from ..langchain_tools.field_agent_tool import FieldAgentTool
        from ..langchain_tools.work_log_registration_agent_tool import WorkLogRegistrationAgentTool
        from ..langchain_tools.work_log_search_agent_tool import WorkLogSearchAgentTool

        self.tools = [
            FieldAgentTool(self.field_agent),  # 圃場情報専門エージェント
            WorkLogRegistrationAgentTool(),  # 作業記録登録専門エージェント
            WorkLogSearchAgentTool(),  # 作業記録検索専門エージェント
        ]

    def _initialize_agent(self):
        """エージェントの作成とエグゼキュータの初期化（メモリなし版）"""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._get_system_prompt()),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_openai_tools_agent(self.llm, self.tools, prompt)

        # メモリなし版のエグゼキュータ（互換性のため保持）
        self.agent_executor = AgentExecutor(
            agent=agent, tools=self.tools, verbose=True, handle_parsing_errors=True, max_iterations=5
        )
    
    def create_agent_with_memory(self, user_id: str, thread_id: str = "default") -> AgentExecutor:
        """
        メモリ付きAgentExecutorを作成
        
        Args:
            user_id: ユーザーID
            thread_id: スレッドID
            
        Returns:
            AgentExecutor: メモリ付きエージェント
        """
        try:
            # Redis接続を試行
            try:
                # RedisChatMessageHistory を使用（LangChain標準）
                message_history = RedisChatMessageHistory(
                    session_id=f"{user_id}:{thread_id}",
                    url=os.getenv("REDIS_URL", "redis://localhost:6379"),
                    ttl=86400  # 24時間
                )
                
                # Redis接続テスト
                message_history.add_user_message("test")
                message_history.clear()  # テストメッセージを削除
                
                logger.info(f"Redis接続成功 - メモリ付きエージェント: {user_id}")
                
            except Exception as redis_error:
                logger.warning(f"Redis接続失敗、インメモリ履歴を使用: {redis_error}")
                # フォールバック: インメモリ履歴
                from langchain.memory import ChatMessageHistory
                message_history = ChatMessageHistory()
            
            # ConversationBufferMemory に履歴を注入
            memory = ConversationBufferMemory(
                chat_memory=message_history,
                return_messages=True,
                memory_key="chat_history"
            )
            
            # メモリ付きプロンプト
            prompt_with_memory = ChatPromptTemplate.from_messages([
                ("system", self._get_system_prompt()),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            # エージェント作成
            agent = create_openai_tools_agent(self.llm, self.tools, prompt_with_memory)
            
            # メモリ付きAgentExecutor
            agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                memory=memory,  # ここが重要！
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5
            )
            
            logger.info(f"メモリ付きエージェント作成成功: {user_id}:{thread_id}")
            return agent_executor
            
        except Exception as e:
            logger.error(f"メモリ付きエージェント作成エラー: {e}")
            # フォールバック: メモリなし版を返す
            logger.info(f"フォールバック: メモリなしエージェントを使用 - {user_id}")
            return self.agent_executor

    def _get_system_prompt(self) -> str:
        """システムプロンプトの取得"""
        return """
あなたは農業管理を支援するAIエージェントの司令塔「MasterAgent」です。
あなたの主な役割は、ユーザーからの問い合わせを分析し、それを適切な専門エージェントに振り分けることです。

利用可能なツール：
1. `field_agent_tool`: 圃場（畑やハウス）に関する情報の照会を担当します。「〇〇ハウスの状況は？」「A畑の面積を教えて」といった問い合わせに使用します。
2. `work_log_registration_agent_tool`: 日々の作業報告を記録・保存します。「昨日トマトに薬を撒いた」「今日の収穫量は30kgだった」といった作業記録の登録に使用します。
3. `work_log_search`: 過去の作業記録を検索し、ユーザーの質問に答えます。「先週の作業記録を教えて」「トマトの防除履歴は？」といった問い合わせに使用します。

あなたの行動フロー:
1. ユーザーの要求を分析します。
2. 最も適した専門エージェントを選択します。
3. 専門エージェントにタスクを依頼します。
4. 専門エージェントからの報告を元に、最終的な回答を生成してユーザーに伝えます。

あなたは直接的なデータベース検索や情報提供を行いません。必ず専門エージェントを通じてタスクを実行してください。
"""

    async def process_message_async(self, message: str, user_id: str) -> dict:
        """
        非同期でユーザーからのメッセージを処理し、応答を生成する

        Returns:
            dict: {
                'response': str,      # ユーザーへの応答
                'plan': str,          # 実行プラン（オプション）
                'agent_used': str     # 使用したエージェント
            }
        """
        if not self.agent_executor:
            logger.error("エージェントが初期化されていません。")
            return {
                "response": "申し訳ございません。システムの準備ができていません。少し待ってから再度お試しください。",
                "agent_used": "master_agent",
                "error": True,
            }

        # MongoDB接続確認
        if not mongodb_client.is_connected:
            try:
                await mongodb_client.connect()
            except Exception as e:
                logger.error(f"MongoDB接続エラー: {e}")
                return {
                    "response": "データベース接続エラーが発生しました。しばらくしてから再度お試しください。",
                    "agent_used": "master_agent",
                    "error": True,
                }

        try:
            # 1. クエリ分析と実行プランの作成
            analysis_result = await self.query_analyzer.analyze_query_intent(message)
            plan = await self.query_analyzer.create_execution_plan(analysis_result)

            # 2. エージェント実行
            response = self.agent_executor.invoke({"input": message, "user_id": user_id})

            if isinstance(response, dict) and "output" in response:
                final_response = response["output"]
            else:
                final_response = str(response)

            return {"response": final_response, "plan": plan, "agent_used": "master_agent"}

        except Exception as e:
            logger.error(f"メッセージ処理エラー: {e}")
            return {
                "response": "申し訳ございません。処理中にエラーが発生しました。しばらくしてから再度お試しください。",
                "agent_used": "master_agent",
                "error": True,
            }

    def process_message(self, message: str, user_id: str) -> str:
        """同期ラッパー関数（後方互換性のため）"""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # 既にイベントループが実行中の場合は同期実行できない
            logger.warning("イベントループ実行中のため、同期実行はできません")
            return "システムが処理中です。しばらくお待ちください。"
        except RuntimeError:
            # イベントループが実行されていない場合は非同期実行結果を取得
            result = asyncio.run(self.process_message_async(message, user_id))
            return result.get("response", "エラーが発生しました")


# グローバルエージェントインスタンス
master_agent = MasterAgent()
