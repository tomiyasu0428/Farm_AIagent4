"""
LangGraphワークフローの可視化とトレーシング
"""

import asyncio
import sys
import os
from typing import Dict, Any

sys.path.append('src')
from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState


def print_mermaid_diagram():
    """Mermaidダイアグラムを出力"""
    print("📊 LangGraph構造 (Mermaid形式)")
    print("=" * 50)
    
    try:
        mermaid = langgraph_app.get_graph().draw_mermaid()
        print(mermaid)
    except Exception as e:
        print(f"エラー: {e}")


def print_graph_info():
    """グラフの詳細情報を表示"""
    print("\n🔍 グラフ詳細情報")
    print("=" * 50)
    
    graph = langgraph_app.get_graph()
    
    print("📍 ノード詳細:")
    for i, node in enumerate(graph.nodes, 1):
        print(f"  {i}. {node}")
    
    print("\n🔗 エッジ詳細:")
    for i, edge in enumerate(graph.edges, 1):
        edge_type = "条件付き" if edge.conditional else "直接"
        print(f"  {i}. {edge.source} → {edge.target} ({edge_type})")


async def trace_execution_with_steps(query: str, user_id: str = "trace_user"):
    """ステップバイステップでの実行トレーシング"""
    print(f"\n🔍 実行トレース: '{query}'")
    print("=" * 50)
    
    # 初期状態
    initial_state = AgriAgentState(
        messages=[{"role": "user", "content": query}],
        user_id=user_id,
        thread_id=f"trace_{hash(query)}",
        next_agent="",
        pending_confirmation={},
        final_response="",
        intermediate_steps=[]
    )
    
    print("📥 初期状態:")
    print(f"  ユーザーID: {initial_state['user_id']}")
    print(f"  メッセージ: {query}")
    print(f"  スレッドID: {initial_state['thread_id']}")
    
    try:
        # LangGraphの実行（ストリーミング形式でステップを追跡）
        print("\n🚀 LangGraph実行開始...")
        
        step_count = 0
        async for event in langgraph_app.astream(initial_state):
            step_count += 1
            print(f"\n📌 ステップ {step_count}:")
            
            for node_name, node_result in event.items():
                print(f"  ノード: {node_name}")
                
                if isinstance(node_result, dict):
                    # 主要な状態変化を表示
                    if 'next_agent' in node_result:
                        print(f"    次のエージェント: {node_result.get('next_agent', 'なし')}")
                    
                    if 'final_response' in node_result and node_result['final_response']:
                        response = node_result['final_response']
                        print(f"    最終応答: {response[:50]}...")
                    
                    if 'intermediate_steps' in node_result:
                        steps = node_result['intermediate_steps']
                        if steps:
                            latest_step = steps[-1] if steps else "なし"
                            print(f"    実行ステップ: {latest_step}")
        
        print(f"\n✅ 実行完了 (総ステップ数: {step_count})")
        
    except Exception as e:
        print(f"❌ 実行エラー: {e}")
        import traceback
        traceback.print_exc()


async def performance_trace(query: str):
    """パフォーマンストレーシング"""
    print(f"\n⏱️ パフォーマンストレース: '{query}'")
    print("=" * 50)
    
    import time
    
    initial_state = AgriAgentState(
        messages=[{"role": "user", "content": query}],
        user_id="perf_user",
        thread_id="perf_thread",
        next_agent="",
        pending_confirmation={},
        final_response="",
        intermediate_steps=[]
    )
    
    start_time = time.time()
    step_times = []
    
    try:
        step_count = 0
        async for event in langgraph_app.astream(initial_state):
            step_time = time.time()
            step_count += 1
            step_duration = step_time - (step_times[-1] if step_times else start_time)
            step_times.append(step_time)
            
            node_name = list(event.keys())[0] if event else "unknown"
            print(f"  ステップ {step_count} ({node_name}): {step_duration:.3f}秒")
        
        total_time = time.time() - start_time
        print(f"\n📊 パフォーマンス結果:")
        print(f"  総実行時間: {total_time:.3f}秒")
        print(f"  平均ステップ時間: {total_time/step_count:.3f}秒")
        print(f"  総ステップ数: {step_count}")
        
    except Exception as e:
        print(f"❌ パフォーマンストレースエラー: {e}")


async def main():
    """メイン実行関数"""
    print("🎭 LangGraph可視化・トレーシングツール")
    print("=" * 70)
    
    # 1. グラフ構造の可視化
    print_mermaid_diagram()
    print_graph_info()
    
    # 2. 実行トレーシング（複数のクエリ）
    test_queries = [
        "圃場の情報を教えて",
        "昨日トマトの水やりをしました"
    ]
    
    for query in test_queries:
        await trace_execution_with_steps(query)
        await performance_trace(query)
    
    print("\n🎉 可視化・トレーシング完了")


if __name__ == "__main__":
    asyncio.run(main())