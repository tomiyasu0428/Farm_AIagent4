"""
作業情報スコアラー

抽出された作業情報の信頼度スコアを計算するドメインロジック
I/Oに依存しない純粋なビジネスロジック
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class WorkInfoScorer:
    """
    作業情報の信頼度スコア計算クラス
    
    責務: ドメインロジックのみ
    - 抽出データの品質評価
    - 信頼度スコア算出
    - データ完整性チェック
    """
    
    def __init__(self):
        # スコア重み設定
        self.score_weights = {
            "work_date": 0.15,      # 作業日
            "field_name": 0.20,     # 圃場名
            "crop_name": 0.15,      # 作物名
            "work_category": 0.15,  # 作業分類
            "materials": 0.20,      # 使用資材
            "quantity": 0.10,       # 使用量
            "specificity": 0.05     # 具体性ボーナス
        }
    
    def calculate_confidence_score(self, extracted_data: Dict[str, Any]) -> float:
        """
        抽出データの信頼度スコアを計算
        
        Args:
            extracted_data: LLMから抽出されたデータ
            
        Returns:
            float: 信頼度スコア (0.0-1.0)
        """
        score = 0.0
        
        try:
            # 各項目の評価
            score += self._evaluate_work_date(extracted_data.get("work_date")) * self.score_weights["work_date"]
            score += self._evaluate_field_name(extracted_data.get("field_name")) * self.score_weights["field_name"]
            score += self._evaluate_crop_name(extracted_data.get("crop_name")) * self.score_weights["crop_name"]
            score += self._evaluate_work_category(extracted_data.get("work_category")) * self.score_weights["work_category"]
            score += self._evaluate_materials(extracted_data.get("materials", [])) * self.score_weights["materials"]
            score += self._evaluate_quantity(extracted_data.get("quantity"), extracted_data.get("unit")) * self.score_weights["quantity"]
            score += self._evaluate_specificity(extracted_data) * self.score_weights["specificity"]
            
            # スコアを0-1の範囲にクランプ
            score = max(0.0, min(1.0, score))
            
            logger.debug(f"信頼度スコア算出: {score:.3f}")
            return score
            
        except Exception as e:
            logger.error(f"信頼度スコア計算エラー: {e}")
            return 0.0
    
    def _evaluate_work_date(self, work_date: Optional[str]) -> float:
        """作業日の評価"""
        if not work_date:
            return 0.0
        
        # 相対日付の評価
        relative_patterns = ["今日", "昨日", "一昨日", r"\d+日前", "先週", "今週"]
        for pattern in relative_patterns:
            if re.search(pattern, work_date):
                return 0.9  # 相対日付は高評価
        
        # 具体的な日付の評価
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",       # YYYY-MM-DD
            r"\d{1,2}/\d{1,2}",         # M/D
            r"\d{1,2}月\d{1,2}日"       # M月D日
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, work_date):
                return 1.0  # 具体的な日付は最高評価
        
        # その他の日付表現
        if any(keyword in work_date for keyword in ["日", "月", "週"]):
            return 0.6
        
        return 0.3  # 曖昧な日付表現
    
    def _evaluate_field_name(self, field_name: Optional[str]) -> float:
        """圃場名の評価"""
        if not field_name:
            return 0.0
        
        field_name = field_name.strip()
        
        # 具体的な圃場名パターン
        specific_patterns = [
            r"[A-Za-z0-9]+[畑圃場]",    # A畑、第1圃場など
            r"[あ-ん]+[ハウス]",         # トマトハウスなど
            r"[0-9]+[号棟]",             # 1号棟など
        ]
        
        for pattern in specific_patterns:
            if re.search(pattern, field_name):
                return 1.0
        
        # 一般的な圃場表現
        if any(keyword in field_name for keyword in ["畑", "田", "圃場", "ハウス", "温室"]):
            return 0.8
        
        # 抽象的な表現
        if len(field_name) >= 2:
            return 0.5
        
        return 0.2
    
    def _evaluate_crop_name(self, crop_name: Optional[str]) -> float:
        """作物名の評価"""
        if not crop_name:
            return 0.0
        
        crop_name = crop_name.strip()
        
        # 一般的な作物名
        common_crops = [
            "トマト", "キュウリ", "ナス", "ピーマン", "イチゴ",
            "レタス", "キャベツ", "白菜", "大根", "人参",
            "じゃがいも", "玉ねぎ", "ねぎ", "ほうれん草"
        ]
        
        if crop_name in common_crops:
            return 1.0
        
        # 部分一致チェック
        for crop in common_crops:
            if crop in crop_name or crop_name in crop:
                return 0.8
        
        # その他の具体的な名前
        if len(crop_name) >= 2 and not crop_name.isdigit():
            return 0.6
        
        return 0.3
    
    def _evaluate_work_category(self, work_category: Optional[str]) -> float:
        """作業分類の評価"""
        if not work_category:
            return 0.0
        
        # 標準的な作業分類
        standard_categories = ["防除", "施肥", "収穫", "栽培", "管理"]
        
        if work_category in standard_categories:
            return 1.0
        
        # 関連キーワード
        category_keywords = {
            "防除": ["農薬", "殺菌", "殺虫", "散布", "防虫"],
            "施肥": ["肥料", "追肥", "元肥", "堆肥"],
            "収穫": ["収穫", "採取", "出荷"],
            "栽培": ["播種", "定植", "移植", "植付"],
            "管理": ["草刈", "除草", "清掃", "点検", "整枝"]
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in work_category for keyword in keywords):
                return 0.8
        
        # その他の明確な作業表現
        if len(work_category) >= 2:
            return 0.5
        
        return 0.2
    
    def _evaluate_materials(self, materials: list) -> float:
        """使用資材の評価"""
        if not materials:
            return 0.0
        
        total_score = 0.0
        
        for material in materials:
            if not isinstance(material, str):
                continue
            
            material = material.strip()
            
            # 具体的な商品名パターン
            if re.search(r"[A-Za-z0-9]+.*[0-9]+", material):  # 英数字+数字
                total_score += 1.0
            elif any(keyword in material for keyword in ["剤", "液", "粉", "粒"]):
                total_score += 0.8
            elif len(material) >= 3:
                total_score += 0.6
            else:
                total_score += 0.3
        
        # 平均スコア
        return min(1.0, total_score / len(materials))
    
    def _evaluate_quantity(self, quantity: Optional[float], unit: Optional[str]) -> float:
        """使用量の評価"""
        score = 0.0
        
        # 数量の評価
        if quantity is not None and quantity > 0:
            score += 0.6
        
        # 単位の評価
        if unit:
            common_units = ["L", "ml", "kg", "g", "袋", "本", "回"]
            if unit in common_units:
                score += 0.4
            elif len(unit) >= 1:
                score += 0.2
        
        return min(1.0, score)
    
    def _evaluate_specificity(self, extracted_data: Dict[str, Any]) -> float:
        """全体的な具体性の評価"""
        specificity_indicators = 0
        total_fields = 0
        
        for field in ["work_date", "field_name", "crop_name", "work_category", "materials"]:
            total_fields += 1
            value = extracted_data.get(field)
            
            if value:
                if isinstance(value, list):
                    if len(value) > 0:
                        specificity_indicators += 1
                elif isinstance(value, str) and len(value.strip()) > 0:
                    specificity_indicators += 1
        
        # 補足情報の存在
        if extracted_data.get("notes"):
            specificity_indicators += 0.5
        if extracted_data.get("work_count"):
            specificity_indicators += 0.5
        
        return min(1.0, specificity_indicators / total_fields)
    
    def get_score_breakdown(self, extracted_data: Dict[str, Any]) -> Dict[str, float]:
        """スコアの内訳を取得（デバッグ用）"""
        breakdown = {}
        
        breakdown["work_date"] = self._evaluate_work_date(extracted_data.get("work_date"))
        breakdown["field_name"] = self._evaluate_field_name(extracted_data.get("field_name"))
        breakdown["crop_name"] = self._evaluate_crop_name(extracted_data.get("crop_name"))
        breakdown["work_category"] = self._evaluate_work_category(extracted_data.get("work_category"))
        breakdown["materials"] = self._evaluate_materials(extracted_data.get("materials", []))
        breakdown["quantity"] = self._evaluate_quantity(extracted_data.get("quantity"), extracted_data.get("unit"))
        breakdown["specificity"] = self._evaluate_specificity(extracted_data)
        
        return breakdown