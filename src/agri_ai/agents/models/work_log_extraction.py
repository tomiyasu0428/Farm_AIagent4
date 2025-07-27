"""
作業記録抽出用のPydanticモデル定義

LLMのFunction Calling機能を活用した構造化データ抽出のためのスキーマ
"""

from typing import List, Optional, Literal
from datetime import date
from pydantic import BaseModel, Field


class ExtractedWorkInfo(BaseModel):
    """作業記録から抽出された情報のモデル"""
    
    work_date: Optional[str] = Field(
        None, 
        description="作業日。相対日付（昨日、今日、一昨日）または具体的な日付（YYYY-MM-DD形式）"
    )
    
    field_name: Optional[str] = Field(
        None,
        description="圃場名。「トマトハウス」「橋向こう①」「第1圃場」など"
    )
    
    crop_name: Optional[str] = Field(
        None,
        description="作物名。「トマト」「キュウリ」「ナス」「ピーマン」「イチゴ」など"
    )
    
    work_category: Optional[Literal["防除", "施肥", "栽培", "収穫", "管理", "その他"]] = Field(
        None,
        description="作業分類。防除（農薬散布）、施肥（肥料）、栽培（定植・誘引など）、収穫、管理（草刈りなど）"
    )
    
    materials: List[str] = Field(
        default_factory=list,
        description="使用した資材・農薬・肥料のリスト。「ダコニール1000」「化成肥料」など"
    )
    
    quantity: Optional[float] = Field(
        None,
        description="使用量・実施量の数値。500、2.5、10など"
    )
    
    unit: Optional[str] = Field(
        None,
        description="単位。「L」「kg」「袋」「回」「ha」など"
    )
    
    work_count: Optional[int] = Field(
        None,
        description="作業回数。「3回目の防除」の場合は3"
    )
    
    notes: Optional[str] = Field(
        None,
        description="その他のメモや特記事項"
    )
    
    confidence_score: Optional[float] = Field(
        None,
        description="抽出の信頼度スコア（0.0-1.0）。内部的に計算される"
    )


class WorkLogValidationResult(BaseModel):
    """作業記録の検証結果"""
    
    is_valid: bool = Field(description="全体的な検証結果")
    field_validation: dict = Field(description="圃場名の検証結果")
    crop_validation: dict = Field(description="作物名の検証結果") 
    material_validation: List[dict] = Field(description="資材の検証結果リスト")
    missing_info: List[str] = Field(description="不足している情報のリスト")
    suggestions: List[str] = Field(description="改善提案のリスト")


class UserConfirmationData(BaseModel):
    """ユーザー確認用のデータ"""
    
    extracted_info: ExtractedWorkInfo
    validation_result: WorkLogValidationResult
    confirmation_message: str = Field(description="ユーザー確認用のメッセージ")
    options: List[dict] = Field(description="選択肢やボタンの情報")