"""
統一データベースモデル定義

型安全性とバリデーションを強化したMongoDBドキュメントモデル
LegacyシステムとLangGraphシステム間で共有される全データモデルを定義
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal, Union
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
from bson import ObjectId


class PyObjectId(ObjectId):
    """PydanticでObjectIdを使用するための拡張クラス"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema, _handler):
        field_schema.update(type="string")
        return field_schema


class BaseDocument(BaseModel):
    """基底ドキュメントクラス - 共通フィールドと設定"""
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0", description="スキーマバージョン")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        use_enum_values = True


# ================================
# Enumクラス定義（型安全性向上）
# ================================

class WorkCategory(str, Enum):
    """作業分類"""
    PREVENTION = "防除"
    FERTILIZATION = "施肥"
    CULTIVATION = "栽培"
    HARVEST = "収穫"
    MANAGEMENT = "管理"
    MAINTENANCE = "メンテナンス"


class MaterialType(str, Enum):
    """資材タイプ"""
    PESTICIDE = "農薬"
    FERTILIZER = "肥料"
    SEED = "種子"
    TOOL = "道具"
    EQUIPMENT = "機器"


class WorkStatus(str, Enum):
    """作業状態"""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REVIEWED = "reviewed"
    COMPLETED = "completed"


class Priority(str, Enum):
    """優先度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ExtractionMethod(str, Enum):
    """抽出方法"""
    AUTO = "auto"
    MANUAL = "manual"
    HYBRID = "hybrid"


# ================================
# 作物関連モデル
# ================================

class CultivationStage(BaseModel):
    """栽培ステージ"""
    stage: str = Field(..., description="ステージ名")
    days_from_planting: int = Field(..., description="植付けからの日数")
    typical_work: List[str] = Field(default_factory=list, description="典型的作業")
    risk_factors: List[str] = Field(default_factory=list, description="リスク要因")


class CropDocument(BaseDocument):
    """作物マスターモデル"""
    
    name: str = Field(..., min_length=1, description="作物名")
    variety: Optional[str] = Field(None, description="品種")
    category: str = Field(..., description="作物カテゴリ")
    cultivation_calendar: List[CultivationStage] = Field(default_factory=list, description="栽培カレンダー")
    disease_pest_risks: List[Dict[str, Any]] = Field(default_factory=list, description="病害虫リスク")
    applicable_materials: List[PyObjectId] = Field(default_factory=list, description="適用資材ID")
    growth_period_days: Optional[int] = Field(None, gt=0, description="栽培期間（日数）")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('作物名は必須です')
        return v.strip()


# ================================
# 資材関連モデル
# ================================

class DilutionRate(BaseModel):
    """希釈倍率"""
    crop: str = Field(..., description="対象作物")
    rate: str = Field(..., description="希釈倍率")
    usage: str = Field(..., description="使用方法")


class MaterialDocument(BaseDocument):
    """資材マスターモデル"""
    
    name: str = Field(..., min_length=1, description="資材名")
    type: MaterialType = Field(..., description="資材タイプ")
    active_ingredient: Optional[str] = Field(None, description="有効成分")
    manufacturer: Optional[str] = Field(None, description="製造会社")
    dilution_rates: List[DilutionRate] = Field(default_factory=list, description="希釈倍率")
    preharvest_interval: Optional[int] = Field(None, ge=0, description="収穫前日数")
    max_applications_per_season: Optional[int] = Field(None, gt=0, description="年間最大使用回数")
    rotation_group: Optional[str] = Field(None, description="ローテーション群")
    target_diseases: List[str] = Field(default_factory=list, description="対象病害")
    usage_restrictions: Dict[str, Any] = Field(default_factory=dict, description="使用制限")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('資材名は必須です')
        return v.strip()


# ================================
# 圃場関連モデル
# ================================

class Location(BaseModel):
    """位置情報"""
    latitude: float = Field(..., ge=-90, le=90, description="緯度")
    longitude: float = Field(..., ge=-180, le=180, description="経度")
    altitude: Optional[float] = Field(None, description="標高")


class CurrentCultivation(BaseModel):
    """現在の作付け状況"""
    crop_id: PyObjectId = Field(..., description="作物ID")
    planting_date: datetime = Field(..., description="植付け日")
    expected_harvest: datetime = Field(..., description="収穫予定日")
    status: str = Field(..., description="栽培状況")


class FieldDocument(BaseDocument):
    """圃場マスターモデル"""
    
    field_code: str = Field(..., min_length=1, description="圃場コード")
    name: str = Field(..., min_length=1, description="圃場名")
    area: float = Field(..., gt=0, description="面積(㎡)")
    location: Optional[Location] = Field(None, description="位置情報")
    soil_type: Optional[str] = Field(None, description="土壌タイプ")
    irrigation_system: Optional[str] = Field(None, description="灌漑システム")
    current_cultivation: Optional[CurrentCultivation] = Field(None, description="現在の作付け状況")
    next_scheduled_work: Optional[Dict[str, Any]] = Field(None, description="次回予定作業")
    
    @validator('field_code')
    def validate_field_code(cls, v):
        if not v.strip():
            raise ValueError('圃場コードは必須です')
        return v.strip().upper()
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('圃場名は必須です')
        return v.strip()


# ================================
# 作業記録関連モデル
# ================================

class ExtractedData(BaseModel):
    """抽出された構造化データ"""
    field_names: List[str] = Field(default_factory=list, description="圃場名")
    crop_names: List[str] = Field(default_factory=list, description="作物名")
    work_types: List[str] = Field(default_factory=list, description="作業種類")
    materials_used: List[str] = Field(default_factory=list, description="使用資材")
    quantities: List[str] = Field(default_factory=list, description="使用量")
    work_duration: Optional[str] = Field(None, description="作業時間")
    weather_condition: Optional[str] = Field(None, description="天候")
    notes: Optional[str] = Field(None, description="備考")


class ReviewStatus(BaseModel):
    """レビュー状態"""
    reviewed: bool = Field(default=False, description="レビュー済み")
    reviewer_id: Optional[str] = Field(None, description="レビュアーID")
    reviewed_at: Optional[datetime] = Field(None, description="レビュー日時")
    review_notes: Optional[str] = Field(None, description="レビューメモ")


class WorkLogDocument(BaseDocument):
    """作業記録モデル - 型安全性強化版"""
    
    log_id: str = Field(..., min_length=1, description="人間可読な記録ID")
    user_id: str = Field(..., min_length=1, description="作業者のユーザーID")
    work_date: datetime = Field(..., description="実際の作業実施日")
    original_message: str = Field(..., min_length=1, description="ユーザーの元メッセージ")
    
    extracted_data: ExtractedData = Field(default_factory=ExtractedData, description="構造化された抽出データ")
    category: WorkCategory = Field(..., description="作業分類")
    subcategory: Optional[str] = Field(None, description="詳細分類")
    tags: List[str] = Field(default_factory=list, description="検索用タグ配列")
    
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="情報抽出の信頼度")
    extraction_method: ExtractionMethod = Field(default=ExtractionMethod.AUTO, description="抽出方法")
    status: WorkStatus = Field(default=WorkStatus.CONFIRMED, description="記録状態")
    
    review_status: ReviewStatus = Field(default_factory=ReviewStatus, description="レビュー状態")
    related_task_id: Optional[str] = Field(None, description="関連タスクID")
    photo_urls: List[str] = Field(default_factory=list, description="作業写真URL配列")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="添付ファイル情報")
    
    source: str = Field(default="line_bot", description="データソース")
    sync_status: Dict[str, Any] = Field(default_factory=dict, description="同期状態")
    
    @validator('log_id')
    def validate_log_id(cls, v):
        if not v.strip():
            raise ValueError('記録IDは必須です')
        return v.strip()
    
    @validator('work_date')
    def validate_work_date(cls, v):
        # テスト環境では1日のマージンを許可
        from datetime import timedelta
        max_allowed = datetime.utcnow() + timedelta(days=1)
        if v > max_allowed:
            raise ValueError('作業日は過去または現在の日付である必要があります')
        return v


# ================================
# タスク関連モデル
# ================================

class AutoTaskDocument(BaseDocument):
    """自動生成タスクモデル"""
    
    field_id: PyObjectId = Field(..., description="圃場ID")
    scheduled_date: datetime = Field(..., description="予定日")
    work_type: WorkCategory = Field(..., description="作業種別")
    priority: Priority = Field(default=Priority.MEDIUM, description="優先度")
    status: WorkStatus = Field(default=WorkStatus.DRAFT, description="ステータス")
    materials: List[PyObjectId] = Field(default_factory=list, description="使用予定資材")
    notes: Optional[str] = Field(None, description="メモ")
    auto_generated: bool = Field(default=True, description="自動生成フラグ")
    estimated_duration: Optional[int] = Field(None, gt=0, description="予想作業時間（分）")
    
    @validator('scheduled_date')
    def validate_scheduled_date(cls, v):
        if v < datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0):
            raise ValueError('予定日は今日以降である必要があります')
        return v


# ================================
# ユーザー関連モデル
# ================================

class WorkerDocument(BaseDocument):
    """作業者マスターモデル"""
    
    name: str = Field(..., min_length=1, description="作業者名")
    role: str = Field(default="worker", description="役割")
    line_user_id: Optional[str] = Field(None, description="LINE User ID")
    skills: List[str] = Field(default_factory=list, description="スキル")
    is_active: bool = Field(default=True, description="アクティブ状態")
    contact_info: Optional[Dict[str, str]] = Field(None, description="連絡先情報")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('作業者名は必須です')
        return v.strip()


# ================================
# 在庫関連モデル
# ================================

class InventoryDocument(BaseDocument):
    """在庫管理モデル"""
    
    material_id: PyObjectId = Field(..., description="資材ID")
    current_qty: float = Field(..., ge=0, description="現在数量")
    unit: str = Field(..., min_length=1, description="単位")
    min_threshold: float = Field(..., ge=0, description="最小しきい値")
    max_threshold: Optional[float] = Field(None, gt=0, description="最大しきい値")
    location: Optional[str] = Field(None, description="保管場所")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="最終更新日時")
    
    @validator('max_threshold')
    def validate_thresholds(cls, v, values):
        if v is not None and 'min_threshold' in values and v <= values['min_threshold']:
            raise ValueError('最大しきい値は最小しきい値より大きくしてください')
        return v


# ================================
# 統計・分析関連モデル
# ================================

class StatisticsDocument(BaseDocument):
    """統計情報モデル"""
    
    period_start: datetime = Field(..., description="集計期間開始")
    period_end: datetime = Field(..., description="集計期間終了")
    field_id: Optional[PyObjectId] = Field(None, description="圃場ID（全体統計の場合はNone）")
    metrics: Dict[str, Union[int, float, str]] = Field(..., description="統計メトリクス")
    breakdown: Dict[str, Any] = Field(default_factory=dict, description="詳細内訳")
    
    @validator('period_end')
    def validate_period(cls, v, values):
        if 'period_start' in values and v <= values['period_start']:
            raise ValueError('期間終了は期間開始より後である必要があります')
        return v


# ================================
# 型安全性のためのUnion型定義
# ================================

DocumentType = Union[
    CropDocument,
    MaterialDocument, 
    FieldDocument,
    WorkLogDocument,
    AutoTaskDocument,
    WorkerDocument,
    InventoryDocument,
    StatisticsDocument
]


# ================================
# ヘルパー関数
# ================================

def create_log_id(user_id: str, work_date: datetime) -> str:
    """作業記録IDを生成"""
    import uuid
    date_str = work_date.strftime("%Y%m%d")
    short_uuid = str(uuid.uuid4())[:8].upper()
    return f"LOG-{date_str}-{short_uuid}"


def validate_document_type(document_data: Dict[str, Any], expected_type: type) -> bool:
    """ドキュメントタイプの検証"""
    try:
        expected_type(**document_data)
        return True
    except Exception:
        return False