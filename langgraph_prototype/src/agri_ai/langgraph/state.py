from typing import TypedDict, Annotated, List, Dict, Any
from langchain_core.messages import BaseMessage
import operator

class AgriAgentState(TypedDict):
    """
    LangGraphの全体的な状態を管理するクラス。

    Attributes:
        messages: 会話履歴。新しいメッセージが追加される。
        next_agent: 次に実行するエージェントの名前。
        current_agent: 現在実行中のエージェントの名前。
        user_id: 対話しているユーザーのID。
        thread_id: 会話のスレッドID。
        pending_confirmation: ユーザーに確認を待っている情報。
        confirmation_data: ユーザーによって確認されたデータ。
        task_plan: 複雑なタスクの実行計画。
        intermediate_steps: エージェントの途中実行ステップ。デバッグ用。
        final_response: ユーザーへの最終的な応答メッセージ。
    """
    # 会話履歴（追加モード）
    messages: Annotated[List[BaseMessage], operator.add]
    
    # ルーティング制御
    next_agent: str
    current_agent: str
    
    # ユーザー情報
    user_id: str
    thread_id: str
    
    # 確認フロー状態（既存システムから継承）
    pending_confirmation: Dict[str, Any]
    confirmation_data: Dict[str, Any]
    
    # 複雑タスク管理（Manus式）
    task_plan: Dict[str, Any]
    
    # デバッグ・分析用
    intermediate_steps: Annotated[List[Dict], operator.add]
    
    # 最終レスポンス
    final_response: str
