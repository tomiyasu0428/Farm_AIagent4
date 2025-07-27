"""
Phase 1 リファクタリング移行ヘルパー

既存システムからsharedモジュールへの段階的移行を支援
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Tuple


class Phase1Migrator:
    """Phase 1 移行管理クラス"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.shared_dir = self.project_root / "shared"
        self.legacy_dir = self.project_root / "src" / "agri_ai"
        self.langgraph_dir = self.project_root / "langgraph_prototype" / "src" / "agri_ai"
    
    def create_migration_report(self) -> Dict[str, any]:
        """移行前の状況レポートを作成"""
        
        duplicate_files = self._find_duplicate_files()
        import_dependencies = self._analyze_import_dependencies()
        
        return {
            "duplicate_files": duplicate_files,
            "import_dependencies": import_dependencies,
            "migration_plan": self._create_migration_plan(duplicate_files)
        }
    
    def _find_duplicate_files(self) -> List[Dict[str, str]]:
        """重複ファイルを検出"""
        
        duplicates = []
        
        # 重複候補のファイルパス
        duplicate_candidates = [
            ("core/config.py", "core/config.py"),
            ("database/models.py", "database/models.py"),
            ("langchain_tools/base_tool.py", "langchain_tools/base_tool.py"),
            ("services/work_log_extractor.py", "services/work_log_extractor.py"),
        ]
        
        for legacy_path, langgraph_path in duplicate_candidates:
            legacy_full = self.legacy_dir / legacy_path
            langgraph_full = self.langgraph_dir / langgraph_path
            
            if legacy_full.exists() and langgraph_full.exists():
                duplicates.append({
                    "name": legacy_path,
                    "legacy_path": str(legacy_full),
                    "langgraph_path": str(langgraph_full),
                    "size_legacy": legacy_full.stat().st_size,
                    "size_langgraph": langgraph_full.stat().st_size,
                    "identical": self._files_identical(legacy_full, langgraph_full)
                })
        
        return duplicates
    
    def _files_identical(self, file1: Path, file2: Path) -> bool:
        """ファイルが同一かどうかをチェック"""
        try:
            with open(file1, 'r', encoding='utf-8') as f1, open(file2, 'r', encoding='utf-8') as f2:
                return f1.read() == f2.read()
        except Exception:
            return False
    
    def _analyze_import_dependencies(self) -> Dict[str, List[str]]:
        """インポート依存関係を分析"""
        
        dependencies = {}
        
        # 主要ファイルの依存関係を分析
        key_files = [
            self.legacy_dir / "line_bot" / "webhook.py",
            self.langgraph_dir / "langgraph" / "supervisor.py",
            self.langgraph_dir / "langgraph" / "read_agent.py",
        ]
        
        for file_path in key_files:
            if file_path.exists():
                deps = self._extract_imports(file_path)
                dependencies[str(file_path.relative_to(self.project_root))] = deps
        
        return dependencies
    
    def _extract_imports(self, file_path: Path) -> List[str]:
        """ファイルからインポート文を抽出"""
        imports = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('from ') and 'agri_ai' in line:
                        imports.append(line)
                    elif line.startswith('import ') and 'agri_ai' in line:
                        imports.append(line)
        except Exception as e:
            imports.append(f"Error reading file: {e}")
        
        return imports
    
    def _create_migration_plan(self, duplicate_files: List[Dict]) -> List[Dict[str, str]]:
        """移行計画を作成"""
        
        plan = []
        
        for dup in duplicate_files:
            file_name = dup["name"]
            
            if file_name == "core/config.py":
                plan.append({
                    "action": "migrate_to_shared",
                    "source": dup["legacy_path"],
                    "target": "shared/config/settings.py",
                    "description": "設定管理を統一版に移行"
                })
            
            elif file_name == "database/models.py":
                plan.append({
                    "action": "migrate_to_shared", 
                    "source": dup["legacy_path"],
                    "target": "shared/models/database.py",
                    "description": "データベースモデルを統一版に移行"
                })
            
            elif file_name == "langchain_tools/base_tool.py":
                plan.append({
                    "action": "migrate_to_shared",
                    "source": dup["legacy_path"],
                    "target": "shared/tools/base.py", 
                    "description": "ツール基盤を統一版に移行"
                })
        
        return plan
    
    def execute_migration_step(self, step_name: str) -> bool:
        """特定の移行ステップを実行"""
        
        if step_name == "backup_original_files":
            return self._backup_original_files()
        elif step_name == "update_import_paths":
            return self._update_import_paths()
        elif step_name == "create_compatibility_layer":
            return self._create_compatibility_layer()
        else:
            print(f"Unknown migration step: {step_name}")
            return False
    
    def _backup_original_files(self) -> bool:
        """元ファイルをバックアップ"""
        
        backup_dir = self.project_root / "backup_phase1"
        backup_dir.mkdir(exist_ok=True)
        
        files_to_backup = [
            self.legacy_dir / "core" / "config.py",
            self.legacy_dir / "database" / "models.py",
            self.legacy_dir / "langchain_tools" / "base_tool.py",
            self.langgraph_dir / "core" / "config.py",
            self.langgraph_dir / "database" / "models.py",
        ]
        
        for file_path in files_to_backup:
            if file_path.exists():
                relative_path = file_path.relative_to(self.project_root)
                backup_path = backup_dir / relative_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_path)
                print(f"Backed up: {relative_path}")
        
        return True
    
    def _update_import_paths(self) -> bool:
        """インポートパスを更新"""
        
        # 主要ファイルのインポートパスを更新
        files_to_update = [
            self.legacy_dir / "line_bot" / "webhook.py",
            self.langgraph_dir / "langgraph" / "supervisor.py",
            self.langgraph_dir / "langgraph" / "read_agent.py",
            self.langgraph_dir / "langgraph" / "write_agent.py",
        ]
        
        import_mappings = {
            "from ..core.config import settings": "from shared.config.settings import settings",
            "from ...core.config import settings": "from shared.config.settings import settings",
            "from ..database.models import": "from shared.models.database import",
            "from ...database.models import": "from shared.models.database import",
            "from ..langchain_tools.base_tool import": "from shared.tools.base import",
        }
        
        for file_path in files_to_update:
            if file_path.exists():
                self._update_file_imports(file_path, import_mappings)
        
        return True
    
    def _update_file_imports(self, file_path: Path, mappings: Dict[str, str]):
        """ファイル内のインポート文を更新"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            updated_content = content
            for old_import, new_import in mappings.items():
                updated_content = updated_content.replace(old_import, new_import)
            
            if updated_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                print(f"Updated imports in: {file_path.relative_to(self.project_root)}")
            
        except Exception as e:
            print(f"Error updating {file_path}: {e}")
    
    def _create_compatibility_layer(self) -> bool:
        """後方互換性レイヤーを作成"""
        
        # レガシーインポートパスからsharedへのエイリアスを作成
        compatibility_files = [
            {
                "path": self.legacy_dir / "core" / "_config_compat.py",
                "content": "# 後方互換性のための設定インポート\nfrom shared.config.settings import settings, UnifiedSettings as Settings\n"
            },
            {
                "path": self.legacy_dir / "database" / "_models_compat.py", 
                "content": "# 後方互換性のためのモデルインポート\nfrom shared.models.database import *\n"
            },
            {
                "path": self.langgraph_dir / "core" / "_config_compat.py",
                "content": "# 後方互換性のための設定インポート\nfrom shared.config.settings import settings, UnifiedSettings as Settings\n"
            }
        ]
        
        for compat_file in compatibility_files:
            compat_file["path"].parent.mkdir(parents=True, exist_ok=True)
            with open(compat_file["path"], 'w', encoding='utf-8') as f:
                f.write(compat_file["content"])
            print(f"Created compatibility layer: {compat_file['path'].relative_to(self.project_root)}")
        
        return True


def main():
    """移行プロセスのメイン実行"""
    
    project_root = "/Users/tomiyasuhiroki/Desktop/開発/Agri_AI_LangGraph"
    migrator = Phase1Migrator(project_root)
    
    print("🔍 Phase 1 移行前分析開始")
    print("=" * 50)
    
    # 移行前レポート作成
    report = migrator.create_migration_report()
    
    print(f"📁 重複ファイル検出: {len(report['duplicate_files'])}件")
    for dup in report['duplicate_files']:
        status = "✅ 同一" if dup['identical'] else "⚠️ 差分あり"
        print(f"  - {dup['name']}: {status}")
    
    print(f"\n📦 インポート依存関係分析:")
    for file_path, imports in report['import_dependencies'].items():
        print(f"  - {file_path}: {len(imports)}個のインポート")
    
    print(f"\n📋 移行計画: {len(report['migration_plan'])}ステップ")
    for i, step in enumerate(report['migration_plan'], 1):
        print(f"  {i}. {step['description']}")
    
    print(f"\n🎯 推奨次ステップ:")
    print("  1. migrator.execute_migration_step('backup_original_files')")
    print("  2. migrator.execute_migration_step('create_compatibility_layer')")
    print("  3. migrator.execute_migration_step('update_import_paths')")
    
    return migrator


if __name__ == "__main__":
    migrator = main()