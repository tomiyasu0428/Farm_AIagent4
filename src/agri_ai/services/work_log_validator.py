"""
作業記録検証サービス

抽出された情報をマスターデータと照合し、検証結果を提供
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..agents.models.work_log_extraction import ExtractedWorkInfo, WorkLogValidationResult
from ..services.master_data_resolver import MasterDataResolver
from ..dependencies.database import DatabaseConnection

logger = logging.getLogger(__name__)


class WorkLogValidator:
    """作業記録検証クラス"""
    
    def __init__(self, db_connection: DatabaseConnection = None):
        self.db_connection = db_connection or DatabaseConnection()
        self.master_resolver = MasterDataResolver(self.db_connection)
    
    async def validate_work_log(self, extracted_info: ExtractedWorkInfo) -> WorkLogValidationResult:
        """
        抽出された作業記録をマスターデータと照合・検証
        
        Args:
            extracted_info: 抽出された作業情報
            
        Returns:
            WorkLogValidationResult: 検証結果
        """
        try:
            validation_result = WorkLogValidationResult(
                is_valid=True,
                field_validation={},
                crop_validation={},
                material_validation=[],
                missing_info=[],
                suggestions=[]
            )
            
            # 1. 圃場名の検証
            if extracted_info.field_name:
                field_result = await self._validate_field_name(extracted_info.field_name)
                validation_result.field_validation = field_result
                
                if not field_result.get("is_valid", False):
                    validation_result.is_valid = False
            else:
                validation_result.missing_info.append("圃場名")
                validation_result.suggestions.append("どちらの圃場での作業でしょうか？")
            
            # 2. 作物名の検証
            if extracted_info.crop_name:
                crop_result = await self._validate_crop_name(extracted_info.crop_name)
                validation_result.crop_validation = crop_result
                
                if not crop_result.get("is_valid", False):
                    validation_result.is_valid = False
            else:
                # 作物名は必須ではないが、あると良い
                validation_result.suggestions.append("どの作物に対する作業でしょうか？")
            
            # 3. 資材の検証
            if extracted_info.materials:
                for material_name in extracted_info.materials:
                    material_result = await self._validate_material_name(material_name)
                    validation_result.material_validation.append(material_result)
                    
                    if not material_result.get("is_valid", False):
                        validation_result.is_valid = False
            
            # 4. 必須情報のチェック
            self._check_required_fields(extracted_info, validation_result)
            
            # 5. 論理的整合性のチェック
            self._check_logical_consistency(extracted_info, validation_result)
            
            logger.info(f"作業記録検証完了: valid={validation_result.is_valid}")
            return validation_result
            
        except Exception as e:
            logger.error(f"作業記録検証エラー: {e}")
            # エラー時は検証失敗として扱う
            return WorkLogValidationResult(
                is_valid=False,
                field_validation={"error": str(e)},
                crop_validation={},
                material_validation=[],
                missing_info=["検証処理でエラーが発生"],
                suggestions=["再度お試しいただくか、より詳細な情報を入力してください"]
            )
    
    async def _validate_field_name(self, field_name: str) -> Dict[str, Any]:
        """
        圃場名の検証
        
        Args:
            field_name: 圃場名
            
        Returns:
            Dict: 検証結果
        """
        try:
            # MasterDataResolverを使用して圃場データを解決
            field_data = await self.master_resolver.resolve_field_data(field_name)
            
            if field_data.get("field_id"):
                return {
                    "is_valid": True,
                    "matched_field": {
                        "field_id": field_data["field_id"],
                        "field_name": field_data["field_name"],
                        "confidence": field_data.get("confidence", 0.0),
                        "method": field_data.get("method", "unknown")
                    },
                    "message": f"圃場「{field_data['field_name']}」が見つかりました"
                }
            else:
                # 候補があるかチェック
                candidates = await self._find_field_candidates(field_name)
                
                return {
                    "is_valid": False,
                    "input_field": field_name,
                    "candidates": candidates,
                    "message": f"圃場「{field_name}」が見つかりません" + 
                              (f"。似た名前の圃場: {', '.join([c['name'] for c in candidates[:3]])}" if candidates else "")
                }
                
        except Exception as e:
            logger.error(f"圃場名検証エラー: {e}")
            return {
                "is_valid": False,
                "error": str(e),
                "message": "圃場名の検証中にエラーが発生しました"
            }
    
    async def _validate_crop_name(self, crop_name: str) -> Dict[str, Any]:
        """
        作物名の検証
        
        Args:
            crop_name: 作物名
            
        Returns:
            Dict: 検証結果
        """
        try:
            # MasterDataResolverを使用して作物データを解決
            crop_data = await self.master_resolver.resolve_crop_data(crop_name)
            
            if crop_data.get("crop_id"):
                return {
                    "is_valid": True,
                    "matched_crop": {
                        "crop_id": crop_data["crop_id"],
                        "crop_name": crop_data["crop_name"],
                        "confidence": crop_data.get("confidence", 0.0),
                        "method": crop_data.get("method", "unknown")
                    },
                    "message": f"作物「{crop_data['crop_name']}」が見つかりました"
                }
            else:
                # 候補があるかチェック
                candidates = await self._find_crop_candidates(crop_name)
                
                return {
                    "is_valid": False,
                    "input_crop": crop_name,
                    "candidates": candidates,
                    "message": f"作物「{crop_name}」が見つかりません" + 
                              (f"。似た名前の作物: {', '.join([c['name'] for c in candidates[:3]])}" if candidates else "")
                }
                
        except Exception as e:
            logger.error(f"作物名検証エラー: {e}")
            return {
                "is_valid": False,
                "error": str(e),
                "message": "作物名の検証中にエラーが発生しました"
            }
    
    async def _validate_material_name(self, material_name: str) -> Dict[str, Any]:
        """
        資材名の検証
        
        Args:
            material_name: 資材名
            
        Returns:
            Dict: 検証結果
        """
        try:
            # MasterDataResolverを使用して資材データを解決
            material_data = await self.master_resolver.resolve_material_data(material_name)
            
            if material_data.get("material_id"):
                return {
                    "is_valid": True,
                    "material_name": material_name,
                    "matched_material": {
                        "material_id": material_data["material_id"],
                        "material_name": material_data["material_name"],
                        "confidence": material_data.get("confidence", 0.0),
                        "method": material_data.get("method", "unknown")
                    },
                    "message": f"資材「{material_data['material_name']}」が見つかりました"
                }
            else:
                # 候補があるかチェック
                candidates = await self._find_material_candidates(material_name)
                
                return {
                    "is_valid": False,
                    "input_material": material_name,
                    "candidates": candidates,
                    "message": f"資材「{material_name}」が見つかりません" + 
                              (f"。似た名前の資材: {', '.join([c['name'] for c in candidates[:3]])}" if candidates else "")
                }
                
        except Exception as e:
            logger.error(f"資材名検証エラー: {e}")
            return {
                "is_valid": False,
                "error": str(e),
                "message": "資材名の検証中にエラーが発生しました"
            }
    
    async def _find_field_candidates(self, field_name: str) -> List[Dict[str, Any]]:
        """圃場名の候補を検索"""
        try:
            # 部分一致で候補を検索
            client = await self.db_connection.get_client()
            fields_collection = await client.get_collection("fields")
            
            # 正規表現での部分一致検索
            cursor = fields_collection.find({
                "$or": [
                    {"name": {"$regex": field_name, "$options": "i"}},
                    {"field_code": {"$regex": field_name, "$options": "i"}}
                ]
            }).limit(5)
            
            candidates = []
            async for field in cursor:
                candidates.append({
                    "field_id": str(field["_id"]),
                    "name": field["name"],
                    "field_code": field.get("field_code", "")
                })
            
            return candidates
            
        except Exception as e:
            logger.error(f"圃場候補検索エラー: {e}")
            return []
    
    async def _find_crop_candidates(self, crop_name: str) -> List[Dict[str, Any]]:
        """作物名の候補を検索"""
        try:
            client = await self.db_connection.get_client()
            crops_collection = await client.get_collection("crops")
            
            cursor = crops_collection.find({
                "name": {"$regex": crop_name, "$options": "i"}
            }).limit(5)
            
            candidates = []
            async for crop in cursor:
                candidates.append({
                    "crop_id": str(crop["_id"]),
                    "name": crop["name"],
                    "category": crop.get("category", "")
                })
            
            return candidates
            
        except Exception as e:
            logger.error(f"作物候補検索エラー: {e}")
            return []
    
    async def _find_material_candidates(self, material_name: str) -> List[Dict[str, Any]]:
        """資材名の候補を検索"""
        try:
            client = await self.db_connection.get_client()
            materials_collection = await client.get_collection("materials")
            
            cursor = materials_collection.find({
                "$or": [
                    {"name": {"$regex": material_name, "$options": "i"}},
                    {"product_name": {"$regex": material_name, "$options": "i"}}
                ]
            }).limit(5)
            
            candidates = []
            async for material in cursor:
                candidates.append({
                    "material_id": str(material["_id"]),
                    "name": material["name"],
                    "product_name": material.get("product_name", ""),
                    "category": material.get("category", "")
                })
            
            return candidates
            
        except Exception as e:
            logger.error(f"資材候補検索エラー: {e}")
            return []
    
    def _check_required_fields(self, extracted_info: ExtractedWorkInfo, validation_result: WorkLogValidationResult):
        """必須フィールドのチェック"""
        
        # 作業日が必須
        if not extracted_info.work_date:
            validation_result.missing_info.append("作業日")
            validation_result.suggestions.append("いつの作業でしょうか？（今日、昨日、具体的な日付など）")
        
        # 作業分類が必須
        if not extracted_info.work_category:
            validation_result.missing_info.append("作業分類")
            validation_result.suggestions.append("どのような作業でしょうか？（防除、施肥、収穫、栽培、管理など）")
    
    def _check_logical_consistency(self, extracted_info: ExtractedWorkInfo, validation_result: WorkLogValidationResult):
        """論理的整合性のチェック"""
        
        # 防除作業なのに資材がない場合
        if extracted_info.work_category == "防除" and not extracted_info.materials:
            validation_result.suggestions.append("防除作業の場合、使用した農薬を教えてください")
        
        # 資材があるのに数量・単位がない場合
        if extracted_info.materials and not extracted_info.quantity:
            validation_result.suggestions.append("資材の使用量を教えてください")
        
        # 数量があるのに単位がない場合
        if extracted_info.quantity and not extracted_info.unit:
            validation_result.suggestions.append("使用量の単位を教えてください（L、kg、袋など）")