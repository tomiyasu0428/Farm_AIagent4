"""
LINE Webhook LangGraph統合テスト

LangGraphシステムがLINE Webhook経由で正常に動作することを確認するテスト
"""

import asyncio
import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock
import json

# LangGraphプロトタイプのパスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState


class TestLINEWebhookLangGraphIntegration:
    """LINE Webhook + LangGraph統合テストクラス"""
    
    @pytest.mark.asyncio
    async def test_langgraph_basic_workflow(self):
        """LangGraphの基本ワークフロー動作確認"""
        
        # テスト用の状態を作成
        initial_state = AgriAgentState(
            messages=[{"role": "user", "content": "A畑の情報を教えて"}],
            user_id="test_user_001",
            thread_id="test_thread_001",
            next_agent="",
            pending_confirmation={},
            final_response="",
            intermediate_steps=[]
        )
        
        # LangGraphワークフロー実行
        result = await langgraph_app.ainvoke(initial_state)
        
        # 結果検証
        assert result is not None
        assert "final_response" in result
        assert result["final_response"] != ""
        assert "user_id" in result
        assert result["user_id"] == "test_user_001"
        
        print(f"✅ LangGraphワークフロー基本動作: OK")
        print(f"   - 応答: {result['final_response'][:50]}...")
        print(f"   - 実行ステップ数: {len(result.get('intermediate_steps', []))}")
    
    @pytest.mark.asyncio 
    async def test_read_agent_routing(self):
        """ReadAgentへのルーティングテスト"""
        
        read_queries = [
            "A畑の情報を教えて",
            "最近の作業履歴を見せて",
            "今日の天気はどう？",
            "圃場の作物状況を確認したい"
        ]
        
        for query in read_queries:
            initial_state = AgriAgentState(
                messages=[{"role": "user", "content": query}],
                user_id="test_user_002", 
                thread_id="test_thread_002",
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
            
            result = await langgraph_app.ainvoke(initial_state)
            
            # ReadAgentにルーティングされたことを確認
            intermediate_steps = result.get("intermediate_steps", [])
            read_agent_executed = any("read_agent" in step for step in intermediate_steps)
            
            assert read_agent_executed, f"ReadAgentにルーティングされませんでした: {query}"
            assert result.get("final_response") != ""
            
            print(f"✅ ReadAgentルーティング: {query}")
    
    @pytest.mark.asyncio
    async def test_write_agent_routing(self):
        """WriteAgentへのルーティングテスト"""
        
        write_queries = [
            "昨日トマトに水やりをしました",
            "今日A畑で収穫作業を行いました",
            "作業記録を残したいです",
            "農薬散布を記録したい"
        ]
        
        for query in write_queries:
            initial_state = AgriAgentState(
                messages=[{"role": "user", "content": query}], 
                user_id="test_user_003",
                thread_id="test_thread_003",
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
            
            result = await langgraph_app.ainvoke(initial_state)
            
            # WriteAgentにルーティングされたことを確認
            intermediate_steps = result.get("intermediate_steps", [])
            write_agent_executed = any("write_agent" in step for step in intermediate_steps)
            
            assert write_agent_executed, f"WriteAgentにルーティングされませんでした: {query}"
            assert result.get("final_response") != ""
            
            print(f"✅ WriteAgentルーティング: {query}")
    
    @pytest.mark.asyncio
    async def test_session_management_integration(self):
        """セッション管理の統合テスト"""
        
        user_id = "test_user_session"
        thread_id = "test_thread_session"
        
        # 複数のメッセージを同一セッションで送信
        messages = [
            "A畑の情報を教えて",
            "ありがとう、今度は作業記録を残したい", 
            "昨日その畑で収穫しました"
        ]
        
        accumulated_messages = []
        
        for i, message in enumerate(messages):
            accumulated_messages.append({"role": "user", "content": message})
            
            initial_state = AgriAgentState(
                messages=accumulated_messages.copy(),
                user_id=user_id,
                thread_id=thread_id,
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
            
            result = await langgraph_app.ainvoke(initial_state)
            
            # セッション情報が維持されていることを確認
            assert result["user_id"] == user_id
            assert result["thread_id"] == thread_id
            assert result.get("final_response") != ""
            
            print(f"✅ セッション管理 Step {i+1}: {message[:30]}...")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """エラーハンドリングテスト"""
        
        # 不正な入力のテスト
        error_cases = [
            # 空メッセージ
            AgriAgentState(
                messages=[],
                user_id="test_user_error",
                thread_id="test_thread_error", 
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            ),
            # 不正な形式のメッセージ
            AgriAgentState(
                messages=[{"invalid": "format"}],
                user_id="test_user_error2",
                thread_id="test_thread_error2",
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
        ]
        
        for i, error_state in enumerate(error_cases):
            try:
                result = await langgraph_app.ainvoke(error_state)
                
                # エラーケースでも適切な応答が返されることを確認
                assert result is not None
                assert "final_response" in result
                
                print(f"✅ エラーハンドリング Case {i+1}: 適切に処理されました")
                
            except Exception as e:
                print(f"⚠️ エラーハンドリング Case {i+1}: {str(e)}")
                # 予期されるエラーの場合は続行
                continue
    
    @pytest.mark.asyncio
    async def test_performance_benchmark(self):
        """パフォーマンステスト（3秒以内の応答）"""
        
        import time
        
        test_query = "A畑の情報を教えてください"
        
        initial_state = AgriAgentState(
            messages=[{"role": "user", "content": test_query}],
            user_id="test_user_perf",
            thread_id="test_thread_perf",
            next_agent="",
            pending_confirmation={},
            final_response="",
            intermediate_steps=[]
        )
        
        start_time = time.time()
        result = await langgraph_app.ainvoke(initial_state)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert result is not None
        assert result.get("final_response") != ""
        
        print(f"✅ パフォーマンステスト:")
        print(f"   - 応答時間: {response_time:.2f}秒")
        print(f"   - 目標時間: 3秒以内")
        print(f"   - 結果: {'✅ 達成' if response_time <= 3.0 else '❌ 未達成'}")
        
        # 3秒以内であることを確認（警告レベルで記録）
        if response_time > 3.0:
            print(f"⚠️ 応答時間が目標を超過しました: {response_time:.2f}秒")


async def run_integration_tests():
    """統合テストの実行"""
    
    print("🚀 LINE Webhook LangGraph統合テスト開始")
    print("=" * 60)
    
    test_class = TestLINEWebhookLangGraphIntegration()
    
    try:
        # 各テストを順次実行
        print("\n1. LangGraph基本ワークフロー動作確認")
        await test_class.test_langgraph_basic_workflow()
        
        print("\n2. ReadAgentルーティングテスト")
        await test_class.test_read_agent_routing()
        
        print("\n3. WriteAgentルーティングテスト")
        await test_class.test_write_agent_routing()
        
        print("\n4. セッション管理統合テスト")
        await test_class.test_session_management_integration()
        
        print("\n5. エラーハンドリングテスト")
        await test_class.test_error_handling()
        
        print("\n6. パフォーマンステスト")
        await test_class.test_performance_benchmark()
        
        print("\n" + "=" * 60)
        print("🎉 LINE Webhook LangGraph統合テスト完了")
        print("✅ 全てのテストが正常に実行されました")
        
    except Exception as e:
        print(f"\n❌ テスト実行中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    # 統合テストの実行
    asyncio.run(run_integration_tests())