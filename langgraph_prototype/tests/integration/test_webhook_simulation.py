"""
LINE Webhook シミュレーションテスト

実際のLINE Webhook処理フローをシミュレートするテスト
"""

import asyncio
import sys
import os
from unittest.mock import Mock, patch, AsyncMock
import json

# LangGraphプロトタイプのパスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../src'))

from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState


async def simulate_webhook_message_processing(message_text: str, user_id: str = "test_user"):
    """
    LINE Webhookメッセージ処理のシミュレーション
    
    Args:
        message_text: ユーザーメッセージ
        user_id: ユーザーID
    
    Returns:
        処理結果
    """
    
    print(f"\n📱 LINE メッセージシミュレーション")
    print(f"   ユーザー: {user_id}")
    print(f"   メッセージ: {message_text}")
    print(f"   {'='*50}")
    
    try:
        # Step 1: セッション管理と連携したthread_idの取得をシミュレート
        thread_id = f"thread_{user_id}_{hash(message_text) % 1000}"
        
        # Step 2: LangGraphの状態を作成
        initial_state = AgriAgentState(
            messages=[{"role": "user", "content": message_text}],
            user_id=user_id,
            thread_id=thread_id,
            next_agent="",
            pending_confirmation={},
            final_response="",
            intermediate_steps=[]
        )
        
        print(f"🧠 LangGraph処理開始...")
        
        # Step 3: LangGraphワークフロー実行
        import time
        start_time = time.time()
        
        result = await langgraph_app.ainvoke(initial_state)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Step 4: 結果の解析
        response_text = result.get("final_response", "申し訳ございませんが、処理できませんでした。")
        intermediate_steps = result.get("intermediate_steps", [])
        
        print(f"✅ LangGraph処理完了")
        print(f"   処理時間: {response_time:.2f}秒")
        print(f"   実行ステップ: {len(intermediate_steps)}個")
        
        # Step 5: 実行されたエージェントの確認
        executed_agents = []
        for step in intermediate_steps:
            if "read_agent" in step.lower():
                executed_agents.append("ReadAgent")
            elif "write_agent" in step.lower():
                executed_agents.append("WriteAgent")
            elif "supervisor" in step.lower():
                executed_agents.append("SupervisorAgent")
        
        print(f"   実行エージェント: {', '.join(set(executed_agents))}")
        
        # Step 6: 確認フロー対応の結果解析
        is_confirmation = _is_confirmation_response(response_text)
        if is_confirmation:
            print(f"🔄 確認フローが必要です")
        
        # Step 7: LINE応答シミュレート
        print(f"\n📤 LINE応答:")
        print(f"   {response_text}")
        
        return {
            "success": True,
            "response_text": response_text,
            "response_time": response_time,
            "executed_agents": executed_agents,
            "intermediate_steps": intermediate_steps,
            "is_confirmation": is_confirmation,
            "user_id": user_id,
            "thread_id": thread_id
        }
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        
        # エラー時の応答をシミュレート
        error_message = "😅 申し訳ございません。処理中にエラーが発生しました。\nしばらくしてから再度お試しください。"
        print(f"\n📤 エラー応答:")
        print(f"   {error_message}")
        
        return {
            "success": False,
            "error": str(e),
            "response_text": error_message,
            "user_id": user_id
        }


def _is_confirmation_response(response_text: str) -> bool:
    """応答が確認を求めているかどうかを判定"""
    confirmation_keywords = [
        "登録しますか", "実行しますか", "よろしいですか", "確認", 
        "はい」と", "OK」と", "実行する場合", "登録する場合"
    ]
    return any(keyword in response_text for keyword in confirmation_keywords)


async def run_webhook_simulation_tests():
    """複数のWebhookシミュレーションテストを実行"""
    
    print("🚀 LINE Webhook シミュレーションテスト開始")
    print("=" * 60)
    
    # テストケース定義
    test_cases = [
        {
            "message": "A畑の情報を教えて",
            "user_id": "user_001", 
            "expected_agent": "ReadAgent",
            "description": "圃場情報検索テスト"
        },
        {
            "message": "昨日トマトの水やりをしました",
            "user_id": "user_002",
            "expected_agent": "WriteAgent", 
            "description": "作業記録登録テスト"
        },
        {
            "message": "最近の作業履歴を見せて",
            "user_id": "user_003",
            "expected_agent": "ReadAgent",
            "description": "作業履歴検索テスト"
        },
        {
            "message": "今日収穫作業を行いました",
            "user_id": "user_004",
            "expected_agent": "WriteAgent",
            "description": "収穫記録登録テスト"
        },
        {
            "message": "こんにちは",
            "user_id": "user_005",
            "expected_agent": "ReadAgent",  # デフォルト
            "description": "あいさつメッセージテスト"
        }
    ]
    
    results = []
    total_tests = len(test_cases)
    successful_tests = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print("-" * 40)
        
        result = await simulate_webhook_message_processing(
            test_case["message"], 
            test_case["user_id"]
        )
        
        results.append({
            "test_case": test_case,
            "result": result
        })
        
        if result["success"]:
            successful_tests += 1
            
            # 期待されるエージェントが実行されたかチェック
            executed_agents = result.get("executed_agents", [])
            expected_agent = test_case["expected_agent"]
            
            if expected_agent in executed_agents:
                print(f"✅ 期待されたエージェント ({expected_agent}) が実行されました")
            else:
                print(f"⚠️ 期待されたエージェント ({expected_agent}) が実行されませんでした")
                print(f"   実行されたエージェント: {executed_agents}")
        
        print(f"\n{'='*60}")
    
    # 結果サマリー
    print(f"\n📊 テスト結果サマリー")
    print(f"   総テスト数: {total_tests}")
    print(f"   成功: {successful_tests}")
    print(f"   失敗: {total_tests - successful_tests}")
    print(f"   成功率: {(successful_tests / total_tests) * 100:.1f}%")
    
    # パフォーマンス解析
    response_times = [r["result"].get("response_time", 0) for r in results if r["result"]["success"]]
    if response_times:
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        print(f"\n⏱️ パフォーマンス解析")
        print(f"   平均応答時間: {avg_response_time:.2f}秒")
        print(f"   最大応答時間: {max_response_time:.2f}秒")
        print(f"   最小応答時間: {min_response_time:.2f}秒")
        print(f"   目標達成: {'✅' if avg_response_time <= 3.0 else '❌'} (3秒以内)")
    
    print(f"\n🎉 LINE Webhook シミュレーションテスト完了")
    
    return results


if __name__ == "__main__":
    # Webhookシミュレーションテストの実行
    asyncio.run(run_webhook_simulation_tests())