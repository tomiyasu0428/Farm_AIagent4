"""
マスターデータマッチャー

抽出された情報とマスターデータの照合・検証を専門的に処理
I/Oに依存しない純粋なドメインロジック
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)


class MasterDataMatcher:
    """
    マスターデータマッチングロジック
    
    責務: ドメインロジックのみ
    - 文字列類似度計算
    - マッチング戦略の実行
    - 信頼度スコア算出
    - 曖昧性の検出
    """
    
    def __init__(self):
        # マッチング閾値設定
        self.match_thresholds = {
            "exact": 1.0,           # 完全一致
            "high": 0.8,            # 高精度マッチ
            "medium": 0.6,          # 中程度マッチ
            "low": 0.4              # 低精度マッチ
        }
        
        # 正規化設定
        self.normalization_config = {
            "remove_spaces": True,
            "lowercase": True,
            "remove_punctuation": True,
            "katakana_hiragana": True
        }
    
    def match_field_data(
        self, 
        extracted_name: str, 
        master_fields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        圃場データのマッチング
        
        Args:
            extracted_name: 抽出された圃場名
            master_fields: マスター圃場データリスト
            
        Returns:
            Dict: マッチング結果
        """
        if not extracted_name or not master_fields:
            return self._create_no_match_result("field")
        
        # 正規化
        normalized_input = self._normalize_text(extracted_name)
        
        matches = []
        for field in master_fields:
            field_name = field.get('field_name', '')
            field_code = field.get('field_code', '')
            
            # 名前でのマッチング
            name_score = self._calculate_similarity(normalized_input, self._normalize_text(field_name))
            
            # コードでのマッチング（部分一致も考慮）
            code_score = 0.0
            if field_code and (field_code.lower() in normalized_input.lower() or 
                              normalized_input.lower() in field_code.lower()):
                code_score = 0.9
            
            # 最高スコアを採用
            best_score = max(name_score, code_score)
            
            if best_score >= self.match_thresholds["low"]:
                matches.append({
                    'field_id': field.get('field_id'),
                    'field_name': field_name,
                    'field_code': field_code,
                    'confidence': best_score,
                    'match_method': 'name_similarity' if name_score > code_score else 'code_match'
                })
        
        return self._select_best_match(matches, "field")
    
    def match_crop_data(
        self, 
        extracted_name: str, 
        master_crops: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        作物データのマッチング
        
        Args:
            extracted_name: 抽出された作物名
            master_crops: マスター作物データリスト
            
        Returns:
            Dict: マッチング結果
        """
        if not extracted_name or not master_crops:
            return self._create_no_match_result("crop")
        
        normalized_input = self._normalize_text(extracted_name)
        
        matches = []
        for crop in master_crops:
            crop_name = crop.get('crop_name', '')
            scientific_name = crop.get('scientific_name', '')
            aliases = crop.get('aliases', [])
            
            # 主名称でのマッチング
            main_score = self._calculate_similarity(normalized_input, self._normalize_text(crop_name))
            
            # 学名でのマッチング
            scientific_score = 0.0
            if scientific_name:
                scientific_score = self._calculate_similarity(normalized_input, self._normalize_text(scientific_name))
            
            # 別名でのマッチング
            alias_score = 0.0
            for alias in aliases:
                alias_score = max(alias_score, self._calculate_similarity(normalized_input, self._normalize_text(alias)))
            
            # 最高スコアを採用
            best_score = max(main_score, scientific_score, alias_score)
            
            if best_score >= self.match_thresholds["low"]:
                match_method = "main_name"
                if scientific_score == best_score:
                    match_method = "scientific_name"
                elif alias_score == best_score:
                    match_method = "alias"
                
                matches.append({
                    'crop_id': crop.get('crop_id'),
                    'crop_name': crop_name,
                    'confidence': best_score,
                    'match_method': match_method
                })
        
        return self._select_best_match(matches, "crop")
    
    def match_material_data(
        self, 
        extracted_names: List[str], 
        master_materials: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        資材データのマッチング（複数対応）
        
        Args:
            extracted_names: 抽出された資材名リスト
            master_materials: マスター資材データリスト
            
        Returns:
            List[Dict]: マッチング結果リスト
        """
        if not extracted_names or not master_materials:
            return []
        
        all_matches = []
        for extracted_name in extracted_names:
            match_result = self._match_single_material(extracted_name, master_materials)
            if match_result.get('matched_material'):
                all_matches.append(match_result)
        
        return all_matches
    
    def _match_single_material(
        self, 
        extracted_name: str, 
        master_materials: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        単一資材のマッチング
        """
        if not extracted_name:
            return self._create_no_match_result("material")
        
        normalized_input = self._normalize_text(extracted_name)
        
        matches = []
        for material in master_materials:
            material_name = material.get('material_name', '')
            brand_name = material.get('brand_name', '')
            active_ingredients = material.get('active_ingredients', [])
            
            # 商品名でのマッチング
            name_score = self._calculate_similarity(normalized_input, self._normalize_text(material_name))
            
            # ブランド名でのマッチング
            brand_score = 0.0
            if brand_name:
                brand_score = self._calculate_similarity(normalized_input, self._normalize_text(brand_name))
            
            # 有効成分でのマッチング
            ingredient_score = 0.0
            for ingredient in active_ingredients:
                ingredient_score = max(
                    ingredient_score, 
                    self._calculate_similarity(normalized_input, self._normalize_text(ingredient))
                )
            
            # 部分文字列マッチング（商品名の特徴）
            partial_score = 0.0
            if len(normalized_input) >= 3:
                if normalized_input in self._normalize_text(material_name):
                    partial_score = 0.7
                elif self._normalize_text(material_name) in normalized_input:
                    partial_score = 0.6
            
            # 最高スコアを採用
            best_score = max(name_score, brand_score, ingredient_score, partial_score)
            
            if best_score >= self.match_thresholds["low"]:
                match_method = "material_name"
                if brand_score == best_score:
                    match_method = "brand_name"
                elif ingredient_score == best_score:
                    match_method = "active_ingredient"
                elif partial_score == best_score:
                    match_method = "partial_match"
                
                matches.append({
                    'material_id': material.get('material_id'),
                    'material_name': material_name,
                    'confidence': best_score,
                    'match_method': match_method
                })
        
        return self._select_best_match(matches, "material")
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        文字列類似度の計算
        
        Args:
            text1: 比較文字列1
            text2: 比較文字列2
            
        Returns:
            float: 類似度スコア (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        # 完全一致チェック
        if text1 == text2:
            return 1.0
        
        # Levenshtein距離ベースの類似度
        similarity = SequenceMatcher(None, text1, text2).ratio()
        
        # 部分一致ボーナス
        if text1 in text2 or text2 in text1:
            shorter_len = min(len(text1), len(text2))
            longer_len = max(len(text1), len(text2))
            partial_bonus = shorter_len / longer_len * 0.2
            similarity = min(1.0, similarity + partial_bonus)
        
        return similarity
    
    def _normalize_text(self, text: str) -> str:
        """
        テキストの正規化
        
        Args:
            text: 正規化対象テキスト
            
        Returns:
            str: 正規化されたテキスト
        """
        if not text:
            return ""
        
        normalized = text
        
        # 小文字化
        if self.normalization_config["lowercase"]:
            normalized = normalized.lower()
        
        # 空白除去
        if self.normalization_config["remove_spaces"]:
            normalized = re.sub(r'\s+', '', normalized)
        
        # 句読点除去
        if self.normalization_config["remove_punctuation"]:
            normalized = re.sub(r'[。、.,!?！？\-\(\)（）\[\]「」]', '', normalized)
        
        # カタカナ・ひらがな統一（カタカナに統一）
        if self.normalization_config["katakana_hiragana"]:
            normalized = self._hiragana_to_katakana(normalized)
        
        return normalized
    
    def _hiragana_to_katakana(self, text: str) -> str:
        """ひらがなをカタカナに変換"""
        result = []
        for char in text:
            if 'あ' <= char <= 'ん':
                # ひらがなをカタカナに変換
                result.append(chr(ord(char) + ord('ア') - ord('あ')))
            else:
                result.append(char)
        return ''.join(result)
    
    def _select_best_match(self, matches: List[Dict[str, Any]], data_type: str) -> Dict[str, Any]:
        """
        最適なマッチを選択
        
        Args:
            matches: マッチ候補リスト
            data_type: データタイプ（field, crop, material）
            
        Returns:
            Dict: 選択されたマッチ結果
        """
        if not matches:
            return self._create_no_match_result(data_type)
        
        # 信頼度順でソート
        sorted_matches = sorted(matches, key=lambda x: x['confidence'], reverse=True)
        best_match = sorted_matches[0]
        
        # 曖昧性チェック
        ambiguity_detected = False
        if len(sorted_matches) >= 2:
            confidence_diff = best_match['confidence'] - sorted_matches[1]['confidence']
            if confidence_diff < 0.1:  # 信頼度差が小さい場合は曖昧
                ambiguity_detected = True
        
        return {
            'matched_' + data_type: best_match,
            'candidates': sorted_matches[:3],  # 上位3候補
            'ambiguity_detected': ambiguity_detected,
            'match_quality': self._assess_match_quality(best_match['confidence'])
        }
    
    def _create_no_match_result(self, data_type: str) -> Dict[str, Any]:
        """マッチなし結果の作成"""
        return {
            'matched_' + data_type: None,
            'candidates': [],
            'ambiguity_detected': False,
            'match_quality': 'no_match'
        }
    
    def _assess_match_quality(self, confidence: float) -> str:
        """マッチ品質の評価"""
        if confidence >= self.match_thresholds["exact"]:
            return "exact"
        elif confidence >= self.match_thresholds["high"]:
            return "high"
        elif confidence >= self.match_thresholds["medium"]:
            return "medium"
        elif confidence >= self.match_thresholds["low"]:
            return "low"
        else:
            return "no_match"
    
    def get_similarity_metrics(self, text1: str, text2: str) -> Dict[str, float]:
        """類似度メトリクスの詳細取得（デバッグ用）"""
        return {
            "raw_similarity": SequenceMatcher(None, text1, text2).ratio(),
            "normalized_similarity": self._calculate_similarity(
                self._normalize_text(text1), 
                self._normalize_text(text2)
            ),
            "length_ratio": min(len(text1), len(text2)) / max(len(text1), len(text2)) if text1 and text2 else 0
        }