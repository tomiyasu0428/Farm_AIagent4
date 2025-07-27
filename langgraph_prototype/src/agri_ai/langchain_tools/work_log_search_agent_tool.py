from typing import Type, Any
from pydantic import BaseModel, Field
from .base_tool import AgriAIBaseTool


class WorkLogSearchInput(BaseModel):
    query: str = Field(
        description="検索したい作業記録に関する自然言語のクエリ。例: '昨日のトマトハウスの作業', '先月の防除記録', '第3圃場の収穫量"
    )
    user_id: str = Field(description="LINEユーザーID")


class WorkLogSearchAgentTool(AgriAIBaseTool):
    name: str = "work_log_search"
    description: str = "ユーザーのクエリに基づいて作業記録を検索し、結果を返します。"
    args_schema: Type[BaseModel] = WorkLogSearchInput
    work_log_search_agent: Any = Field(default=None, exclude=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _get_agent(self):
        """遅延インポートでWorkLogSearchAgentを取得"""
        if self.work_log_search_agent is None:
            from ..agents.work_log_search_agent import WorkLogSearchAgent

            self.work_log_search_agent = WorkLogSearchAgent()
        return self.work_log_search_agent

    async def _arun(self, query: str, user_id: str) -> str:
        """非同期で作業記録検索エージェントを実行します。"""
        try:
            agent = self._get_agent()
            result = await agent.search_work_logs(query=query, user_id=user_id)
            if result.get("success"):
                if result.get("total_count", 0) > 0:
                    formatted_summaries = []
                    for record in result["results"]:
                        formatted_summaries.append(record.get("summary", record["original_message"]))

                    response_message = f"作業記録が見つかりました ({result['total_count']}件):\n" + "\n".join(
                        formatted_summaries
                    )

                    if result.get("recommendations"):
                        response_message += "\n\n推奨事項:\n" + "\n".join(result["recommendations"])

                    return response_message
                else:
                    return result.get("message", "該当する作業記録は見つかりませんでした。")
            else:
                return result.get("message", "作業記録の検索中にエラーが発生しました。")
        except Exception as e:
            return f"作業記録検索ツールでエラーが発生しました: {e}"
