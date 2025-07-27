"""
ヘルスチェックとシステム状態確認テスト
"""

import asyncio
import sys
import os
from unittest.mock import Mock, patch, AsyncMock

# LangGraphプロトタイプのパスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../src'))

from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState


async def test_system_health():
    """システム全体のヘルスチェック"""
    
    print("🏥 システムヘルスチェック開始")
    print("=" * 50)
    
    # 1. LangGraphアプリケーションの初期化確認
    print("\n1. LangGraphアプリケーション確認")
    try:
        assert langgraph_app is not None
        print("✅ LangGraphアプリケーション: 正常に初期化済み")
    except Exception as e:
        print(f"❌ LangGraphアプリケーション: {e}")
        return False
    
    # 2. AgriAgentStateの作成確認
    print("\n2. AgriAgentState作成確認")
    try:
        test_state = AgriAgentState(
            messages=[{"role": "user", "content": "テスト"}],
            user_id="health_check_user",
            thread_id="health_check_thread",
            next_agent="",
            pending_confirmation={},
            final_response="",
            intermediate_steps=[]
        )
        assert test_state is not None
        print("✅ AgriAgentState: 正常に作成可能")
    except Exception as e:
        print(f"❌ AgriAgentState: {e}")
        return False
    
    # 3. LangGraphワークフロー実行確認
    print("\n3. LangGraphワークフロー実行確認")
    try:
        result = await langgraph_app.ainvoke(test_state)
        assert result is not None
        assert "final_response" in result
        print("✅ LangGraphワークフロー: 正常に実行可能")
        print(f"   応答例: {result['final_response'][:30]}...")
    except Exception as e:
        print(f"❌ LangGraphワークフロー: {e}")
        return False
    
    # 4. 主要エージェントの動作確認
    print("\n4. 主要エージェントの動作確認")
    
    # ReadAgentテスト
    read_state = AgriAgentState(
        messages=[{"role": "user", "content": "圃場の情報を教えて"}],
        user_id="health_read_user",
        thread_id="health_read_thread", 
        next_agent="",
        pending_confirmation={},
        final_response="",
        intermediate_steps=[]
    )
    
    try:
        read_result = await langgraph_app.ainvoke(read_state)
        read_steps = read_result.get("intermediate_steps", [])
        read_agent_executed = any("read_agent" in step.lower() for step in read_steps)
        
        if read_agent_executed:
            print("✅ ReadAgent: 正常に動作")
        else:
            print("⚠️ ReadAgent: 実行されませんでした")
            
    except Exception as e:
        print(f"❌ ReadAgent: {e}")
    
    # WriteAgentテスト
    write_state = AgriAgentState(
        messages=[{"role": "user", "content": "昨日作業を行いました"}],
        user_id="health_write_user",
        thread_id="health_write_thread",
        next_agent="",
        pending_confirmation={},
        final_response="",
        intermediate_steps=[]
    )
    
    try:
        write_result = await langgraph_app.ainvoke(write_state)
        write_steps = write_result.get("intermediate_steps", [])
        write_agent_executed = any("write_agent" in step.lower() for step in write_steps)
        
        if write_agent_executed:
            print("✅ WriteAgent: 正常に動作")
        else:
            print("⚠️ WriteAgent: 実行されませんでした")
            
    except Exception as e:
        print(f"❌ WriteAgent: {e}")
    
    # 5. パフォーマンス確認
    print("\n5. パフォーマンス確認")
    import time
    
    perf_state = AgriAgentState(
        messages=[{"role": "user", "content": "こんにちは"}],
        user_id="health_perf_user",
        thread_id="health_perf_thread",
        next_agent="",
        pending_confirmation={},
        final_response="",
        intermediate_steps=[]
    )
    
    try:
        start_time = time.time()
        perf_result = await langgraph_app.ainvoke(perf_state)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        print(f"✅ パフォーマンス: {response_time:.2f}秒")
        if response_time <= 3.0:
            print("   🎯 目標時間(3秒以内)達成")
        else:
            print("   ⚠️ 目標時間(3秒以内)未達成")
            
    except Exception as e:
        print(f"❌ パフォーマンステスト: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 システムヘルスチェック完了")
    
    return True


async def test_error_resilience():
    """エラー耐性テスト"""
    
    print("\n🛡️ エラー耐性テスト開始")
    print("=" * 50)
    
    error_cases = [
        {
            "name": "空メッセージ",
            "state": AgriAgentState(
                messages=[],
                user_id="error_user_1",
                thread_id="error_thread_1",
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
        },
        {
            "name": "不正形式メッセージ",
            "state": AgriAgentState(
                messages=[{"invalid": "format"}],
                user_id="error_user_2", 
                thread_id="error_thread_2",
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
        },
        {
            "name": "超長文メッセージ", 
            "state": AgriAgentState(
                messages=[{"role": "user", "content": "あ" * 10000}],
                user_id="error_user_3",
                thread_id="error_thread_3",
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
        }
    ]
    
    resilient_count = 0
    
    for case in error_cases:
        print(f"\n{case['name']}テスト:")
        try:
            result = await langgraph_app.ainvoke(case["state"])
            
            if result and "final_response" in result:
                print(f"✅ 適切にハンドリング: {result['final_response'][:50]}...")
                resilient_count += 1
            else:
                print("⚠️ 結果が不完全です")
                
        except Exception as e:
            print(f"❌ エラーが発生: {e}")
    
    print(f"\n📊 エラー耐性結果: {resilient_count}/{len(error_cases)} ケースで適切に処理")
    
    return resilient_count == len(error_cases)


async def run_comprehensive_health_check():
    """包括的ヘルスチェックの実行"""
    
    print("🔍 包括的システムヘルスチェック開始")
    print("🔄 LINE Webhook + LangGraph統合システム")
    print("=" * 70)
    
    # システムヘルスチェック
    health_ok = await test_system_health()
    
    # エラー耐性チェック 
    resilience_ok = await test_error_resilience()
    
    # 最終判定
    print("\n" + "=" * 70)
    print("📋 最終診断結果")
    print(f"   システム基本動作: {'✅ 正常' if health_ok else '❌ 異常'}")
    print(f"   エラー耐性: {'✅ 良好' if resilience_ok else '❌ 要改善'}")
    
    overall_status = health_ok and resilience_ok
    print(f"   総合判定: {'🎉 システム正常' if overall_status else '⚠️ 要注意'}")
    
    if overall_status:
        print("\n🚀 LINE Webhook LangGraph統合システムは実用可能です！")
    else:
        print("\n🔧 システムの改善が必要です")
    
    return overall_status


if __name__ == "__main__":
    # 包括的ヘルスチェックの実行
    asyncio.run(run_comprehensive_health_check())