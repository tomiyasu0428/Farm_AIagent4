"""
ReadAgent統合テスト
LLMベースのツール選択・実行機能をテスト
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.agri_ai.langgraph.read_agent import ReadAgent
from src.agri_ai.langgraph.state import AgriAgentState


async def test_read_agent():
    """ReadAgentの統合テスト"""
    print("🧪 ReadAgent統合テスト開始")
    
    try:
        # ReadAgentの初期化
        agent = ReadAgent()
        print("✅ ReadAgent初期化成功")
        
        # テストケース1: 圃場情報クエリ
        print("\n📝 テストケース1: 圃場情報クエリ")
        state1 = AgriAgentState(
            messages=[{"content": "A畑の情報を教えて"}],
            final_response="",
            intermediate_steps=[]
        )
        result1 = await agent.run(state1)
        print(f"応答: {result1['final_response']}")
        
        # テストケース2: 作業記録検索クエリ
        print("\n📝 テストケース2: 作業記録検索クエリ")
        state2 = AgriAgentState(
            messages=[{"content": "過去の作業記録を検索して"}],
            final_response="",
            intermediate_steps=[]
        )
        result2 = await agent.run(state2)
        print(f"応答: {result2['final_response']}")
        
        # テストケース3: 複雑な圃場関連クエリ
        print("\n📝 テストケース3: 複雑な圃場関連クエリ")
        state3 = AgriAgentState(
            messages=[{"content": "すべての圃場の詳細な状況と作付け計画を教えて"}],
            final_response="",
            intermediate_steps=[]
        )
        result3 = await agent.run(state3)
        print(f"応答: {result3['final_response']}")
        
        print("\n🎉 ReadAgent統合テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン実行関数"""
    print("ReadAgent LLMベース統合テスト")
    print("=" * 50)
    
    # 非同期テスト実行
    success = asyncio.run(test_read_agent())
    
    if success:
        print("\n✅ すべてのテストが成功しました")
    else:
        print("\n❌ テストが失敗しました")


if __name__ == "__main__":
    main()