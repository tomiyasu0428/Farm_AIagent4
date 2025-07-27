"""
MongoDB接続とクライアント管理
"""

import asyncio
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging

from ..core.config import settings

logger = logging.getLogger(__name__)


class MongoDBClient:
    """MongoDB接続クライアント"""
    
    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or settings.mongodb.connection_string
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        
    async def __aenter__(self):
        """非同期コンテキストマネージャーの開始"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了"""
        await self.disconnect()
        
    async def connect(self) -> None:
        """MongoDB接続の確立"""
        # 既存のクライアントがあっても新しいイベントループでは再作成する
        if self.client is not None:
            # 古いクライアントを閉じる
            try:
                self.client.close()
            except:
                pass
            
        try:
            mongo_settings = settings.mongodb
            
            self.client = AsyncIOMotorClient(
                self.connection_string,
                serverSelectionTimeoutMS=mongo_settings.server_selection_timeout,
                connectTimeoutMS=mongo_settings.connect_timeout,
                maxPoolSize=mongo_settings.max_pool_size,
                minPoolSize=mongo_settings.min_pool_size,
            )
            
            # 接続テスト
            await self.client.admin.command('ping')
            self.database = self.client[mongo_settings.database_name]
            
            logger.info("MongoDB接続が正常に確立されました")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB接続エラー: {e}")
            raise
    
    async def disconnect(self) -> None:
        """MongoDB接続の切断"""
        if self.client is not None:
            self.client.close()
            self.client = None
            self.database = None
            logger.info("MongoDB接続を切断しました")
    
    async def get_collection(self, collection_name: str):
        """指定されたコレクションを取得"""
        if self.database is None:
            raise RuntimeError("データベース接続が確立されていません")
        return self.database[collection_name]
    
    async def health_check(self) -> Dict[str, Any]:
        """データベースの健全性チェック"""
        try:
            if self.client is None:
                return {"status": "error", "message": "接続未確立"}
            
            # ping test
            await self.client.admin.command('ping')
            
            # サーバー情報取得
            server_info = await self.client.admin.command('serverStatus')
            
            return {
                "status": "healthy",
                "host": server_info.get("host", "unknown"),
                "version": server_info.get("version", "unknown"),
                "uptime": server_info.get("uptime", 0)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @property
    def is_connected(self) -> bool:
        """接続状態の確認"""
        return self.client is not None and self.database is not None


# ファクトリー関数
def create_mongodb_client(connection_string: Optional[str] = None) -> MongoDBClient:
    """MongoDBクライアントのファクトリー関数"""
    return MongoDBClient(connection_string)


# グローバルMongoDBクライアントインスタンス（後方互換性のため）
mongodb_client = MongoDBClient()