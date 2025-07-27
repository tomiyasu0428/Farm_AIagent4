"""
セッション管理クラス

LINE Webhookでの会話状態を永続化し、確認フローの文脈を保持する
Redis をバックエンドとして使用
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class SessionManager:
    """
    ユーザーセッション管理クラス
    
    機能:
    - 会話状態の永続化
    - 確認フロー状態の管理
    - セッション有効期限管理
    """
    
    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = 86400):
        """
        SessionManager初期化
        
        Args:
            redis_url: Redis接続URL（環境変数REDIS_URLがデフォルト）
            default_ttl: デフォルトセッション有効期限（秒、デフォルト24時間）
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.default_ttl = default_ttl
        
        try:
            self.redis_client = Redis.from_url(
                self.redis_url,
                decode_responses=True,  # 文字列として取得
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # 接続テスト
            self.redis_client.ping()
            logger.info("Redis接続成功")
            
        except RedisError as e:
            logger.error(f"Redis接続エラー: {e}")
            # フォールバック: インメモリ辞書（開発用）
            self.redis_client = None
            self._memory_store = {}
            logger.warning("Redis接続失敗 - インメモリストレージにフォールバック")
    
    def _session_key(self, user_id: str, thread_id: str = "default") -> str:
        """セッションキー生成"""
        return f"session:{user_id}:{thread_id}"
    
    def _confirmation_key(self, user_id: str, thread_id: str = "default") -> str:
        """確認データキー生成"""
        return f"confirmation:{user_id}:{thread_id}"
    
    def load_session(self, user_id: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        セッションデータを読み込み
        
        Args:
            user_id: ユーザーID
            thread_id: スレッドID（デフォルト: "default"）
            
        Returns:
            Dict: セッションデータ
        """
        try:
            if self.redis_client:
                key = self._session_key(user_id, thread_id)
                raw_data = self.redis_client.get(key)
                
                if raw_data:
                    data = json.loads(raw_data)
                    logger.debug(f"セッション読み込み成功: {user_id}")
                    return data
                else:
                    logger.debug(f"セッション未存在: {user_id}")
                    return self._create_empty_session()
            else:
                # フォールバック
                key = self._session_key(user_id, thread_id)
                return self._memory_store.get(key, self._create_empty_session())
                
        except Exception as e:
            logger.error(f"セッション読み込みエラー: {e}")
            return self._create_empty_session()
    
    def save_session(self, user_id: str, data: Dict[str, Any], thread_id: str = "default", ttl: Optional[int] = None):
        """
        セッションデータを保存
        
        Args:
            user_id: ユーザーID
            data: 保存するデータ
            thread_id: スレッドID
            ttl: 有効期限（秒、Noneの場合はデフォルト値）
        """
        try:
            # タイムスタンプ更新
            data["updated_at"] = datetime.now().isoformat()
            if "created_at" not in data:
                data["created_at"] = data["updated_at"]
            
            serialized_data = json.dumps(data, ensure_ascii=False, default=str)
            ttl = ttl or self.default_ttl
            
            if self.redis_client:
                key = self._session_key(user_id, thread_id)
                self.redis_client.setex(key, ttl, serialized_data)
                logger.debug(f"セッション保存成功: {user_id}, TTL: {ttl}秒")
            else:
                # フォールバック
                key = self._session_key(user_id, thread_id)
                self._memory_store[key] = data
                logger.debug(f"セッション保存成功（メモリ）: {user_id}")
                
        except Exception as e:
            logger.error(f"セッション保存エラー: {e}")
    
    def has_pending_confirmation(self, user_id: str, thread_id: str = "default") -> bool:
        """
        確認待ち状態かチェック
        
        Returns:
            bool: 確認待ち状態の場合True
        """
        try:
            if self.redis_client:
                key = self._confirmation_key(user_id, thread_id)
                exists = self.redis_client.exists(key)
                logger.debug(f"確認待ち状態チェック: {user_id} -> {bool(exists)}")
                return bool(exists)
            else:
                # フォールバック
                key = self._confirmation_key(user_id, thread_id)
                exists = key in self._memory_store
                logger.debug(f"確認待ち状態チェック（メモリ）: {user_id} -> {exists}")
                return exists
                
        except Exception as e:
            logger.error(f"確認待ち状態チェックエラー: {e}")
            return False
    
    def get_pending_confirmation(self, user_id: str, thread_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        確認待ちデータを取得
        
        Returns:
            Optional[Dict]: 確認データ（存在しない場合はNone）
        """
        try:
            if self.redis_client:
                key = self._confirmation_key(user_id, thread_id)
                raw_data = self.redis_client.get(key)
                
                if raw_data:
                    data = json.loads(raw_data)
                    logger.debug(f"確認データ取得成功: {user_id}")
                    return data
                else:
                    logger.debug(f"確認データ未存在: {user_id}")
                    return None
            else:
                # フォールバック
                key = self._confirmation_key(user_id, thread_id)
                data = self._memory_store.get(key)
                logger.debug(f"確認データ取得（メモリ）: {user_id}")
                return data
                
        except Exception as e:
            logger.error(f"確認データ取得エラー: {e}")
            return None
    
    def set_pending_confirmation(
        self, 
        user_id: str, 
        confirmation_data: Dict[str, Any], 
        thread_id: str = "default", 
        timeout_minutes: int = 30
    ):
        """
        確認待ち状態を設定
        
        Args:
            user_id: ユーザーID
            confirmation_data: 確認データ
            thread_id: スレッドID
            timeout_minutes: タイムアウト時間（分）
        """
        try:
            # タイムスタンプとタイムアウト情報を追加
            enhanced_data = {
                **confirmation_data,
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(minutes=timeout_minutes)).isoformat(),
                "timeout_minutes": timeout_minutes
            }
            
            serialized_data = json.dumps(enhanced_data, ensure_ascii=False, default=str)
            ttl_seconds = timeout_minutes * 60
            
            if self.redis_client:
                key = self._confirmation_key(user_id, thread_id)
                self.redis_client.setex(key, ttl_seconds, serialized_data)
                logger.info(f"確認データ設定成功: {user_id}, タイムアウト: {timeout_minutes}分")
            else:
                # フォールバック
                key = self._confirmation_key(user_id, thread_id)
                self._memory_store[key] = enhanced_data
                logger.info(f"確認データ設定成功（メモリ）: {user_id}")
                
        except Exception as e:
            logger.error(f"確認データ設定エラー: {e}")
    
    def clear_pending_confirmation(self, user_id: str, thread_id: str = "default"):
        """
        確認待ち状態をクリア
        """
        try:
            if self.redis_client:
                key = self._confirmation_key(user_id, thread_id)
                deleted = self.redis_client.delete(key)
                logger.info(f"確認データクリア: {user_id}, 削除件数: {deleted}")
            else:
                # フォールバック
                key = self._confirmation_key(user_id, thread_id)
                if key in self._memory_store:
                    del self._memory_store[key]
                    logger.info(f"確認データクリア（メモリ）: {user_id}")
                    
        except Exception as e:
            logger.error(f"確認データクリアエラー: {e}")
    
    def _create_empty_session(self) -> Dict[str, Any]:
        """空のセッションデータを作成"""
        return {
            "conversation_history": [],
            "user_context": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    def extend_session(self, user_id: str, thread_id: str = "default", additional_ttl: int = 3600):
        """
        セッション有効期限を延長
        
        Args:
            user_id: ユーザーID
            thread_id: スレッドID
            additional_ttl: 追加する有効期限（秒）
        """
        try:
            if self.redis_client:
                session_key = self._session_key(user_id, thread_id)
                confirmation_key = self._confirmation_key(user_id, thread_id)
                
                # 両方のキーの有効期限を延長
                for key in [session_key, confirmation_key]:
                    if self.redis_client.exists(key):
                        self.redis_client.expire(key, additional_ttl)
                
                logger.debug(f"セッション有効期限延長: {user_id}, +{additional_ttl}秒")
                
        except Exception as e:
            logger.error(f"セッション有効期限延長エラー: {e}")
    
    def get_session_info(self, user_id: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        セッション情報を取得（デバッグ用）
        
        Returns:
            Dict: セッション状態の情報
        """
        try:
            info = {
                "user_id": user_id,
                "thread_id": thread_id,
                "has_session": False,
                "has_pending_confirmation": False,
                "session_ttl": None,
                "confirmation_ttl": None
            }
            
            if self.redis_client:
                session_key = self._session_key(user_id, thread_id)
                confirmation_key = self._confirmation_key(user_id, thread_id)
                
                info["has_session"] = bool(self.redis_client.exists(session_key))
                info["has_pending_confirmation"] = bool(self.redis_client.exists(confirmation_key))
                
                if info["has_session"]:
                    info["session_ttl"] = self.redis_client.ttl(session_key)
                
                if info["has_pending_confirmation"]:
                    info["confirmation_ttl"] = self.redis_client.ttl(confirmation_key)
            else:
                # フォールバック
                session_key = self._session_key(user_id, thread_id)
                confirmation_key = self._confirmation_key(user_id, thread_id)
                
                info["has_session"] = session_key in self._memory_store
                info["has_pending_confirmation"] = confirmation_key in self._memory_store
            
            return info
            
        except Exception as e:
            logger.error(f"セッション情報取得エラー: {e}")
            return {"error": str(e)}
    
    def cleanup_expired_sessions(self) -> int:
        """
        期限切れセッションのクリーンアップ
        
        Returns:
            int: クリーンアップしたセッション数
        """
        # Redis の場合、TTL による自動削除があるため手動クリーンアップは不要
        # メモリストレージの場合のみ実装
        
        if not self.redis_client:
            # フォールバック時のクリーンアップ
            cleaned_count = 0
            current_time = datetime.now()
            
            expired_keys = []
            for key, data in self._memory_store.items():
                if isinstance(data, dict) and "expires_at" in data:
                    try:
                        expires_at = datetime.fromisoformat(data["expires_at"])
                        if current_time > expires_at:
                            expired_keys.append(key)
                    except (ValueError, TypeError):
                        # 無効な日付形式の場合も削除対象
                        expired_keys.append(key)
            
            for key in expired_keys:
                del self._memory_store[key]
                cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"期限切れセッションクリーンアップ: {cleaned_count}件")
            
            return cleaned_count
        
        return 0