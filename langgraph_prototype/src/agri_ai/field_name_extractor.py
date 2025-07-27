"""
FieldNameExtractor: データベースベースの動的圃場名抽出システム

アイデア:
1. データベースから全圃場名を取得
2. 部分一致・あいまい一致で圃場名を特定
3. 複数候補がある場合は最適マッチを選択
4. ユーザー別の圃場名も考慮
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from ..database.mongodb_client import create_mongodb_client

logger = logging.getLogger(__name__)


class FieldNameExtractor:
    """データベースベースの動的圃場名抽出サービス"""
    
    def __init__(self):
        self.field_cache = None
        self.cache_timeout = 300  # 5分キャッシュ
        self.last_cache_time = 0
    
    async def extract_field_name(self, query: str, user_id: Optional[str] = None) -> Dict[str, any]:
        """
        クエリから圃場名を動的に抽出
        
        Args:
            query: ユーザークエリ
            user_id: ユーザーID（将来のユーザー別圃場対応）
            
        Returns:
            {
                'field_name': str,      # 抽出された圃場名
                'confidence': float,    # 信頼度 (0.0-1.0)
                'method': str,          # 抽出方法
                'candidates': List[str], # 候補一覧
                'original_query': str   # 元のクエリ
            }
        """
        try:
            # データベースから圃場名を取得
            field_names = await self._get_all_field_names()
            
            # 段階的抽出アプローチ
            result = await self._multi_stage_extraction(query, field_names)
            result['original_query'] = query
            
            logger.info(f"圃場名抽出結果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"圃場名抽出エラー: {e}")
            return {
                'field_name': '',
                'confidence': 0.0,
                'method': 'error',
                'candidates': [],
                'original_query': query,
                'error': str(e)
            }
    
    async def _get_all_field_names(self) -> List[str]:
        """データベースから全圃場名を取得（キャッシュ機能付き）"""
        import time
        current_time = time.time()
        
        # キャッシュチェック
        if (self.field_cache is not None and 
            current_time - self.last_cache_time < self.cache_timeout):
            return self.field_cache
        
        # データベースから取得
        client = create_mongodb_client()
        try:
            await client.connect()
            fields_collection = await client.get_collection("fields")
            
            # 全圃場の名前を取得
            fields = await fields_collection.find(
                {}, 
                {"name": 1, "field_code": 1}
            ).to_list(1000)
            
            field_names = []
            for field in fields:
                if field.get("name"):
                    field_names.append(field["name"])
                if field.get("field_code"):
                    field_names.append(field["field_code"])
            
            # キャッシュ更新
            self.field_cache = field_names
            self.last_cache_time = current_time
            
            logger.info(f"データベースから{len(field_names)}個の圃場名を取得")
            return field_names
            
        finally:
            await client.disconnect()
    
    async def _multi_stage_extraction(self, query: str, field_names: List[str]) -> Dict[str, any]:
        """段階的圃場名抽出"""
        
        # Stage 1: 完全一致
        exact_match = self._exact_match(query, field_names)
        if exact_match:
            return {
                'field_name': exact_match,
                'confidence': 1.0,
                'method': 'exact_match',
                'candidates': [exact_match]
            }
        
        # Stage 2: 部分一致
        partial_matches = self._partial_match(query, field_names)
        if partial_matches:
            best_match = partial_matches[0]  # 最初が最良マッチ
            return {
                'field_name': best_match,
                'confidence': 0.8,
                'method': 'partial_match',
                'candidates': partial_matches[:3]  # 上位3候補
            }
        
        # Stage 3: あいまい一致（編集距離ベース）
        fuzzy_matches = self._fuzzy_match(query, field_names)
        if fuzzy_matches:
            best_match, similarity = fuzzy_matches[0]
            if similarity > 0.6:  # 60%以上の類似度
                return {
                    'field_name': best_match,
                    'confidence': similarity,
                    'method': 'fuzzy_match',
                    'candidates': [match[0] for match in fuzzy_matches[:3]]
                }
        
        # Stage 4: 正規表現フォールバック
        regex_match = self._regex_fallback(query)
        if regex_match:
            return {
                'field_name': regex_match,
                'confidence': 0.5,
                'method': 'regex_fallback',
                'candidates': [regex_match]
            }
        
        # Stage 5: 抽出失敗
        return {
            'field_name': '',
            'confidence': 0.0,
            'method': 'no_match',
            'candidates': []
        }
    
    def _exact_match(self, query: str, field_names: List[str]) -> Optional[str]:
        """完全一致検索"""
        for field_name in field_names:
            if field_name in query:
                return field_name
        return None
    
    def _partial_match(self, query: str, field_names: List[str]) -> List[str]:
        """部分一致検索（長い順にソート）"""
        matches = []
        for field_name in field_names:
            # 圃場名の一部がクエリに含まれているか
            if any(part in query for part in field_name.split()):
                matches.append(field_name)
            # クエリの一部が圃場名に含まれているか
            elif any(part in field_name for part in query.split()):
                matches.append(field_name)
        
        # 長い順にソート（より具体的なマッチを優先）
        return sorted(set(matches), key=len, reverse=True)
    
    def _fuzzy_match(self, query: str, field_names: List[str]) -> List[Tuple[str, float]]:
        """あいまい一致検索（編集距離ベース）"""
        similarities = []
        
        for field_name in field_names:
            # 全体の類似度
            similarity = SequenceMatcher(None, query, field_name).ratio()
            
            # 個別単語の最大類似度も考慮
            query_words = query.split()
            field_words = field_name.split()
            
            max_word_similarity = 0.0
            for q_word in query_words:
                for f_word in field_words:
                    word_sim = SequenceMatcher(None, q_word, f_word).ratio()
                    max_word_similarity = max(max_word_similarity, word_sim)
            
            # 総合スコア（全体類似度と単語類似度の平均）
            final_score = (similarity + max_word_similarity) / 2
            
            if final_score > 0.3:  # 30%以上の類似度のみ
                similarities.append((field_name, final_score))
        
        # スコア順にソート
        return sorted(similarities, key=lambda x: x[1], reverse=True)
    
    def _regex_fallback(self, query: str) -> Optional[str]:
        """正規表現フォールバック（改良版）"""
        # より柔軟な正規表現パターン
        patterns = [
            r'「([^」]+)」',           # 「圃場名」
            r'([^のを\s]{2,})の(?:面積|情報|詳細|状況)',  # 2文字以上の圃場名
            r'([^のを\s]{2,})を(?:登録|追加)',         # 2文字以上の圃場名
            r'([^のを\s]{2,})は(?:どこ|何)',           # 2文字以上の圃場名
            r'([一-龯]+[畑田圃場ハウス]+\d*)',         # 日本語＋畑/田/圃場/ハウス
            r'([A-Za-z]+[畑田圃場ハウス]+\d*)',        # 英語＋畑/田/圃場/ハウス
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                extracted = match.group(1)
                # 最小長チェック
                if len(extracted) >= 2:
                    return extracted
        
        return None
    
    def get_extraction_stats(self) -> Dict[str, any]:
        """抽出統計情報を取得"""
        import time
        return {
            'cached_fields': len(self.field_cache) if self.field_cache else 0,
            'cache_age': (time.time() - self.last_cache_time) if self.last_cache_time else 0,
            'cache_timeout': self.cache_timeout
        }


# 使用例とテスト用の関数
async def test_field_name_extractor():
    """FieldNameExtractorのテスト実行"""
    extractor = FieldNameExtractor()
    
    test_queries = [
        "橋向こう①の面積を教えて",        # 完全一致
        "山田さんの畑の詳細情報",          # あいまい一致
        "池の向こうはどこにある？",        # 新しい圃場名
        "テスト用新圃場を登録したい",      # 正規表現
        "第1ハウスの状況確認",            # 既存圃場
        "新しく借りた畑について教えて"     # 複雑な表現
    ]
    
    for query in test_queries:
        print(f"\n--- テスト: {query} ---")
        result = await extractor.extract_field_name(query)
        print(f"抽出圃場名: {result['field_name']}")
        print(f"信頼度: {result['confidence']:.2f}")
        print(f"方法: {result['method']}")
        print(f"候補: {result['candidates']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_field_name_extractor())