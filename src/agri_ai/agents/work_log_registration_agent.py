"""
WorkLogRegistrationAgent: 作業記録登録専門エージェント (v3.0 - Strategy Pattern版)

自然言語の作業報告を受け取り、高精度な情報抽出とマスターデータ検証を経て、
戦略パターンによる最適な登録フローでデータベースに保存する。

v3.0の新機能:
- Strategy Patternによる責務分離
- 戦略の動的選択と実行
- テスタビリティとメンテナンス性の向上
- 拡張可能なアーキテクチャ
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from ..dependencies.database import DatabaseConnection
from ..providers.service_provider import IServiceProvider, ServiceProvider
from ..agents.models.work_log_extraction import (
    ExtractedWorkInfo, 
    WorkLogValidationResult,
    UserConfirmationData
)
from ..strategies.strategy_factory import RegistrationStrategyFactory

logger = logging.getLogger(__name__)


class WorkLogRegistrationAgent:
    """作業記録登録専門エージェント (v3.0 Strategy Pattern版)"""
    
    def __init__(self, service_provider: Optional[IServiceProvider] = None, db_connection: DatabaseConnection = None):
        # 依存性注入対応
        self.service_provider = service_provider or ServiceProvider(db_connection)
        self.db_connection = db_connection or DatabaseConnection()
        
        # 戦略ファクトリーの初期化
        self.strategy_factory = RegistrationStrategyFactory(
            self.service_provider, self.db_connection
        )
        
        # 戦略コンテキストの作成
        self.strategy_context = self.strategy_factory.create_strategy_context()
    
    

    async def register_work_log(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        作業記録を登録するメイン処理 (v2.0 高度化版)
        
        Args:
            message: ユーザーの自然言語報告
            user_id: ユーザーID
            
        Returns:
            登録結果または確認フローの辞書
        """
        try:
            # v2.0: 高精度情報抽出フロー
            return await self._enhanced_registration_flow(message, user_id)
            
        except Exception as e:
            logger.error(f"作業記録登録エラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '作業記録の登録中にエラーが発生しました。',
                'requires_confirmation': False
            }
    
    async def _enhanced_registration_flow(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        Strategy Pattern を使用した高度化登録フロー (v3.0)
        
        1. LLM Function Callingによる高精度情報抽出
        2. マスターデータとの照合・検証
        3. Strategy Patternによる最適な戦略選択・実行
        """
        # Step 1: 高精度情報抽出 (DI経由)
        extractor = self.service_provider.get_work_log_extractor()
        extracted_info = await extractor.extract_work_information(message)
        
        logger.info(f"情報抽出完了: 信頼度={extracted_info.confidence_score:.2f}")
        
        # Step 2: マスターデータ検証 (DI経由)
        validator = self.service_provider.get_work_log_validator()
        validation_result = await validator.validate_work_log(extracted_info)
        
        logger.info(f"検証完了: valid={validation_result.is_valid}")
        
        # Step 3: Strategy Pattern による最適戦略実行
        return await self.strategy_context.execute_best_strategy(
            extracted_info, validation_result, message, user_id
        )
    
    async def _legacy_hybrid_decision_flow(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult, 
        message: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        ハイブリッド判断フロー: 固定ルールとLLM判断の組み合わせ
        """
        # Step 1: 基本的な判定（固定ルール）
        confidence = extracted_info.confidence_score or 0.0
        
        # 確実に自動登録すべきケース
        if validation_result.is_valid and confidence >= 0.8:
            logger.info("高信頼度＋検証成功: 自動登録")
            return await self._direct_registration(
                extracted_info, validation_result, message, user_id
            )
        
        # 確実に確認が必要なケース
        if confidence <= 0.4 or len(validation_result.missing_info) >= 3:
            logger.info("低信頼度または大量不足情報: 確認フロー")
            return await self._confirmation_flow(
                extracted_info, validation_result, message, user_id
            )
        
        # Step 2: グレーゾーンでLLM判断が必要かチェック (DI経由)
        intelligent_decision_service = self.service_provider.get_intelligent_decision_service()
        
        should_use_llm = await intelligent_decision_service.should_use_intelligent_decision(
            message, extracted_info, validation_result
        )
        
        if should_use_llm:
            logger.info("LLM知的判断を実行")
            # Step 3: LLMによる文脈分析 (DI経由)
            user_history = await intelligent_decision_service.get_user_recent_history(user_id)
            context_analysis = await intelligent_decision_service.analyze_context(
                message, extracted_info, validation_result, user_history
            )
            
            # Step 4: LLM判断結果に基づく分岐
            if context_analysis.should_override:
                action = context_analysis.recommended_action
                
                if action == "auto_register_urgent":
                    logger.info("LLM判断: 緊急自動登録")
                    return await self._direct_registration(
                        extracted_info, validation_result, message, user_id
                    )
                elif action == "auto_register_inferred":
                    logger.info("LLM判断: 推測自動登録")
                    # 推測情報をextracted_infoに反映
                    if context_analysis.missing_info_inference:
                        extracted_info = self._apply_llm_inferences(
                            extracted_info, context_analysis.missing_info_inference
                        )
                    return await self._direct_registration(
                        extracted_info, validation_result, message, user_id
                    )
                elif action == "confirm_with_suggestions":
                    logger.info("LLM判断: 提案付き確認")
                    return await self._enhanced_confirmation_flow(
                        extracted_info, validation_result, message, user_id, context_analysis
                    )
        
        # Step 5: デフォルト（通常の確認フロー）
        logger.info("デフォルト: 通常確認フロー")
        return await self._confirmation_flow(
            extracted_info, validation_result, message, user_id
        )
    
    def _apply_llm_inferences(
        self, 
        extracted_info: ExtractedWorkInfo, 
        inferences: Dict[str, Any]
    ) -> ExtractedWorkInfo:
        """
        LLMの推測情報をExtractedWorkInfoに適用
        """
        updated_data = extracted_info.dict()
        
        # 推測可能な情報を適用
        for key, value in inferences.items():
            if key in updated_data and not updated_data[key]:
                updated_data[key] = value
                logger.info(f"LLM推測適用: {key}={value}")
        
        return ExtractedWorkInfo(**updated_data)
    
    async def _enhanced_confirmation_flow(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult, 
        message: str, 
        user_id: str,
        context_analysis
    ) -> Dict[str, Any]:
        """
        LLM分析結果を活用した高度化確認フロー
        """
        # 通常の確認フローにLLM分析結果を追加
        confirmation_result = await self._confirmation_flow(
            extracted_info, validation_result, message, user_id
        )
        
        # LLM分析による追加情報を付与
        if confirmation_result.get('confirmation_data'):
            confirmation_result['confirmation_data']['llm_analysis'] = {
                'urgency_level': context_analysis.urgency_level,
                'reasoning': context_analysis.reasoning[:200],  # 要約
                'confidence': context_analysis.confidence
            }
        
        return confirmation_result

    async def _direct_registration(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult, 
        original_message: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        高信頼度データの直接登録
        """
        try:
            # 構造化データで登録
            log_record = await self._save_enhanced_work_log(
                extracted_info, validation_result, original_message, user_id
            )
            
            return {
                'success': True,
                'log_id': log_record['log_id'],
                'message': f"作業記録を登録しました（記録ID: {log_record['log_id']}）",
                'confidence_score': extracted_info.confidence_score,
                'extracted_data': log_record['extracted_data'],
                'requires_confirmation': False,
                'registration_type': 'auto'
            }
            
        except Exception as e:
            logger.error(f"直接登録エラー: {e}")
            # エラー時は確認フローにフォールバック
            return await self._confirmation_flow(
                extracted_info, validation_result, original_message, user_id
            )
    
    async def _confirmation_flow(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult, 
        original_message: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        ユーザー確認フロー
        """
        try:
            # 確認メッセージとオプションを生成 (DI経由)
            confirmation_service = self.service_provider.get_work_log_confirmation_service()
            confirmation_data = confirmation_service.generate_confirmation_message(
                extracted_info, validation_result
            )
            
            return {
                'success': True,
                'requires_confirmation': True,
                'confirmation_data': {
                    'message': confirmation_data.confirmation_message,
                    'options': confirmation_data.options,
                    'extracted_info': extracted_info.dict(),
                    'validation_result': validation_result.dict(),
                    'original_message': original_message,
                    'user_id': user_id
                },
                'confidence_score': extracted_info.confidence_score,
                'registration_type': 'confirmation_required'
            }
            
        except Exception as e:
            logger.error(f"確認フローエラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '確認処理中にエラーが発生しました。',
                'requires_confirmation': False
            }
    
    async def confirm_and_register(
        self, 
        confirmation_data: Dict[str, Any], 
        user_choice: str, 
        additional_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        ユーザー確認後の登録処理
        
        Args:
            confirmation_data: 確認フローのデータ
            user_choice: ユーザーの選択 (confirm_registration, modify_info, 等)
            additional_data: 追加データ
            
        Returns:
            登録結果
        """
        try:
            if user_choice == "confirm_registration":
                # 登録実行
                extracted_info = ExtractedWorkInfo(**confirmation_data['extracted_info'])
                validation_result = WorkLogValidationResult(**confirmation_data['validation_result'])
                
                log_record = await self._save_enhanced_work_log(
                    extracted_info, 
                    validation_result, 
                    confirmation_data['original_message'], 
                    confirmation_data['user_id']
                )
                
                return {
                    'success': True,
                    'log_id': log_record['log_id'],
                    'message': f"作業記録を登録しました（記録ID: {log_record['log_id']}）",
                    'extracted_data': log_record['extracted_data'],
                    'registration_type': 'confirmed'
                }
                
            elif user_choice == "modify_info":
                # 修正モード
                return {
                    'success': True,
                    'message': '情報を修正してください。再度作業報告を入力してください。',
                    'action_required': 'modify_input'
                }
                
            elif user_choice == "cancel":
                # キャンセル
                return {
                    'success': True,
                    'message': '作業記録の登録をキャンセルしました。',
                    'action_required': 'cancelled'
                }
            
            # その他の選択肢処理は必要に応じて実装
            else:
                return {
                    'success': False,
                    'message': f'未対応の選択: {user_choice}',
                    'action_required': 'unknown_choice'
                }
                
        except Exception as e:
            logger.error(f"確認後登録エラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '登録処理中にエラーが発生しました。'
            }
    
    async def _save_enhanced_work_log(
        self, 
        extracted_info: ExtractedWorkInfo, 
        validation_result: WorkLogValidationResult, 
        original_message: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        高度化された作業記録保存（v2.0）
        
        Args:
            extracted_info: 抽出された作業情報
            validation_result: 検証結果
            original_message: 元のメッセージ
            user_id: ユーザーID
            
        Returns:
            Dict: 保存されたログレコード
        """
        try:
            # ログIDの生成
            log_id = f"LOG-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            # 作業日の解釈
            work_date = self._parse_enhanced_work_date(extracted_info.work_date)
            
            # 高度化された抽出データの構築
            extracted_data = {
                'extraction_version': '2.0',
                'confidence_score': extracted_info.confidence_score,
                'extraction_method': 'llm_function_calling'
            }
            
            # 検証済み圃場データ
            if validation_result.field_validation.get('matched_field'):
                field_match = validation_result.field_validation['matched_field']
                extracted_data.update({
                    'field_id': field_match['field_id'],
                    'field_name': field_match['field_name'],
                    'field_confidence': field_match.get('confidence', 0.0),
                    'field_match_method': field_match.get('method', 'unknown')
                })
            
            # 検証済み作物データ
            if validation_result.crop_validation.get('matched_crop'):
                crop_match = validation_result.crop_validation['matched_crop']
                extracted_data.update({
                    'crop_id': crop_match['crop_id'],
                    'crop_name': crop_match['crop_name'],
                    'crop_confidence': crop_match.get('confidence', 0.0),
                    'crop_match_method': crop_match.get('method', 'unknown')
                })
            
            # 検証済み資材データ
            validated_materials = [
                m for m in validation_result.material_validation 
                if m.get('matched_material')
            ]
            
            if validated_materials:
                material_ids = []
                material_names = []
                material_confidences = []
                
                for material_validation in validated_materials:
                    material_match = material_validation['matched_material']
                    material_ids.append(material_match['material_id'])
                    material_names.append(material_match['material_name'])
                    material_confidences.append(material_match.get('confidence', 0.0))
                
                extracted_data.update({
                    'material_ids': material_ids,
                    'material_names': material_names,
                    'material_confidences': material_confidences
                })
            
            # 数量・単位情報
            if extracted_info.quantity is not None:
                extracted_data['quantity'] = extracted_info.quantity
            if extracted_info.unit:
                extracted_data['unit'] = extracted_info.unit
            if extracted_info.work_count:
                extracted_data['work_count'] = extracted_info.work_count
            
            # メモ・特記事項
            if extracted_info.notes:
                extracted_data['notes'] = extracted_info.notes
            
            # 検証結果サマリー
            extracted_data['validation_summary'] = {
                'is_valid': validation_result.is_valid,
                'missing_info_count': len(validation_result.missing_info),
                'suggestions_count': len(validation_result.suggestions),
                'validated_at': datetime.now().isoformat()
            }
            
            # ログレコードの作成
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
            logger.info(f"v2.0作業記録保存完了: {log_id}, 信頼度: {extracted_info.confidence_score:.2f}")
            
            return log_record
            
        except Exception as e:
            logger.error(f"高度化作業記録保存エラー: {e}")
            raise
    
    def _parse_enhanced_work_date(self, work_date_str: Optional[str]) -> datetime:
        """
        高度化された作業日解釈
        
        Args:
            work_date_str: 作業日文字列
            
        Returns:
            datetime: 解釈された作業日
        """
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
        
        # 具体的な日付形式の解析（必要に応じて拡張）
        try:
            # YYYY-MM-DD形式
            if re.match(r'\d{4}-\d{2}-\d{2}', work_date_str):
                return datetime.strptime(work_date_str, '%Y-%m-%d')
            # MM/DD形式（今年と仮定）
            elif re.match(r'\d{1,2}/\d{1,2}', work_date_str):
                return datetime.strptime(f"{today.year}/{work_date_str}", '%Y/%m/%d')
        except ValueError:
            logger.warning(f"日付解析に失敗: {work_date_str}")
        
        # デフォルトは今日
        return today
    
    async def _extract_work_info(self, message: str) -> Dict[str, str]:
        """自然言語から基本情報を抽出"""
        import re
        
        extracted = {
            'raw_field_name': '',
            'raw_crop_name': '',
            'raw_material_names': [],
            'work_type_keywords': [],
            'quantities': [],
            'work_count': None,
            'relative_date': '',
        }
        
        # 相対日付の抽出
        date_patterns = [
            (r'昨日|きのう', '昨日'),
            (r'一昨日|おととい', '一昨日'),
            (r'今日|きょう', '今日'),
            (r'(\d+)日前', r'\1日前'),
        ]
        
        for pattern, replacement in date_patterns:
            if re.search(pattern, message):
                extracted['relative_date'] = replacement
                break
        
        # 作業種別キーワード
        work_types = {
            '防除': ['防除', '農薬', '散布', '殺菌', '殺虫'],
            '施肥': ['施肥', '肥料', '追肥', '元肥'],
            '栽培': ['播種', '定植', '摘心', '誘引', '整枝'],
            '収穫': ['収穫', '収穫量', '出荷'],
            '管理': ['草刈り', '清掃', '点検'],
        }
        
        for work_type, keywords in work_types.items():
            if any(keyword in message for keyword in keywords):
                extracted['work_type_keywords'].append(work_type)
        
        # 回数の抽出
        count_match = re.search(r'(\d+)回目', message)
        if count_match:
            extracted['work_count'] = int(count_match.group(1))
        
        # 簡易的な名詞抽出（改良の余地あり）
        # 圃場名候補
        field_patterns = [
            r'([^、。\s]+)(?:ハウス|畑|田|圃場)',
            r'([^、。\s]+)の(?:防除|施肥|作業)',
        ]
        
        for pattern in field_patterns:
            match = re.search(pattern, message)
            if match:
                extracted['raw_field_name'] = match.group(1)
                break
        
        # 作物名候補
        crop_patterns = [
            r'(トマト|キュウリ|ナス|ピーマン|イチゴ)',  # 主要作物
            r'([^、。\s]+)(?:の防除|に散布|を収穫)',
        ]
        
        for pattern in crop_patterns:
            match = re.search(pattern, message)
            if match:
                extracted['raw_crop_name'] = match.group(1)
                break
        
        # 資材名候補
        material_patterns = [
            r'(ダコニール\d*|モレスタン|アブラムシ\w*)',  # 具体的な農薬名
            r'([^、。\s]+)(?:を散布|使用)',
        ]
        
        for pattern in material_patterns:
            matches = re.findall(pattern, message)
            extracted['raw_material_names'].extend(matches)
        
        return extracted
    
    async def _resolve_master_data(self, extracted_info: Dict[str, str]) -> Dict[str, str]:
        """マスターデータとの照合・ID変換"""
        resolved = {
            'field_data': None,
            'crop_data': None,
            'material_data': [],
        }
        
        # 圃場データ解決
        if extracted_info['raw_field_name']:
            resolved['field_data'] = await self.master_resolver.resolve_field_data(
                extracted_info['raw_field_name']
            )
        
        # 作物データ解決
        if extracted_info['raw_crop_name']:
            resolved['crop_data'] = await self.master_resolver.resolve_crop_data(
                extracted_info['raw_crop_name']
            )
        
        # 資材データ解決
        for material_name in extracted_info['raw_material_names']:
            material_data = await self.master_resolver.resolve_material_data(material_name)
            resolved['material_data'].append(material_data)
        
        return resolved
    
    def _parse_work_date(self, message: str, extracted_info: Dict) -> datetime:
        """作業日の解釈"""
        # datetime.date ではなく datetime.datetime を使用
        today = datetime.now() 
        
        relative_date = extracted_info.get('relative_date', '')
        
        if relative_date == '昨日':
            return today - timedelta(days=1)
        elif relative_date == '一昨日':
            return today - timedelta(days=2)
        elif relative_date == '今日':
            return today
        elif '日前' in relative_date:
            import re
            days_match = re.search(r'(\d+)日前', relative_date)
            if days_match:
                days = int(days_match.group(1))
                return today - timedelta(days=days)
        
        # デフォルトは今日
        return today
    
    def _classify_work_type(self, extracted_info: Dict, resolved_data: Dict) -> str:
        """作業分類の決定"""
        work_keywords = extracted_info.get('work_type_keywords', [])
        
        if work_keywords:
            return work_keywords[0]  # 最初に見つかった分類
        
        # 資材から推定
        material_data = resolved_data.get('material_data', [])
        for material in material_data:
            if material.get('material_id'):
                # 資材の種別から作業分類を推定（簡易版）
                material_name = material.get('material_name', '').lower()
                if any(keyword in material_name for keyword in ['殺菌', '殺虫', '農薬']):
                    return '防除'
                elif any(keyword in material_name for keyword in ['肥料', '化成']):
                    return '施肥'
        
        return 'その他'
    
    async def _save_work_log(self, original_message: str, resolved_data: Dict, 
                           work_date: datetime, work_category: str, user_id: str) -> Dict:
        """作業記録をデータベースに保存"""
        
        # ログIDの生成
        log_id = f"LOG-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # 抽出データの構築
        extracted_data = {}
        
        if resolved_data['field_data'] and resolved_data['field_data']['field_id']:
            extracted_data['field_id'] = resolved_data['field_data']['field_id']
            extracted_data['field_name'] = resolved_data['field_data']['field_name']
        
        if resolved_data['crop_data'] and resolved_data['crop_data']['crop_id']:
            extracted_data['crop_id'] = resolved_data['crop_data']['crop_id']
            extracted_data['crop_name'] = resolved_data['crop_data']['crop_name']
        
        if resolved_data['material_data']:
            material_ids = []
            material_names = []
            for material in resolved_data['material_data']:
                if material.get('material_id'):
                    material_ids.append(material['material_id'])
                    material_names.append(material['material_name'])
            
            if material_ids:
                extracted_data['material_ids'] = material_ids
                extracted_data['material_names'] = material_names
        
        # 記録の作成
        log_record = {
            'log_id': log_id,
            'user_id': user_id,
            'work_date': work_date,
            'original_message': original_message,
            'extracted_data': extracted_data,
            'category': work_category,
            'tags': [work_category],
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'status': 'confirmed'
        }
        
        # データベース保存
        client = await self.db_connection.get_client()
        try:
            work_logs_collection = await client.get_collection('work_logs')
            
            await work_logs_collection.insert_one(log_record)
            logger.info(f"作業記録保存完了: {log_id}")
            
            return log_record
            
        finally:
            pass  # 接続は再利用されるためdisconnectしない
    
    def _format_registration_result(self, log_record: Dict, resolved_data: Dict) -> Dict[str, str]:
        """登録結果の整形"""
        
        # 信頼度の計算
        confidences = []
        if resolved_data['field_data']:
            confidences.append(resolved_data['field_data'].get('confidence', 0))
        if resolved_data['crop_data']:
            confidences.append(resolved_data['crop_data'].get('confidence', 0))
        for material in resolved_data['material_data']:
            confidences.append(material.get('confidence', 0))
        
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            'success': True,
            'log_id': log_record['log_id'],
            'work_date': log_record['work_date'].strftime('%Y-%m-%d'),
            'category': log_record['category'],
            'extracted_data': log_record['extracted_data'],
            'confidence': overall_confidence,
            'message': f"作業記録を登録しました（記録ID: {log_record['log_id']}）"
        }