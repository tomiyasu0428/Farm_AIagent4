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

from ..core.config import settings
from ..core.master_agent import master_agent
from ..core.confirmation_middleware import ConfirmationMiddleware
from ..core.session_manager import SessionManager

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
            "agent": "initialized" if master_agent.agent_executor else "not_initialized",
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
        
        # Step 2: 通常のエージェント処理
        if middleware_result.get("requires_agent_processing"):
            # MasterAgentが初期化されているか確認
            if not master_agent.agent_executor:
                logger.info("MasterAgentが初期化されていません。初回リクエストのため初期化します。")
                master_agent.initialize()

            # メモリ付きエージェントを作成
            agent_executor = master_agent.create_agent_with_memory(user_id)
            
            # エージェント実行
            result = agent_executor.invoke({"input": message_text})
            response_text = result.get("output", "申し訳ございませんが、処理できませんでした。")
            
            # 確認フロー対応の結果解析
            if _is_confirmation_response(response_text):
                confirmation_data = _extract_confirmation_data(response_text, result)
                if confirmation_data:
                    # 確認データからエージェントタイプを取得（より正確）
                    agent_type = confirmation_data.get("agent_type") or _detect_agent_type(response_text, result)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
