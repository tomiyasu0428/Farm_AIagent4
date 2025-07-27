"""
QueryAnalyzer: ユーザークエリ分析サービス

MasterAgentから切り出した、ユーザーの意図分析と実行プラン生成を担当するサービス。
単一責任原則に基づき、クエリ分析に特化した処理を提供する。
"""

import re
import logging
from typing import Dict, Optional
from .field_name_extractor import FieldNameExtractor

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """ユーザークエリの分析・意図理解サービス"""
    
    def __init__(self):
        self.field_name_extractor = FieldNameExtractor()
    
    async def analyze_query_intent(self, message: str) -> Dict[str, any]:
        """
        ユーザークエリを分析し、意図とパラメータを抽出
        
        Args:
            message: ユーザーのメッセージ
            
        Returns:
            {
                'intent': str,           # 意図タイプ
                'agent': str,           # 担当エージェント
                'extracted_data': Dict, # 抽出されたデータ
                'confidence': float     # 信頼度
            }
        """
        try:
            # 基本的な意図分析
            intent_result = self._analyze_basic_intent(message)
            
            # 詳細データ抽出
            extracted_data = await self._extract_detailed_data(message, intent_result['intent'])
            
            return {
                'intent': intent_result['intent'],
                'agent': intent_result['agent'],
                'extracted_data': extracted_data,
                'confidence': intent_result['confidence'],
                'original_message': message
            }
            
        except Exception as e:
            logger.error(f"クエリ分析エラー: {e}")
            return {
                'intent': 'unknown',
                'agent': 'field_agent',  # デフォルト
                'extracted_data': {},
                'confidence': 0.0,
                'original_message': message,
                'error': str(e)
            }
    
    def _analyze_basic_intent(self, message: str) -> Dict[str, any]:
        """基本的な意図分析"""
        
        # 圃場登録系
        if any(keyword in message for keyword in ["登録", "追加", "新しい", "作成"]) and \
           any(keyword in message for keyword in ["圃場", "ハウス", "畑", "田"]):
            return {
                'intent': 'field_registration',
                'agent': 'field_registration_agent',
                'confidence': 0.9
            }
        
        # 圃場情報系
        if any(keyword in message for keyword in ["圃場", "ハウス", "畑", "面積", "作付け"]):
            return {
                'intent': 'field_info',
                'agent': 'field_agent',
                'confidence': 0.8
            }
        
        # その他のパターンも今後追加予定
        
        # デフォルト: 圃場情報として処理
        return {
            'intent': 'field_info',
            'agent': 'field_agent',
            'confidence': 0.5
        }
    
    async def _extract_detailed_data(self, message: str, intent: str) -> Dict[str, any]:
        """意図に応じた詳細データ抽出"""
        
        extracted = {}
        
        # 共通: 圃場名抽出
        field_name = await self._extract_field_name(message)
        if field_name:
            extracted['field_name'] = field_name
        
        # 意図別の詳細抽出
        if intent == 'field_registration':
            extracted.update(self._extract_registration_data(message))
        elif intent == 'field_info':
            extracted.update(self._extract_info_query_data(message))
        
        return extracted
    
    def _extract_registration_data(self, message: str) -> Dict[str, any]:
        """圃場登録用データ抽出"""
        data = {}
        
        # 面積抽出
        area = self._extract_area(message)
        if area:
            data['area'] = area
        
        # エリア名抽出
        area_name = self._extract_area_name(message)
        if area_name:
            data['area_name'] = area_name
        
        return data
    
    def _extract_info_query_data(self, message: str) -> Dict[str, any]:
        """圃場情報クエリ用データ抽出"""
        data = {}
        
        # クエリタイプ判定
        if "面積" in message:
            data['query_type'] = 'area'
        elif "一覧" in message or "すべて" in message:
            data['query_type'] = 'list'
        elif "状況" in message or "詳細" in message:
            data['query_type'] = 'detail'
        else:
            data['query_type'] = 'general'
        
        return data
    
    async def create_execution_plan(self, analysis_result: Dict[str, any]) -> str:
        """
        分析結果に基づいて実行プランを生成
        
        Args:
            analysis_result: analyze_query_intent()の結果
            
        Returns:
            実行プランのテキスト
        """
        intent = analysis_result['intent']
        extracted_data = analysis_result['extracted_data']
        
        try:
            if intent == 'field_registration':
                return self._create_registration_plan(extracted_data)
            elif intent == 'field_info':
                return self._create_info_plan(extracted_data)
            else:
                return self._create_general_plan(analysis_result)
                
        except Exception as e:
            logger.error(f"実行プラン生成エラー: {e}")
            return "📋 実行プラン\n1. ユーザーリクエストを処理\n2. 結果をレポート"
    
    def _create_registration_plan(self, extracted_data: Dict[str, any]) -> str:
        """圃場登録用プラン生成"""
        field_name = extracted_data.get('field_name', '新しい圃場')
        
        if field_name != '新しい圃場':
            return f"""📋 実行プラン
1. 「{field_name}」を新規圃場として登録処理
2. 面積・エリア情報を含めてデータベースに保存
3. 登録完了通知をユーザーに送信"""
        else:
            return """📋 実行プラン
1. 圃場登録専門エージェント(FieldRegistrationAgent)で新しい圃場を登録
2. 登録結果を確認してユーザーに報告"""
    
    def _create_info_plan(self, extracted_data: Dict[str, any]) -> str:
        """圃場情報クエリ用プラン生成"""
        field_name = extracted_data.get('field_name', '')
        query_type = extracted_data.get('query_type', 'general')
        area_name = extracted_data.get('area_name', '')
        
        if field_name:
            if query_type == 'area':
                return f"""📋 実行プラン
1. 「{field_name}」の面積情報をリサーチ
2. 結果をha単位でユーザーにレポート"""
            elif query_type == 'detail':
                return f"""📋 実行プラン
1. 「{field_name}」の詳細情報をリサーチ
2. 面積・作付け・作業予定をユーザーにレポート"""
            else:
                return f"""📋 実行プラン
1. 「{field_name}」の情報をリサーチ
2. 詳細データをユーザーにレポート"""
        elif query_type == 'list':
            if area_name:
                return f"""📋 実行プラン
1. 「{area_name}」の圃場一覧をリサーチ
2. 各圃場の面積・作付け状況をユーザーにレポート"""
            else:
                return """📋 実行プラン
1. 全圃場の一覧情報をリサーチ
2. 面積・作付け状況を整理してユーザーにレポート"""
        else:
            return """📋 実行プラン
1. 圃場情報を専門エージェント(FieldAgent)で調査
2. 結果をわかりやすく整理して報告"""
    
    def _create_general_plan(self, analysis_result: Dict[str, any]) -> str:
        """汎用プラン生成"""
        query_type = self._analyze_query_type(analysis_result['original_message'])
        return f"""📋 実行プラン
1. 「{query_type}」について最適なツールで情報収集
2. 結果を整理してユーザーにレポート"""
    
    async def _extract_field_name(self, message: str) -> str:
        """メッセージから圃場名を動的に抽出"""
        try:
            result = await self.field_name_extractor.extract_field_name(message)
            
            # 信頼度が50%以上の場合のみ採用
            if result['confidence'] >= 0.5:
                logger.info(f"動的圃場名抽出成功: {result['field_name']} (信頼度: {result['confidence']:.2f})")
                return result['field_name']
            else:
                logger.info(f"動的圃場名抽出: 信頼度不足 ({result['confidence']:.2f})")
                return ""
                
        except Exception as e:
            logger.error(f"動的圃場名抽出エラー: {e}")
            # フォールバック: 従来の正規表現方式
            return self._extract_field_name_fallback(message)
    
    def _extract_field_name_fallback(self, message: str) -> str:
        """フォールバック用の従来圃場名抽出"""
        # 改良された正規表現パターン
        field_patterns = [
            r'「([^」]+)」',           # 「圃場名」
            r'([^のを\s]{2,})の(?:面積|情報|詳細|状況)',  # 2文字以上の圃場名
            r'([^のを\s]{2,})を(?:登録|追加)',         # 2文字以上の圃場名
            r'([^のを\s]{2,})は(?:どこ|何)',           # 2文字以上の圃場名
        ]
        
        for pattern in field_patterns:
            match = re.search(pattern, message)
            if match:
                extracted = match.group(1)
                if len(extracted) >= 2:  # 最小長チェック
                    return extracted
        
        return ""
    
    def _extract_area(self, message: str) -> Optional[str]:
        """面積情報を抽出"""
        area_patterns = [
            r'(\d+\.?\d*)\s*ha',
            r'(\d+\.?\d*)\s*ヘクタール',
            r'(\d+\.?\d*)\s*㎡',
            r'(\d+\.?\d*)\s*平方メートル',
        ]
        
        for pattern in area_patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_area_name(self, message: str) -> str:
        """メッセージからエリア名を抽出"""
        if "豊糠" in message:
            return "豊糠エリア"
        elif "豊緑" in message:
            return "豊緑エリア"
        return ""
    
    def _extract_material_name(self, message: str) -> str:
        """メッセージから資材名を抽出"""
        # 資材名のパターン
        material_patterns = [
            r'「([^」]+)」',  # 「農薬名」
            r'([^の\s]+)の希釈',  # 農薬名の希釈
            r'([^を\s]+)を',     # 農薬名を
        ]
        
        for pattern in material_patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)
        
        return ""
    
    def _analyze_query_type(self, message: str) -> str:
        """クエリタイプを分析"""
        if any(keyword in message for keyword in ["天気", "気温", "雨"]):
            return "天気情報"
        elif any(keyword in message for keyword in ["病気", "害虫", "症状"]):
            return "病害虫診断"
        elif any(keyword in message for keyword in ["収穫", "出荷", "販売"]):
            return "収穫・出荷情報"
        else:
            return "農業全般の問い合わせ"