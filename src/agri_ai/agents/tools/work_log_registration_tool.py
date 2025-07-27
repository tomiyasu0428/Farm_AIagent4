# src/agri_ai/agents/tools/work_log_registration_tool.py

"""
WorkLogRegistrationAgentが内部で使用する、作業記録登録ツール
"""

import logging
from typing import Dict, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool

from ...protocols.agents import WorkLogRegistrationAgentProtocol

logger = logging.getLogger(__name__)

# WorkLogRegistrationAgentのregister_work_logメソッドの入力に合わせる
class WorkLogRegistrationToolInput(BaseModel):
    message: str = Field(description="ユーザーの作業報告メッセージ")
    user_id: str = Field(description="作業者のユーザーID")

class WorkLogRegistrationTool(BaseTool):
    name: str = "work_log_registration"
    description: str = """
    自然言語の作業報告を構造化データに変換してデータベースに保存します。
    使用例: 「昨日トマトハウスで防除作業をしました」
    """
    args_schema: Type[BaseModel] = WorkLogRegistrationToolInput
    
    # WorkLogRegistrationAgentのインスタンスを保持
    agent_instance: WorkLogRegistrationAgentProtocol

    def __init__(self, agent_instance: WorkLogRegistrationAgentProtocol):
        super().__init__()
        self.agent_instance = agent_instance

    async def _arun(self, message: str, user_id: str) -> Dict[str, str]:
        logger.info(f"Executing internal WorkLogRegistrationTool for user {user_id}")
        try:
            # WorkLogRegistrationAgentのregister_work_logメソッドを呼び出す
            result = await self.agent_instance.register_work_log(message=message, user_id=user_id)
            return result
        except Exception as e:
            logger.error(f"Error in internal WorkLogRegistrationTool: {e}")
            return {"success": False, "error": str(e), "message": "作業記録の登録中にエラーが発生しました。"}

    def _run(self, message: str, user_id: str) -> Dict[str, str]:
        # 同期実行は非推奨だが、LangChainのBaseToolの要件を満たすために実装
        import asyncio
        return asyncio.run(self._arun(message=message, user_id=user_id))
