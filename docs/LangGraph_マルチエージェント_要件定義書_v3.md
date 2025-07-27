# 農業AIエージェント 総合要件定義書 v4.0

**バージョン**: 4.0
**作成日**: 2025-07-27
**対象**: LangGraphによる次世代マルチエージェントシステムの新規構築
**基盤**: 既存システム「Agri_AI3」の資産と知見

---

## 第1部: プロジェクトビジョンと戦略 (Why)

### 1.1. 核心コンセプト：LINEで完結する、農家のためのAIパートナー

本プロジェクトは、日常的に使われる**LINEプラットフォーム**をインターフェースとし、農業従事者に**「パーソナライズされ、共に進化するデジタルパートナー」**を提供することを目的とする。

LINEでの自然な対話と、直感的なLIFFアプリケーションをシームレスに連携させる。これにより、情報の分断や判断の迷いといった農業現場の根本課題を解決し、**思考のプロセスそのものをなくす**。誰もが熟練者のように自信を持って日々の作業に取り組める未来を実現する。

### 1.2. 解決したい課題

-   **情報の散在**: 天気、市況、作業履歴などの情報が別々のツールに散在し、統合的な判断が難しい。
-   **経験と勘への依存**: 新規就農者や経験の浅い作業者にとって、「どの畑に」「いつ、どの農薬を散布すべきか」といった判断は大きな負担となっている。
-   **記録と報告の負荷**: 圃場での作業後、事務所に戻ってから日報を作成するなど、記録・報告作業が非効率。
-   **労働力不足と多忙**: 日々の作業記録や計画立案に多くの時間が割かれている。

### 1.3. 開発のゴールと成功指標

-   **定性ゴール**: 農業従事者が、圃場のどこにいても、**LINEを開けば「次に何をすべきか」が分かり**、思考の負荷なく、自信を持って作業に集中できる状態を実現する。
-   **定量ゴール (KPI)**:
    -   農作業の判断と思考にかかる時間を平均10分から**0分**にする。
    -   新人作業員が判断に迷う時間が週平均60分から**5分未満**に短縮される。
    -   **LINE経由での作業記録・タスク完了率が95%以上**を維持する。
    -   AIの応答時間を**平均3秒以内**に短縮する。

---

## 第2部: システム設計とアーキテクチャ (How)

### 2.1. 全体アーキテクチャ：LINE中心のSupervisor-Workerパターン

**LangGraph**フレームワークを利用した**「スーパーバイザー・ワーカー」マルチエージェント・アーキテクチャ**を採用する。ユーザーとのすべての対話はLINEを起点とし、SupervisorAgentが司令塔として機能する。

```mermaid
graph TD
    subgraph "ユーザーインターフェース"
        A[👤 農業従事者] --> B[📱 LINE (チャット / LIFF)]
    end

    subgraph "AIエージェント層 (LangGraph on Google Cloud Run)"
        B -- Webhook --> C[🧠 SupervisorAgent]
        C -- "タスク割当" --> D[📖 ReadAgent]
        C -- "タスク割当" --> E[✏️ WriteAgent]
        C -- "タスク割当" --> F[🎯 RecommendationAgent]
        C -- "タスク割当" --> G[📢 NotificationAgent]
    end

    subgraph "バックエンド & データ層"
        subgraph "既存ツール群（100%流用）"
            T1[TaskLookupTool]
            T2[FieldInfoTool]
            T3[WorkLogRegistrationTool]
            T4[CropMaterialTool]
            T5[WeatherForecastTool]
            T6[InventoryCheckTool]
            T7[SensorDataTool]
            T8[NotificationTool]
            T9[TaskUpdateTool]
            T10[TaskCreateTool]
            T11[WorkerLogTool]
        end
        H[🗄️ MongoDB Atlas]
        I[☁️ 外部API (気象情報など)]
    end

    D --> T1 & T2 & T4 & T5 & T6 & T7 & T11
    E --> T3 & T9 & T10
    F --> T1 & T2 & T4 & T5 & T6 & I
    G --> T8

    D & E & F & G --> H
    H -- "データ" --> D & E & F & G

    D & E & F & G -- "結果報告" --> C
    C -- "最終応答" --> B
```

### 2.2. UI/UX設計：LINEとLIFFのシームレスな連携

-   **LINEチャット (対話インターフェース)**:
    -   「今日の消毒作業、A畑とB畑で終わりました」といった自然言語での作業報告。
    -   「明日の天気は？」「A畑の次の作業は？」といった簡単な質問応答。
    -   AIからの能動的なアラート通知（例：「明日は雨予報です。今日の内に散布を終えましょう」）。

-   **LIFF (LINE Front-end Framework) (リッチUI)**:
    -   **基本ダッシュボード**: AIによる注意喚起がある圃場のハイライト表示、本日の推奨作業リスト、気象・市況ウィジェット。
    -   **作業計画・可視化**: カレンダー形式での作業計画表示や、過去の作業履歴のグラフ表示。
    -   **複雑なデータ入力**: 新しい圃場の登録など、定型的なデータ入力フォーム。

### 2.3. エージェントと状態管理

#### **エージェント詳細**
-   **SupervisorAgent (指揮者)**: LINE Webhookからのメッセージを起点に、ユーザー意図を分析し、最適な専門エージェントを選択。最終応答を整形しLINEに返信する。
-   **ReadAgent (読み取り専門)**: 作業履歴の検索、圃場情報の参照など、全ての読み取り専用クエリを高速に処理。
-   **WriteAgent (書き込み専門)**: 作業記録の登録、タスクの作成・更新など、データの整合性を保証しながら書き込み処理を実行。**ユーザー確認フロー**を内包する。
-   **RecommendationAgent (推薦専門)**: 天候、作業履歴、作物情報などを統合的に分析し、農薬散布のタイミングや作業計画を提案する。
-   **NotificationAgent (通知専門)**: スケジュールされたタスクのリマインドや、気象警報などを非同期でユーザーにLINE通知する。

#### **状態管理 (`AgriAgentState`)**
会話の文脈とタスクの状態を管理する。`MongoDBSaver`により永続化され、ユーザーごとの会話セッションを維持する。
```python
from typing import TypedDict, Annotated, List, Dict, Any
from langchain_core.messages import BaseMessage
import operator

class AgriAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_id: str
    thread_id: str
    next_agent: str
    pending_confirmation: Dict[str, Any]
    # ... (その他、タスク管理やデバッグ用のフィールド)
```

---

## 第3部: 開発ロードマップと技術スタック (What)

### 3.1. 開発フェーズ戦略

| フェーズ | 期間 | 主要目標 |
|---|---|---|
| **Phase 1: 基盤構築** | 3週間 | Supervisor+ReadAgentによる**LINEでの基本的な質疑応答**を実現。 |
| **Phase 2: コア機能実装** | 3週間 | WriteAgentによる**LINEからの作業記録登録**と確認フローを実装。**LIFF基本ダッシュボード**を公開。 |
| **Phase 3: AI機能高度化** | 4週間 | RecommendationAgentによる**作業提案機能**を実装。LIFFの高機能化。 |
| **Phase 4: 自律システムの実現** | 4週間 | NotificationAgentによる**プロアクティブな通知機能**を実装。非同期処理基盤を構築。 |

### 3.2. 技術スタック

-   **UI/UX**: **LINE Messaging API, LIFF**
-   **AI/エージェント**: Python 3.9+, LangChain, **LangGraph**
-   **LLM**: Google Gemini Pro / Flash
-   **データベース**: MongoDB Atlas (Motorによる非同期アクセス)
-   **インフラ**: Google Cloud Functions (Webhook), Google Cloud Run (エージェント実行), Google Cloud Pub/Sub (非同期通知)
-   **監視**: LangSmith

### 3.3. 既存資産の活用

-   **ツール群**: 既存の11個のLangChainツールを100%流用。
-   **データベース**: 既存のMongoDBスキーマとデータを100%流用。
-   **ドメインロジック**: 確認フロー、抽出ロジックなどを90%以上流用。

---

## 第4部: 移行計画とリスク管理

（このセクションはv3の内容をほぼ維持）

### 4.1. 移行戦略
既存システムは稼働を継続し、並行してLangGraphシステムを新規構築。Phase 2完了後、一部ユーザーから段階的に新システムへ移行を開始し、最終的に完全移行を目指す。

### 4.2. リスク軽減策
-   **フォールバック**: 問題発生時は、DNSレベルで即座に既存システムへ切り戻せる構成を準備。
-   **並行テスト**: 同一の入力に対し、両システムの結果を比較検証する仕組みを導入。
-   **段階的ロールアウト**: 機能単位、ユーザーグループ単位での慎重な移行を実施。

---
