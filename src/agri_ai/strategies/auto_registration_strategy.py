"""
自動登録戦略

高信頼度データの自動登録を担当
明確で信頼性の高いデータを即座に登録する戦略
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any

from .registration_strategy import RegistrationStrategy
from ..agents.models.work_log_extraction import ExtractedWorkInfo, WorkLogValidationResult
from ..dependencies.database import DatabaseConnection

logger = logging.getLogger(__name__)


class AutoRegistrationStrategy(RegistrationStrategy):
    """
    自動登録戦略
    
    高信頼度かつ検証済みデータを自動的にデータベースに登録
    """
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection
    
    @property
    def strategy_name(self) -> str:
        return "自動登録戦略"
    
    def can_handle(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult
    ) -> bool:
        """
        自動登録可能かどうかを判定
        
        条件:
        - 信頼度が0.8以上
        - 検証が成功している
        - 必須情報が揃っている
        """
        confidence = extracted_info.confidence_score or 0.0
        
        # 基本条件チェック
        if not validation_result.is_valid or confidence < 0.8:
            return False
        
        # 必須情報の存在チェック
        has_essential_info = (
            extracted_info.work_category and
            (extracted_info.field_name or validation_result.field_validation.get('matched_field'))
        )
        
        # 不足情報が少ない
        missing_count = len(validation_result.missing_info)
        
        return has_essential_info and missing_count <= 1
    
    async def execute(
        self, 
        extracted_info: ExtractedWorkInfo,
        validation_result: WorkLogValidationResult,
        message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        高信頼度データの自動登録実行
        """
        try:
            log_record = await self._save_work_log(
                extracted_info, validation_result, message, user_id
            )
            
            logger.info(f"自動登録完了: {log_record['log_id']}, 信頼度: {extracted_info.confidence_score:.2f}")
            
            return {
                'success': True,
                'log_id': log_record['log_id'],
                'message': f"作業記録を自動登録しました（記録ID: {log_record['log_id']}）",
                'confidence_score': extracted_info.confidence_score,
                'extracted_data': log_record['extracted_data'],
                'requires_confirmation': False,
                'registration_type': 'auto',
                'strategy_used': self.strategy_name
            }
            
        except Exception as e:
            logger.error(f"自動登録エラー: {e}")
            raise
    
    async def _save_work_log(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult, 
        original_message: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        作業記録をデータベースに保存
        """
        log_id = f"LOG-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        work_date = self._parse_work_date(extracted_info.work_date)
        
        # 検証済みデータの構築
        extracted_data = {
            'extraction_version': '2.0',
            'confidence_score': extracted_info.confidence_score,
            'extraction_method': 'llm_function_calling',
            'strategy_used': self.strategy_name
        }
        
        # 検証済み圃場データ
        if validation_result.field_validation.get('matched_field'):
            field_match = validation_result.field_validation['matched_field']
            extracted_data.update({
                'field_id': field_match['field_id'],
                'field_name': field_match['field_name'],
                'field_confidence': field_match.get('confidence', 0.0)
            })
        
        # 検証済み作物データ
        if validation_result.crop_validation.get('matched_crop'):
            crop_match = validation_result.crop_validation['matched_crop']
            extracted_data.update({
                'crop_id': crop_match['crop_id'],
                'crop_name': crop_match['crop_name'],
                'crop_confidence': crop_match.get('confidence', 0.0)
            })
        
        # 検証済み資材データ
        validated_materials = [
            m for m in validation_result.material_validation 
            if m.get('matched_material')
        ]
        
        if validated_materials:
            material_ids = []
            material_names = []
            
            for material_validation in validated_materials:
                material_match = material_validation['matched_material']
                material_ids.append(material_match['material_id'])
                material_names.append(material_match['material_name'])
            
            extracted_data.update({
                'material_ids': material_ids,
                'material_names': material_names
            })
        
        # 数量・単位情報
        if extracted_info.quantity is not None:
            extracted_data['quantity'] = extracted_info.quantity
        if extracted_info.unit:
            extracted_data['unit'] = extracted_info.unit
        if extracted_info.work_count:
            extracted_data['work_count'] = extracted_info.work_count
        if extracted_info.notes:
            extracted_data['notes'] = extracted_info.notes
        
        # ログレコード作成
        log_record = {
            'log_id': log_id,
            'user_id': user_id,
            'work_date': work_date,
            'original_message': original_message,
            'extracted_data': extracted_data,
            'category': extracted_info.work_category or 'その他',
            'tags': [extracted_info.work_category] if extracted_info.work_category else ['その他'],
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'status': 'confirmed',
            'version': '2.0'
        }
        
        # データベース保存
        client = await self.db_connection.get_client()
        work_logs_collection = await client.get_collection('work_logs')
        await work_logs_collection.insert_one(log_record)
        
        return log_record
    
    def _parse_work_date(self, work_date_str: str) -> datetime:
        """作業日の解釈"""
        if not work_date_str:
            return datetime.now()
        
        today = datetime.now()
        
        # 相対日付パターン
        if work_date_str == '今日':
            return today
        elif work_date_str == '昨日':
            return today - timedelta(days=1)
        elif work_date_str == '一昨日':
            return today - timedelta(days=2)
        elif '日前' in work_date_str:
            import re
            days_match = re.search(r'(\d+)日前', work_date_str)
            if days_match:
                days = int(days_match.group(1))
                return today - timedelta(days=days)
        
        # デフォルトは今日
        return today