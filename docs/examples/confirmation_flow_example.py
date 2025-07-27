"""
確認フローミドルウェアの動作例

実際のLINE Webhookでの処理フローを詳細に説明
"""

from typing import Dict, Any
import json
from datetime import datetime

# 模擬SessionManager
class MockSessionManager:
    def __init__(self):
        self.sessions = {}  # 実際はRedis
    
    def has_pending_confirmation(self, user_id: str) -> bool:
        session = self.sessions.get(user_id, {})
        return session.get("pending_confirmation") is not None
    
    def save_session(self, user_id: str, data: Dict[str, Any]):
        self.sessions[user_id] = data
    
    def get_pending_confirmation(self, user_id: str) -> Dict:
        session = self.sessions.get(user_id, {})
        return session.get("pending_confirmation", {})

# 模擬LINE Webhook処理
def handle_line_message(user_id: str, message_text: str, session_manager: MockSessionManager):
    """
    LINE Webhookのメッセージ処理メイン関数
    これが「確認フローミドルウェア」の核心部分
    """
    
    print(f"\n=== 受信メッセージ ===")
    print(f"ユーザーID: {user_id}")
    print(f"メッセージ: {message_text}")
    
    # 🔍 ここが重要！確認待ち状態かどうかをチェック
    if session_manager.has_pending_confirmation(user_id):
        print("📋 確認待ち状態を検出 → 確認処理フローへ")
        return handle_confirmation_response(user_id, message_text, session_manager)
    else:
        print("🆕 通常メッセージ → 標準エージェント処理へ")
        return handle_normal_message(user_id, message_text, session_manager)

def handle_normal_message(user_id: str, message_text: str, session_manager: MockSessionManager):
    """通常のエージェント処理（1回目のメッセージ）"""
    
    print(f"🤖 AgentExecutorを新規作成して処理開始...")
    
    # 模擬エージェント処理
    if "収穫" in message_text and "ケース" in message_text:
        # WorkLogRegistrationAgentが動作
        print("📝 WorkLogRegistrationAgentが作業記録として認識")
        
        # 確認が必要と判定
        confirmation_data = {
            "agent_type": "WorkLogRegistrationAgent",
            "extracted_data": {
                "field_name": "鵡川の家裏",
                "work_type": "収穫", 
                "quantity": 1699,
                "unit": "ケース",
                "work_date": "昨日"
            },
            "original_message": message_text,
            "created_at": datetime.now().isoformat()
        }
        
        # 🎯 重要: セッションに確認データを保存
        session_manager.save_session(user_id, {
            "pending_confirmation": confirmation_data
        })
        
        response = (
            "以下の内容で作業記録を登録しますか？\n\n"
            "📍 圃場: 鵡川の家裏\n"
            "🥕 作業: 収穫\n" 
            "📦 数量: 1699ケース\n"
            "📅 日付: 昨日\n\n"
            "登録する場合は「はい」と返信してください。"
        )
        
        print(f"✅ 確認メッセージを生成: {response}")
        print(f"💾 セッションに確認データを保存完了")
        return response
    
    else:
        return "申し訳ございませんが、理解できませんでした。"

def handle_confirmation_response(user_id: str, message_text: str, session_manager: MockSessionManager):
    """確認への返答処理（2回目のメッセージ）"""
    
    print(f"🔄 確認処理フロー開始")
    
    # 保存されている確認データを取得
    pending_data = session_manager.get_pending_confirmation(user_id)
    print(f"📥 セッションから確認データを取得: {json.dumps(pending_data, indent=2, ensure_ascii=False)}")
    
    # 肯定的な返答かチェック
    if is_affirmative_response(message_text):
        print(f"✅ 肯定的な返答を検出: '{message_text}'")
        
        # エージェント種別に応じて実際の処理を実行
        agent_type = pending_data.get("agent_type")
        extracted_data = pending_data.get("extracted_data", {})
        
        if agent_type == "WorkLogRegistrationAgent":
            print(f"📝 WorkLogRegistrationAgentで実際の登録処理を実行")
            
            # 実際の登録処理（模擬）
            log_id = f"LOG-{datetime.now().strftime('%Y%m%d')}-001"
            
            result = (
                f"✅ 作業記録を登録しました！\n\n"
                f"🆔 記録ID: {log_id}\n"
                f"📍 圃場: {extracted_data['field_name']}\n"
                f"🥕 作業: {extracted_data['work_type']}\n"
                f"📦 数量: {extracted_data['quantity']}{extracted_data['unit']}\n"
                f"📅 日付: {extracted_data['work_date']}\n\n"
                f"登録が完了しました。"
            )
            
            print(f"🎉 登録完了メッセージを生成")
            
        # 🧹 重要: 確認待ち状態をクリア
        session_manager.save_session(user_id, {})
        print(f"🧹 セッションから確認データをクリア")
        
        return result
    
    else:
        print(f"❌ 否定的な返答: '{message_text}'")
        
        # 確認待ち状態をクリア  
        session_manager.save_session(user_id, {})
        print(f"🧹 セッションクリア（キャンセル）")
        
        return "処理をキャンセルしました。"

def is_affirmative_response(text: str) -> bool:
    """肯定的な返答かどうかを判定"""
    affirmative_patterns = [
        "はい", "ok", "OK", "オーケー", "了解", "お願いします", 
        "やって", "実行", "登録して", "yes", "Yes", "YES"
    ]
    return any(pattern in text.lower() for pattern in affirmative_patterns)

# 実行例
if __name__ == "__main__":
    session_manager = MockSessionManager()
    user_id = "LINE_USER_12345"
    
    print("🚀 確認フローミドルウェアのデモ実行\n")
    
    # === 1回目のメッセージ ===
    print("=" * 50)
    print("1回目のメッセージ（通常処理）")
    print("=" * 50)
    
    response1 = handle_line_message(
        user_id, 
        "昨日、鵡川の家裏、収穫1699ケースでした。登録しておいて",
        session_manager
    )
    print(f"\n📤 LINEへの返信: {response1}")
    
    # === 2回目のメッセージ ===  
    print("\n" + "=" * 50)
    print("2回目のメッセージ（確認処理）")
    print("=" * 50)
    
    response2 = handle_line_message(
        user_id,
        "はい",
        session_manager
    )
    print(f"\n📤 LINEへの返信: {response2}")
    
    # === 3回目のメッセージ（確認後）===
    print("\n" + "=" * 50) 
    print("3回目のメッセージ（確認完了後）")
    print("=" * 50)
    
    response3 = handle_line_message(
        user_id,
        "ありがとう",
        session_manager
    )
    print(f"\n📤 LINEへの返信: {response3}")