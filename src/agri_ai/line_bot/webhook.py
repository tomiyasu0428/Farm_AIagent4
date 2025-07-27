"""
LINE Bot Webhook実装
"""

from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import logging
import concurrent.futures

from shared.config.settings import settings
# from ..core.master_agent import master_agent  # 従来システム（コメントアウト）
from ..core.confirmation_middleware import ConfirmationMiddleware
from ..core.session_manager import SessionManager

# LangGraphシステムの統合
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../langgraph_prototype/src'))
from agri_ai.langgraph.supervisor import app as langgraph_app
from agri_ai.langgraph.state import AgriAgentState

logger = logging.getLogger(__name__)

# FastAPIアプリケーションの作成
app = FastAPI(title="農業AI LINE Webhook", version="1.0.0")

# LINE Bot APIの初期化
line_bot_api = LineBotApi(settings.line_bot.channel_access_token)
handler = WebhookHandler(settings.line_bot.channel_secret)

# 確認フローミドルウェアの初期化
confirmation_middleware = ConfirmationMiddleware()
session_manager = SessionManager()


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {"message": "Agri AI LINE Bot Webhook is running."}


@app.get("/health")
async def health_check():
    """詳細なヘルスチェック"""
    try:
        # MongoDB接続チェック（新しい接続を作成）
        from ..database.mongodb_client import create_mongodb_client
        
        test_client = create_mongodb_client()
        db_health = await test_client.health_check()
        
        # テスト用クライアントを閉じる
        await test_client.disconnect()

        return {
            "status": "healthy",
            "database": db_health,
            "agent": "langgraph_initialized",
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/webhook")
async def webhook(request: Request):
    """LINE Webhookエンドポイント"""
    # 署名の検証を WebhookHandler に任せる
    signature = request.headers["X-Line-Signature"]
    body = await request.body()

    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        logger.error("署名検証に失敗しました。")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except LineBotApiError as e:
        logger.error(f"LINE Bot API エラー: {e.status_code} {e.error.message}")
        raise HTTPException(status_code=500, detail=f"LINE Bot API error: {e.error.message}")
    except Exception as e:
        logger.error(f"Webhook処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"status": "ok"}


# 自前の署名検証関数は不要なため削除
# def _verify_signature(body: bytes, signature: str) -> bool:
#    """署名の検証"""
#    try:
#        hash_value = hmac.new(settings.line_channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
#
#        signature_hash = base64.b64encode(hash_value).decode("utf-8")
#        return hmac.compare_digest(signature, signature_hash)
#    except Exception as e:
#        logger.error(f"署名検証エラー: {e}")
#        return False


async def _process_message_async(message_text: str, user_id: str, reply_token: str):
    """非同期でメッセージを処理する関数（確認フローミドルウェア対応版）"""
    try:
        logger.info(f"メッセージ処理開始 - ユーザー: {user_id}, 内容: {message_text}")
        
        # Step 1: 確認フローミドルウェアで状態判定
        is_confirmation, middleware_result = confirmation_middleware.process_message(
            user_id, message_text
        )
        
        if is_confirmation:
            # 確認フロー処理
            logger.info(f"確認フロー処理 - ユーザー: {user_id}")
            response_text = middleware_result.get("message", "処理が完了しました。")
            
            line_bot_api.reply_message(reply_token, TextSendMessage(text=response_text))
            logger.info(f"確認フロー応答送信完了 - ユーザー: {user_id}")
            return
        
        # Step 2: LangGraphエージェント処理
        if middleware_result.get("requires_agent_processing"):
            logger.info(f"LangGraphシステム実行開始 - ユーザー: {user_id}")
            
            # セッション管理と連携したthread_idの取得
            thread_id = session_manager.get_or_create_session(user_id)
            
            # LangGraphの状態を作成
            initial_state = AgriAgentState(
                messages=[{"role": "user", "content": message_text}],
                user_id=user_id,
                thread_id=thread_id,
                next_agent="",
                pending_confirmation={},
                final_response="",
                intermediate_steps=[]
            )
            
            logger.debug(f"LangGraph状態作成 - user_id: {user_id}, thread_id: {thread_id}")
            
            # LangGraphワークフロー実行
            try:
                result = await langgraph_app.ainvoke(initial_state)
                response_text = result.get("final_response", "申し訳ございませんが、処理できませんでした。")
                
                # セッション情報の更新
                session_manager.update_last_activity(user_id)
                
                # デバッグ情報
                intermediate_steps = result.get("intermediate_steps", [])
                if intermediate_steps:
                    logger.info(f"LangGraph実行ステップ: {len(intermediate_steps)}ステップ")
                    for step in intermediate_steps:
                        logger.debug(f"  - {step}")
                        
                # 結果の永続化（将来的にLangGraphの状態永続化と統合）
                logger.debug(f"LangGraph処理完了 - 応答長: {len(response_text)}文字")
                        
            except Exception as e:
                logger.error(f"LangGraph実行エラー: {e}")
                response_text = "申し訳ございませんが、システム処理中にエラーが発生しました。"
            
            # 確認フロー対応の結果解析（LangGraph対応）
            if _is_confirmation_response(response_text):
                confirmation_data = _extract_confirmation_data_langgraph(response_text, result)
                if confirmation_data:
                    # LangGraphから実行されたエージェント情報を取得
                    agent_type = _detect_agent_type_langgraph(result)
                    confirmation_middleware.save_confirmation_request(
                        user_id, agent_type, confirmation_data
                    )
                    logger.info(f"確認フロー開始 - ユーザー: {user_id}, エージェント: {agent_type}")
            
            line_bot_api.reply_message(reply_token, TextSendMessage(text=response_text))
            logger.info(f"通常フロー応答送信完了 - ユーザー: {user_id}")
        else:
            # エラーケース
            error_message = middleware_result.get("message", "処理中にエラーが発生しました。")
            line_bot_api.reply_message(reply_token, TextSendMessage(text=error_message))
            
    except Exception as e:
        logger.error(f"メッセージ処理エラー - ユーザー: {user_id}, エラー: {e}")
        # エラー時の応答
        try:
            error_message = "😅 申し訳ございません。処理中にエラーが発生しました。\nしばらくしてから再度お試しください。"
            line_bot_api.reply_message(reply_token, TextSendMessage(text=error_message))
        except Exception as reply_error:
            logger.error(f"エラー応答送信失敗: {reply_error}")


def _is_confirmation_response(response_text: str) -> bool:
    """応答が確認を求めているかどうかを判定"""
    confirmation_keywords = [
        "登録しますか", "実行しますか", "よろしいですか", "確認", 
        "はい」と", "OK」と", "実行する場合", "登録する場合"
    ]
    return any(keyword in response_text for keyword in confirmation_keywords)


def _extract_confirmation_data(response_text: str, agent_result: dict) -> dict:
    """エージェント結果から確認データを抽出"""
    try:
        # HTMLコメント内のJSONデータを検出（WorkLogRegistrationAgentTool形式）
        import re
        import json
        
        # HTMLコメント形式の確認データを検索
        comment_match = re.search(r'<!-- CONFIRMATION_DATA: ({.*?}) -->', response_text)
        if comment_match:
            try:
                confirmation_data = json.loads(comment_match.group(1))
                logger.info(f"HTML形式確認データ抽出成功: {confirmation_data.get('agent_type', 'Unknown')}")
                return confirmation_data
            except json.JSONDecodeError as e:
                logger.warning(f"HTML形式確認データJSON解析エラー: {e}")
        
        # 従来形式の確認データチェック（後方互換性）
        if "requires_confirmation" in str(agent_result):
            json_match = re.search(r'\{.*"requires_confirmation".*\}', str(agent_result))
            if json_match:
                try:
                    legacy_data = json.loads(json_match.group(0))
                    logger.info("従来形式確認データ抽出成功")
                    return legacy_data
                except json.JSONDecodeError:
                    pass
        
        # フォールバック: 基本的な確認データを作成
        logger.info("フォールバック確認データ作成")
        return {
            "requires_confirmation": True,
            "agent_type": "UnknownAgent",
            "extracted_info": {},
            "confirmation_message": response_text,
            "created_at": "2025-01-01T00:00:00"
        }
        
    except Exception as e:
        logger.error(f"確認データ抽出エラー: {e}")
        return {}


def _detect_agent_type(response_text: str, agent_result: dict) -> str:
    """応答からエージェントタイプを推定"""
    # 応答内容からエージェントタイプを推定
    if any(keyword in response_text for keyword in ["作業記録", "登録", "収穫", "ケース"]):
        return "WorkLogRegistrationAgent"
    elif any(keyword in response_text for keyword in ["圃場", "フィールド", "畑"]):
        return "FieldAgent"
    elif any(keyword in response_text for keyword in ["検索", "探す", "調べる"]):
        return "SearchAgent"
    else:
        return "UnknownAgent"


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージの処理"""
    try:
        user_id = event.source.user_id
        message_text = event.message.text
        reply_token = event.reply_token

        logger.info(f"受信メッセージ - ユーザー: {user_id}, 内容: {message_text}")

        # 非同期処理をバックグラウンドタスクで実行
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # バックグラウンドタスクとして非同期処理を実行
            loop.create_task(_process_message_async(message_text, user_id, reply_token))
        except RuntimeError:
            # イベントループがない場合のフォールバック
            logger.warning("イベントループが利用できません。ThreadPoolExecutorで処理します。")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(_process_message_async(message_text, user_id, reply_token))
                )
                future.result(timeout=30)  # 30秒でタイムアウト

    except concurrent.futures.TimeoutError:
        logger.error("メッセージ処理がタイムアウトしました")
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="処理に時間がかかっています。しばらくしてから再度お試しください。"),
            )
        except Exception as reply_error:
            logger.error(f"タイムアウト応答送信失敗: {reply_error}")

    except Exception as e:
        logger.error(f"メッセージハンドラーエラー: {e}")
        # エラー時の応答
        try:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="申し訳ございません。処理中にエラーが発生しました。")
            )
        except Exception as reply_error:
            logger.error(f"エラー応答送信失敗: {reply_error}")


@app.post("/push")
async def push_message(data: Dict[str, Any]):
    """プッシュメッセージの送信（開発・テスト用）"""
    try:
        user_id = data.get("user_id")
        message = data.get("message")

        if not user_id or not message:
            raise HTTPException(status_code=400, detail="user_id and message are required")

        line_bot_api.push_message(user_id, TextSendMessage(text=message))

        return {"status": "sent", "user_id": user_id, "message": message}

    except Exception as e:
        logger.error(f"プッシュメッセージ送信エラー: {e}")
        raise HTTPException(status_code=500, detail="Failed to send push message")


# LangGraph対応のヘルパー関数
def _extract_confirmation_data_langgraph(response_text: str, langgraph_result: dict) -> dict:
    """
    LangGraphの結果から確認データを抽出
    
    Args:
        response_text: 応答テキスト
        langgraph_result: LangGraphの実行結果
        
    Returns:
        確認データ辞書
    """
    try:
        # LangGraphの結果から確認に必要な情報を抽出
        confirmation_data = {
            "original_message": response_text,
            "agent_steps": langgraph_result.get("intermediate_steps", []),
            "user_id": langgraph_result.get("user_id", ""),
            "pending_confirmation": langgraph_result.get("pending_confirmation", {})
        }
        
        # 既存の確認データ抽出ロジックも併用
        legacy_data = _extract_confirmation_data(response_text, {"output": response_text})
        if legacy_data:
            confirmation_data.update(legacy_data)
            
        return confirmation_data
        
    except Exception as e:
        logger.error(f"LangGraph確認データ抽出エラー: {e}")
        return {}


def _detect_agent_type_langgraph(langgraph_result: dict) -> str:
    """
    LangGraphの実行結果からエージェントタイプを検出
    
    Args:
        langgraph_result: LangGraphの実行結果
        
    Returns:
        エージェントタイプ
    """
    try:
        # 中間ステップからエージェント情報を取得
        intermediate_steps = langgraph_result.get("intermediate_steps", [])
        
        for step in intermediate_steps:
            if "ReadAgent" in step:
                return "read_agent"
            elif "WriteAgent" in step:
                return "write_agent"
        
        # next_agentフィールドからも確認
        next_agent = langgraph_result.get("next_agent", "")
        if next_agent:
            return next_agent
            
        # デフォルト
        return "supervisor_agent"
        
    except Exception as e:
        logger.error(f"LangGraphエージェントタイプ検出エラー: {e}")
        return "unknown_agent"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
