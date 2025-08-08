"""
Copyright (c) Microsoft Corporation. All rights reserved.
Licensed under the MIT License.
"""

import asyncio
import json
from http import HTTPStatus
from aiohttp import web
from aiohttp.web import FileResponse
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.core import TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount
import os

from bot import bot_app, planner, model
from config import Config
from teams.state import TurnState

routes = web.RouteTableDef()

@routes.post("/api/messages")
async def on_messages(req: web.Request) -> web.Response:
    res = await bot_app.process(req)
    if res is not None:
        return res
    return web.Response(status=HTTPStatus.OK)

@routes.get("/")
async def index(request):
    html_path = f"{os.getcwd()}/src/test_interface.html"
    try:
        return FileResponse(html_path)
    except Exception as e:
        print(f"Error reading HTML file: {e}")
        return web.Response(text="Error loading page", status=500)

@routes.get("/test")
async def test_page(request):
    return await index(request)

@routes.options("/api/chat")
async def chat_options(request):
    return web.Response(
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    )

@routes.post("/api/chat")
async def chat_api(req: web.Request) -> web.Response:
    try:
        data = await req.json()
        user_message = data.get('message', '')
        
        if not user_message:
            response = web.json_response({'error': 'Message is required'}, status=400)
        else:
            try:
                print(f"Processing message: {user_message}")
                
                # 建立更完整的 state，模擬 TurnState 結構
                state = TurnState()
                state.conversation = {}
                state.user = {}
                state.temp = {'input': user_message}
                
                # 建立更完整的模擬 context
                class MockTurnContext:
                    def __init__(self, message):
                        # 建立完整的 Activity 物件
                        self.activity = Activity(
                            type=ActivityTypes.message,
                            text=message,
                            from_property=ChannelAccount(id='web_user', name='Web User'),
                            recipient=ChannelAccount(id='bot', name='DataBot'),
                            conversation={'id': 'web_conversation'},
                            channel_id='webchat',
                            service_url='http://localhost'
                        )
                        self.sent_activities = []
                        self._responded = False
                        
                    async def send_activity(self, activity_or_text):
                        if isinstance(activity_or_text, str):
                            self.sent_activities.append(activity_or_text)
                        elif hasattr(activity_or_text, 'text'):
                            self.sent_activities.append(activity_or_text.text)
                        else:
                            self.sent_activities.append(str(activity_or_text))
                        self._responded = True
                        print(f"Bot response captured: {self.sent_activities[-1]}")
                
                context = MockTurnContext(user_message)
                
                # 使用您的 planner
                print("Calling planner.begin_task...")
                plan = await planner.begin_task(context, state)
                print(f"Plan generated: {plan}")
                
                if plan and hasattr(plan, 'commands') and plan.commands:
                    print(f"Executing {len(plan.commands)} commands")
                    for i, command in enumerate(plan.commands):
                        print(f"Command {i}: type={getattr(command, 'type', 'unknown')}")
                        
                        # 檢查是否為 SAY 命令
                        if hasattr(command, 'type') and command.type == 'SAY':
                            print("Executing SAY command...")
                            try:
                                # 導入並執行 say_command
                                from custom_say_command import say_command
                                # 建立適當的 data 結構
                                command_data = {
                                    'response': command
                                }
                                await say_command(context, state, command_data, feedback_loop_enabled=False)
                            except Exception as say_error:
                                print(f"Error in say_command: {say_error}")
                                # 如果 say_command 失敗，嘗試直接取得回應內容
                                if hasattr(command, 'response') and hasattr(command.response, 'content'):
                                    await context.send_activity(command.response.content)
                                elif hasattr(command, 'content'):
                                    await context.send_activity(command.content)
                else:
                    print("No commands in plan or plan is None")
                
                # 取得 bot 的回應
                if context.sent_activities:
                    bot_response = context.sent_activities[-1]
                    print(f"Final response: {bot_response}")
                else:
                    bot_response = "抱歉，我無法處理您的問題。"
                    print("No response captured, using default message")
                
            except Exception as e:
                print(f"Error processing with AI: {e}")
                import traceback
                traceback.print_exc()
                bot_response = f"處理過程中發生錯誤：{str(e)}"

            response = web.json_response({'response': bot_response})
        
        # 添加 CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response
        
    except Exception as e:
        print(f"API Error: {e}")
        import traceback
        traceback.print_exc()
        response = web.json_response({'error': '處理請求時發生錯誤'}, status=500)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

app = web.Application(middlewares=[aiohttp_error_middleware])
app.add_routes(routes)

if __name__ == "__main__":
    web.run_app(app, host="localhost", port=Config.PORT)