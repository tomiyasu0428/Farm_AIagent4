# src/agri_ai/protocols/agents.py

"""
エージェント関連のプロトコル定義
"""

from typing import Protocol, Dict, Any
from typing_extensions import runtime_checkable


@runtime_checkable
class WorkLogRegistrationAgentProtocol(Protocol):
    """作業記録登録エージェントのプロトコル"""
    
    async def register_work_log(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        作業記録を登録する
        
        Args:
            message: ユーザーの作業報告メッセージ
            user_id: ユーザーID
            
        Returns:
            登録結果の辞書
        """
        ...


@runtime_checkable
class WorkLogSearchAgentProtocol(Protocol):
    """作業記録検索エージェントのプロトコル"""
    
    async def search_work_logs(self, query: str, user_id: str) -> Dict[str, Any]:
        """
        作業記録を検索する
        
        Args:
            query: 検索クエリ
            user_id: ユーザーID
            
        Returns:
            検索結果の辞書
        """
        ...