# src/agri_ai/dependencies/database.py

"""
データベース依存性注入
"""

from typing import Optional
from ..database.mongodb_client import MongoDBClient, create_mongodb_client


class DatabaseConnection:
    """データベース接続管理クラス"""
    
    def __init__(self, client: Optional[MongoDBClient] = None):
        self._client = client
    
    async def get_client(self) -> MongoDBClient:
        """MongoDB クライアントを取得"""
        # 常に新しいクライアントを作成してイベントループ問題を回避
        if self._client is None or not self._client.is_connected:
            self._client = create_mongodb_client()
            await self._client.connect()
        
        return self._client
    
    async def disconnect(self):
        """接続を切断"""
        if self._client and self._client.is_connected:
            await self._client.disconnect()


# グローバル接続インスタンス（必要に応じて）
_db_connection: Optional[DatabaseConnection] = None


def get_database_connection() -> DatabaseConnection:
    """データベース接続を取得"""
    global _db_connection
    # イベントループ問題を回避するため常に新しいインスタンスを作成
    _db_connection = DatabaseConnection()
    return _db_connection