import logging
from typing import Dict, Any
from langgraph.graph import StateGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from .state import AgriAgentState
from .read_agent import ReadAgent
from .write_agent import WriteAgent
from shared.config.settings import settings

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    ユーザーからの入力を受け取り、タスクを各専門エージェント（ReadAgent/WriteAgent）に振り分ける司令塔エージェント。
    LLMベースでRead/Writeの意図を判定し、適切なエージェントにルーティングする。
    """

    def __init__(self):
        """SupervisorAgentの初期化"""
        logger.info("SupervisorAgent初期化開始")
        
        # LLMの初期化
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1,
            google_api_key=settings.google_ai.api_key
        )
        
        logger.info("SupervisorAgent初期化完了")

    def run(self, state: AgriAgentState) -> Dict[str, Any]:
        """
        エージェントの実行ロジック - ユーザーの意図を分析し適切なエージェントにルーティング
        """
        logger.info("--- SUPERVISOR AGENT 実行開始 ---")
        
        try:
            # メッセージから最新のユーザー入力を取得
            messages = state.get('messages', [])
            if not messages:
                state['next_agent'] = '__end__'
                state['final_response'] = "メッセージが見つかりません"
                return state
                
            latest_message = messages[-1] if messages else ""
            user_query = latest_message.get('content', '') if isinstance(latest_message, dict) else str(latest_message)
            
            logger.info(f"SupervisorAgent処理クエリ: {user_query}")
            
            # LLMベースでRead/Write意図を判定
            intent = self._analyze_intent(user_query)
            
            # 次のエージェントを決定
            if intent == "write":
                state['next_agent'] = 'write_agent'
                logger.info("WriteAgentにルーティング")
            elif intent == "read":
                state['next_agent'] = 'read_agent'
                logger.info("ReadAgentにルーティング")
            else:
                state['next_agent'] = 'read_agent'  # デフォルト
                logger.info("デフォルトでReadAgentにルーティング")
            
            # 中間ステップの記録
            state['intermediate_steps'] = state.get('intermediate_steps', []) + [
                f"SupervisorAgent: {intent}意図を検出 → {state['next_agent']}にルーティング"
            ]
            
            logger.info("SupervisorAgent実行完了")
            
        except Exception as e:
            logger.error(f"SupervisorAgent実行エラー: {e}")
            state['next_agent'] = 'read_agent'  # エラー時はReadAgentにフォールバック
            state['final_response'] = f"SupervisorAgentでエラーが発生しました: {str(e)}"
            
        return state
    
    def _analyze_intent(self, query: str) -> str:
        """
        LLMを使用してユーザーの意図（Read/Write）を分析
        
        Args:
            query: ユーザークエリ
            
        Returns:
            "read" または "write"
        """
        try:
            # シンプルなプロンプトで意図を判定
            prompt = f"""
以下のユーザーメッセージを分析し、「read」または「write」のいずれかで回答してください。

判定基準:
- 「read」: 情報の検索・確認・表示（例：「作業記録を見たい」「圃場情報を教えて」）
- 「write」: データの登録・保存・更新（例：「作業を記録したい」「今日トマトに水をやった」）

ユーザーメッセージ: {query}

回答（readまたはwrite）:
"""
            
            response = self.llm.invoke(prompt)
            result = response.content.strip().lower()
            
            if "write" in result:
                return "write"
            else:
                return "read"  # デフォルト
                
        except Exception as e:
            logger.error(f"意図分析エラー: {e}")
            return "read"  # エラー時はreadをデフォルト


def should_continue(state: AgriAgentState) -> str:
    """
    次に実行するエージェントを決定する条件関数
    
    Args:
        state: 現在の状態
        
    Returns:
        次のノード名
    """
    next_agent = state.get('next_agent')
    
    if next_agent == 'read_agent':
        return 'read_agent'
    elif next_agent == 'write_agent':
        return 'write_agent'
    else:
        return '__end__'


# ワークフローの定義
def create_langgraph_workflow():
    """LangGraphワークフローを作成"""
    workflow = StateGraph(AgriAgentState)
    
    # エージェントインスタンスの作成
    supervisor = SupervisorAgent()
    read_agent = ReadAgent()
    write_agent = WriteAgent()
    
    # ノードの定義
    workflow.add_node("supervisor", supervisor.run)
    workflow.add_node("read_agent", read_agent.run)
    workflow.add_node("write_agent", write_agent.run)
    
    # エントリーポイントの設定
    workflow.set_entry_point("supervisor")
    
    # 条件付きエッジの設定
    workflow.add_conditional_edges(
        "supervisor",
        should_continue,
        {
            "read_agent": "read_agent",
            "write_agent": "write_agent",
            "__end__": "__end__"
        }
    )
    
    # 各エージェントの終了エッジ
    workflow.add_edge("read_agent", "__end__")
    workflow.add_edge("write_agent", "__end__")
    
    # グラフのコンパイル
    app = workflow.compile()
    
    logger.info("LangGraphワークフロー作成完了: Supervisor → Read/WriteAgent")
    return app


# メインワークフローの作成
app = create_langgraph_workflow()

logger.info("SupervisorAgent with Read/WriteAgent routing が完成しました。")