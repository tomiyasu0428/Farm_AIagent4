from typing import Any, List
from .base_tool import AgriAIBaseTool


class FieldInfoTool(AgriAIBaseTool):
    name: str = "field_info"
    description: str = (
        "圃場の情報を検索します。圃場名やエリア名を指定して、面積、土壌タイプ、現在の作付け状況などを取得できます。"
    )

    async def _arun(self, query: str) -> str:
        if not self.mongodb_client or not self.mongodb_client.is_connected:
            await self.mongodb_client.connect()

        db = self.mongodb_client.get_database()
        collection = db["fields"]

        # 簡易的な検索クエリ
        search_filter = {"field_name": {"$regex": query, "$options": "i"}}

        cursor = collection.find(search_filter)
        fields = await cursor.to_list(length=10)  # 最大10件まで

        if not fields:
            return f"「{query}」に一致する圃場は見つかりませんでした。"
        return self._format_result(fields)

    def _format_result(self, result: List[Any]) -> str:
        if not result:
            return "情報が見つかりませんでした。"

        formatted_results = []
        for field in result:
            info = f"圃場名: {field.get('field_name')}, 面積: {field.get('area')}㎡"
            formatted_results.append(info)
        return "\n".join(formatted_results)
