"""
Phase 1 統合テスト

shared/モジュールの動作確認とレガシーシステムとの互換性テスト
"""

import asyncio
import sys
from pathlib import Path

# sharedモジュールのパスを追加
project_root = Path("/Users/tomiyasuhiroki/Desktop/開発/Agri_AI_LangGraph")
sys.path.insert(0, str(project_root))

def test_shared_config():
    """統一設定システムのテスト"""
    print("🔧 shared.config.settings テスト")
    
    try:
        from shared.config.settings import settings, get_settings, SystemConstants
        
        # 基本設定の確認
        assert settings.google_ai.model_name == "gemini-2.5-flash"
        assert settings.app.environment in ["development", "staging", "production"]
        assert settings.constants.HIGH_CONFIDENCE_THRESHOLD == 0.8
        
        # 動的設定取得
        test_settings = get_settings()
        assert test_settings.mongodb.database_name == "Agri-AI-Project"
        
        print("  ✅ 設定読み込み: OK")
        print(f"  ✅ 環境: {settings.app.environment}")
        print(f"  ✅ データベース: {settings.mongodb.database_name}")
        print(f"  ✅ 定数: HIGH_CONFIDENCE = {settings.constants.HIGH_CONFIDENCE_THRESHOLD}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        return False


def test_shared_models():
    """統一データベースモデルのテスト"""
    print("\n📊 shared.models.database テスト")
    
    try:
        from shared.models.database import (
            WorkLogDocument, FieldDocument, CropDocument,
            WorkCategory, WorkStatus, create_log_id
        )
        from datetime import datetime
        
        # WorkLogDocumentの作成テスト
        work_log = WorkLogDocument(
            log_id="TEST-001",
            user_id="test_user",
            work_date=datetime.now(),
            original_message="テスト作業記録",
            category=WorkCategory.CULTIVATION,
            status=WorkStatus.CONFIRMED
        )
        
        assert work_log.category == WorkCategory.CULTIVATION
        assert work_log.status == WorkStatus.CONFIRMED
        
        # FieldDocumentの作成テスト
        field = FieldDocument(
            field_code="F-001",
            name="テスト圃場",
            area=1000.0
        )
        
        assert field.field_code == "F-001"
        assert field.area == 1000.0
        
        # ヘルパー関数テスト
        log_id = create_log_id("test_user", datetime.now())
        assert log_id.startswith("LOG-")
        
        print("  ✅ WorkLogDocument: OK")
        print("  ✅ FieldDocument: OK") 
        print("  ✅ Enumクラス: OK")
        print(f"  ✅ ヘルパー関数: {log_id}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_shared_exceptions():
    """統一エラーハンドリングのテスト"""
    print("\n🚨 shared.exceptions.errors テスト")
    
    try:
        from shared.exceptions.errors import (
            AgriAIResult, ValidationError, DatabaseError,
            ErrorCategory, handle_exceptions
        )
        
        # 成功結果のテスト
        success_result = AgriAIResult.success_result({"test": "data"})
        assert success_result.success == True
        assert success_result.data["test"] == "data"
        
        # エラー結果のテスト
        error_result = AgriAIResult.error_result(
            "テストエラー",
            ErrorCategory.VALIDATION,
            "TEST_ERROR"
        )
        assert error_result.success == False
        assert error_result.error_category == ErrorCategory.VALIDATION
        
        # カスタム例外のテスト
        try:
            raise ValidationError("バリデーションエラー", field="test_field")
        except ValidationError as e:
            result = e.to_result()
            assert result.success == False
            assert result.error_category == ErrorCategory.VALIDATION
        
        # デコレータのテスト
        @handle_exceptions()
        def test_function():
            raise ValueError("テスト例外")
        
        result = test_function()
        assert isinstance(result, AgriAIResult)
        assert result.success == False
        
        print("  ✅ AgriAIResult: OK")
        print("  ✅ カスタム例外: OK")
        print("  ✅ エラーハンドリングデコレータ: OK")
        
        return True
        
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_shared_tools():
    """統一ツール基盤のテスト"""
    print("\n🔧 shared.tools.base テスト")
    
    try:
        from shared.tools.base import (
            AgriAIBaseTool, AgriAILLMTool, tool_registry,
            register_tool, CacheManager
        )
        
        # キャッシュマネージャーのテスト
        cache = CacheManager(ttl=60)
        cache.set("test_key", "test_value")
        cached_value = cache.get("test_key")
        assert cached_value == "test_value"
        
        # ツールレジストリのテスト
        @register_tool("test_tool")
        class TestTool(AgriAIBaseTool):
            name: str = "test_tool"
            description: str = "テストツール"
            require_db: bool = False
            
            async def _execute(self, query: str, **kwargs):
                return f"Test result for: {query}"
        
        # ツール取得テスト
        tool = tool_registry.get_tool("test_tool")
        assert tool.name == "test_tool"
        
        # ツール実行テスト（簡単なもの）
        result = await tool._execute("test query")
        assert "Test result" in result
        
        print("  ✅ CacheManager: OK")
        print("  ✅ ToolRegistry: OK") 
        print("  ✅ AgriAIBaseTool: OK")
        print(f"  ✅ ツール実行結果: {result}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """後方互換性のテスト"""
    print("\n🔄 後方互換性テスト")
    
    try:
        # レガシーパスの互換性レイヤーをテスト
        import importlib.util
        
        # 直接ファイルをロードしてテスト
        config_compat_path = project_root / "src" / "agri_ai" / "core" / "_config_compat.py"
        models_compat_path = project_root / "src" / "agri_ai" / "database" / "_models_compat.py"
        
        # 設定ファイルが存在し読み込めるかテスト
        assert config_compat_path.exists(), f"設定互換ファイルが見つかりません: {config_compat_path}"
        assert models_compat_path.exists(), f"モデル互換ファイルが見つかりません: {models_compat_path}"
        
        # 簡易インポートテスト
        sys.path.insert(0, str(project_root / "src"))
        from agri_ai.core._config_compat import settings as legacy_settings
        from agri_ai.database._models_compat import WorkLogDocument as LegacyWorkLogDocument
        
        # 設定が正しくインポートされているかテスト
        assert hasattr(legacy_settings, 'google_ai')
        assert hasattr(legacy_settings, 'mongodb')
        
        # モデルが正しくインポートされているかテスト
        # WorkLogDocumentクラスが存在するかテスト
        assert LegacyWorkLogDocument is not None
        assert hasattr(LegacyWorkLogDocument, '__fields__') or hasattr(LegacyWorkLogDocument, 'model_fields')
        
        print("  ✅ レガシー設定インポート: OK")
        print("  ✅ レガシーモデルインポート: OK")
        
        return True
        
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_comprehensive_tests():
    """包括的テストの実行"""
    print("🧪 Phase 1 統合テスト開始")
    print("=" * 60)
    
    test_results = []
    
    # 各テストを実行
    test_results.append(("shared.config", test_shared_config()))
    test_results.append(("shared.models", test_shared_models()))
    test_results.append(("shared.exceptions", test_shared_exceptions()))
    test_results.append(("shared.tools", await test_shared_tools()))
    test_results.append(("backward_compatibility", test_backward_compatibility()))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    success_rate = (passed / total) * 100
    print(f"\n成功率: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate == 100:
        print("🎉 全テスト合格！Phase 1 リファクタリング基盤が正常に動作しています")
    elif success_rate >= 80:
        print("⚠️ 大部分のテストが合格。一部問題があります")
    else:
        print("❌ 多数のテストが失敗。リファクタリングに問題があります")
    
    return success_rate


def main():
    """メイン実行"""
    return asyncio.run(run_comprehensive_tests())


if __name__ == "__main__":
    main()