"""
新しいプロジェクト名でLangSmithテスト
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.append('src')
from agri_ai.core.config import settings

# 環境変数を確実に設定
os.environ["LANGSMITH_API_KEY"] = settings.langsmith.api_key
os.environ["LANGSMITH_PROJECT"] = settings.langsmith.project_name
os.environ["LANGSMITH_TRACING"] = str(settings.langsmith.tracing_enabled).lower()
os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith.endpoint

from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState


async def test_new_project():
    """新しいプロジェクト名でのLangSmithテスト"""
    
    print(f"🧪 新しいプロジェクト '{settings.langsmith.project_name}' でのLangSmithテスト")
    print("=" * 60)
    
    test_query = "新しいプロジェクトでのテスト実行"
    
    print(f"テストクエリ: {test_query}")
    print(f"プロジェクト名: {settings.langsmith.project_name}")
    print(f"トレーシング: {settings.langsmith.tracing_enabled}")
    
    try:
        initial_state = AgriAgentState(
            messages=[{"role": "user", "content": test_query}],
            user_id="new_project_test_user",
            thread_id=f"new_project_test_{datetime.now().strftime('%H%M%S')}",
            next_agent="",
            pending_confirmation={},
            final_response="",
            intermediate_steps=[]
        )
        
        print("\n🚀 LangGraph実行開始...")
        result = await langgraph_app.ainvoke(initial_state)
        
        response = result.get("final_response", "応答なし")
        print(f"✅ 実行成功: {response[:50]}...")
        
        print(f"\n📊 LangSmithダッシュボード確認URL:")
        print(f"   https://smith.langchain.com/o/default/projects/p/{settings.langsmith.project_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ 実行エラー: {e}")
        return False


async def check_langsmith_connection():
    """LangSmith接続確認"""
    
    print("\n🔌 LangSmith接続確認")
    print("-" * 30)
    
    try:
        import requests
        
        headers = {'X-API-Key': settings.langsmith.api_key}
        
        # プロジェクト一覧取得
        response = requests.get('https://api.smith.langchain.com/projects', headers=headers)
        
        print(f"API応答ステータス: {response.status_code}")
        
        if response.status_code == 200:
            projects = response.json()
            print(f"✅ アクセス可能なプロジェクト数: {len(projects)}")
            
            # 現在のプロジェクトが存在するかチェック
            current_project = settings.langsmith.project_name
            project_exists = any(p.get('name') == current_project for p in projects)
            
            if project_exists:
                print(f"✅ プロジェクト '{current_project}' が見つかりました")
            else:
                print(f"⚠️ プロジェクト '{current_project}' が見つかりません")
                print("利用可能なプロジェクト:")
                for p in projects[:5]:  # 最初の5つを表示
                    print(f"  - {p.get('name', '名前なし')}")
        
        elif response.status_code == 401:
            print("❌ 認証エラー: API Keyが無効です")
        elif response.status_code == 403:
            print("❌ 権限エラー: アクセス権限がありません")
        else:
            print(f"❌ エラー: {response.text}")
            
    except Exception as e:
        print(f"❌ 接続エラー: {e}")


async def main():
    """メイン実行"""
    
    print("🔄 LangSmith新プロジェクト設定テスト")
    print("=" * 70)
    
    await check_langsmith_connection()
    await test_new_project()
    
    print("\n🎯 まとめ:")
    print("  - LangSmithプロジェクト名を 'farm-aiagent4' に更新しました")
    print("  - GitHubレポジトリ名と一致させました")
    print("  - プロジェクトが存在しない場合は新規作成されます")
    print("  - ローカル可視化ツールも並行して利用可能です")


if __name__ == "__main__":
    asyncio.run(main())