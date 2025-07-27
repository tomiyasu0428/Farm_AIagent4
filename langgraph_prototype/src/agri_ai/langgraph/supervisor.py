from typing import Dict, Any
from langgraph.graph import StateGraph
from .state import AgriAgentState

class SupervisorAgent:
    """
    ユーザーからの入力を受け取り、タスクを各専門エージェントに振り分ける司令塔エージェント。
    """

    def __init__(self):
        # ここに初期化処理を記述
        pass

    def run(self, state: AgriAgentState) -> Dict[str, Any]:
        """
        エージェントの実行ロジック
        """
        print("--- SUPERVISOR AGENT --- ")
        # TODO: ユーザーの意図を分析し、next_agentを決定する
        # 現時点では、仮でReadAgentを次に設定
        state['next_agent'] = 'ReadAgent'
        return state

# ワークフローの定義
workflow = StateGraph(AgriAgentState)

# ノードの定義
workflow.add_node("supervisor", SupervisorAgent().run)

from .read_agent import ReadAgent

# ノードの定義
workflow.add_node("supervisor", SupervisorAgent().run)
workflow.add_node("read_agent", ReadAgent().run)

# エントリーポイントの設定
workflow.set_entry_point("supervisor")

# エッジ（ノード間の遷移）を定義
workflow.add_edge("supervisor", "read_agent")

# ReadAgentの次は終了
workflow.add_edge("read_agent", "__end__")

# グラフのコンパイル
app = workflow.compile()

print("SupervisorとReadAgentを接続し、基本的なルーティングが完成しました。")


# エントリーポイントの設定
workflow.set_entry_point("supervisor")

# TODO: エッジ（ノード間の遷移）を定義

# グラフのコンパイル
app = workflow.compile()

print("SupervisorAgentの基本的な枠組みが作成されました。")
