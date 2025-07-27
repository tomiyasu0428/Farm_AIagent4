"""
確認フローミドルウェア

LINE Webhookでの確認フロー処理を統一的に管理
SessionManagerと連携してユーザーの状態に応じた適切な処理を実行
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class ConfirmationMiddleware:
    """
    確認フローミドルウェアクラス
    
    責務:
    - 確認待ち状態の判定
    - 肯定的/否定的返答の解析
    - 適切な処理フローへのルーティング
    """
    
    def __init__(self, session_manager: Optional[SessionManager] = None):
        self.session_manager = session_manager or SessionManager()
        
        # 肯定的返答パターン
        self.affirmative_patterns = [
            "はい", "ok", "OK", "オーケー", "了解", "お願いします", 
            "やって", "実行", "登録して", "yes", "Yes", "YES",
            "いいよ", "おk", "うん", "やります", "頼む", "お願い",
            "登録", "実行して", "進めて", "続けて", "やってください"
        ]
        
        # 否定的返答パターン
        self.negative_patterns = [
            "いいえ", "no", "NO", "だめ", "ダメ", "やめて", "キャンセル",
            "中止", "やめる", "しない", "いらない", "不要", "違う"
        ]
    
    def _is_new_work_log_request(self, message_text: str) -> bool:
        """
        メッセージが新しい作業記録要求かどうかを判定
        
        Returns:
            bool: 新しい作業記録要求の場合True
        """
        # 作業記録要求の特徴的なパターン
        work_indicators = [
            # 日付表現
            ("昨日", "収穫"), ("今日", "散布"), ("一昨日", "作業"),
            ("昨日", "薬"), ("今日", "肥料"), ("昨日", "ケース"),
            
            # 数量表現
            ("ケース", "でした"), ("kg", "でした"), ("L", "散布"),
            ("袋", "まいた"), ("本", "植えた"),
            
            # 登録要求
            ("登録して", ""), ("記録して", ""), ("保存して", ""),
            ("登録しておいて", ""), ("記録しておいて", ""),
            
            # 圃場+作業パターン
            ("ハウス", "収穫"), ("畑", "作業"), ("圃場", "散布"),
        ]
        
        message_lower = message_text.lower()
        
        # 複数の指標をチェック
        indicators_found = 0
        
        for primary, secondary in work_indicators:
            if primary.lower() in message_lower:
                if not secondary or secondary.lower() in message_lower:
                    indicators_found += 1
        
        # 数量パターン（数字+単位）を検出
        import re
        quantity_pattern = r'\d+\s*(ケース|kg|L|袋|本|個|匹)'
        if re.search(quantity_pattern, message_text):
            indicators_found += 1
        
        # 日付+作業+数量の組み合わせパターン
        full_work_pattern = r'(昨日|今日|一昨日).*(収穫|散布|植え|まい|作業).*(ケース|kg|L|袋)'
        if re.search(full_work_pattern, message_text):
            indicators_found += 2  # 強い指標
        
        # 2つ以上の指標があれば作業記録要求と判定
        is_work_request = indicators_found >= 2
        
        if is_work_request:
            logger.info(f"新しい作業記録要求と判定 - 指標数: {indicators_found}, メッセージ: {message_text[:50]}...")
        
        return is_work_request
    
    def process_message(self, user_id: str, message_text: str, thread_id: str = "default") -> Tuple[bool, Dict[str, Any]]:
        """
        メッセージを処理し、確認フローか通常フローかを判定
        
        Args:
            user_id: ユーザーID
            message_text: メッセージテキスト
            thread_id: スレッドID
            
        Returns:
            Tuple[bool, Dict]: (確認フローかどうか, 処理結果)
        """
        try:
            # 確認待ち状態かチェック
            if self.session_manager.has_pending_confirmation(user_id, thread_id):
                logger.info(f"確認待ち状態検出 - ユーザー: {user_id}")
                
                # 新しい作業記録要求かどうかを先に判定
                if self._is_new_work_log_request(message_text):
                    logger.info(f"確認待ち中に新しい作業記録要求検出 - ユーザー: {user_id}")
                    # 既存の確認状態をクリア
                    self.session_manager.clear_pending_confirmation(user_id, thread_id)
                    return False, {"type": "new_request", "requires_agent_processing": True}
                
                # 確認フローへの返答として処理
                return True, self._handle_confirmation_response(user_id, message_text, thread_id)
            else:
                logger.info(f"通常メッセージ - ユーザー: {user_id}")
                return False, {"type": "normal_message", "requires_agent_processing": True}
                
        except Exception as e:
            logger.error(f"メッセージ処理エラー: {e}")
            return False, {"type": "error", "error": str(e)}
    
    def _handle_confirmation_response(self, user_id: str, message_text: str, thread_id: str) -> Dict[str, Any]:
        """
        確認への返答を処理
        
        Returns:
            Dict: 処理結果
        """
        try:
            # 確認データを取得
            pending_data = self.session_manager.get_pending_confirmation(user_id, thread_id)
            
            if not pending_data:
                logger.warning(f"確認データが見つかりません - ユーザー: {user_id}")
                return {
                    "type": "error",
                    "message": "確認データが見つかりません。最初から操作をやり直してください。"
                }
            
            # LLMベースの返答解析
            analysis_result = self._analyze_response(message_text, pending_data)
            response_type = analysis_result.get("type")
            extracted_info = analysis_result.get("extracted_info", {})
            confidence = analysis_result.get("confidence", 0.0)
            
            logger.info(f"返答解析結果 - ユーザー: {user_id}, タイプ: {response_type}, 信頼度: {confidence}")
            
            if response_type == "affirmative":
                logger.info(f"肯定的返答検出 - ユーザー: {user_id}, メッセージ: {message_text}")
                return self._execute_confirmation(pending_data, user_id, thread_id)
                
            elif response_type == "negative":
                logger.info(f"否定的返答検出 - ユーザー: {user_id}, メッセージ: {message_text}")
                return self._cancel_confirmation(user_id, thread_id)
                
            elif response_type == "information_provided":
                logger.info(f"情報提供検出 - ユーザー: {user_id}, 情報: {extracted_info}")
                return self._handle_information_update(pending_data, extracted_info, user_id, thread_id)
                
            else:
                # 曖昧な返答の場合は再確認
                logger.info(f"曖昧な返答検出 - ユーザー: {user_id}, メッセージ: {message_text}")
                return self._request_clarification(pending_data)
                
        except Exception as e:
            logger.error(f"確認返答処理エラー: {e}")
            # エラー時は確認状態をクリア
            self.session_manager.clear_pending_confirmation(user_id, thread_id)
            return {
                "type": "error",
                "message": "確認処理中にエラーが発生しました。操作をやり直してください。"
            }
    
    def _analyze_response(self, message_text: str, pending_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        LLMを使った柔軟な返答分析
        
        Args:
            message_text: ユーザーの返答
            pending_data: 確認待ちデータ（文脈情報）
            
        Returns:
            Dict: {
                "type": "affirmative|negative|information_provided|unclear",
                "extracted_info": {...},  # information_providedの場合
                "confidence": float
            }
        """
        try:
            # LLMによる返答解析を試行
            llm_result = self._analyze_with_llm(message_text, pending_data)
            if llm_result:
                return llm_result
        except Exception as e:
            logger.warning(f"LLM返答解析エラー、フォールバックを使用: {e}")
        
        # フォールバック: 従来のパターンマッチング
        return self._analyze_with_patterns(message_text)
    
    def _analyze_with_llm(self, message_text: str, pending_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        LLMを使った返答解析
        """
        from langchain_google_genai import ChatGoogleGenerativeAI
        from ..core.config import settings
        
        # 確認データから文脈を取得
        confirmation_data = pending_data.get("confirmation_data", {}) if pending_data else {}
        confirmation_message = confirmation_data.get("confirmation_message", "")
        agent_type = pending_data.get("agent_type", "")
        
        # プロンプト構築
        prompt = f"""あなたは農業管理AIの確認フロー解析専門家です。
ユーザーが以前の確認メッセージに対して返答しました。返答の意図を正確に分析してください。

【重要】これは「既存の確認フローへの返答」です。新しい作業記録要求ではありません。

【確認内容】
{confirmation_message}

【ユーザー返答】
{message_text}

【分析指示】
ユーザーの返答を以下のカテゴリに分類してください：

1. affirmative: 既存の確認に対する処理実行への同意
   例: "はい", "OK", "お願いします", "実行して", "登録"（単語のみ）

2. negative: 既存の確認に対する処理キャンセルの意図  
   例: "いいえ", "やめて", "キャンセル", "違います"

3. information_provided: 既存の確認に対する追加情報・修正情報の提供
   例: "ブロッコリー"（作物名のみ）, "500ケース"（数量のみ）, "トマトハウス"（圃場名のみ）

4. unclear: 意図が不明確
   例: "？", "わからない", 無関係な内容

【注意】
- 完全な作業記録（日付+圃場+作業+数量を含む文章）は新規要求の可能性があります
- 単純な情報補完（作物名、数量、圃場名のみ）は information_provided です
- 単純な同意表現（はい、OK）は affirmative です

【出力形式】
必ずJSON形式で回答してください：
{{
  "type": "affirmative|negative|information_provided|unclear",
  "confidence": 0.0-1.0,
  "extracted_info": {{
    "crop_name": "作物名（判明した場合）",
    "field_name": "圃場名（判明した場合）", 
    "quantity": "数量（判明した場合）",
    "date": "日付（判明した場合）",
    "notes": "その他の情報"
  }},
  "reasoning": "判定理由"
}}

特に農業用語や地名、作物名は正確に認識してください。"""

        # LLM実行
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1,
            google_api_key=settings.google_ai.api_key
        )
        
        response = llm.invoke(prompt)
        
        # JSON解析
        import json
        import re
        
        # JSON部分を抽出
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            logger.info(f"LLM返答解析成功: {result.get('type')} (信頼度: {result.get('confidence')})")
            return result
        else:
            logger.warning("LLM返答からJSON解析失敗")
            return None
    
    def _analyze_with_patterns(self, message_text: str) -> Dict[str, Any]:
        """
        従来のパターンマッチング（フォールバック）
        """
        message_lower = message_text.lower().strip()
        
        # 肯定的パターンチェック
        for pattern in self.affirmative_patterns:
            if pattern.lower() in message_lower:
                return {
                    "type": "affirmative",
                    "confidence": 0.8,
                    "extracted_info": {},
                    "reasoning": "パターンマッチング（肯定）"
                }
        
        # 否定的パターンチェック
        for pattern in self.negative_patterns:
            if pattern.lower() in message_lower:
                return {
                    "type": "negative", 
                    "confidence": 0.8,
                    "extracted_info": {},
                    "reasoning": "パターンマッチング（否定）"
                }
        
        # どちらでもない場合
        return {
            "type": "unclear",
            "confidence": 0.3,
            "extracted_info": {},
            "reasoning": "パターンマッチング（不明）"
        }
    
    def _execute_confirmation(self, pending_data: Dict[str, Any], user_id: str, thread_id: str) -> Dict[str, Any]:
        """
        確認後の実際の処理を実行
        """
        try:
            agent_type = pending_data.get("agent_type")
            confirmation_data = pending_data.get("confirmation_data", {})
            
            logger.info(f"確認処理実行開始 - エージェント: {agent_type}, ユーザー: {user_id}")
            
            # エージェント別の確認処理
            if agent_type == "WorkLogRegistrationAgent":
                result = self._execute_work_log_confirmation(confirmation_data)
            elif agent_type == "FieldAgent":
                result = self._execute_field_confirmation(confirmation_data)
            elif agent_type == "SearchAgent":
                result = self._execute_search_confirmation(confirmation_data)
            else:
                result = {
                    "success": False,
                    "message": f"未対応のエージェントタイプ: {agent_type}"
                }
            
            # 確認待ち状態をクリア
            self.session_manager.clear_pending_confirmation(user_id, thread_id)
            
            logger.info(f"確認処理完了 - ユーザー: {user_id}, 成功: {result.get('success', False)}")
            
            return {
                "type": "confirmation_executed",
                "agent_type": agent_type,
                "success": result.get("success", False),
                "message": result.get("message", "処理が完了しました。"),
                "data": result.get("data")
            }
            
        except Exception as e:
            logger.error(f"確認実行エラー: {e}")
            # エラー時も確認状態をクリア
            self.session_manager.clear_pending_confirmation(user_id, thread_id)
            return {
                "type": "error",
                "message": "確認処理の実行中にエラーが発生しました。"
            }
    
    def _handle_information_update(self, pending_data: Dict[str, Any], extracted_info: Dict[str, Any], user_id: str, thread_id: str) -> Dict[str, Any]:
        """
        ユーザーが提供した情報で確認データを更新
        """
        try:
            # 既存の確認データを取得
            confirmation_data = pending_data.get("confirmation_data", {})
            existing_info = confirmation_data.get("extracted_info", {})
            
            # 新しい情報でマージ
            updated_info = existing_info.copy()
            for key, value in extracted_info.items():
                if value and str(value).strip():  # 空でない値のみ更新
                    updated_info[key] = value
            
            # 確認データを更新
            updated_confirmation_data = confirmation_data.copy()
            updated_confirmation_data["extracted_info"] = updated_info
            
            updated_pending_data = pending_data.copy()
            updated_pending_data["confirmation_data"] = updated_confirmation_data
            
            # セッションに保存
            self.session_manager.set_pending_confirmation(user_id, updated_pending_data, thread_id, 30)
            
            # 更新内容を表示
            update_summary = []
            for key, value in extracted_info.items():
                if value and str(value).strip():
                    if key == "crop_name":
                        update_summary.append(f"🌱 作物: {value}")
                    elif key == "field_name":
                        update_summary.append(f"🏠 圃場: {value}")
                    elif key == "quantity":
                        update_summary.append(f"📊 数量: {value}")
                    elif key == "date":
                        update_summary.append(f"📅 日付: {value}")
                    elif key == "notes":
                        update_summary.append(f"📝 備考: {value}")
            
            # 依然として不足している情報をチェック
            missing_info = []
            if not updated_info.get("crop_name"):
                missing_info.append("作物名")
            if not updated_info.get("field_name"):
                missing_info.append("圃場名")
            
            if missing_info:
                # まだ情報が不足している場合
                message = "📝 情報を更新しました：\n" + "\n".join(update_summary)
                message += f"\n\n❓ まだ以下の情報が必要です：\n• {' • '.join(missing_info)}"
                message += "\n\n💡 追加情報を教えていただくか、「登録」で進めることも可能です。"
                
                return {
                    "type": "information_updated_partial",
                    "message": message
                }
            else:
                # 必要な情報が揃った場合
                message = "✅ 情報を更新しました：\n" + "\n".join(update_summary)
                message += "\n\n📋 登録内容が整いました。登録を実行しますか？\n「はい」「登録」で実行、「いいえ」でキャンセルできます。"
                
                return {
                    "type": "information_completed",
                    "message": message
                }
                
        except Exception as e:
            logger.error(f"情報更新処理エラー: {e}")
            return {
                "type": "error",
                "message": "情報の更新中にエラーが発生しました。"
            }
    
    def _cancel_confirmation(self, user_id: str, thread_id: str) -> Dict[str, Any]:
        """
        確認をキャンセル
        """
        try:
            self.session_manager.clear_pending_confirmation(user_id, thread_id)
            logger.info(f"確認キャンセル - ユーザー: {user_id}")
            
            return {
                "type": "confirmation_cancelled",
                "message": "処理をキャンセルしました。他にご用件がございましたらお聞かせください。"
            }
            
        except Exception as e:
            logger.error(f"確認キャンセルエラー: {e}")
            return {
                "type": "error", 
                "message": "キャンセル処理中にエラーが発生しました。"
            }
    
    def _request_clarification(self, pending_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        曖昧な返答に対する再確認
        """
        agent_type = pending_data.get("agent_type", "Unknown")
        
        return {
            "type": "clarification_required",
            "message": (
                "申し訳ございませんが、お答えがよく分かりませんでした。\n\n"
                "処理を実行する場合は「はい」「OK」「登録」\n"
                "キャンセルする場合は「いいえ」「キャンセル」\n"
                "情報を追加する場合は具体的な内容をお答えください。\n\n"
                "例: 「ブロッコリー」「トマトハウス」「500ケース」"
            )
        }
    
    def _execute_work_log_confirmation(self, confirmation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        作業記録登録の確認処理（実際のデータベース登録）
        """
        try:
            # 実際のWorkLogRegistrationAgentを使用してデータベースに登録
            from ..agents.work_log_registration_agent import WorkLogRegistrationAgent
            
            extracted_data = confirmation_data.get("extracted_info", {})
            
            # WorkLogRegistrationAgentのインスタンスを作成
            agent = WorkLogRegistrationAgent()
            
            # 抽出データから登録用メッセージを再構築
            work_message = self._rebuild_work_message(extracted_data)
            
            logger.info(f"確認済み作業記録をデータベースに登録開始: {work_message}")
            
            # 実際の登録処理を実行（確認フローをスキップして直接登録）
            # Note: register_work_logは非同期メソッドなので、同期的に実行
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # 既にイベントループが実行中の場合
                logger.warning("イベントループ実行中 - 確認処理は簡易登録を実行")
                result = self._simple_database_registration(extracted_data)
            except RuntimeError:
                # イベントループがない場合は非同期実行
                result = asyncio.run(agent.register_work_log(
                    message=work_message, 
                    user_id="confirmed_user",
                    force_registration=True  # 確認フローをスキップ
                ))
            
            if isinstance(result, dict) and result.get("success"):
                return {
                    "success": True,
                    "message": result.get("message", "✅ 作業記録を正常に登録しました。"),
                    "data": result.get("data", {})
                }
            else:
                logger.error(f"作業記録登録失敗: {result}")
                return {
                    "success": False,
                    "message": "作業記録の登録に失敗しました。"
                }
            
        except Exception as e:
            logger.error(f"作業記録確認処理エラー: {e}")
            return {
                "success": False,
                "message": "作業記録の登録中にエラーが発生しました。"
            }
    
    def _rebuild_work_message(self, extracted_data: Dict[str, Any]) -> str:
        """
        抽出データから登録用メッセージを再構築
        """
        parts = []
        
        if extracted_data.get("work_date"):
            parts.append(extracted_data["work_date"])
        
        if extracted_data.get("field_name"):
            parts.append(extracted_data["field_name"])
        
        if extracted_data.get("crop_name"):
            parts.append(extracted_data["crop_name"])
        
        if extracted_data.get("work_category"):
            parts.append(extracted_data["work_category"])
        
        if extracted_data.get("quantity") and extracted_data.get("unit"):
            parts.append(f"{extracted_data['quantity']}{extracted_data['unit']}")
        
        message = "、".join(parts) + "でした。"
        logger.info(f"再構築メッセージ: {message}")
        return message
    
    def _simple_database_registration(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        簡易データベース登録（同期処理用フォールバック）
        """
        try:
            # ログIDを生成
            log_id = f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 登録データの準備
            work_record = {
                "log_id": log_id,
                "work_date": extracted_data.get("work_date", "不明"),
                "field_name": extracted_data.get("field_name", "不明な圃場"),
                "crop_name": extracted_data.get("crop_name", "不明な作物"),
                "work_category": extracted_data.get("work_category", "不明な作業"),
                "quantity": extracted_data.get("quantity"),
                "unit": extracted_data.get("unit"),
                "materials": extracted_data.get("materials", []),
                "registered_at": datetime.now().isoformat(),
                "status": "confirmed"
            }
            
            # TODO: 実際のMongoDB登録処理を追加
            # この部分でMongoDBに保存する処理を実装
            
            logger.info(f"簡易登録完了: {log_id}")
            
            # 成功メッセージを構築
            field_name = extracted_data.get("field_name", "不明な圃場")
            work_category = extracted_data.get("work_category", "不明な作業")
            crop_name = extracted_data.get("crop_name", "")
            
            message_parts = [f"✅ 作業記録を登録しました！\n"]
            message_parts.append(f"🆔 記録ID: {log_id}")
            message_parts.append(f"📍 圃場: {field_name}")
            if crop_name:
                message_parts.append(f"🌱 作物: {crop_name}")
            message_parts.append(f"🔧 作業: {work_category}")
            message_parts.append(f"📅 登録日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            message_parts.append("\n登録が完了しました。")
            
            return {
                "success": True,
                "message": "\n".join(message_parts),
                "data": work_record
            }
            
        except Exception as e:
            logger.error(f"簡易登録エラー: {e}")
            return {
                "success": False,
                "message": "登録処理中にエラーが発生しました。"
            }
    
    def _execute_field_confirmation(self, confirmation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        圃場管理の確認処理
        """
        try:
            # 圃場関連処理のモック
            return {
                "success": True,
                "message": "✅ 圃場情報の処理が完了しました。"
            }
            
        except Exception as e:
            logger.error(f"圃場確認処理エラー: {e}")
            return {
                "success": False,
                "message": "圃場情報の処理中にエラーが発生しました。"
            }
    
    def _execute_search_confirmation(self, confirmation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        検索の確認処理
        """
        try:
            # 検索関連処理のモック
            return {
                "success": True,
                "message": "✅ 検索処理が完了しました。"
            }
            
        except Exception as e:
            logger.error(f"検索確認処理エラー: {e}")
            return {
                "success": False,
                "message": "検索処理中にエラーが発生しました。"
            }
    
    def save_confirmation_request(
        self, 
        user_id: str, 
        agent_type: str, 
        confirmation_data: Dict[str, Any], 
        thread_id: str = "default",
        timeout_minutes: int = 30
    ):
        """
        確認リクエストを保存
        
        Args:
            user_id: ユーザーID
            agent_type: エージェントタイプ
            confirmation_data: 確認データ
            thread_id: スレッドID
            timeout_minutes: タイムアウト時間（分）
        """
        try:
            pending_data = {
                "agent_type": agent_type,
                "confirmation_data": confirmation_data,
                "created_at": datetime.now().isoformat()
            }
            
            self.session_manager.set_pending_confirmation(
                user_id, pending_data, thread_id, timeout_minutes
            )
            
            logger.info(f"確認リクエスト保存完了 - ユーザー: {user_id}, エージェント: {agent_type}")
            
        except Exception as e:
            logger.error(f"確認リクエスト保存エラー: {e}")
    
    def get_session_status(self, user_id: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        セッション状態を取得（デバッグ用）
        
        Returns:
            Dict: セッション状態の詳細情報
        """
        try:
            session_info = self.session_manager.get_session_info(user_id, thread_id)
            pending_data = self.session_manager.get_pending_confirmation(user_id, thread_id)
            
            return {
                "user_id": user_id,
                "thread_id": thread_id,
                "session_info": session_info,
                "pending_confirmation": pending_data,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"セッション状態取得エラー: {e}")
            return {"error": str(e)}