"""
作業記録確認サービス

曖昧性解決とユーザー確認フローの管理
"""

import logging
from typing import Dict, List, Any, Optional
from ..agents.models.work_log_extraction import (
    ExtractedWorkInfo, 
    WorkLogValidationResult, 
    UserConfirmationData
)

logger = logging.getLogger(__name__)


class WorkLogConfirmationService:
    """作業記録確認サービス"""
    
    def __init__(self):
        pass
    
    def generate_confirmation_message(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult
    ) -> UserConfirmationData:
        """
        ユーザー確認用のメッセージとオプションを生成
        
        Args:
            extracted_info: 抽出された作業情報
            validation_result: 検証結果
            
        Returns:
            UserConfirmationData: 確認用データ
        """
        try:
            if validation_result.is_valid:
                # 全て検証OK → 最終確認
                return self._generate_final_confirmation(extracted_info, validation_result)
            else:
                # 検証に問題あり → 曖昧性解決
                return self._generate_ambiguity_resolution(extracted_info, validation_result)
                
        except Exception as e:
            logger.error(f"確認メッセージ生成エラー: {e}")
            return self._generate_error_confirmation(str(e))
    
    def _generate_final_confirmation(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult
    ) -> UserConfirmationData:
        """
        最終確認メッセージの生成
        
        Args:
            extracted_info: 抽出された作業情報
            validation_result: 検証結果
            
        Returns:
            UserConfirmationData: 最終確認用データ
        """
        # 確認メッセージの構築
        confirmation_lines = ["📝 以下の内容で作業記録を登録しますか？", ""]
        
        # 作業日
        if extracted_info.work_date:
            work_date_display = self._format_work_date(extracted_info.work_date)
            confirmation_lines.append(f"📅 作業日: {work_date_display}")
        
        # 圃場
        if validation_result.field_validation.get("matched_field"):
            field_info = validation_result.field_validation["matched_field"]
            confirmation_lines.append(f"🏠 圃場: {field_info['field_name']}")
        
        # 作物
        if validation_result.crop_validation.get("matched_crop"):
            crop_info = validation_result.crop_validation["matched_crop"]
            confirmation_lines.append(f"🌱 作物: {crop_info['crop_name']}")
        
        # 作業分類
        if extracted_info.work_category:
            category_emoji = self._get_category_emoji(extracted_info.work_category)
            confirmation_lines.append(f"{category_emoji} 作業: {extracted_info.work_category}")
        
        # 資材
        if validation_result.material_validation:
            valid_materials = [
                m["matched_material"]["material_name"] 
                for m in validation_result.material_validation 
                if m.get("matched_material")
            ]
            if valid_materials:
                materials_text = ", ".join(valid_materials)
                confirmation_lines.append(f"🧪 資材: {materials_text}")
        
        # 使用量
        if extracted_info.quantity and extracted_info.unit:
            confirmation_lines.append(f"📊 使用量: {extracted_info.quantity}{extracted_info.unit}")
        
        # メモ
        if extracted_info.notes:
            confirmation_lines.append(f"📝 メモ: {extracted_info.notes}")
        
        confirmation_lines.append("")
        
        # 信頼度表示
        if extracted_info.confidence_score:
            confidence_percent = int(extracted_info.confidence_score * 100)
            confirmation_lines.append(f"🎯 抽出精度: {confidence_percent}%")
        
        confirmation_message = "\n".join(confirmation_lines)
        
        # オプション
        options = [
            {
                "type": "button",
                "action": "confirm_registration",
                "label": "✅ 登録する",
                "data": {
                    "extracted_info": extracted_info.dict(),
                    "validation_result": validation_result.dict()
                }
            },
            {
                "type": "button", 
                "action": "modify_info",
                "label": "✏️ 修正する",
                "data": {}
            },
            {
                "type": "button",
                "action": "cancel",
                "label": "❌ キャンセル",
                "data": {}
            }
        ]
        
        return UserConfirmationData(
            extracted_info=extracted_info,
            validation_result=validation_result,
            confirmation_message=confirmation_message,
            options=options
        )
    
    def _generate_ambiguity_resolution(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult
    ) -> UserConfirmationData:
        """
        曖昧性解決メッセージの生成
        
        Args:
            extracted_info: 抽出された作業情報
            validation_result: 検証結果
            
        Returns:
            UserConfirmationData: 曖昧性解決用データ
        """
        confirmation_lines = ["❓ いくつか確認したいことがあります", ""]
        options = []
        
        # 圃場名の曖昧性解決
        if not validation_result.field_validation.get("is_valid", True):
            field_validation = validation_result.field_validation
            
            if field_validation.get("candidates"):
                confirmation_lines.append("🏠 圃場名について：")
                confirmation_lines.append(f"「{field_validation.get('input_field', '')}」という圃場が見つかりませんでした。")
                confirmation_lines.append("以下のどちらかでしょうか？")
                confirmation_lines.append("")
                
                for i, candidate in enumerate(field_validation["candidates"][:3], 1):
                    confirmation_lines.append(f"{i}. {candidate['name']}")
                    options.append({
                        "type": "button",
                        "action": "select_field",
                        "label": f"{i}. {candidate['name']}",
                        "data": {
                            "field_id": candidate["field_id"],
                            "field_name": candidate["name"]
                        }
                    })
                
                confirmation_lines.append("")
        
        # 作物名の曖昧性解決
        if not validation_result.crop_validation.get("is_valid", True):
            crop_validation = validation_result.crop_validation
            
            if crop_validation.get("candidates"):
                confirmation_lines.append("🌱 作物名について：")
                confirmation_lines.append(f"「{crop_validation.get('input_crop', '')}」という作物が見つかりませんでした。")
                confirmation_lines.append("以下のどちらかでしょうか？")
                confirmation_lines.append("")
                
                for i, candidate in enumerate(crop_validation["candidates"][:3], 1):
                    confirmation_lines.append(f"{i}. {candidate['name']}")
                    options.append({
                        "type": "button",
                        "action": "select_crop",
                        "label": f"{i}. {candidate['name']}",
                        "data": {
                            "crop_id": candidate["crop_id"],
                            "crop_name": candidate["name"]
                        }
                    })
                
                confirmation_lines.append("")
        
        # 資材の曖昧性解決
        invalid_materials = [
            m for m in validation_result.material_validation 
            if not m.get("is_valid", True)
        ]
        
        if invalid_materials:
            confirmation_lines.append("🧪 資材について：")
            
            for material_validation in invalid_materials[:2]:  # 最初の2つまで
                input_material = material_validation.get("input_material", "")
                candidates = material_validation.get("candidates", [])
                
                if candidates:
                    confirmation_lines.append(f"「{input_material}」という資材が見つかりませんでした。")
                    confirmation_lines.append("以下のどちらかでしょうか？")
                    confirmation_lines.append("")
                    
                    for i, candidate in enumerate(candidates[:3], 1):
                        display_name = candidate.get("product_name") or candidate["name"]
                        confirmation_lines.append(f"{i}. {display_name}")
                        options.append({
                            "type": "button",
                            "action": "select_material",
                            "label": f"{i}. {display_name}",
                            "data": {
                                "material_id": candidate["material_id"],
                                "material_name": candidate["name"],
                                "original_input": input_material
                            }
                        })
                    
                    confirmation_lines.append("")
        
        # 不足情報の確認
        if validation_result.missing_info:
            confirmation_lines.append("ℹ️ 追加で教えてください：")
            for missing in validation_result.missing_info:
                confirmation_lines.append(f"• {missing}")
            confirmation_lines.append("")
        
        # 提案
        if validation_result.suggestions:
            confirmation_lines.append("💡 確認事項：")
            for suggestion in validation_result.suggestions:
                confirmation_lines.append(f"• {suggestion}")
            confirmation_lines.append("")
        
        # その他のオプション
        options.extend([
            {
                "type": "button",
                "action": "manual_input",
                "label": "✏️ 手動で入力",
                "data": {}
            },
            {
                "type": "button",
                "action": "skip_ambiguity",
                "label": "⏭️ そのまま登録",
                "data": {
                    "extracted_info": extracted_info.dict(),
                    "validation_result": validation_result.dict()
                }
            },
            {
                "type": "button",
                "action": "cancel",
                "label": "❌ キャンセル",
                "data": {}
            }
        ])
        
        confirmation_message = "\n".join(confirmation_lines)
        
        return UserConfirmationData(
            extracted_info=extracted_info,
            validation_result=validation_result,
            confirmation_message=confirmation_message,
            options=options
        )
    
    def _generate_error_confirmation(self, error_message: str) -> UserConfirmationData:
        """
        エラー時の確認メッセージ生成
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            UserConfirmationData: エラー用確認データ
        """
        confirmation_message = f"""
❌ 作業記録の処理中にエラーが発生しました

エラー詳細: {error_message}

お手数ですが、以下をお試しください：
• より詳細な情報を含めて再入力
• 簡潔な表現で再入力
• 手動での入力

ご不明な点がございましたら、サポートまでお問い合わせください。
"""
        
        options = [
            {
                "type": "button",
                "action": "retry",
                "label": "🔄 再試行",
                "data": {}
            },
            {
                "type": "button",
                "action": "manual_input",
                "label": "✏️ 手動入力",
                "data": {}
            },
            {
                "type": "button",
                "action": "contact_support",
                "label": "🆘 サポート",
                "data": {}
            }
        ]
        
        return UserConfirmationData(
            extracted_info=ExtractedWorkInfo(),
            validation_result=WorkLogValidationResult(
                is_valid=False,
                field_validation={},
                crop_validation={},
                material_validation=[],
                missing_info=[],
                suggestions=[]
            ),
            confirmation_message=confirmation_message,
            options=options
        )
    
    def _format_work_date(self, work_date: str) -> str:
        """作業日の表示形式を整形"""
        if work_date in ["今日", "昨日", "一昨日"]:
            return work_date
        elif "日前" in work_date:
            return work_date
        else:
            # 具体的な日付の場合はそのまま
            return work_date
    
    def _get_category_emoji(self, category: str) -> str:
        """作業分類に対応する絵文字を取得"""
        emoji_map = {
            "防除": "🛡️",
            "施肥": "🌱",
            "栽培": "🌿",
            "収穫": "🌾",
            "管理": "🔧",
            "その他": "📋"
        }
        return emoji_map.get(category, "📋")