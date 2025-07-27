"""
MasterDataResolver: マスターデータとの連携・ID変換サービス

文字列表記ゆれを解決し、圃場名・作物名・資材名をマスターデータのIDに変換する。
作業記録システムでのデータ正規化と統合分析を実現する。
"""

import logging
from typing import Dict, List
from difflib import SequenceMatcher
from ..dependencies.database import DatabaseConnection

logger = logging.getLogger(__name__)


class MasterDataResolver:
    """マスターデータとの照合・ID変換サービス"""
    
    def __init__(self, db_connection: DatabaseConnection = None):
        # キャッシュ管理
        self.fields_cache = None
        self.crops_cache = None  
        self.materials_cache = None
        self.cache_timeout = 300  # 5分キャッシュ
        self.fields_cache_time = 0
        self.crops_cache_time = 0
        self.materials_cache_time = 0
        self.db_connection = db_connection or DatabaseConnection()
    
    async def resolve_field_data(self, field_text: str) -> Dict[str, str]:
        """
        圃場名をマスターデータと照合してIDに変換
        
        Args:
            field_text: ユーザーが入力した圃場名
            
        Returns:
            {
                'field_id': str,        # マスターデータのID
                'field_name': str,      # 正規化された圃場名
                'confidence': float,    # 照合信頼度
                'method': str           # 照合方法
            }
        """
        try:
            fields_data = await self._get_fields_data()
            
            # 段階的照合
            result = self._multi_stage_field_matching(field_text, fields_data)
            
            if result['field_id']:
                logger.info(f"圃場ID変換成功: '{field_text}' → {result['field_id']} (信頼度: {result['confidence']:.2f})")
            else:
                logger.warning(f"圃場ID変換失敗: '{field_text}' - マスターデータに見つかりません")
            
            return result
            
        except Exception as e:
            logger.error(f"圃場データ解決エラー: {e}")
            return {
                'field_id': None,
                'field_name': field_text,
                'confidence': 0.0,
                'method': 'error',
                'error': str(e)
            }
    
    async def resolve_crop_data(self, crop_text: str) -> Dict[str, any]:
        """
        作物名をマスターデータと照合してIDに変換
        
        Args:
            crop_text: ユーザーが入力した作物名
            
        Returns:
            {
                'crop_id': str,         # マスターデータのID
                'crop_name': str,       # 正規化された作物名
                'confidence': float,    # 照合信頼度
                'method': str          # 照合方法
            }
        """
        try:
            crops_data = await self._get_crops_data()
            
            # 段階的照合
            result = self._multi_stage_crop_matching(crop_text, crops_data)
            
            if result['crop_id']:
                logger.info(f"作物ID変換成功: '{crop_text}' → {result['crop_id']} (信頼度: {result['confidence']:.2f})")
            else:
                logger.warning(f"作物ID変換失敗: '{crop_text}' - マスターデータに見つかりません")
            
            return result
            
        except Exception as e:
            logger.error(f"作物データ解決エラー: {e}")
            return {
                'crop_id': None,
                'crop_name': crop_text,
                'confidence': 0.0,
                'method': 'error',
                'error': str(e)
            }
    
    async def resolve_material_data(self, material_text: str) -> Dict[str, any]:
        """
        資材名をマスターデータと照合してIDに変換
        
        Args:
            material_text: ユーザーが入力した資材名
            
        Returns:
            {
                'material_id': str,     # マスターデータのID
                'material_name': str,   # 正規化された資材名
                'confidence': float,    # 照合信頼度
                'method': str          # 照合方法
            }
        """
        try:
            materials_data = await self._get_materials_data()
            
            # 段階的照合
            result = self._multi_stage_material_matching(material_text, materials_data)
            
            if result['material_id']:
                logger.info(f"資材ID変換成功: '{material_text}' → {result['material_id']} (信頼度: {result['confidence']:.2f})")
            else:
                logger.warning(f"資材ID変換失敗: '{material_text}' - マスターデータに見つかりません")
            
            return result
            
        except Exception as e:
            logger.error(f"資材データ解決エラー: {e}")
            return {
                'material_id': None,
                'material_name': material_text,
                'confidence': 0.0,
                'method': 'error',
                'error': str(e)
            }
    
    async def _get_fields_data(self) -> List[Dict]:
        """圃場マスターデータを取得（キャッシュ付き）"""
        import time
        current_time = time.time()
        
        # キャッシュチェック
        if (self.fields_cache is not None and 
            current_time - self.fields_cache_time < self.cache_timeout):
            return self.fields_cache
        
        # データベースから取得
        client = await self.db_connection.get_client()
        try:
            fields_collection = await client.get_collection("fields")
            
            fields = await fields_collection.find(
                {}, 
                {"_id": 1, "field_code": 1, "name": 1}
            ).to_list(1000)
            
            # キャッシュ更新
            self.fields_cache = fields
            self.fields_cache_time = current_time
            
            logger.info(f"圃場マスターデータ取得: {len(fields)}件")
            return fields
            
        finally:
            pass  # 接続は再利用されるため、ここではdisconnectしない
    
    async def _get_crops_data(self) -> List[Dict]:
        """作物マスターデータを取得（キャッシュ付き）"""
        import time
        current_time = time.time()
        
        # キャッシュチェック
        if (self.crops_cache is not None and 
            current_time - self.crops_cache_time < self.cache_timeout):
            return self.crops_cache
        
        # データベースから取得
        client = await self.db_connection.get_client()
        try:
            crops_collection = await client.get_collection("crops")
            
            crops = await crops_collection.find(
                {}, 
                {"_id": 1, "crop_code": 1, "name": 1, "varieties": 1}
            ).to_list(1000)
            
            # キャッシュ更新
            self.crops_cache = crops
            self.crops_cache_time = current_time
            
            logger.info(f"作物マスターデータ取得: {len(crops)}件")
            return crops
            
        finally:
            pass  # 接続は再利用されるため、ここではdisconnectしない
    
    async def _get_materials_data(self) -> List[Dict]:
        """資材マスターデータを取得（キャッシュ付き）"""
        import time
        current_time = time.time()
        
        # キャッシュチェック
        if (self.materials_cache is not None and 
            current_time - self.materials_cache_time < self.cache_timeout):
            return self.materials_cache
        
        # データベースから取得
        client = await self.db_connection.get_client()
        try:
            materials_collection = await client.get_collection("materials")
            
            materials = await materials_collection.find(
                {}, 
                {"_id": 1, "material_code": 1, "name": 1, "aliases": 1}
            ).to_list(1000)
            
            # キャッシュ更新  
            self.materials_cache = materials
            self.materials_cache_time = current_time
            
            logger.info(f"資材マスターデータ取得: {len(materials)}件")
            return materials
            
        finally:
            pass  # 接続は再利用されるため、ここではdisconnectしない
    
    def _multi_stage_field_matching(self, field_text: str, fields_data: List[Dict]) -> Dict[str, any]:
        """圃場の段階的照合"""
        
        # Stage 1: 完全一致
        for field in fields_data:
            if field.get('name') == field_text or field.get('field_code') == field_text:
                return {
                    'field_id': str(field['_id']),
                    'field_name': field.get('name', field.get('field_code')),
                    'confidence': 1.0,
                    'method': 'exact_match'
                }
        
        # Stage 2: 部分一致
        partial_matches = []
        for field in fields_data:
            field_name = field.get('name', '')
            field_code = field.get('field_code', '')
            
            if (field_text in field_name or field_name in field_text or
                field_text in field_code or field_code in field_text):
                score = max(
                    len(field_text) / len(field_name) if field_name else 0,
                    len(field_name) / len(field_text) if field_text else 0
                )
                partial_matches.append((field, score))
        
        if partial_matches:
            best_field, score = max(partial_matches, key=lambda x: x[1])
            return {
                'field_id': str(best_field['_id']),
                'field_name': best_field.get('name', best_field.get('field_code')),
                'confidence': min(score, 0.8),
                'method': 'partial_match'
            }
        
        # Stage 3: あいまい一致
        fuzzy_matches = []
        for field in fields_data:
            field_name = field.get('name', '')
            if field_name:
                similarity = SequenceMatcher(None, field_text, field_name).ratio()
                if similarity > 0.6:
                    fuzzy_matches.append((field, similarity))
        
        if fuzzy_matches:
            best_field, similarity = max(fuzzy_matches, key=lambda x: x[1])
            return {
                'field_id': str(best_field['_id']),
                'field_name': best_field.get('name'),
                'confidence': similarity,
                'method': 'fuzzy_match'
            }
        
        # マッチなし
        return {
            'field_id': None,
            'field_name': field_text,
            'confidence': 0.0,
            'method': 'no_match'
        }
    
    def _multi_stage_crop_matching(self, crop_text: str, crops_data: List[Dict]) -> Dict[str, any]:
        """作物の段階的照合"""
        
        # Stage 1: 完全一致
        for crop in crops_data:
            if crop.get('name') == crop_text:
                return {
                    'crop_id': str(crop['_id']),
                    'crop_name': crop.get('name'),
                    'confidence': 1.0,
                    'method': 'exact_match'
                }
            
            # 品種名での照合
            varieties = crop.get('varieties', [])
            for variety in varieties:
                if variety.get('name') == crop_text:
                    return {
                        'crop_id': str(crop['_id']),
                        'crop_name': crop.get('name'),
                        'variety': variety.get('name'),
                        'confidence': 1.0,
                        'method': 'variety_match'
                    }
        
        # Stage 2: 部分一致
        partial_matches = []
        for crop in crops_data:
            crop_name = crop.get('name', '')
            
            if crop_text in crop_name or crop_name in crop_text:
                score = max(
                    len(crop_text) / len(crop_name) if crop_name else 0,
                    len(crop_name) / len(crop_text) if crop_text else 0
                )
                partial_matches.append((crop, score))
        
        if partial_matches:
            best_crop, score = max(partial_matches, key=lambda x: x[1])
            return {
                'crop_id': str(best_crop['_id']),
                'crop_name': best_crop.get('name'),
                'confidence': min(score, 0.8),
                'method': 'partial_match'
            }
        
        # Stage 3: あいまい一致
        fuzzy_matches = []
        for crop in crops_data:
            crop_name = crop.get('name', '')
            if crop_name:
                similarity = SequenceMatcher(None, crop_text, crop_name).ratio() 
                if similarity > 0.6:
                    fuzzy_matches.append((crop, similarity))
        
        if fuzzy_matches:
            best_crop, similarity = max(fuzzy_matches, key=lambda x: x[1])
            return {
                'crop_id': str(best_crop['_id']),
                'crop_name': best_crop.get('name'),
                'confidence': similarity,
                'method': 'fuzzy_match'
            }
        
        # マッチなし
        return {
            'crop_id': None,
            'crop_name': crop_text,
            'confidence': 0.0,
            'method': 'no_match'
        }
    
    def _multi_stage_material_matching(self, material_text: str, materials_data: List[Dict]) -> Dict[str, any]:
        """資材の段階的照合"""
        
        # Stage 1: 完全一致
        for material in materials_data:
            if material.get('name') == material_text:
                return {
                    'material_id': str(material['_id']),
                    'material_name': material.get('name'),
                    'confidence': 1.0,
                    'method': 'exact_match'
                }
            
            # エイリアス(別名)での照合
            aliases = material.get('aliases', [])
            if material_text in aliases:
                return {
                    'material_id': str(material['_id']),
                    'material_name': material.get('name'),
                    'confidence': 1.0,
                    'method': 'alias_match'
                }
        
        # Stage 2: 部分一致
        partial_matches = []
        for material in materials_data:
            material_name = material.get('name', '')
            
            if material_text in material_name or material_name in material_text:
                score = max(
                    len(material_text) / len(material_name) if material_name else 0,
                    len(material_name) / len(material_text) if material_text else 0
                )
                partial_matches.append((material, score))
        
        if partial_matches:
            best_material, score = max(partial_matches, key=lambda x: x[1])
            return {
                'material_id': str(best_material['_id']),
                'material_name': best_material.get('name'),
                'confidence': min(score, 0.8),
                'method': 'partial_match'
            }
        
        # Stage 3: あいまい一致
        fuzzy_matches = []
        for material in materials_data:
            material_name = material.get('name', '')
            if material_name:
                similarity = SequenceMatcher(None, material_text, material_name).ratio()
                if similarity > 0.6:
                    fuzzy_matches.append((material, similarity))
        
        if fuzzy_matches:
            best_material, similarity = max(fuzzy_matches, key=lambda x: x[1])
            return {
                'material_id': str(best_material['_id']),
                'material_name': best_material.get('name'),
                'confidence': similarity,
                'method': 'fuzzy_match'
            }
        
        # マッチなし
        return {
            'material_id': None,
            'material_name': material_text,
            'confidence': 0.0,
            'method': 'no_match'
        }
    
    def get_cache_stats(self) -> Dict[str, any]:
        """キャッシュ統計情報を取得"""
        import time
        return {
            'fields_cached': len(self.fields_cache) if self.fields_cache else 0,
            'crops_cached': len(self.crops_cache) if self.crops_cache else 0,
            'materials_cached': len(self.materials_cache) if self.materials_cache else 0,
            'cache_age_seconds': time.time() - self.last_cache_time if self.last_cache_time else 0,
            'cache_timeout': self.cache_timeout
        }