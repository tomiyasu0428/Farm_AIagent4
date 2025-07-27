"""
作業記録バリデーションサービス (v2.0 - 責務分離版)

ExtractedWorkInfoの検証処理を担当
I/O処理とドメインロジックを分離したアーキテクチャ
"""

import logging
from typing import Dict, Any, List

from ..agents.models.work_log_extraction import ExtractedWorkInfo, WorkLogValidationResult
from ..domain.master_data_matcher import MasterDataMatcher
from ..gateways.master_data_gateway import MasterDataGateway

logger = logging.getLogger(__name__)


class WorkLogValidator:
    """
    作業記録バリデーションクラス (リファクタリング版)
    
    責務:
    - MasterDataGatewayとMatcherの統合
    - バリデーションフローの調整
    - 結果の構造化
    """
    
    def __init__(self, gateway: MasterDataGateway = None, matcher: MasterDataMatcher = None):
        # 依存性注入対応（テスト時にモック差し替え可能）
        self.gateway = gateway or MasterDataGateway()
        self.matcher = matcher or MasterDataMatcher()
    
    async def validate_work_log(self, extracted_info: ExtractedWorkInfo) -> WorkLogValidationResult:
        """
        作業記録の検証 (I/O分離版)
        
        Args:
            extracted_info: 抽出された作業情報
            
        Returns:
            WorkLogValidationResult: 検証結果
        """
        try:
            # Step 1: 必要なマスターデータを並列取得 (Gateway経由)
            master_data = await self._fetch_master_data_parallel()
            
            # Step 2: ドメインロジックによるマッチング (Matcher経由)
            validation_results = await self._execute_matching_logic(extracted_info, master_data)
            
            # Step 3: 結果の統合と構造化
            return self._build_validation_result(extracted_info, validation_results)
            
        except Exception as e:
            logger.error(f"作業記録検証エラー: {e}")
            return self._create_error_result(str(e))
    
    async def _fetch_master_data_parallel(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        マスターデータの並列取得
        """
        # Gateway経由で並列取得
        master_fields = await self.gateway.get_all_fields()
        master_crops = await self.gateway.get_all_crops()
        master_materials = await self.gateway.get_all_materials()
        
        return {
            'fields': master_fields,
            'crops': master_crops,
            'materials': master_materials
        }
    
    async def _execute_matching_logic(
        self, 
        extracted_info: ExtractedWorkInfo, 
        master_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        ドメインロジックによるマッチング実行
        """
        validation_results = {}
        
        # 圃場データマッチング
        if extracted_info.field_name:
            validation_results['field_validation'] = self.matcher.match_field_data(
                extracted_info.field_name, master_data['fields']
            )
        else:
            validation_results['field_validation'] = self.matcher._create_no_match_result('field')
        
        # 作物データマッチング
        if extracted_info.crop_name:
            validation_results['crop_validation'] = self.matcher.match_crop_data(
                extracted_info.crop_name, master_data['crops']
            )
        else:
            validation_results['crop_validation'] = self.matcher._create_no_match_result('crop')
        
        # 資材データマッチング
        if extracted_info.materials:
            validation_results['material_validation'] = self.matcher.match_material_data(
                extracted_info.materials, master_data['materials']
            )
        else:
            validation_results['material_validation'] = []
        
        return validation_results
    
    def _build_validation_result(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_results: Dict[str, Any]
    ) -> WorkLogValidationResult:
        """
        検証結果の構造化
        """
        # 基本的な有効性判定
        is_valid = self._assess_overall_validity(validation_results)
        
        # 不足情報の特定
        missing_info = self._identify_missing_information(extracted_info, validation_results)
        
        # 提案情報の生成
        suggestions = self._generate_suggestions(validation_results)
        
        # 品質スコア計算
        quality_score = self._calculate_quality_score(validation_results)
        
        return WorkLogValidationResult(
            is_valid=is_valid,
            field_validation=validation_results.get('field_validation', {}),
            crop_validation=validation_results.get('crop_validation', {}),
            material_validation=validation_results.get('material_validation', []),
            missing_info=missing_info,
            suggestions=suggestions,
            quality_score=quality_score,
            validation_method='matcher_based_v2'
        )
    
    def _assess_overall_validity(self, validation_results: Dict[str, Any]) -> bool:
        """
        全体的な有効性の評価
        """
        # 少なくとも圃場または作業分類が特定できている場合は有効とする
        field_valid = validation_results.get('field_validation', {}).get('matched_field') is not None
        crop_valid = validation_results.get('crop_validation', {}).get('matched_crop') is not None
        material_valid = len(validation_results.get('material_validation', [])) > 0
        
        # 圃場情報があることを最低条件とする
        return field_valid or (crop_valid and material_valid)
    
    def _identify_missing_information(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_results: Dict[str, Any]
    ) -> List[str]:
        """
        不足情報の特定
        """
        missing = []
        
        # 必須フィールドのチェック
        if not extracted_info.work_date:
            missing.append('work_date')
        
        if not validation_results.get('field_validation', {}).get('matched_field'):
            missing.append('field_name')
        
        if not extracted_info.work_category:
            missing.append('work_category')
        
        # 作業分類に応じた必須情報
        if extracted_info.work_category in ['防除', '施肥']:
            if not validation_results.get('material_validation'):
                missing.append('materials')
        
        if extracted_info.work_category == '収穫':
            if not extracted_info.quantity:
                missing.append('quantity')
        
        return missing
    
    def _generate_suggestions(self, validation_results: Dict[str, Any]) -> List[str]:
        """
        提案情報の生成
        """
        suggestions = []
        
        # 曖昧なマッチングの場合の提案
        field_validation = validation_results.get('field_validation', {})
        if field_validation.get('ambiguity_detected'):
            candidates = field_validation.get('candidates', [])
            if len(candidates) > 1:
                candidate_names = [c.get('field_name', '') for c in candidates[:2]]
                suggestions.append(f"圃場名の候補: {', '.join(candidate_names)}")
        
        crop_validation = validation_results.get('crop_validation', {})
        if crop_validation.get('ambiguity_detected'):
            candidates = crop_validation.get('candidates', [])
            if len(candidates) > 1:
                candidate_names = [c.get('crop_name', '') for c in candidates[:2]]
                suggestions.append(f"作物名の候補: {', '.join(candidate_names)}")
        
        # 部分マッチの場合の提案
        material_validations = validation_results.get('material_validation', [])
        for material_val in material_validations:
            if material_val.get('matched_material', {}).get('match_method') == 'partial_match':
                material_name = material_val.get('matched_material', {}).get('material_name', '')
                suggestions.append(f"資材名の確認: {material_name}")
        
        return suggestions
    
    def _calculate_quality_score(self, validation_results: Dict[str, Any]) -> float:
        """
        品質スコアの計算
        """
        scores = []
        
        # 圃場マッチング品質
        field_match = validation_results.get('field_validation', {}).get('matched_field')
        if field_match:
            scores.append(field_match.get('confidence', 0.0))
        
        # 作物マッチング品質
        crop_match = validation_results.get('crop_validation', {}).get('matched_crop')
        if crop_match:
            scores.append(crop_match.get('confidence', 0.0))
        
        # 資材マッチング品質（平均）
        material_validations = validation_results.get('material_validation', [])
        if material_validations:
            material_scores = []
            for material_val in material_validations:
                material_match = material_val.get('matched_material')
                if material_match:
                    material_scores.append(material_match.get('confidence', 0.0))
            if material_scores:
                scores.append(sum(material_scores) / len(material_scores))
        
        # 全体品質スコア
        return sum(scores) / len(scores) if scores else 0.0
    
    def _create_error_result(self, error_message: str) -> WorkLogValidationResult:
        """
        エラー時の結果作成
        """
        return WorkLogValidationResult(
            is_valid=False,
            field_validation={},
            crop_validation={},
            material_validation=[],
            missing_info=['validation_error'],
            suggestions=[f"検証エラー: {error_message}"],
            quality_score=0.0,
            validation_method='error'
        )