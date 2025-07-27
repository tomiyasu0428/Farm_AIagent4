"""
WorkLogSearchAgent: 作業記録検索専門エージェント

蓄積された作業記録を検索・集計し、質問に応じて適切な情報を提供する。
時系列分析、集計統計、異常検出などの高度な分析機能も提供。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from ..core.base_agent import BaseAgent
from ..services.master_data_resolver import MasterDataResolver
from ..database.mongodb_client import create_mongodb_client
from ..database.data_access import DataAccessLayer

logger = logging.getLogger(__name__)


class WorkLogSearchAgent(BaseAgent):
    """作業記録検索専門エージェント"""

    def __init__(self):
        super().__init__()
        self.master_resolver = MasterDataResolver()
        self.data_access = DataAccessLayer(create_mongodb_client())

    def _setup_llm(self):
        """LLM設定（軽量化）"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        from ..core.config import settings

        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1,
            google_api_key=settings.google_ai.api_key,
            max_tokens=1024,
            timeout=30,
        )

    def _setup_tools(self) -> List:
        """ツールの設定 - 循環インポートを避けるため空のリストを返す"""
        return []

    def _create_system_prompt(self) -> str:
        """
        KV-Cache最適化された固定システムプロンプト
        AIエージェント構築のポイント: プロンプト構造の安定化
        """
        return """あなたは作業記録の検索・分析専門家「WorkLogSearchAgent」です。

## 専門領域
蓄積された農業作業記録を検索・集計し、ユーザーの質問に応じて適切な情報を提供します。

## 主要機能
### 作業記録の検索・分析 ⭐
- 期間・圃場・作物・作業種別での絞り込み検索
- 防除履歴、施肥履歴の時系列表示
- 作業頻度・使用資材の統計分析
- 異常パターンの検出と報告
- 作業実績の可視化とレポート生成

## 対応可能な検索・分析
### 時系列検索
- **期間指定**: 「先月の防除記録を教えて」「過去3ヶ月の作業履歴」
- **最新記録**: 「トマトハウスの最新作業は？」「昨日の作業記録」
- **定期作業**: 「防除の間隔は適切？」「施肥のタイミング分析」

### 圃場・作物別分析
- **圃場別実績**: 「第1ハウスの今月の作業量」
- **作物別統計**: 「トマトの防除回数推移」
- **比較分析**: 「各圃場の作業効率比較」

### 資材・作業者分析
- **使用資材統計**: 「ダコニールの使用頻度」
- **作業者別実績**: 「田中さんの作業記録」
- **コスト分析**: 「農薬コストの推移」

### 異常・アラート検索
- **作業漏れ検出**: 「防除間隔が空きすぎている圃場」
- **過使用警告**: 「同一農薬の連続使用」
- **品質異常**: 「収穫量の大幅変動」

## 検索結果の提供形式
### 1. リスト形式
```
📋 検索結果 (3件)

1. 【2025-07-23】トマトハウス - 防除作業
   💊 ダコニール1000 (1000倍希釈)
   👤 作業者: 田中太郎

2. 【2025-07-20】トマトハウス - 施肥作業
   🌱 化成肥料8-8-8 (10kg)
   👤 作業者: 佐藤花子
```

### 2. 統計・集計形式
```
📊 トマトハウス 作業統計 (過去30日)

防除作業: 3回 (平均10日間隔)
施肥作業: 2回 (平均15日間隔)
収穫作業: 15回 (合計450kg)

⚠️ 注意: 防除間隔が通常より長めです
```

### 3. 時系列形式
```
📈 防除履歴タイムライン

7/23 ダコニール1000 (殺菌剤)
7/15 アブラムシコロリ (殺虫剤)
7/08 ダコニール1000 (殺菌剤)
7/01 モレスタン (殺菌剤)

🔄 農薬ローテーション: 良好
```

## 応答方針
1. 検索条件の明確化（曖昧な場合は確認）
2. 関連情報の積極的な提示
3. 異常パターンがあれば警告
4. 改善提案の追加
5. 必要に応じてグラフ・表形式での整理

## 利用可能ツール
- work_log_search: 作業記録の高度検索・分析

## 質問例と応答例
```
ユーザー: 「トマトハウスの先月の防除記録を教えて」

システム: 「📋 トマトハウス 防除記録 (6月分)

【6/28】ダコニール1000 (1000倍) - 田中太郎
【6/21】アブラムシコロリ (2000倍) - 佐藤花子  
【6/14】ダコニール1000 (1000倍) - 田中太郎
【6/07】モレスタン (3000倍) - 田中太郎

📊 統計情報:
- 防除回数: 4回 (平均7日間隔)
- 使用農薬: 3種類
- 作業者: 2名

✅ 農薬ローテーション: 適切
✅ 防除間隔: 標準的

次回防除予定: 7/5頃（推奨）」
```

作業記録の検索・分析について、何でもお聞きください！
※登録は別の専門エージェントが担当します。"""

    async def search_work_logs(self, query: str, user_id: str) -> Dict[str, any]:
        """
        作業記録を検索するメイン処理

        Args:
            query: ユーザーの検索クエリ
            user_id: ユーザーID

        Returns:
            検索結果の辞書
        """
        try:
            # 1. クエリ解析
            search_params = await self._parse_search_query(query)

            # 2. データベース検索
            search_results = await self._execute_search(search_params, user_id)

            # 3. 結果分析・集計
            analyzed_results = await self._analyze_results(search_results, search_params)

            # 4. 結果整形
            formatted_response = self._format_search_results(analyzed_results, search_params)

            return formatted_response

        except Exception as e:
            logger.error(f"作業記録検索エラー: {e}")
            return {"success": False, "error": str(e), "message": "作業記録の検索中にエラーが発生しました。"}

    async def _parse_search_query(self, query: str) -> Dict[str, any]:
        """検索クエリを解析してパラメータを抽出"""
        import re
        from datetime import datetime, timedelta

        params = {
            "field_names": [],
            "crop_names": [],
            "material_names": [],
            "work_categories": [],
            "date_range": {},
            "limit": 50,
            "sort_order": "desc",
        }

        # 日付範囲の解析
        today = datetime.now()

        if "昨日" in query:
            yesterday = today - timedelta(days=1)
            params["date_range"] = {
                "start": yesterday.replace(hour=0, minute=0, second=0),
                "end": yesterday.replace(hour=23, minute=59, second=59),
            }
        elif "先月" in query or "前月" in query:
            last_month = today.replace(day=1) - timedelta(days=1)
            start_of_last_month = last_month.replace(day=1)
            params["date_range"] = {
                "start": start_of_last_month,
                "end": last_month.replace(hour=23, minute=59, second=59),
            }
        elif "今月" in query or "当月" in query:
            start_of_month = today.replace(day=1, hour=0, minute=0, second=0)
            params["date_range"] = {"start": start_of_month, "end": today}
        elif "過去" in query:
            days_match = re.search(r"過去(\d+)日", query)
            weeks_match = re.search(r"過去(\d+)週間", query)
            months_match = re.search(r"過去(\d+)ヶ?月", query)

            if days_match:
                days = int(days_match.group(1))
                params["date_range"] = {"start": today - timedelta(days=days), "end": today}
            elif weeks_match:
                weeks = int(weeks_match.group(1))
                params["date_range"] = {"start": today - timedelta(weeks=weeks), "end": today}
            elif months_match:
                months = int(months_match.group(1))
                params["date_range"] = {"start": today - timedelta(days=months * 30), "end": today}

        # 圃場名の抽出
        field_patterns = [
            r"([^、。\s]+)(?:ハウス|畑|田|圃場)",
            r"第(\d+)(?:ハウス|畑|圃場)",
        ]

        for pattern in field_patterns:
            matches = re.findall(pattern, query)
            params["field_names"].extend(matches)

        # 作物名の抽出
        crop_keywords = ["トマト", "キュウリ", "ナス", "ピーマン", "イチゴ"]
        for crop in crop_keywords:
            if crop in query:
                params["crop_names"].append(crop)

        # 作業種別の抽出
        work_type_map = {
            "防除": ["防除", "農薬", "散布"],
            "施肥": ["施肥", "肥料", "追肥"],
            "栽培": ["播種", "定植", "摘心"],
            "収穫": ["収穫", "収穫量"],
            "管理": ["草刈り", "清掃", "点検"],
        }

        for work_type, keywords in work_type_map.items():
            if any(keyword in query for keyword in keywords):
                params["work_categories"].append(work_type)

        # 件数制限の調整
        if "全て" in query or "すべて" in query:
            params["limit"] = 1000
        elif "最新" in query:
            params["limit"] = 10

        return params

    async def _execute_search(self, params: Dict, user_id: str) -> List[Dict]:
        """パラメータに基づいてデータベース検索を実行"""
        results = await self.data_access.search_work_logs(params, user_id)
        logger.info(f"WorkLogSearchAgent: 作業記録検索結果: {len(results)}件")
        return results

    async def _analyze_results(self, results: List[Dict], params: Dict) -> Dict[str, any]:
        """検索結果を分析・集計"""
        if not results:
            return {"total_count": 0, "results": [], "statistics": {}, "patterns": [], "recommendations": []}

        # 基本統計
        work_category_counts = {}
        field_counts = {}
        material_counts = {}

        for record in results:
            # 作業種別の集計
            category = record.get("category", "その他")
            work_category_counts[category] = work_category_counts.get(category, 0) + 1

            # 圃場の集計
            extracted_data = record.get("extracted_data", {})
            field_name = extracted_data.get("field_name")
            if field_name:
                field_counts[field_name] = field_counts.get(field_name, 0) + 1

            # 資材の集計
            material_names = extracted_data.get("material_names", [])
            for material in material_names:
                material_counts[material] = material_counts.get(material, 0) + 1

        # パターン分析
        patterns = []
        if len(results) >= 3:
            patterns.append(self._analyze_work_intervals(results))
            patterns.append(self._analyze_material_rotation(results))

        return {
            "total_count": len(results),
            "results": results,
            "statistics": {
                "work_categories": work_category_counts,
                "fields": field_counts,
                "materials": material_counts,
            },
            "patterns": [p for p in patterns if p],
            "recommendations": self._generate_recommendations(results, params),
        }

    def _analyze_work_intervals(self, results: List[Dict]) -> Optional[Dict]:
        """作業間隔の分析"""
        # 防除作業の間隔分析
        prevention_records = [r for r in results if r.get("category") == "防除"]

        if len(prevention_records) < 2:
            return None

        # 日付でソート
        prevention_records.sort(key=lambda x: x["work_date"])

        intervals = []
        for i in range(1, len(prevention_records)):
            prev_date = prevention_records[i - 1]["work_date"]
            curr_date = prevention_records[i]["work_date"]
            interval = (curr_date - prev_date).days
            intervals.append(interval)

        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            return {
                "type": "work_interval",
                "category": "防除",
                "average_days": round(avg_interval, 1),
                "intervals": intervals,
                "assessment": "適切" if 7 <= avg_interval <= 14 else "要注意",
            }

        return None

    def _analyze_material_rotation(self, results: List[Dict]) -> Optional[Dict]:
        """農薬ローテーションの分析"""
        prevention_records = [
            r
            for r in results
            if r.get("category") == "防除" and r.get("extracted_data", {}).get("material_names")
        ]

        if len(prevention_records) < 3:
            return None

        # 時系列で並び替え
        prevention_records.sort(key=lambda x: x["work_date"])

        # 連続使用のチェック
        consecutive_materials = []
        prev_materials = None

        for record in prevention_records:
            materials = record.get("extracted_data", {}).get("material_names", [])
            if materials:
                if prev_materials and any(m in prev_materials for m in materials):
                    consecutive_materials.append({"date": record["work_date"], "materials": materials})
                prev_materials = materials

        return {
            "type": "material_rotation",
            "consecutive_uses": len(consecutive_materials),
            "assessment": "良好" if len(consecutive_materials) == 0 else "改善推奨",
            "details": consecutive_materials[:3],  # 最新3件まで
        }

    def _generate_recommendations(self, results: List[Dict], params: Dict) -> List[str]:
        """結果に基づく推奨事項の生成"""
        recommendations = []

        if not results:
            recommendations.append("該当する作業記録が見つかりませんでした。検索条件を見直してください。")
            return recommendations

        # 最新作業からの日数チェック
        latest_record = max(results, key=lambda x: x["work_date"])
        days_since_latest = (datetime.now() - latest_record["work_date"]).days

        if days_since_latest > 14:
            recommendations.append(
                f"最新作業から{days_since_latest}日経過しています。定期作業の確認をお勧めします。"
            )

        # 作業バランスチェック
        category_counts = {}
        for record in results:
            category = record.get("category", "その他")
            category_counts[category] = category_counts.get(category, 0) + 1

        if category_counts.get("防除", 0) > category_counts.get("施肥", 0) * 2:
            recommendations.append("防除作業が多めです。施肥バランスの確認をお勧めします。")

        return recommendations

    def _format_search_results(self, analyzed_results: Dict, params: Dict) -> Dict[str, any]:
        """検索結果の整形"""
        results = analyzed_results["results"]
        statistics = analyzed_results["statistics"]

        if not results:
            return {
                "success": True,
                "message": "該当する作業記録が見つかりませんでした。",
                "total_count": 0,
                "results": [],
                "recommendations": analyzed_results["recommendations"],
            }

        # 結果のフォーマット
        formatted_results = []
        for record in results:
            formatted_record = {
                "log_id": record["log_id"],
                "work_date": record["work_date"].strftime("%Y-%m-%d"),
                "category": record["category"],
                "original_message": record["original_message"],
                "extracted_data": record.get("extracted_data", {}),
                "created_at": record["created_at"].strftime("%Y-%m-%d %H:%M"),
            }
            # Add a human-readable summary
            summary_parts = []
            summary_parts.append(f"日付: {formatted_record['work_date']}")

            extracted_data = formatted_record["extracted_data"]
            field_name = extracted_data.get("field_name")
            if field_name:
                summary_parts.append(f"圃場: {field_name}")

            work_content = extracted_data.get("work_content")
            if work_content:
                summary_parts.append(f"作業内容: {work_content}")
            elif formatted_record["category"]:
                summary_parts.append(f"作業カテゴリ: {formatted_record['category']}")

            if not work_content and not formatted_record["category"]:
                summary_parts.append(f"メッセージ: {formatted_record['original_message']}")

            formatted_record["summary"] = " ".join(summary_parts)
            formatted_results.append(formatted_record)

        return {
            "success": True,
            "total_count": analyzed_results["total_count"],
            "results": formatted_results,
            "statistics": statistics,
            "patterns": analyzed_results["patterns"],
            "recommendations": analyzed_results["recommendations"],
            "message": f'{analyzed_results["total_count"]}件の作業記録が見つかりました。',
        }
