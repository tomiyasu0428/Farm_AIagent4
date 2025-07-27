"""
エージェント用データモデル
"""

from .work_log_extraction import (
    ExtractedWorkInfo,
    WorkLogValidationResult,
    UserConfirmationData
)

__all__ = [
    "ExtractedWorkInfo",
    "WorkLogValidationResult", 
    "UserConfirmationData"
]