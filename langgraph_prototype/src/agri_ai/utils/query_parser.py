"""
クエリ解析ユーティリティ
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import dateparser
import logging

logger = logging.getLogger(__name__)


class QueryParser:
    """自然言語クエリ解析クラス"""

    def __init__(self):
        # 日本語の日付表現パターン
        self.date_patterns = {
            "今日": lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            "明日": lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            + timedelta(days=1),
            "昨日": lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=1),
            "今週": self._get_this_week_range,
            "来週": self._get_next_week_range,
            "先週": self._get_last_week_range,
            "今月": self._get_this_month_range,
            "来月": self._get_next_month_range,
        }

        # 圃場名パターン
        self.field_patterns = [
            r"([ABC]畑)",
            r"(第[0-9]+[ハウス|棟|区画]*)",
            r"([A-Z]-[0-9]+)",
            r"(ハウス[0-9]+)",
            r"([0-9]+号[棟|区画]*)",
        ]

        # 作業種別パターン
        self.work_type_patterns = {
            "防除": ["防除", "農薬散布", "薬剤散布", "消毒"],
            "灌水": ["灌水", "水やり", "散水"],
            "追肥": ["追肥", "肥料", "施肥"],
            "除草": ["除草", "草取り", "草刈り"],
            "収穫": ["収穫", "採取"],
            "定植": ["定植", "植付け", "移植"],
            "播種": ["播種", "種まき", "蒔種"],
            "摘芯": ["摘芯", "芯止め"],
            "誘引": ["誘引", "支柱立て"],
        }

        # 作物名パターン
        self.crop_patterns = [
            r"(トマト|ミニトマト)",
            r"(きゅうり|キュウリ)",
            r"(なす|ナス)",
            r"(ピーマン|パプリカ)",
            r"(レタス|サニーレタス)",
            r"(キャベツ|白菜)",
            r"(人参|にんじん|ニンジン)",
            r"(大根|だいこん)",
            r"(玉ねぎ|たまねぎ)",
            r"(じゃがいも|ジャガイモ)",
        ]

        # 資材名パターン
        self.material_patterns = [
            r"(殺虫剤|農薬)",
            r"(殺菌剤|防除剤)",
            r"(除草剤)",
            r"(肥料|追肥)",
            r"(有機肥料|化成肥料)",
            r"(農薬|薬剤)",
        ]

    def parse_date_query(self, query: str) -> Optional[Dict[str, Any]]:
        """日付関連クエリの解析"""
        try:
            # 日本語の日付表現をチェック
            for pattern, handler in self.date_patterns.items():
                if pattern in query:
                    if callable(handler):
                        if pattern in ["今週", "来週", "先週", "今月", "来月"]:
                            start_date, end_date = handler()
                            return {"date_range": {"$gte": start_date, "$lt": end_date}, "pattern": pattern}
                        else:
                            date = handler()
                            return {
                                "date_range": {"$gte": date, "$lt": date + timedelta(days=1)},
                                "pattern": pattern,
                            }

            # dateparserを使用してより複雑な日付表現を解析
            parsed_date = dateparser.parse(query, languages=["ja"])
            if parsed_date:
                return {
                    "date_range": {
                        "$gte": parsed_date.replace(hour=0, minute=0, second=0, microsecond=0),
                        "$lt": parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        + timedelta(days=1),
                    },
                    "pattern": "dateparser",
                }

            return None

        except Exception as e:
            logger.error(f"日付解析エラー: {e}")
            return None

    def parse_field_query(self, query: str) -> Optional[Dict[str, Any]]:
        """圃場関連クエリの解析"""
        try:
            # 全圃場を指定する表現
            if any(word in query for word in ["全圃場", "すべての圃場", "全ての圃場", "全部"]):
                return {"all_fields": True}

            # 圃場名パターンマッチング
            for pattern in self.field_patterns:
                match = re.search(pattern, query)
                if match:
                    field_name = match.group(1)
                    return {
                        "field_filter": {
                            "$or": [
                                {"field_code": {"$regex": field_name, "$options": "i"}},
                                {"name": {"$regex": field_name, "$options": "i"}},
                            ]
                        },
                        "field_name": field_name,
                    }

            return None

        except Exception as e:
            logger.error(f"圃場解析エラー: {e}")
            return None

    def parse_work_type_query(self, query: str) -> Optional[List[str]]:
        """作業種別クエリの解析"""
        try:
            found_work_types = []

            for work_type, keywords in self.work_type_patterns.items():
                if any(keyword in query for keyword in keywords):
                    found_work_types.append(work_type)

            return found_work_types if found_work_types else None

        except Exception as e:
            logger.error(f"作業種別解析エラー: {e}")
            return None

    def parse_priority_query(self, query: str) -> Optional[str]:
        """優先度クエリの解析"""
        priority_patterns = {
            "high": ["緊急", "至急", "重要", "高優先度", "優先"],
            "medium": ["通常", "普通", "中優先度"],
            "low": ["低優先度", "後回し", "時間があるとき"],
        }

        for priority, keywords in priority_patterns.items():
            if any(keyword in query for keyword in keywords):
                return priority

        return None

    def parse_comprehensive_query(self, query: str) -> Dict[str, Any]:
        """総合的なクエリ解析"""
        result = {"original_query": query, "parsed_components": {}}

        # 日付解析
        date_result = self.parse_date_query(query)
        if date_result:
            result["parsed_components"]["date"] = date_result

        # 圃場解析
        field_result = self.parse_field_query(query)
        if field_result:
            result["parsed_components"]["field"] = field_result

        # 作業種別解析
        work_types = self.parse_work_type_query(query)
        if work_types:
            result["parsed_components"]["work_types"] = work_types

        # 優先度解析
        priority = self.parse_priority_query(query)
        if priority:
            result["parsed_components"]["priority"] = priority

        return result

    def extract_material_name_from_query(self, query: str) -> Optional[str]:
        """クエリからより柔軟に資材名を抽出する"""
        try:
            # 冗長な表現を削除
            patterns_to_remove = [
                r"の希釈倍率を教えて",
                r"の希釈倍率",
                r"の使い方",
                r"について教えて",
                r"について",
                r"農薬",
                r"薬剤",
                r"です",
                r"を教えて",
            ]

            processed_query = query
            for pattern in patterns_to_remove:
                processed_query = re.sub(pattern, "", processed_query, flags=re.IGNORECASE)

            # 前後の空白をトリム
            material_name = processed_query.strip()

            logger.debug(f"抽出された資材名候補: '{material_name}' (元クエリ: '{query}')")

            # 空文字列でないことを確認
            return material_name if material_name else None

        except Exception as e:
            logger.error(f"資材名の抽出中にエラーが発生しました: {e}", exc_info=True)
            return None

    def _get_this_week_range(self) -> tuple:
        """今週の範囲を取得"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # 月曜日を週の始まりとする
        days_since_monday = today.weekday()
        start_of_week = today - timedelta(days=days_since_monday)
        end_of_week = start_of_week + timedelta(days=7)
        return start_of_week, end_of_week

    def _get_next_week_range(self) -> tuple:
        """来週の範囲を取得"""
        start_of_this_week, _ = self._get_this_week_range()
        start_of_next_week = start_of_this_week + timedelta(days=7)
        end_of_next_week = start_of_next_week + timedelta(days=7)
        return start_of_next_week, end_of_next_week

    def _get_last_week_range(self) -> tuple:
        """先週の範囲を取得"""
        start_of_this_week, _ = self._get_this_week_range()
        start_of_last_week = start_of_this_week - timedelta(days=7)
        end_of_last_week = start_of_this_week
        return start_of_last_week, end_of_last_week

    def _get_this_month_range(self) -> tuple:
        """今月の範囲を取得"""
        today = datetime.now()
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # 来月の1日を取得
        if today.month == 12:
            end_of_month = start_of_month.replace(year=today.year + 1, month=1)
        else:
            end_of_month = start_of_month.replace(month=today.month + 1)
        return start_of_month, end_of_month

    def _get_next_month_range(self) -> tuple:
        """来月の範囲を取得"""
        today = datetime.now()
        if today.month == 12:
            start_of_next_month = today.replace(
                year=today.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            end_of_next_month = start_of_next_month.replace(month=2)
        else:
            start_of_next_month = today.replace(
                month=today.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            if today.month == 11:
                end_of_next_month = start_of_next_month.replace(year=today.year + 1, month=1)
            else:
                end_of_next_month = start_of_next_month.replace(month=today.month + 2)
        return start_of_next_month, end_of_next_month

    def extract_crop_name(self, query: str) -> Optional[str]:
        """作物名抽出の共通メソッド"""
        try:
            for pattern in self.crop_patterns:
                match = re.search(pattern, query)
                if match:
                    return match.group(1)
            return None
        except Exception as e:
            logger.error(f"作物名抽出エラー: {e}")
            return None

    def extract_material_name(self, query: str) -> Optional[str]:
        """資材名抽出の共通メソッド"""
        try:
            for pattern in self.material_patterns:
                match = re.search(pattern, query)
                if match:
                    return match.group(1)
            return None
        except Exception as e:
            logger.error(f"資材名抽出エラー: {e}")
            return None


# グローバルインスタンス
query_parser = QueryParser()
