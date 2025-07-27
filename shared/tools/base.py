"""
統一ツール基盤システム

型安全で効率的なツール基盤を提供します。
複雑な非同期処理を簡素化し、共通のインターフェースを定義
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, TypeVar, Generic, Callable, Union
from functools import wraps

from langchain_core.tools import BaseTool
from pydantic import Field

from ..config.settings import settings
from ..exceptions.errors import (
    AgriAIResult, AgriAIException, DatabaseError, TimeoutError,
    handle_exceptions, ErrorCategory
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConnectionPool:
    """データベース接続プール"""
    
    def __init__(self, max_connections: int = 10):
        self._max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._total_connections = 0
        self._lock = asyncio.Lock()
    
    async def get_connection(self):
        """接続を取得"""
        from ...database.mongodb_client import create_mongodb_client
        
        if self._pool.empty() and self._total_connections < self._max_connections:
            async with self._lock:
                if self._total_connections < self._max_connections:
                    connection = create_mongodb_client()
                    await connection.connect()
                    self._total_connections += 1
                    return connection
        
        return await self._pool.get()
    
    async def release_connection(self, connection):
        """接続を返却"""
        if connection and connection.is_connected:
            await self._pool.put(connection)
        else:
            self._total_connections -= 1


class CacheManager:
    """LLMレスポンスキャッシュマネージャー"""
    
    def __init__(self, ttl: int = 3600):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュから取得"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """キャッシュに保存"""
        self._cache[key] = (value, time.time())
    
    def clear(self):
        """キャッシュをクリア"""
        self._cache.clear()


# グローバルインスタンス
connection_pool = ConnectionPool(max_connections=settings.constants.CONNECTION_POOL_SIZE)
cache_manager = CacheManager(ttl=settings.constants.LLM_CACHE_TTL_SECONDS)


class AgriAIBaseTool(BaseTool, ABC):
    """統一農業AIツール基盤クラス"""

    # ツール固有設定
    cache_enabled: bool = Field(default=True, description="キャッシュ有効化")
    timeout_seconds: int = Field(default=30, description="タイムアウト時間")
    require_db: bool = Field(default=True, description="データベース接続必須")
    
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cache_key_prefix = self.__class__.__name__

    @asynccontextmanager
    async def get_db_connection(self):
        """データベース接続のコンテキストマネージャー"""
        if not self.require_db:
            yield None
            return
            
        connection = None
        try:
            connection = await connection_pool.get_connection()
            yield connection
        except Exception as e:
            logger.error(f"DB接続エラー: {e}")
            raise DatabaseError(f"データベース接続に失敗しました: {str(e)}")
        finally:
            if connection:
                await connection_pool.release_connection(connection)

    def _generate_cache_key(self, query: str, **kwargs) -> str:
        """キャッシュキーを生成"""
        import hashlib
        
        cache_data = f"{self._cache_key_prefix}:{query}:{str(sorted(kwargs.items()))}"
        return hashlib.sha256(cache_data.encode()).hexdigest()

    def _run(self, query: str = "", **kwargs: Any) -> Any:
        """
        同期実行メソッド - 簡素化されたバージョン
        複雑なスレッド処理を削除し、標準的な非同期処理に置き換え
        """
        try:
            # 新しいイベントループで実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    asyncio.wait_for(
                        self._arun(query, **kwargs),
                        timeout=self.timeout_seconds
                    )
                )
                return result
            finally:
                loop.close()
                
        except asyncio.TimeoutError:
            error_msg = f"ツール実行がタイムアウトしました ({self.timeout_seconds}秒)"
            logger.error(error_msg)
            raise TimeoutError(error_msg, timeout_seconds=self.timeout_seconds)
        except Exception as e:
            logger.error(f"ツール実行エラー: {e}")
            raise

    @handle_exceptions(default_category=ErrorCategory.SYSTEM)
    async def _arun(self, query: str, **kwargs: Any) -> Any:
        """非同期実行メソッド - キャッシュとエラーハンドリング統合"""
        
        # キャッシュチェック
        if self.cache_enabled:
            cache_key = self._generate_cache_key(query, **kwargs)
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"キャッシュヒット: {self.__class__.__name__}")
                return cached_result

        # 実際の処理実行
        result = await self._execute(query, **kwargs)
        
        # 成功時のキャッシュ保存
        if self.cache_enabled and isinstance(result, (str, dict, list)):
            cache_manager.set(cache_key, result)
        
        return result

    @abstractmethod
    async def _execute(self, query: str, **kwargs: Any) -> Any:
        """
        実際のツール処理を実装する抽象メソッド
        
        Args:
            query: 処理対象のクエリ
            **kwargs: 追加パラメータ
            
        Returns:
            処理結果
        """
        pass

    async def _execute_with_db(self, operation_func: Callable, *args, **kwargs) -> Any:
        """
        データベース操作ヘルパー - 接続プール使用
        
        Args:
            operation_func: 実行する非同期関数
            *args, **kwargs: 関数に渡すパラメータ
            
        Returns:
            操作結果
        """
        async with self.get_db_connection() as db_client:
            if db_client is None and self.require_db:
                raise DatabaseError("データベース接続が必要ですが取得できませんでした")
            
            return await operation_func(db_client, *args, **kwargs)


class AgriAILLMTool(AgriAIBaseTool):
    """LLM呼び出し専用ツール基盤"""
    
    model_name: str = Field(default="gemini-2.5-flash", description="使用するLLMモデル")
    temperature: float = Field(default=0.1, description="生成温度")
    max_retries: int = Field(default=3, description="最大リトライ回数")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_llm()
    
    def _init_llm(self):
        """LLMを初期化"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            temperature=self.temperature,
            google_api_key=settings.google_ai.api_key,
            timeout=self.timeout_seconds
        )
    
    @handle_exceptions(default_category=ErrorCategory.EXTERNAL_API)
    async def _call_llm(self, prompt: str, **kwargs) -> str:
        """
        LLM呼び出しヘルパー - リトライ機能付き
        
        Args:
            prompt: LLMに送信するプロンプト
            **kwargs: 追加パラメータ
            
        Returns:
            LLMの応答
        """
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(self.llm.invoke, prompt)
                return response.content.strip()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise AgriAIException(
                        f"LLM呼び出しが{self.max_retries}回失敗しました: {str(e)}",
                        category=ErrorCategory.EXTERNAL_API
                    )
                
                wait_time = 2 ** attempt  # 指数バックオフ
                logger.warning(f"LLM呼び出し失敗 (試行{attempt + 1}): {e}, {wait_time}秒後にリトライ")
                await asyncio.sleep(wait_time)


class AgriAIDataTool(AgriAIBaseTool):
    """データ操作専用ツール基盤"""
    
    collection_name: str = Field(..., description="対象コレクション名")
    require_db: bool = Field(default=True, description="データベース接続必須")
    
    async def _find_documents(self, client, filter_dict: Dict[str, Any], limit: int = 100) -> list[Dict[str, Any]]:
        """ドキュメント検索ヘルパー"""
        collection = await client.get_collection(self.collection_name)
        cursor = collection.find(filter_dict).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def _insert_document(self, client, document: Dict[str, Any]) -> str:
        """ドキュメント挿入ヘルパー"""
        collection = await client.get_collection(self.collection_name)
        result = await collection.insert_one(document)
        return str(result.inserted_id)
    
    async def _update_document(self, client, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> int:
        """ドキュメント更新ヘルパー"""
        collection = await client.get_collection(self.collection_name)
        result = await collection.update_many(filter_dict, {"$set": update_dict})
        return result.modified_count


class ToolRegistry:
    """ツールレジストリ - 依存性注入パターン"""
    
    def __init__(self):
        self._tools: Dict[str, type] = {}
        self._instances: Dict[str, AgriAIBaseTool] = {}
    
    def register_tool(self, name: str, tool_class: type):
        """ツールクラスを登録"""
        self._tools[name] = tool_class
    
    def get_tool(self, name: str, **kwargs) -> AgriAIBaseTool:
        """ツールインスタンスを取得"""
        if name not in self._instances:
            if name not in self._tools:
                raise ValueError(f"Unknown tool: {name}")
            self._instances[name] = self._tools[name](**kwargs)
        return self._instances[name]
    
    def list_tools(self) -> list[str]:
        """登録済みツール一覧"""
        return list(self._tools.keys())


# グローバルツールレジストリ
tool_registry = ToolRegistry()


def register_tool(name: str):
    """ツール登録デコレータ"""
    def decorator(cls):
        tool_registry.register_tool(name, cls)
        return cls
    return decorator


# ================================
# パフォーマンス監視
# ================================

class PerformanceMonitor:
    """ツールパフォーマンス監視"""
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, float]] = {}
    
    def record_execution(self, tool_name: str, execution_time: float, success: bool):
        """実行メトリクスを記録"""
        if tool_name not in self.metrics:
            self.metrics[tool_name] = {
                "total_calls": 0,
                "success_calls": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "max_time": 0.0,
                "min_time": float('inf')
            }
        
        metrics = self.metrics[tool_name]
        metrics["total_calls"] += 1
        if success:
            metrics["success_calls"] += 1
        
        metrics["total_time"] += execution_time
        metrics["avg_time"] = metrics["total_time"] / metrics["total_calls"]
        metrics["max_time"] = max(metrics["max_time"], execution_time)
        metrics["min_time"] = min(metrics["min_time"], execution_time)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポートを取得"""
        return {
            "summary": {
                "total_tools": len(self.metrics),
                "cache_hit_rate": self._calculate_cache_hit_rate(),
                "average_response_time": self._calculate_avg_response_time()
            },
            "by_tool": dict(self.metrics)
        }
    
    def _calculate_cache_hit_rate(self) -> float:
        """キャッシュヒット率を計算"""
        # 実装は具体的なキャッシュメトリクス次第
        return 0.0
    
    def _calculate_avg_response_time(self) -> float:
        """平均応答時間を計算"""
        if not self.metrics:
            return 0.0
        
        total_time = sum(m["total_time"] for m in self.metrics.values())
        total_calls = sum(m["total_calls"] for m in self.metrics.values())
        
        return total_time / total_calls if total_calls > 0 else 0.0


# グローバルパフォーマンスモニター
performance_monitor = PerformanceMonitor()