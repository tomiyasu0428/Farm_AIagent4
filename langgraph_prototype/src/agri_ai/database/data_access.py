"""
データアクセス共通レイヤー
各ツールで共通して使用されるデータベース操作を提供します。
"""

import logging
from typing import Dict, Any, List
from bson import ObjectId
from .mongodb_client import MongoDBClient

logger = logging.getLogger(__name__)


class DataAccessLayer:
    """データアクセス共通レイヤー"""

    def __init__(self, mongodb_client: MongoDBClient):
        self.mongodb_client = mongodb_client

    async def _get_collection(self, collection_name: str):
        """コレクション取得の共通メソッド"""
        return await self.mongodb_client.get_collection(collection_name)

    async def get_field_info(self, field_id: ObjectId) -> Dict[str, Any]:
        """圃場情報取得の共通メソッド"""
        try:
            fields_collection = await self._get_collection("fields")
            field_info = await fields_collection.find_one({"_id": field_id})

            if not field_info:
                return {}

            # 現在の栽培情報を取得
            if field_info.get("current_cultivation"):
                crop_info = await self.get_crop_info(field_info["current_cultivation"]["crop_id"])
                field_info["current_cultivation"]["crop_name"] = crop_info.get("name", "不明")

            return field_info

        except Exception as e:
            logger.error(f"圃場情報取得エラー: {e}")
            return {}

    async def get_field_ids_by_name(self, field_filter: Dict[str, Any]) -> List[ObjectId]:
        """圃場ID取得の共通メソッド"""
        try:
            fields_collection = await self._get_collection("fields")
            fields = await fields_collection.find(field_filter).to_list(None)
            return [field["_id"] for field in fields]

        except Exception as e:
            logger.error(f"圃場ID取得エラー: {e}")
            return []

    async def get_crop_info(self, crop_id: ObjectId) -> Dict[str, Any]:
        """作物情報取得の共通メソッド"""
        try:
            crops_collection = await self._get_collection("crops")
            crop_info = await crops_collection.find_one({"_id": crop_id})
            return crop_info or {}

        except Exception as e:
            logger.error(f"作物情報取得エラー: {e}")
            return {}

    async def get_crop_name(self, crop_id: ObjectId) -> str:
        """作物名取得の共通メソッド"""
        crop_info = await self.get_crop_info(crop_id)
        return crop_info.get("name", "不明")

    async def get_material_info(self, material_id: ObjectId) -> Dict[str, Any]:
        """資材情報取得の共通メソッド"""
        try:
            materials_collection = await self._get_collection("materials")
            material_info = await materials_collection.find_one({"_id": material_id})
            return material_info or {}

        except Exception as e:
            logger.error(f"資材情報取得エラー: {e}")
            return {}

    async def search_work_logs(self, query_params: Dict[str, Any], user_id: str) -> List[Dict[str, Any]]:
        """作業記録を検索する共通メソッド"""
        try:
            work_logs_collection = await self._get_collection("work_logs")

            # 検索クエリの構築
            query = {"user_id": user_id}

            # 日付範囲フィルタ
            if query_params.get("date_range"):
                date_range = query_params["date_range"]
                query["work_date"] = {"$gte": date_range["start"], "$lte": date_range["end"]}

            # 圃場フィルタ
            if query_params.get("field_names"):
                field_conditions = []
                for field_name in query_params["field_names"]:
                    field_conditions.extend(
                        [
                            {"extracted_data.field_name": {"$regex": field_name, "$options": "i"}},
                            {"original_message": {"$regex": field_name, "$options": "i"}},
                        ]
                    )
                if field_conditions:
                    # 既存の $or 条件と結合
                    if "$or" in query:
                        query["$and"] = [{"$or": query["$or"]}, {"$or": field_conditions}]
                        del query["$or"]
                    else:
                        query["$or"] = field_conditions

            # 作業種別フィルタ
            if query_params.get("work_categories"):
                query["category"] = {"$in": query_params["work_categories"]}

            # 検索実行
            cursor = work_logs_collection.find(query)

            # ソート
            if query_params.get("sort_order") == "desc":
                cursor = cursor.sort("work_date", -1)
            else:
                cursor = cursor.sort("work_date", 1)

            # 件数制限
            cursor = cursor.limit(query_params.get("limit", 50))

            results = await cursor.to_list(None)
            logger.info(f"DataAccessLayer: 作業記録検索結果: {len(results)}件")

            return results

        except Exception as e:
            logger.error(f"DataAccessLayer: 作業記録検索エラー: {e}")
            return []

    async def find_fields_by_name(self, name: str):
        """後方互換: 圃場名で曖昧検索し、圃場ドキュメントリストを返す"""
        try:
            # 接続確認
            if not self.mongodb_client.is_connected:
                await self.mongodb_client.connect()

            fields_collection = await self._get_collection("fields")
            cursor = fields_collection.find({"name": {"$regex": name, "$options": "i"}})
            return await cursor.to_list(None)
        except Exception as e:
            logger.error(f"圃場検索エラー: {e}")
            return []


# --- 後方互換エイリアス ----------------------------
# 過去バージョンで使用していた DataAccess 名を保持するためのエイリアス。
# 新しい DataAccessLayer と同等の機能を提供します。
# エイリアスクラスのためのグローバルインスタンス


class DataAccess(DataAccessLayer):
    """後方互換のためのエイリアスクラス
    DataAccessLayer と全く同じだが、コンストラクタ引数を省略可能にして
    既存コードの ``DataAccess()`` 呼び出しをそのまま利用できるようにする。
    """

    def __init__(self, client: MongoDBClient = None):
        super().__init__(client if client else MongoDBClient())
