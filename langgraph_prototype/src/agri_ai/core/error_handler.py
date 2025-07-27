"""
エラーハンドリング共通クラス
各ツールで統一されたエラーハンドリングを提供します。
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ErrorHandler:
    """エラーハンドリング共通クラス"""
    
    @staticmethod
    def handle_tool_error(error: Exception, tool_name: str, operation: str = "") -> Dict[str, Any]:
        """ツールエラーの統一処理"""
        error_message = f"{tool_name}"
        if operation:
            error_message += f"の{operation}"
        error_message += f"でエラーが発生しました: {str(error)}"
        
        logger.error(error_message)
        return {
            "error": error_message,
            "tool": tool_name,
            "operation": operation
        }
    
    @staticmethod
    def handle_validation_error(message: str, tool_name: str) -> Dict[str, Any]:
        """バリデーションエラーの統一処理"""
        error_message = f"{tool_name}: {message}"
        logger.warning(error_message)
        return {
            "error": error_message,
            "tool": tool_name,
            "type": "validation"
        }
    
    @staticmethod
    def handle_not_found_error(resource: str, tool_name: str) -> Dict[str, Any]:
        """リソース未発見エラーの統一処理"""
        error_message = f"{resource}が見つかりません"
        logger.info(f"{tool_name}: {error_message}")
        return {
            "error": error_message,
            "tool": tool_name,
            "type": "not_found"
        }