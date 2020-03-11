import asyncio
from typing import Dict
import websockets
import json
from . import messages


async def make_order():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({messages.REGISTER:messages.CLIENT}))
        await websocket.send(json.dumps({
                    messages.REQUEST:'robot --suite Suite2 --variable CALLER_ID:a0373ef82a884605b7b625f4faff1d30 --variable PABOTLIBURI:127.0.0.1:8270 --variable PABOTEXECUTIONPOOLID:1 --variable PABOTISLASTEXECUTIONINPOOL:0 --variable PABOTQUEUEINDEX:1 --variable PABOTLASTLEVEL:Tmp.Suite2 --log NONE --report NONE --xunit NONE --outputdir %OUTPUTDIR% --consolecolors off --consolemarkers off .'}))
        result = await websocket.recv()
        print(f"Received result {result}")

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(make_order())