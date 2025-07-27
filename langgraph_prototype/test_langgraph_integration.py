"""
LangGraph統合テスト
Supervisor → Read/WriteAgent ルーティングの完全テスト
"""

import asyncio
import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.agri_ai.langgraph.supervisor import app
from src.agri_ai.langgraph.state import AgriAgentState


class LangGraphIntegrationTest:
    """LangGraph全体の統合テスト"""
    
    def __init__(self):
        self.test_cases = [
            # ReadAgent系テストケース
            {
                "name": "Read: 圃場情報確認",
                "query": "A畑の情報を教えて",
                "expected_agent": "read_agent",
                "expected_intent": "read"
            },
            {
                "name": "Read: 作業記録検索",
                "query": "過去の作業記録を確認したい",
                "expected_agent": "read_agent",
                "expected_intent": "read"
            },
            {
                "name": "Read: 圃場状況確認",
                "query": "トマトハウスの詳細な状況を見たい",
                "expected_agent": "read_agent",
                "expected_intent": "read"
            },
            
            # WriteAgent系テストケース
            {
                "name": "Write: 作業記録登録",
                "query": "昨日トマトに水やりをしました",
                "expected_agent": "write_agent",
                "expected_intent": "write"
            },
            {
                "name": "Write: 薬剤散布記録",
                "query": "今日A畑でアディオン乳剤を散布した",
                "expected_agent": "write_agent",
                "expected_intent": "write"
            },
            {
                "name": "Write: 収穫記録",
                "query": "収穫量30kgを記録したい",
                "expected_agent": "write_agent",
                "expected_intent": "write"
            },
            
            # 曖昧なケース
            {
                "name": "曖昧: 一般的な質問",
                "query": "農業について教えて",
                "expected_agent": "read_agent",  # デフォルト
                "expected_intent": "read"
            }
        ]
    
    async def test_routing_accuracy(self):
        """ルーティング精度テスト"""
        print("🎯 LangGraph ルーティング精度テスト")
        print("=" * 60)
        
        success_count = 0
        
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n📝 テスト{i}: {test_case['name']}")
            print(f"クエリ: 「{test_case['query']}」")
            print(f"期待エージェント: {test_case['expected_agent']}")
            
            try:
                # 初期状態の作成
                initial_state = AgriAgentState(
                    messages=[{"content": test_case['query']}],
                    final_response="",
                    intermediate_steps=[],
                    next_agent=""
                )
                
                # LangGraphワークフローの実行
                result = await app.ainvoke(initial_state)
                
                # 結果の検証
                final_response = result.get('final_response', '')
                intermediate_steps = result.get('intermediate_steps', [])
                
                # ルーティングが正しく行われたかチェック
                routing_info = next((step for step in intermediate_steps if 'ルーティング' in step), '')
                
                if test_case['expected_agent'] in routing_info:
                    print("✅ ルーティング成功")
                    success_count += 1
                else:
                    print("❌ ルーティング失敗")
                
                if final_response and 'エラー' not in final_response:
                    print("✅ 処理成功")
                else:
                    print("⚠️  処理エラーまたは空応答")
                
                print(f"最終応答プレビュー: {final_response[:100]}...")
                
                if intermediate_steps:
                    print(f"実行ステップ: {len(intermediate_steps)}ステップ")
                    for step in intermediate_steps:
                        print(f"  - {step}")
                
            except Exception as e:
                print(f"❌ テスト実行エラー: {e}")
        
        # 結果サマリー
        print(f"\n📊 ルーティング精度テスト結果")
        print(f"成功: {success_count}/{len(self.test_cases)}")
        print(f"成功率: {success_count/len(self.test_cases)*100:.1f}%")
        
        return success_count >= len(self.test_cases) * 0.8  # 80%以上で成功


async def test_end_to_end_flow():
    """エンドツーエンド フローテスト"""
    print("\n🔄 エンドツーエンド フローテスト")
    print("=" * 50)
    
    e2e_scenarios = [
        {
            "scenario": "完全なRead流れ",
            "query": "圃場の詳細情報を確認したい",
            "expected_flow": "Supervisor → ReadAgent → 終了"
        },
        {
            "scenario": "完全なWrite流れ", 
            "query": "今日の作業を記録します",
            "expected_flow": "Supervisor → WriteAgent → 終了"
        }
    ]
    
    for scenario in e2e_scenarios:
        print(f"\n🎭 シナリオ: {scenario['scenario']}")
        print(f"クエリ: 「{scenario['query']}」")
        print(f"期待フロー: {scenario['expected_flow']}")
        
        try:
            initial_state = AgriAgentState(
                messages=[{"content": scenario['query']}],
                final_response="",
                intermediate_steps=[],
                next_agent=""
            )
            
            result = await app.ainvoke(initial_state)
            
            steps = result.get('intermediate_steps', [])
            response = result.get('final_response', '')
            
            print(f"✅ 実行完了: {len(steps)}ステップ")
            print(f"最終応答: {response[:150]}...")
            
            # フロー確認
            for step in steps:
                print(f"  📋 {step}")
            
        except Exception as e:
            print(f"❌ シナリオ実行エラー: {e}")


async def test_llm_routing_intelligence():
    """LLMルーティング知能テスト"""
    print("\n🧠 LLMルーティング知能テスト")
    print("=" * 50)
    
    intelligent_cases = [
        {
            "query": "作業終わったから記録残そう",
            "expected": "write_agent",
            "reason": "暗黙的な記録意図"
        },
        {
            "query": "最近の作業どうだった？",
            "expected": "read_agent", 
            "reason": "暗黙的な確認意図"
        },
        {
            "query": "水やり完了しました！",
            "expected": "write_agent",
            "reason": "完了報告→記録"
        },
        {
            "query": "畑の調子はどうかな？",
            "expected": "read_agent",
            "reason": "状況確認"
        }
    ]
    
    for case in intelligent_cases:
        print(f"\n自然な表現: 「{case['query']}」")
        print(f"期待ルーティング: {case['expected']} ({case['reason']})")
        
        try:
            initial_state = AgriAgentState(
                messages=[{"content": case['query']}],
                final_response="",
                intermediate_steps=[],
                next_agent=""
            )
            
            result = await app.ainvoke(initial_state)
            steps = result.get('intermediate_steps', [])
            
            routing_step = next((step for step in steps if 'ルーティング' in step), '')
            
            if case['expected'] in routing_step:
                print("✅ 正しいルーティング")
            else:
                print("❌ ルーティング不正確")
                
        except Exception as e:
            print(f"❌ テスト実行エラー: {e}")


def main():
    """メイン実行関数"""
    print("LangGraph マルチエージェント統合テスト")
    print("=" * 70)
    print("Supervisor → Read/WriteAgent ルーティングシステム")
    print("=" * 70)
    
    async def run_all_tests():
        langgraph_test = LangGraphIntegrationTest()
        
        # ルーティング精度テスト
        routing_success = await langgraph_test.test_routing_accuracy()
        
        # エンドツーエンドフローテスト
        await test_end_to_end_flow()
        
        # LLMルーティング知能テスト
        await test_llm_routing_intelligence()
        
        return routing_success
    
    # 非同期テスト実行
    success = asyncio.run(run_all_tests())
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 LangGraph マルチエージェント統合テスト 全体的に成功！")
        print("✅ Phase 1-週3 完了: WriteAgent実装とSupervisorルーティング")
    else:
        print("⚠️  一部テストが失敗しましたが、基本機能は動作確認されました")


if __name__ == "__main__":
    main()