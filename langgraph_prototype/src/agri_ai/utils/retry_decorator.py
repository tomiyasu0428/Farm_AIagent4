"""
リトライデコレーター

Gemini API 5xx エラーやデータベース接続エラーに対応
"""

import asyncio
import logging
from functools import wraps
from typing import Union, Type, Tuple
import random

logger = logging.getLogger(__name__)


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
):
    """
    非同期関数用のリトライデコレーター
    
    Args:
        max_retries: 最大リトライ回数
        delay: 初期遅延時間（秒）
        backoff: 遅延時間の増加率
        jitter: ランダムジッターを追加するか
        exceptions: リトライ対象の例外クラス
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__}: 最大リトライ回数({max_retries})に到達: {e}"
                        )
                        raise
                    
                    # 遅延時間の計算
                    wait_time = delay * (backoff ** attempt)
                    
                    # ジッターの追加
                    if jitter:
                        wait_time *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"{func.__name__}: リトライ {attempt + 1}/{max_retries}, "
                        f"待機時間: {wait_time:.2f}秒, エラー: {e}"
                    )
                    
                    await asyncio.sleep(wait_time)
            
            # ここには到達しないはずだが、念のため
            raise last_exception
        
        return wrapper
    return decorator


def sync_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
):
    """
    同期関数用のリトライデコレーター
    
    Args:
        max_retries: 最大リトライ回数
        delay: 初期遅延時間（秒）
        backoff: 遅延時間の増加率
        jitter: ランダムジッターを追加するか
        exceptions: リトライ対象の例外クラス
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__}: 最大リトライ回数({max_retries})に到達: {e}"
                        )
                        raise
                    
                    # 遅延時間の計算
                    wait_time = delay * (backoff ** attempt)
                    
                    # ジッターの追加
                    if jitter:
                        wait_time *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"{func.__name__}: リトライ {attempt + 1}/{max_retries}, "
                        f"待機時間: {wait_time:.2f}秒, エラー: {e}"
                    )
                    
                    time.sleep(wait_time)
            
            # ここには到達しないはずだが、念のため
            raise last_exception
        
        return wrapper
    return decorator


# よく使用されるエラーパターン用のプリセット

# Gemini API エラー用
gemini_retry = async_retry(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    jitter=True,
    exceptions=(Exception,)  # 具体的なGemini例外クラスが分かれば指定
)

# MongoDB エラー用
mongodb_retry = async_retry(
    max_retries=2,
    delay=0.5,
    backoff=1.5,
    jitter=True,
    exceptions=(Exception,)  # pymongo.errors.* が分かれば指定
)

# データベース一般用（別名）
database_retry = mongodb_retry

# 軽量リトライ（高速処理向け）
quick_retry = async_retry(
    max_retries=1,
    delay=0.1,
    backoff=1.0,
    jitter=False
)