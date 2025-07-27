"""
統一エラーハンドリングシステム

型安全で一貫したエラーハンドリングを提供します。
レガシーシステムとLangGraphシステム間で共有される全エラー定義
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class ErrorCategory(str, Enum):
    """エラーカテゴリ"""
    VALIDATION = "validation"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    NETWORK = "network"
    TIMEOUT = "timeout"


class ErrorSeverity(str, Enum):
    """エラー重要度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorDetail:
    """エラー詳細情報"""
    field: Optional[str] = None
    message: str = ""
    code: Optional[str] = None
    value: Optional[Any] = None


@dataclass
class AgriAIResult:
    """統一結果オブジェクト - 成功・失敗両方を型安全に表現"""
    
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    error_code: Optional[str] = None
    error_details: List[ErrorDetail] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: Optional[str] = None
    
    @classmethod
    def success_result(
        cls, 
        data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> "AgriAIResult":
        """成功結果を作成"""
        return cls(
            success=True,
            data=data or {},
            trace_id=trace_id
        )
    
    @classmethod
    def error_result(
        cls,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        code: Optional[str] = None,
        details: Optional[List[ErrorDetail]] = None,
        trace_id: Optional[str] = None
    ) -> "AgriAIResult":
        """エラー結果を作成"""
        return cls(
            success=False,
            error_message=message,
            error_category=category,
            error_code=code,
            error_details=details or [],
            trace_id=trace_id
        )
    
    def add_error_detail(self, field: str, message: str, code: Optional[str] = None, value: Optional[Any] = None):
        """エラー詳細を追加"""
        self.error_details.append(ErrorDetail(
            field=field,
            message=message,
            code=code,
            value=value
        ))
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = {
            "success": self.success,
            "timestamp": self.timestamp.isoformat()
        }
        
        if self.success:
            result["data"] = self.data
        else:
            result.update({
                "error": {
                    "message": self.error_message,
                    "category": self.error_category.value if self.error_category else None,
                    "code": self.error_code,
                    "details": [
                        {
                            "field": detail.field,
                            "message": detail.message,
                            "code": detail.code,
                            "value": detail.value
                        }
                        for detail in self.error_details
                    ]
                }
            })
        
        if self.trace_id:
            result["trace_id"] = self.trace_id
            
        return result


# ================================
# カスタム例外クラス
# ================================

class AgriAIException(Exception):
    """農業AIシステム基底例外"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        code: Optional[str] = None,
        details: Optional[List[ErrorDetail]] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.code = code
        self.details = details or []
        self.trace_id = trace_id
        self.timestamp = datetime.utcnow()
    
    def to_result(self) -> AgriAIResult:
        """AgriAIResultに変換"""
        return AgriAIResult.error_result(
            message=self.message,
            category=self.category,
            code=self.code,
            details=self.details,
            trace_id=self.trace_id
        )


class ValidationError(AgriAIException):
    """バリデーションエラー"""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION, **kwargs)
        if field:
            self.details.append(ErrorDetail(field=field, message=message, value=value))


class DatabaseError(AgriAIException):
    """データベースエラー"""
    
    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.DATABASE, **kwargs)
        if operation:
            self.details.append(ErrorDetail(field="operation", message=operation))


class ExternalAPIError(AgriAIException):
    """外部API呼び出しエラー"""
    
    def __init__(self, message: str, api_name: Optional[str] = None, status_code: Optional[int] = None, **kwargs):
        super().__init__(message, ErrorCategory.EXTERNAL_API, **kwargs)
        if api_name:
            self.details.append(ErrorDetail(field="api_name", message=api_name))
        if status_code:
            self.details.append(ErrorDetail(field="status_code", message=str(status_code), value=status_code))


class AuthenticationError(AgriAIException):
    """認証エラー"""
    
    def __init__(self, message: str = "認証に失敗しました", **kwargs):
        super().__init__(message, ErrorCategory.AUTHENTICATION, **kwargs)


class AuthorizationError(AgriAIException):
    """認可エラー"""
    
    def __init__(self, message: str = "アクセス権限がありません", resource: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.AUTHORIZATION, **kwargs)
        if resource:
            self.details.append(ErrorDetail(field="resource", message=resource))


class BusinessLogicError(AgriAIException):
    """ビジネスロジックエラー"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.BUSINESS_LOGIC, **kwargs)


class TimeoutError(AgriAIException):
    """タイムアウトエラー"""
    
    def __init__(self, message: str = "操作がタイムアウトしました", timeout_seconds: Optional[int] = None, **kwargs):
        super().__init__(message, ErrorCategory.TIMEOUT, **kwargs)
        if timeout_seconds:
            self.details.append(ErrorDetail(field="timeout_seconds", message=str(timeout_seconds), value=timeout_seconds))


class NetworkError(AgriAIException):
    """ネットワークエラー"""
    
    def __init__(self, message: str = "ネットワークエラーが発生しました", **kwargs):
        super().__init__(message, ErrorCategory.NETWORK, **kwargs)


# ================================
# エラーハンドリングデコレータ
# ================================

from functools import wraps
from typing import Callable, TypeVar, Union
import asyncio
import logging

T = TypeVar('T')

def handle_exceptions(
    default_category: ErrorCategory = ErrorCategory.SYSTEM,
    logger: Optional[logging.Logger] = None
):
    """エラーハンドリングデコレータ"""
    
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, AgriAIResult]]:
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Union[T, AgriAIResult]:
            try:
                return func(*args, **kwargs)
            except AgriAIException as e:
                if logger:
                    logger.error(f"AgriAI Exception: {e.message}", extra={"trace_id": e.trace_id})
                return e.to_result()
            except Exception as e:
                if logger:
                    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                return AgriAIResult.error_result(
                    message=f"予期しないエラーが発生しました: {str(e)}",
                    category=default_category
                )
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Union[T, AgriAIResult]:
            try:
                return await func(*args, **kwargs)
            except AgriAIException as e:
                if logger:
                    logger.error(f"AgriAI Exception: {e.message}", extra={"trace_id": e.trace_id})
                return e.to_result()
            except Exception as e:
                if logger:
                    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                return AgriAIResult.error_result(
                    message=f"予期しないエラーが発生しました: {str(e)}",
                    category=default_category
                )
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_fields(*required_fields: str):
    """必須フィールドチェックデコレータ"""
    
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, AgriAIResult]]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Union[T, AgriAIResult]:
            # 最初の引数がdictの場合、必須フィールドをチェック
            if args and isinstance(args[0], dict):
                data = args[0]
                missing_fields = []
                for field in required_fields:
                    if field not in data or data[field] is None or data[field] == "":
                        missing_fields.append(field)
                
                if missing_fields:
                    result = AgriAIResult.error_result(
                        message="必須フィールドが不足しています",
                        category=ErrorCategory.VALIDATION,
                        code="MISSING_REQUIRED_FIELDS"
                    )
                    for field in missing_fields:
                        result.add_error_detail(field, f"{field}は必須です", "REQUIRED")
                    return result
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ================================
# エラー解析・報告ユーティリティ
# ================================

class ErrorAnalyzer:
    """エラー解析・統計クラス"""
    
    def __init__(self):
        self.error_counts: Dict[ErrorCategory, int] = {}
        self.error_history: List[AgriAIException] = []
    
    def record_error(self, error: AgriAIException):
        """エラーを記録"""
        self.error_history.append(error)
        self.error_counts[error.category] = self.error_counts.get(error.category, 0) + 1
    
    def get_error_summary(self) -> Dict[str, Any]:
        """エラーサマリーを取得"""
        return {
            "total_errors": len(self.error_history),
            "by_category": dict(self.error_counts),
            "recent_errors": [
                {
                    "message": error.message,
                    "category": error.category.value,
                    "timestamp": error.timestamp.isoformat()
                }
                for error in self.error_history[-10:]  # 最新10件
            ]
        }


# ================================
# グローバルエラーアナライザー
# ================================

global_error_analyzer = ErrorAnalyzer()


def record_error(error: AgriAIException):
    """グローバルエラーアナライザーにエラーを記録"""
    global_error_analyzer.record_error(error)


def get_error_summary() -> Dict[str, Any]:
    """グローバルエラーサマリーを取得"""
    return global_error_analyzer.get_error_summary()