"""
ローカル環境でのLangGraph可視化ツール
LangSmithアクセスできない場合の代替可視化方法
"""

import asyncio
import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, Any, List
import graphviz

sys.path.append('src')
from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState


class LocalLangGraphVisualizer:
    """ローカル環境でのLangGraph可視化クラス"""
    
    def __init__(self):
        self.execution_logs = []
        
    def generate_graphviz_diagram(self) -> str:
        """GraphvizでLangGraphの構造を可視化"""
        
        print("🎨 Graphviz図表生成中...")
        
        try:
            # Graphvizグラフを作成
            dot = graphviz.Digraph(comment='LangGraph農業AIエージェント', format='png')
            dot.attr(rankdir='TB', size='10,8')
            dot.attr('node', shape='box', style='rounded,filled', fontname='Arial')
            
            # ノードの定義
            dot.node('start', '__START__', fillcolor='lightgreen', shape='ellipse')
            dot.node('supervisor', 'SupervisorAgent\n(司令塔)', fillcolor='lightblue')
            dot.node('read_agent', 'ReadAgent\n(データ読み取り)', fillcolor='lightyellow')
            dot.node('write_agent', 'WriteAgent\n(データ書き込み)', fillcolor='lightcoral')
            dot.node('end', '__END__', fillcolor='lightgray', shape='ellipse')
            
            # エッジの定義
            dot.edge('start', 'supervisor', label='開始')
            dot.edge('supervisor', 'read_agent', label='Read意図', style='dashed')
            dot.edge('supervisor', 'write_agent', label='Write意図', style='dashed')
            dot.edge('supervisor', 'end', label='終了', style='dashed')
            dot.edge('read_agent', 'end', label='完了')
            dot.edge('write_agent', 'end', label='完了')
            
            # ファイルに保存
            output_path = 'langgraph_structure'
            dot.render(output_path, cleanup=True)
            
            print(f"✅ Graphviz図表生成完了: {output_path}.png")
            return f"{output_path}.png"
            
        except Exception as e:
            print(f"❌ Graphviz生成エラー: {e}")
            print("💡 Graphvizをインストールしてください: brew install graphviz")
            return None
    
    def create_mermaid_html(self) -> str:
        """MermaidをHTMLで表示するファイルを生成"""
        
        mermaid_code = """
graph TD
    A[👤 ユーザー] --> B[📨 LINE メッセージ]
    B --> C[🧠 SupervisorAgent<br/>意図分析]
    
    C -->|Read意図| D[📖 ReadAgent<br/>データ読み取り]
    C -->|Write意図| E[✏️ WriteAgent<br/>データ書き込み]
    C -->|不明| F[❓ デフォルト処理]
    
    D --> G[🔧 ToolExecution<br/>FieldInfoTool<br/>WorkLogSearchTool]
    E --> H[🔧 ToolExecution<br/>WorkLogRegistrationTool]
    
    G --> I[📤 READ応答]
    H --> J[📤 WRITE応答]
    F --> K[📤 ERROR応答]
    
    I --> L[📱 LINE応答]
    J --> L
    K --> L
    
    style A fill:#e1f5fe
    style C fill:#f3e5f5
    style D fill:#e8f5e8
    style E fill:#fff3e0
    style L fill:#fce4ec
"""
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>LangGraph農業AIエージェント - フロー図</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .diagram {{ text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 LangGraph農業AIエージェント - システムフロー</h1>
        <p>生成日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
    
    <div class="diagram">
        <div class="mermaid">
{mermaid_code}
        </div>
    </div>
    
    <script>
        mermaid.initialize({{ startOnLoad: true }});
    </script>
</body>
</html>
"""
        
        html_file = 'langgraph_flow.html'
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Mermaid HTML生成完了: {html_file}")
        return html_file
    
    async def detailed_execution_trace(self, query: str, user_id: str = "trace_user"):
        """詳細な実行トレースを記録"""
        
        print(f"\n🔍 詳細実行トレース: '{query}'")
        print("=" * 60)
        
        trace_log = {
            "query": query,
            "user_id": user_id,
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "final_result": None,
            "total_duration": 0,
            "error": None
        }
        
        initial_state = AgriAgentState(
            messages=[{"role": "user", "content": query}],
            user_id=user_id,
            thread_id=f"trace_{hash(query)}_{int(time.time())}",
            next_agent="",
            pending_confirmation={},
            final_response="",
            intermediate_steps=[]
        )
        
        start_time = time.time()
        
        try:
            step_count = 0
            async for event in langgraph_app.astream(initial_state):
                step_count += 1
                step_time = time.time()
                step_duration = step_time - start_time
                
                step_info = {
                    "step_number": step_count,
                    "timestamp": datetime.now().isoformat(),
                    "duration_from_start": round(step_duration, 3),
                    "nodes": list(event.keys()),
                    "details": {}
                }
                
                print(f"\n📌 ステップ {step_count} (開始から{step_duration:.3f}秒)")
                
                for node_name, node_result in event.items():
                    print(f"  🏃 実行ノード: {node_name}")
                    
                    if isinstance(node_result, dict):
                        # 重要な情報を抽出
                        details = {}
                        
                        if 'next_agent' in node_result:
                            next_agent = node_result.get('next_agent', '')
                            print(f"    ➡️ 次のエージェント: {next_agent}")
                            details['next_agent'] = next_agent
                        
                        if 'final_response' in node_result and node_result['final_response']:
                            response = node_result['final_response']
                            print(f"    💬 応答: {response[:80]}...")
                            details['response_preview'] = response[:100]
                        
                        if 'intermediate_steps' in node_result:
                            steps = node_result['intermediate_steps']
                            if steps:
                                latest_step = steps[-1] if steps else ""
                                print(f"    🔧 最新ステップ: {latest_step}")
                                details['latest_step'] = latest_step
                                details['total_steps'] = len(steps)
                        
                        step_info['details'][node_name] = details
                
                trace_log['steps'].append(step_info)
            
            total_time = time.time() - start_time
            trace_log['total_duration'] = round(total_time, 3)
            trace_log['end_time'] = datetime.now().isoformat()
            
            print(f"\n✅ トレース完了")
            print(f"   総実行時間: {total_time:.3f}秒")
            print(f"   総ステップ数: {step_count}")
            
        except Exception as e:
            trace_log['error'] = str(e)
            print(f"\n❌ トレースエラー: {e}")
        
        # ログを保存
        self.execution_logs.append(trace_log)
        return trace_log
    
    def generate_execution_report(self) -> str:
        """実行レポートをHTMLで生成"""
        
        if not self.execution_logs:
            print("⚠️ 実行ログがありません")
            return None
        
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>LangGraph実行レポート</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .log-entry { border: 1px solid #ddd; margin: 20px 0; padding: 15px; }
        .step { background: #f5f5f5; margin: 10px 0; padding: 10px; }
        .success { color: green; }
        .error { color: red; }
        .performance { background: #e3f2fd; padding: 10px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 LangGraph実行レポート</h1>
        <p>生成日時: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
    </div>
"""
        
        for i, log in enumerate(self.execution_logs, 1):
            status_class = "success" if not log.get('error') else "error"
            
            html_content += f"""
    <div class="log-entry">
        <h2>🎯 実行 {i}: {log['query']}</h2>
        <div class="performance">
            <strong>パフォーマンス:</strong>
            総実行時間: {log.get('total_duration', 0)}秒 |
            ステップ数: {len(log.get('steps', []))} |
            ユーザー: {log.get('user_id', 'unknown')}
        </div>
        
        <div class="{status_class}">
            <strong>結果:</strong> {'✅ 成功' if not log.get('error') else f'❌ エラー: {log.get("error")}'}
        </div>
"""
            
            for step in log.get('steps', []):
                html_content += f"""
        <div class="step">
            <strong>ステップ {step['step_number']}</strong> ({step['duration_from_start']}秒) - 
            ノード: {', '.join(step['nodes'])}
"""
                for node_name, details in step.get('details', {}).items():
                    if details:
                        html_content += f"<br>　{node_name}: "
                        if 'next_agent' in details:
                            html_content += f"次のエージェント={details['next_agent']} "
                        if 'latest_step' in details:
                            html_content += f"ステップ={details['latest_step'][:50]}... "
                
                html_content += "</div>"
            
            html_content += "</div>"
        
        html_content += """
</body>
</html>
"""
        
        report_file = f'langgraph_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ 実行レポート生成完了: {report_file}")
        return report_file


async def main():
    """メイン実行関数"""
    
    print("🎨 ローカルLangGraph可視化ツール")
    print("=" * 60)
    print("LangSmithアクセス問題の代替可視化ソリューション")
    print()
    
    visualizer = LocalLangGraphVisualizer()
    
    # 1. 構造図の生成
    print("1. 📊 構造図生成")
    visualizer.create_mermaid_html()
    
    try:
        visualizer.generate_graphviz_diagram()
    except:
        print("⚠️ Graphvizスキップ（インストールされていません）")
    
    # 2. 実行トレーシング
    print("\n2. 🔍 実行トレーシング")
    test_queries = [
        "圃場の情報を教えて",
        "昨日トマトの水やりをしました",
        "作業履歴を確認したい"
    ]
    
    for query in test_queries:
        await visualizer.detailed_execution_trace(query)
    
    # 3. レポート生成
    print("\n3. 📑 実行レポート生成")
    visualizer.generate_execution_report()
    
    print("\n🎉 ローカル可視化完了")
    print("\n📁 生成されたファイル:")
    print("  • langgraph_flow.html - インタラクティブフロー図")
    print("  • langgraph_structure.png - 構造図（Graphvizが利用可能な場合）")
    print("  • langgraph_report_*.html - 詳細実行レポート")


if __name__ == "__main__":
    asyncio.run(main())