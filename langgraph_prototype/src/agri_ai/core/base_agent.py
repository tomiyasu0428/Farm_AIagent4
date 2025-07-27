"""
共通ベースエージェント
WorkLogSearchAgent など複数のエージェントが共通で利用する最低限の基底クラス。
LangChain の AgentExecutor を使わない簡易バージョン。
"""

from abc import ABC, abstractmethod
from typing import List, Any
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """エージェント共通の基底クラス"""

    def __init__(self):
        # 下位クラスで実装されたメソッドを呼び出して初期化
        try:
            self.llm = self._setup_llm()
        except Exception as e:
            logger.warning(f"LLMセットアップでエラー: {e}. ダミーを設定します。")
            self.llm = None

        try:
            self.tools: List[Any] = self._setup_tools()
        except Exception as e:
            logger.warning(f"ツールセットアップでエラー: {e}. 空リストを設定します。")
            self.tools = []

        # サブクラスで必要に応じてエージェントエグゼキュータを生成してください

    # ----- サブクラスが実装すべきメソッド -----------------
    @abstractmethod
    def _setup_llm(self):
        """LLM の初期化を行い、インスタンスを返す"""
        raise NotImplementedError

    @abstractmethod
    def _setup_tools(self) -> List[Any]:
        """ツールの初期化を行い、リストで返す"""
        raise NotImplementedError

    @abstractmethod
    def _create_system_prompt(self) -> str:
        """システムプロンプトを返す。KV-Cache 最適化などの固定文"""
        raise NotImplementedError

    # ------------------------------------------------------

    # 汎用ハンドリング関数を必要に応じて追加できます
