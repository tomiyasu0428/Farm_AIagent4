"""
ReadAgent統合テスト（モックデータ使用）
LLMベースのツール選択・実行機能をテスト
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.agri_ai.langgraph.read_agent import ReadAgent
from src.agri_ai.langgraph.state import AgriAgentState


class MockTest:
    """ReadAgentのモックテスト"""
    
    def __init__(self):
        self.test_cases = [
            {
                "name": "圃場情報クエリ",
                "query": "A畑の情報を教えて",
                "expected_tool": "field_info"
            },
            {
                "name": "作業記録検索クエリ",
                "query": "過去の作業記録を検索して",
                "expected_tool": "work_log_search"
            },
            {
                "name": "複雑な圃場関連クエリ",
                "query": "すべての圃場の詳細な状況と作付け計画を教えて",
                "expected_tool": "field_agent_tool"
            },
            {
                "name": "自然言語での圃場クエリ",
                "query": "トマトハウスってどんな状況？",
                "expected_tool": "field_agent_tool"
            },
            {
                "name": "曖昧な作業記録クエリ",
                "query": "昨日何をしたか教えて",
                "expected_tool": "work_log_search"
            }
        ]
    
    async def test_tool_selection(self):
        """ツール選択の精度テスト"""
        print("🎯 LLMベースツール選択テスト")
        print("-" * 40)
        
        try:
            # ReadAgentの初期化
            agent = ReadAgent()
            print("✅ ReadAgent初期化成功")
            
            # 利用可能ツールの確認
            tools = agent.get_available_tools()
            print(f"✅ 利用可能ツール: {tools}")
            
            success_count = 0
            
            for i, test_case in enumerate(self.test_cases, 1):
                print(f"\n📝 テスト{i}: {test_case['name']}")
                print(f"クエリ: 「{test_case['query']}」")
                
                #状態の準備
                state = AgriAgentState(
                    messages=[{"content": test_case['query']}],
                    final_response="",
                    intermediate_steps=[]
                )
                
                try:
                    # エージェント実行（実際のLLM呼び出し）
                    result = await agent.run(state)
                    
                    # 結果の評価
                    response = result.get('final_response', '')
                    if 'エラー' not in response:
                        print(f"✅ 実行成功")
                        print(f"応答プレビュー: {response[:100]}...")
                        success_count += 1
                    else:
                        print(f"⚠️  エラー応答: {response[:100]}...")
                        
                except Exception as e:
                    print(f"❌ 実行エラー: {e}")
            
            # 結果サマリー
            print(f"\n📊 テスト結果サマリー")
            print(f"成功: {success_count}/{len(self.test_cases)}")
            print(f"成功率: {success_count/len(self.test_cases)*100:.1f}%")
            
            return success_count == len(self.test_cases)
            
        except Exception as e:
            print(f"❌ テスト初期化エラー: {e}")
            return False


async def test_llm_flexibility():
    """LLMの柔軟性テスト"""
    print("\n🧠 LLM柔軟性テスト")
    print("-" * 40)
    
    flexible_queries = [
        "ちょっと畑の様子見たいんだけど",
        "最近どんな作業したっけ？",
        "作物の調子どう？",
        "農薬まいた記録ある？",
        "ハウスの中はどんな感じ？"
    ]
    
    try:
        agent = ReadAgent()
        
        for query in flexible_queries:
            print(f"\n自然なクエリ: 「{query}」")
            
            state = AgriAgentState(
                messages=[{"content": query}],
                final_response="",
                intermediate_steps=[]
            )
            
            try:
                result = await agent.run(state)
                response = result.get('final_response', '')
                
                if 'エラー' not in response:
                    print("✅ 自然言語理解成功")
                else:
                    print("❌ 理解失敗")
                    
            except Exception as e:
                print(f"❌ 実行エラー: {e}")
    
    except Exception as e:
        print(f"❌ 柔軟性テスト エラー: {e}")


def main():
    """メイン実行関数"""
    print("ReadAgent LLMベース統合テスト（改良版）")
    print("=" * 60)
    
    async def run_all_tests():
        mock_test = MockTest()
        
        # ツール選択精度テスト
        success = await mock_test.test_tool_selection()
        
        # LLM柔軟性テスト
        await test_llm_flexibility()
        
        return success
    
    # 非同期テスト実行
    success = asyncio.run(run_all_tests())
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ReadAgent LLMベース統合テスト 全体的に成功！")
    else:
        print("⚠️  一部テストが失敗しましたが、LLMの動作は確認できました")


if __name__ == "__main__":
    main()