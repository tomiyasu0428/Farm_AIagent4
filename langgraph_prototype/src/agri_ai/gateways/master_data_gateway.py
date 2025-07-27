"""
マスターデータゲートウェイ

マスターデータベースとの通信を専門的に処理
I/Oとドメインロジックを分離し、テスタビリティを向上
"""

import logging
from typing import Dict, Any, List, Optional

from ..dependencies.database import DatabaseConnection
from ..utils.retry_decorator import database_retry

logger = logging.getLogger(__name__)


class MasterDataGateway:
    """
    マスターデータアクセス専用ゲートウェイクラス
    
    責務: 外部データベースとの通信のみ
    - MongoDB操作
    - エラーハンドリング
    - リトライ処理
    - データ形式の正規化
    """
    
    def __init__(self, db_connection: DatabaseConnection = None):
        self.db_connection = db_connection or DatabaseConnection()
    
    @database_retry
    async def get_all_fields(self) -> List[Dict[str, Any]]:
        """
        全圃場データを取得
        
        Returns:
            List[Dict]: 圃場データリスト
        """
        try:
            client = await self.db_connection.get_client()
            fields_collection = await client.get_collection('fields')
            
            # アクティブな圃場のみ取得
            cursor = fields_collection.find({'status': {'$ne': 'deleted'}})
            fields = await cursor.to_list(length=None)
            
            # ObjectIdを文字列に変換
            for field in fields:
                field['_id'] = str(field.get('_id'))
            
            logger.debug(f"圃場データ取得完了: {len(fields)}件")
            return fields
            
        except Exception as e:
            logger.error(f"圃場データ取得エラー: {e}")
            raise
    
    @database_retry
    async def get_all_crops(self) -> List[Dict[str, Any]]:
        """
        全作物データを取得
        
        Returns:
            List[Dict]: 作物データリスト
        """
        try:
            client = await self.db_connection.get_client()
            crops_collection = await client.get_collection('crops')
            
            # アクティブな作物のみ取得
            cursor = crops_collection.find({'status': {'$ne': 'deleted'}})
            crops = await cursor.to_list(length=None)
            
            # ObjectIdを文字列に変換
            for crop in crops:
                crop['_id'] = str(crop.get('_id'))
            
            logger.debug(f"作物データ取得完了: {len(crops)}件")
            return crops
            
        except Exception as e:
            logger.error(f"作物データ取得エラー: {e}")
            raise
    
    @database_retry
    async def get_all_materials(self) -> List[Dict[str, Any]]:
        """
        全資材データを取得
        
        Returns:
            List[Dict]: 資材データリスト
        """
        try:
            client = await self.db_connection.get_client()
            materials_collection = await client.get_collection('materials')
            
            # アクティブな資材のみ取得
            cursor = materials_collection.find({'status': {'$ne': 'deleted'}})
            materials = await cursor.to_list(length=None)
            
            # ObjectIdを文字列に変換
            for material in materials:
                material['_id'] = str(material.get('_id'))
            
            logger.debug(f"資材データ取得完了: {len(materials)}件")
            return materials
            
        except Exception as e:
            logger.error(f"資材データ取得エラー: {e}")
            raise
    
    @database_retry
    async def get_field_by_id(self, field_id: str) -> Optional[Dict[str, Any]]:
        """
        IDによる圃場データ取得
        
        Args:
            field_id: 圃場ID
            
        Returns:
            Optional[Dict]: 圃場データ（見つからない場合はNone）
        """
        try:
            client = await self.db_connection.get_client()
            fields_collection = await client.get_collection('fields')
            
            field = await fields_collection.find_one({'field_id': field_id})
            
            if field:
                field['_id'] = str(field.get('_id'))
            
            logger.debug(f"圃場データ個別取得: {field_id} -> {'Found' if field else 'Not Found'}")
            return field
            
        except Exception as e:
            logger.error(f"圃場データ個別取得エラー: {e}")
            raise
    
    @database_retry
    async def get_crop_by_id(self, crop_id: str) -> Optional[Dict[str, Any]]:
        """
        IDによる作物データ取得
        
        Args:
            crop_id: 作物ID
            
        Returns:
            Optional[Dict]: 作物データ（見つからない場合はNone）
        """
        try:
            client = await self.db_connection.get_client()
            crops_collection = await client.get_collection('crops')
            
            crop = await crops_collection.find_one({'crop_id': crop_id})
            
            if crop:
                crop['_id'] = str(crop.get('_id'))
            
            logger.debug(f"作物データ個別取得: {crop_id} -> {'Found' if crop else 'Not Found'}")
            return crop
            
        except Exception as e:
            logger.error(f"作物データ個別取得エラー: {e}")
            raise
    
    @database_retry
    async def get_material_by_id(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        IDによる資材データ取得
        
        Args:
            material_id: 資材ID
            
        Returns:
            Optional[Dict]: 資材データ（見つからない場合はNone）
        """
        try:
            client = await self.db_connection.get_client()
            materials_collection = await client.get_collection('materials')
            
            material = await materials_collection.find_one({'material_id': material_id})
            
            if material:
                material['_id'] = str(material.get('_id'))
            
            logger.debug(f"資材データ個別取得: {material_id} -> {'Found' if material else 'Not Found'}")
            return material
            
        except Exception as e:
            logger.error(f"資材データ個別取得エラー: {e}")
            raise
    
    @database_retry
    async def search_fields_by_name(self, field_name: str) -> List[Dict[str, Any]]:
        """
        名前による圃場検索
        
        Args:
            field_name: 検索する圃場名
            
        Returns:
            List[Dict]: マッチした圃場データリスト
        """
        try:
            client = await self.db_connection.get_client()
            fields_collection = await client.get_collection('fields')
            
            # 部分一致検索
            search_pattern = {'$regex': field_name, '$options': 'i'}
            query = {
                '$and': [
                    {'status': {'$ne': 'deleted'}},
                    {'$or': [
                        {'field_name': search_pattern},
                        {'field_code': search_pattern}
                    ]}
                ]
            }
            
            cursor = fields_collection.find(query)
            fields = await cursor.to_list(length=None)
            
            # ObjectIdを文字列に変換
            for field in fields:
                field['_id'] = str(field.get('_id'))
            
            logger.debug(f"圃場名検索完了: '{field_name}' -> {len(fields)}件")
            return fields
            
        except Exception as e:
            logger.error(f"圃場名検索エラー: {e}")
            raise
    
    @database_retry
    async def search_crops_by_name(self, crop_name: str) -> List[Dict[str, Any]]:
        """
        名前による作物検索
        
        Args:
            crop_name: 検索する作物名
            
        Returns:
            List[Dict]: マッチした作物データリスト
        """
        try:
            client = await self.db_connection.get_client()
            crops_collection = await client.get_collection('crops')
            
            # 部分一致検索（作物名、学名、別名）
            search_pattern = {'$regex': crop_name, '$options': 'i'}
            query = {
                '$and': [
                    {'status': {'$ne': 'deleted'}},
                    {'$or': [
                        {'crop_name': search_pattern},
                        {'scientific_name': search_pattern},
                        {'aliases': {'$elemMatch': {'$regex': crop_name, '$options': 'i'}}}
                    ]}
                ]
            }
            
            cursor = crops_collection.find(query)
            crops = await cursor.to_list(length=None)
            
            # ObjectIdを文字列に変換
            for crop in crops:
                crop['_id'] = str(crop.get('_id'))
            
            logger.debug(f"作物名検索完了: '{crop_name}' -> {len(crops)}件")
            return crops
            
        except Exception as e:
            logger.error(f"作物名検索エラー: {e}")
            raise
    
    @database_retry
    async def search_materials_by_name(self, material_name: str) -> List[Dict[str, Any]]:
        """
        名前による資材検索
        
        Args:
            material_name: 検索する資材名
            
        Returns:
            List[Dict]: マッチした資材データリスト
        """
        try:
            client = await self.db_connection.get_client()
            materials_collection = await client.get_collection('materials')
            
            # 部分一致検索（資材名、ブランド名、有効成分）
            search_pattern = {'$regex': material_name, '$options': 'i'}
            query = {
                '$and': [
                    {'status': {'$ne': 'deleted'}},
                    {'$or': [
                        {'material_name': search_pattern},
                        {'brand_name': search_pattern},
                        {'active_ingredients': {'$elemMatch': {'$regex': material_name, '$options': 'i'}}}
                    ]}
                ]
            }
            
            cursor = materials_collection.find(query)
            materials = await cursor.to_list(length=None)
            
            # ObjectIdを文字列に変換
            for material in materials:
                material['_id'] = str(material.get('_id'))
            
            logger.debug(f"資材名検索完了: '{material_name}' -> {len(materials)}件")
            return materials
            
        except Exception as e:
            logger.error(f"資材名検索エラー: {e}")
            raise
    
    async def get_connection_info(self) -> Dict[str, str]:
        """接続情報の取得（デバッグ用）"""
        return {
            "status": "connected" if self.db_connection else "not_connected",
            "database_name": "agri_ai_db"  # 設定から取得
        }