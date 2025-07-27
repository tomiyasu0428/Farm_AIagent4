"""
LangSmith を使ったLangGraphの可視化デモ
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.append('src')
sys.path.append('../src')

# LangSmith環境変数の設定確認と設定
from agri_ai.core.config import settings

print("🔧 LangSmith環境変数設定確認...")
print(f"LANGSMITH_API_KEY: {'設定済み' if settings.langsmith.api_key else '未設定'}")
print(f"LANGSMITH_PROJECT: {settings.langsmith.project_name}")
print(f"LANGSMITH_TRACING: {settings.langsmith.tracing_enabled}")

# 環境変数を確実に設定
os.environ["LANGSMITH_API_KEY"] = settings.langsmith.api_key
os.environ["LANGSMITH_PROJECT"] = settings.langsmith.project_name
os.environ["LANGSMITH_TRACING"] = str(settings.langsmith.tracing_enabled).lower()
os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith.endpoint

from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState


async def demo_with_langsmith_tracing():
    """LangSmithトレーシング付きのデモ実行"""
    
    print("\n🎭 LangSmith可視化デモ開始")
    print("=" * 60)
    
    # デモ用のクエリリスト
    demo_queries = [
        {
            "query": "第1圃場の情報を教えて",
            "description": "ReadAgent - 圃場情報検索",
            "expected_agent": "read_agent"
        },
        {
            "query": "昨日ナスの水やりをしました",
            "description": "WriteAgent - 作業記録登録", 
            "expected_agent": "write_agent"
        },
        {
            "query": "作業履歴を確認したい",
            "description": "ReadAgent - 作業履歴検索",
            "expected_agent": "read_agent"
        }
    ]
    
    for i, demo in enumerate(demo_queries, 1):
        print(f"\n📝 デモ {i}: {demo['description']}")
        print(f"   クエリ: {demo['query']}")
        print(f"   期待エージェント: {demo['expected_agent']}")
        print("-" * 40)
        
        try:
            # ユニークなユーザーIDとスレッドIDを生成
            timestamp = datetime.now().strftime("%H%M%S")
            user_id = f"langsmith_demo_user_{i}_{timestamp}"
            thread_id = f"langsmith_demo_thread_{i}_{timestamp}"
            
            # LangGraphの状態を作成
            initial_state = AgriAgentState(
                messages=[{"role": "user", "content": demo["query"]}],
                user_id=user_id,
                thread_id=thread_id,
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
            
            print(f"🚀 LangGraph実行開始 (トレースID: {thread_id})")
            
            # LangGraphワークフロー実行（LangSmithで自動トレーシング）
            result = await langgraph_app.ainvoke(initial_state)
            
            # 結果の表示
            final_response = result.get("final_response", "応答なし")
            intermediate_steps = result.get("intermediate_steps", [])
            
            print(f"✅ 実行完了")
            print(f"   応答: {final_response[:60]}...")
            print(f"   実行ステップ数: {len(intermediate_steps)}")
            
            # 実行されたエージェントの確認
            executed_agents = []
            for step in intermediate_steps:
                if "ReadAgent" in step:
                    executed_agents.append("read_agent")
                elif "WriteAgent" in step:
                    executed_agents.append("write_agent")
                elif "SupervisorAgent" in step:
                    executed_agents.append("supervisor")
            
            unique_agents = list(set(executed_agents))
            print(f"   実行エージェント: {', '.join(unique_agents)}")
            
            # 期待結果との比較
            if demo["expected_agent"] in unique_agents:
                print("   ✅ 期待通りのエージェントが実行されました")
            else:
                print("   ⚠️ 期待と異なるエージェントが実行されました")
                
        except Exception as e:
            print(f"   ❌ エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
        
        print()  # 空行
    
    print("🎉 LangSmithデモ完了")
    print("\n📊 LangSmithダッシュボードで詳細な実行トレースを確認できます:")
    print(f"   URL: https://smith.langchain.com/o/default/projects/p/{settings.langsmith.project_name}")
    print("\n🔍 LangSmithで確認できる情報:")
    print("   • エージェント間のフロー図")
    print("   • 各ステップの実行時間")
    print("   • ツールの実行詳細")
    print("   • エラートレーシング")
    print("   • パフォーマンス分析")


async def simple_trace_demo():
    """シンプルなトレーシングデモ"""
    
    print("\n🔍 シンプルトレーシングデモ")
    print("=" * 40)
    
    simple_query = "こんにちは"
    
    initial_state = AgriAgentState(
        messages=[{"role": "user", "content": simple_query}],
        user_id="simple_demo_user",
        thread_id="simple_demo_thread",
        next_agent="",
        pending_confirmation={},
        final_response="",
        intermediate_steps=[]
    )
    
    print(f"クエリ: {simple_query}")
    print("実行中...")
    
    try:
        result = await langgraph_app.ainvoke(initial_state)
        response = result.get("final_response", "応答なし")
        print(f"応答: {response}")
        print("✅ トレーシング完了")
    except Exception as e:
        print(f"❌ エラー: {e}")


async def main():
    """メイン実行関数"""
    
    print("🎬 LangSmith + LangGraph 可視化デモ")
    print("=" * 70)
    
    if not settings.langsmith.tracing_enabled:
        print("⚠️ LangSmithトレーシングが無効です")
        print("   .envファイルでLANGSMITH_TRACING=trueに設定してください")
        return
    
    if not settings.langsmith.api_key:
        print("❌ LangSmith API Keyが設定されていません")
        print("   .envファイルでLANGSMITH_API_KEYを設定してください")
        return
    
    print("✅ LangSmithトレーシングが有効です")
    
    # デモの実行
    await simple_trace_demo()
    await demo_with_langsmith_tracing()


if __name__ == "__main__":
    asyncio.run(main())