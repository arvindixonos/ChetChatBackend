from aiohttp import web
import socketio
from chetchatgame.chetchatgameserver import ChetChatGameServer


app = web.Application()
sio = socketio.AsyncServer(async_mode='aiohttp', logger=False)

ChetChatGameServer.configure(sio)

sio.attach(app)

sio.register_namespace(ChetChatGameServer('/'))

web.run_app(app, port=2021)