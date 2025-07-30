import os
import logging
from typing import List
from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    ActivityHandler,
    MessageFactory,
    TurnContext,
    MemoryStorage,
    UserState,
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
    BotFrameworkAdapter
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ChannelAccount
from dotenv import load_dotenv
import asyncio

# 載入環境變數
load_dotenv()

# 從環境變數取資料
MICROSOFT_APP_ID = os.environ.get("MicrosoftAppId", "")
MICROSOFT_APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
MICROSOFT_TENANT_ID = os.environ.get("MicrosoftTenantId", "")
PORT = int(os.environ.get("PORT", 3978))

# 設定日誌
logging.basicConfig(level=logging.INFO)

# 建立 CloudAdapter
bot_framework_authentication = ConfigurationBotFrameworkAuthentication(
    app_id=MICROSOFT_APP_ID,
    app_password=MICROSOFT_APP_PASSWORD,
    app_tenant_id=MICROSOFT_TENANT_ID,
    app_type="SingleTenant"  # 依照多租或單租選填
)

adapter = CloudAdapter(bot_framework_authentication)

# 全局錯誤處理
async def on_error(context: TurnContext, error: Exception):
    print(f"\n [on_error] 未處理的錯誤: {error}")
    print(f"錯誤堆疊: {error.__traceback__}")
    
    try:
        await context.send_activity(f"發生錯誤: {str(error)}")
    except Exception as err:
        print(f"回應錯誤時發生問題: {err}")

adapter.on_turn_error = on_error

# 自定義 Teams Bot
class TeamsBot(ActivityHandler):
    def __init__(self):
        super().__init__()

    async def on_message_activity(self, turn_context: TurnContext):
        """處理訊息事件"""
        user_message = turn_context.activity.text
        response_text = f'您剛才說的是: "{user_message}"'
        await turn_context.send_activity(MessageFactory.text(response_text))

    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        """處理成員加入事件"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome_text = "歡迎加入 Teams Bot！"
                await turn_context.send_activity(MessageFactory.text(welcome_text))
                break

# 建立機器人實例
bot = TeamsBot()

# 配置伺服器的訊息端點 for Teams bot 串接
async def messages(req: Request) -> Response:
    try:
        # 解析請求
        if "application/json" in req.headers.get("Content-Type", ""):
            body = await req.json()
        else:
            return Response(status=415)

        activity = Activity().deserialize(body)
        auth_header = req.headers.get("Authorization", "")

        # 處理活動
        response = await adapter.process_activity(activity, auth_header, bot.on_turn)
        
        if response:
            return json_response(data=response.body, status=response.status)
        return Response(status=200)
        
    except Exception as e:
        print(f"處理訊息時發生錯誤: {e}")
        return Response(status=500)

# 建立並配置伺服器
def create_app() -> web.Application:
    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    return app

async def init_app():
    """初始化應用程式"""
    app = create_app()
    return app

if __name__ == "__main__":
    try:
        # 建立應用程式
        app = create_app()
        
        # 啟動伺服器
        web_app_host_name = os.environ.get("WebAppHostName")
        if web_app_host_name:
            base_url = f"https://{web_app_host_name}"
        else:
            base_url = f"http://localhost:{PORT}"
            
        print(f"伺服器啟動中，網址為 {base_url}")
        
        # 啟動 web 伺服器
        web.run_app(app, host="0.0.0.0", port=PORT)
        
    except Exception as e:
        print(f"啟動伺服器時發生錯誤: {e}")
        raise e