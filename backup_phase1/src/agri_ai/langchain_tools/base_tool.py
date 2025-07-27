"""
農業AIのベースツール定義
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any
import logging
from langchain_core.tools import BaseTool
from pydantic import Field

from ..database.mongodb_client import mongodb_client

logger = logging.getLogger(__name__)


class AgriAIBaseTool(BaseTool, ABC):
    """農業AIエージェントのベースツールクラス"""

    mongodb_client: Any = Field(default=None, exclude=True)

    def __init__(self, mongodb_client_instance=None, **kwargs):
        # LangChain v0.2.0以降の変更に対応
        super().__init__(**kwargs)
        if mongodb_client_instance:
            self.mongodb_client = mongodb_client_instance
        else:
            # グローバルインスタンスを使用
            self.mongodb_client = mongodb_client

    def _run(self, query: str = "", **kwargs: Any) -> Any:
        """同期的にツールを実行する"""
        import concurrent.futures
        import threading
        
        # 常に新しいスレッドで独立したイベントループを実行
        result_container = {}
        exception_container = {}
        
        def run_async():
            try:
                # 新しいイベントループを作成
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result_container['result'] = new_loop.run_until_complete(self._arun(query, **kwargs))
                finally:
                    new_loop.close()
            except Exception as e:
                exception_container['exception'] = e
            finally:
                # スレッド終了時にイベントループをクリア
                asyncio.set_event_loop(None)
        
        # 専用スレッドで実行
        thread = threading.Thread(target=run_async)
        thread.start()
        thread.join(timeout=30)  # 30秒でタイムアウト
        
        if thread.is_alive():
            logger.error("ツール実行がタイムアウトしました")
            return "処理がタイムアウトしました"
        
        if 'exception' in exception_container:
            logger.error(f"ツール実行エラー: {exception_container['exception']}")
            raise exception_container['exception']
        
        return result_container.get('result', "処理中にエラーが発生しました")

    @abstractmethod
    async def _arun(self, query: str, **kwargs: Any) -> Any:
        """非同期にツールを実行する抽象メソッド"""
        pass

    async def _execute_with_db(self, operation_func, *args, **kwargs):
        """データベース操作を新しい接続で実行"""
        from ..database.mongodb_client import create_mongodb_client
        import asyncio
        
        fresh_client = create_mongodb_client()
        try:
            await fresh_client.connect()
            result = await operation_func(fresh_client, *args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"データベース操作エラー: {e}")
            raise
        finally:
            # 安全にDB接続を切断（イベントループが閉じられている場合の対策）
            try:
                # 現在のイベントループが有効かチェック
                loop = asyncio.get_running_loop()
                if not loop.is_closed():
                    await fresh_client.disconnect()
                else:
                    logger.warning("イベントループが閉じられているため、DB切断をスキップ")
            except RuntimeError:
                # イベントループが存在しない場合
                logger.warning("イベントループが見つからないため、DB切断をスキップ")
            except Exception as disconnect_error:
                logger.error(f"DB切断エラー: {disconnect_error}")
                # 切断エラーは無視（メインの処理結果に影響させない）
