# 【Step 1】 Why：この機能を開発する目的と背景

- **1-1. 解決したいユーザー課題 (User Problem / Pain):**
    - **誰が (Who):** 農業で農場での農作業員（特に経験の浅い新人）、および農場管理者。
    - **どんな状況で (When/Where):** 日々の作業計画を立てる時、現場で作業内容を確認する時、特に「どの畑の」「どの作物に」「いつ、どの農薬を散布すべきか」といった専門的な判断が求められる時。
    - **何を解決したいか (What):** 思考のプロセスそのものをなくしたい。紙や個人の記憶、経験と勘に頼った属人的な農業から脱却したい。特に、畑・作物・天候・時期によって最適な農薬や作業を都度考えるのが大きな精神的・時間的負担となっている。使い慣れたLINEでAIに相談すれば、熟練者のように具体的な次の一手を指示してくれる、そんな未来を実現したい。
- **1-2. 解決したいビジネス課題 (Business Problem / Gain):**
    - **生産性の向上:** 作業判断の時間をゼロにし、作業員の稼働率を最大化する。
    - **品質の安定化:** AIによる標準化された最適な作業提案により、作業員のスキルレベルに関わらず、農作物の品質を安定・向上させる。
    - **コスト削減:** 農薬や肥料の過不足ない使用、作業ミスの削減により、資材コストと損失を低減する。
    - **技術伝承と人材育成:** AIが熟練者の知識を学習・提供することで、新人でも即戦力として活躍できるようになり、教育コストを削減する。
- **1-3. 開発のゴール (Project Goal) & 成功指標 (Success Metrics):**
    - **定性ゴール:** 作業員が、圃場のどこにいても、スマホ一つで「次に何をすべきか」の具体的な指示を受け取り、思考の負荷なく、自信を持って作業に集中できるようになる。
    - **定量ゴール (KPI):**
        - 農薬選定にかかる時間が平均10分から0分になる（AIの提案を信頼して採用）。
        - 新人作業員が一人で判断に迷う時間が週平均60分から5分未満に短縮される。
        - LINE経由でのタスク実行率が95%以上を維持する。
        - AIの応答時間を3秒以内に短縮（MongoDB高速検索による）。
- **1-4. スコープ (Scope):**
    - **やること (In Scope):**
        - **フェーズ1:** MongoDBのデータを参照し、「今日のタスク」などを自然言語で応答する基本的なエージェントの構築。
        - **フェーズ2:** 圃場・作物・天候などの情報から、AIが最適な農薬や作業を判断し、自然言語で提案する機能の実装。
        - **フェーズ3:** LINE上での双方向のタスク管理（完了報告、自動スケジュール更新）。
    - **やらないこと (Out of Scope):**
        - リアルタイムの画像認識による病害虫診断（将来展望）。
        - サプライヤーへの資材自動発注機能。

---

## 【Step 2】 How：どうやって目的を実現するのか（仕様・設計）

- **2-1. ユーザーストーリー (User Stories):**
    - `新人作業員として、農薬の選択で絶対に間違えたくないので、「A畑のトマト、次の作業は？」と聞くと、AIが「病害虫Xの予防のため、農薬YをZ倍希釈で散布してください」と具体的に指示してくれる。`
    - `作業員として、「今日の消毒作業終わりました」とLINEで報告すると、AIが該当タスクを自動で完了にし、7日後の次回防除を自動スケジュールしてくれる。`
    - `農場管理者として、「来週の作業予定は？」と聞くと、全圃場の作業計画が一覧で表示され、リソース配分を効率的に判断できる。`
- **2-2. ビジネスルール (Business Rules):**
    - AIの提案は、MongoDB上の以下のコレクション群のデータを正とする：
        - **作物マスター (crops)**: 作物の基本情報、栽培カレンダー、適用可能な農薬リスト
        - **資材マスター (materials)**: 農薬・肥料の詳細情報、希釈倍率、使用制限
        - **圃場マスター (fields)**: 圃場の位置・面積・土壌情報、作付け状況
        - **作付け計画 (cultivation_plans)**: 年間作付けスケジュール、品種・作期情報
        - **作業履歴 (work_records)**: 時系列の全作業実績、使用資材・数量記録
    - MongoDBのドキュメント指向設計により、関連データを統合格納し、高速なデータ取得を実現する。
    - 農薬の提案ロジックは、圃場の作業履歴から過去の散布パターンとローテーション防除を分析し、天候・生育ステージを考慮する。
    - 防除作業完了時は、該当圃場の作業履歴に記録し、自動的に7日後（設定可能）の次回防除をスケジュールする。
    - 全ての作業指示と完了報告は、MongoDB上に構造化ドキュメントとして記録され、AIの学習データとして蓄積される。
- **2-3. 機能要件 (Functional Requirements):**
    - **[F-01] データ参照:** LangChainエージェントはMongoDB上のデータを高速で読み取ることができる。
    - **[F-02] データ作成:** エージェントはMongoDBに新しいドキュメント（作業ログ等）を作成できる。
    - **[F-03] データ更新:** エージェントはMongoDBの既存ドキュメントを更新できる。
    - **[F-04] 自動スケジューリング:**
        - **[F-04-01] 自動タスク生成:** 作業完了時に次回タスクを自動生成する。
        - **[F-04-02] 今日のタスク通知:** 毎朝、作業タスクを対象者にLINEで通知する。
    - **[F-05] 自然言語処理:**
        - **[F-05-01] 自然言語での問い合わせ:** 「今日のタスクは？」「防除の進捗は？」等の質問に回答する。
        - **[F-05-02] 自然言語での作業報告:** 「消毒作業終わりました」等の報告を自動でデータ更新に変換する。
    - **[F-06] AI提案:**
        - **[F-06-01] 農作業提案:** 圃場、作物、天候、生育ステージに基づき、次に実施すべき最適な作業を判断・提案する。
        - **[F-06-02] 農薬ローテーション提案:** 過去の使用履歴から最適な農薬を自動選定する。
    - **[F-07] ユーザー認証:** LINEアカウントとMongoDBの「作業者マスター」を紐付ける。
    - **[F-08] リアルタイム通知:** MongoDBのChange Streamsを使用したリアルタイム更新通知。
    - **[F-09] リッチメニュー:** よく使う機能をLINEのリッチメニューに配置する。
- **2-4. 非機能要件 (Non-Functional Requirements):**
    - **[NF-01] セキュリティ:** APIキーや接続情報はGoogle Secret Manager等で安全に管理する。
    - **[NF-02] パフォーマンス:** ユーザーからの問い合わせに対し、3秒以内に応答を返す（MongoDB高速検索）。
    - **[NF-03] 可用性:** システムは24時間365日稼働を目指す（MongoDB Atlas冗長化）。
    - **[NF-04] スケーラビリティ:** 農場規模拡大に応じてデータ量とアクセス数が増加しても対応可能。

### 2-5. LangChain ツール一覧（フェーズ1で実装予定）
| ID | Tool 名 | 役割 | 主に使うコレクション | 代表クエリ例 |
|----|---------|------|---------------------|---------------|
| T1 | TaskLookupTool | 未完了タスク照会 | `auto_tasks` / `work_records` | 「今日のタスクは？」 |
| T2 | TaskUpdateTool | タスク完了・延期更新 | `work_records` | 「防除終わったよ」 |
| T3 | TaskCreateTool | タスク追加 / schedule_rules 適用 | `auto_tasks` | 「B畑に除草タスク追加」 |
| T4 | FieldInfoTool | 圃場・作付け情報照会 | `fields`, `cultivation_plans` | 「A畑の作付け状況は？」 |
| T5 | CropMaterialTool | 作物⇔資材対応検索／希釈計算 | `crops`, `materials` | 「ダコニール何倍？」 |
| T6 | InventoryCheckTool | 資材在庫確認 | `inventory` | 「在庫が少ない農薬は？」 |
| T7 | MaterialDilutionTool | 希釈倍率・使用制限取得 | `materials` | 「ヨーバルフロアブルの希釈率は？」 |
| T8 | WeatherForecastTool | 天気予報取得 | `weather_forecasts` | 「来週の天気予報は？」 |
| T9 | SensorDataTool | センサ最新値照会 | `sensor_logs` | 「A畑の土壌水分は？」 |
| T10| WorkerLogTool | 作業者ログ集計 | `workers`, `work_records` | 「田中さんの先月の作業時間」 |
| T11| NotificationTool | LINE通知／設定変更 | `notifications` | 「全員に8時集合を通知して」 |

> 拡張予定（Phase3 以降）：CostAnalysisTool, YieldPredictionTool, DiseaseRiskTool, PurchaseOrderTool など。

---

## 【Step 3】 What：具体的に、何を作り、どう進めるのか（タスク・実装）

- **3-1. 主要な成果物 (Key Deliverables):**
    - LangChainで構築されたAIエージェントのソースコード。
    - MongoDB操作、農薬選定ロジック等を実装したLangChainツールのソースコード。
    - Google Cloud Functions上で動作するLINE Webhook用関数。
    - MongoDBデータベース設計ドキュメント。
    - GitHubリポジトリでのソースコード管理。
- **3-2. 実装タスクの内訳 (Task Breakdown / Epics):**
    - **フェーズ1: 基盤構築:** LangChain環境セットアップ、MongoDB接続、Airtableスキーマ・データ完全移行、基本エージェントの構築。
    - **フェーズ2: インテリジェント機能開発:** 農薬提案システム、自動スケジューリング、LINE連携の実装。
    - **フェーズ3: 本番化・運用:** デプロイ、モニタリング体制の構築、継続的改善。
- **3-3. 開発マイルストーン (Development Milestones):**
    - **Sprint 1-2:** フェーズ1完了。ローカル環境でMongoDB連携エージェントが動作する。
    - **Sprint 3-4:** フェーズ2完了。LINE上でAIが自然言語で農薬提案・作業管理を行えるプロトタイプが完成。
    - **Sprint 5:** フェーズ3着手。Cloud Runへデプロイし、一部ユーザーによるUAT（ユーザー受け入れテスト）を開始。
- **3-4. 技術スタック・アーキテクチャ方針 (Tech Stack / Architecture):**
    - **言語:** Python 3.9+
    - **AIエージェント:** LangChain (Agent + Tools)
    - **LLM:** OpenAI GPT-4 または Anthropic Claude
    - **データベース:** MongoDB Atlas (NoSQL)
    - **インフラ:** Google Cloud Functions (Webhook), Google Cloud Run (エージェント実行環境)
    - **UI:** LINE Messaging API
    - **ソースコード管理:** Git / GitHub
    - **秘密管理:** Google Secret Manager
    - **監視:** Google Cloud Monitoring + MongoDB Atlas監視
- **3-5. MongoDB データベース設計:**
    
    **3-5-1. 設計方針:**
    - **ドキュメント指向設計:** 圃場ごとに関連情報を統合したドキュメント構造
    - **埋め込み優先:** 関連データはサブドキュメントとして埋め込み、JOIN操作を最小化
    - **時系列データ対応:** 作業履歴、センサーデータの効率的な格納
    - **Change Streams活用:** リアルタイム更新の自動処理
    
    **3-5-2. コレクション設計:**
    
    **[作物マスター (crops)]**
    ```json
    {
        "_id": ObjectId,
        "name": "トマト",
        "variety": "桃太郎",
        "category": "果菜類",
        "cultivation_calendar": [
            {
                "stage": "育苗期",
                "days_from_planting": [0, 30],
                "key_activities": ["灌水", "温度管理"],
                "applicable_materials": ["発根促進剤", "育苗培土"]
            }
        ],
        "disease_pest_risks": [
            {
                "name": "疫病",
                "risk_period": ["5月", "6月", "7月"],
                "prevention_materials": ["銅水和剤", "ストロビルリン系"]
            }
        ],
        "applicable_materials": [
            {
                "material_id": ObjectId,
                "application_timing": "生育期",
                "dilution_rate": "1000倍"
            }
        ]
    }
    ```
    
    **[資材マスター (materials)]**
    ```json
    {
        "_id": ObjectId,
        "name": "ダコニール1000",
        "type": "殺菌剤",
        "active_ingredient": "TPN",
        "manufacturer": "SBI ALApromo",
        "dilution_rates": {
            "tomato": "1000倍",
            "cucumber": "800倍"
        },
        "preharvest_interval": 7,
        "max_applications_per_season": 5,
        "rotation_group": "M",
        "target_diseases": ["疫病", "灰色かび病"],
        "usage_restrictions": {
            "water_source_distance": 100,
            "bee_toxicity": "注意"
        }
    }
    ```
    
    **[圃場マスター (fields)]**
    ```json
    {
        "_id": ObjectId,
        "field_code": "A-01",
        "name": "第1ハウス",
        "area": 300,
        "location": {
            "latitude": 35.1234,
            "longitude": 139.5678
        },
        "soil_type": "砂壌土",
        "irrigation_system": "点滴灌漑",
        "current_cultivation": {
            "crop_id": ObjectId,
            "variety": "桃太郎",
            "planting_date": "2024-03-15",
            "expected_harvest": "2024-07-15",
            "growth_stage": "開花期"
        },
        "last_work_date": "2024-07-10",
        "next_scheduled_work": {
            "work_type": "防除",
            "scheduled_date": "2024-07-17",
            "materials": [ObjectId]
        }
    }
    ```
    
    **[作付け計画 (cultivation_plans)]**
    ```json
    {
        "_id": ObjectId,
        "year": 2024,
        "field_id": ObjectId,
        "crop_rotations": [
            {
                "season": "春作",
                "crop_id": ObjectId,
                "variety": "桃太郎",
                "planting_date": "2024-03-15",
                "harvest_start": "2024-07-01",
                "harvest_end": "2024-07-31",
                "estimated_yield": 1200
            }
        ],
        "annual_target_yield": 2400,
        "resource_allocation": {
            "labor_hours": 480,
            "material_budget": 150000
        }
    }
    ```
    
    **[作業履歴 (work_records)]**
    ```json
    {
        "_id": ObjectId,
        "field_id": ObjectId,
        "work_date": "2024-07-10",
        "work_type": "防除",
        "worker": "田中太郎",
        "weather": {
            "temperature": 28,
            "humidity": 65,
            "wind_speed": 2.3,
            "conditions": "晴れ"
        },
        "materials_used": [
            {
                "material_id": ObjectId,
                "quantity": 200,
                "unit": "ml",
                "dilution_rate": "1000倍",
                "target_disease": "疫病"
            }
        ],
        "work_details": {
            "start_time": "08:00",
            "end_time": "09:30",
            "covered_area": 300,
            "equipment_used": "電動噴霧器",
            "notes": "葉裏もしっかり散布"
        },
        "next_work_scheduled": {
            "work_type": "防除",
            "scheduled_date": "2024-07-17",
            "auto_generated": true
        },
        "created_at": "2024-07-10T09:30:00Z",
        "updated_at": "2024-07-10T09:30:00Z"
    }
    ```
    
    **3-5-3. インデックス設計:**
    - **fields**: `field_code`, `current_cultivation.crop_id`, `next_scheduled_work.scheduled_date`
    - **work_records**: `field_id + work_date`, `work_type + work_date`, `materials_used.material_id`
    - **crops**: `name`, `category`, `disease_pest_risks.risk_period`
    - **materials**: `name`, `type`, `target_diseases`, `rotation_group`

---

## 【Step 4】 Dashboard 要件（Web 管理 UI）

### 4-1. 目的
LINE ボットでは入力しづらいマスター管理・計画編集・分析機能を Web ダッシュボードで提供し、現場（LINE）と管理業務（Web）を分離することで運用効率とデータ整合性を高める。

### 4-2. 主要ユースケース
1. マスター CRUD（圃場・作物・資材・作業者・在庫）
2. タスク／作付け計画をカレンダー／ガントで可視化・編集
3. 作業進捗・収量・コストなど KPI をグラフで確認
4. LINE 連携設定（通知時刻・メニュー）を変更
5. 権限ロールの付与・変更

### 4-3. 画面モジュール
| モジュール | 機能概要 |
|------------|---------|
| Dashboard (Home) | 今日のタスク数・完了率、在庫アラート、天気ウィジェット |
| Tasks / Calendar | 日/週/月カレンダー、ドラッグ＆ドロップで日付変更、フィルタ（圃場・作物） |
| Fields & Cultivation Plans | 圃場リスト → モーダル編集、作付け計画ガント表示 |
| Materials & Inventory | 資材一覧 + 在庫数量、CSV 入出力、発注点アラート |
| Workers | LINE ID 紐付け、役割変更、作業ログ集計 |
| Settings | 通知テンプレート、スケジュール規則、API キー管理 |

### 4-4. 権限ロール
| ロール | 機能アクセス |
|--------|-------------|
| Admin | 全モジュール CRUD・権限管理・設定 |
| Manager | Tasks / Calendar / Fields / Plans / Workers CRUD（Materials は閲覧のみ） |
| WorkerView | Dashboard / Tasks 閲覧のみ |

### 4-5. 技術スタック方針
- **Frontend:** Next.js + TypeScript + MUI (DataGrid / DateCalendar)
- **Backend API:** FastAPI + Motor (async MongoDB)
- **Auth:** Firebase Auth（LINE OAuth 連携）
- **Realtime:** MongoDB Change Streams → WebSocket/SSE
- **デプロイ:** Frontend → Vercel / Cloud Run、API → Cloud Run

### 4-6. フォーム UX (例: タスク登録)
1. 「＋タスク」ボタン → 右パネルスライドイン
2. 圃場選択 → 作業種別選択 → フォーム動的切替
3. 必須項目バリデーション (Yup/Zod)
4. 保存 → `/tasks` POST → MongoDB `auto_tasks`
5. 生成イベントを Change Streams で LINE Push

### 4-7. 開発フェーズ
| Phase | 機能範囲 |
|-------|----------|
| 0 | Auth & Dashboard 読み取り専用 |
| 1 | Tasks / Calendar CRUD + LINE Push |
| 2 | マスター CRUD（fields, crops, materials） |
| 3 | Inventory & Purchase Orders |
| 4 | KPI / Analytics ダッシュ |
| 5 | センサ可視化 & アラート |

> 上記ダッシュボード要件は MongoDB スキーマおよび LINE ボット機能と整合するよう設計されている。