import asyncio
import websockets
import json
from typing import List, Dict, Set
from websockets.server import WebSocketServerProtocol
from . import messages

workers:Set[WebSocketServerProtocol] = set()

async def coordinate(websocket: WebSocketServerProtocol, path: str):
    print(f"New connection {websocket} - {path}")
    message: object
    try:
        async for message in websocket:
            msg:Dict[str, object] = json.loads(message)
            if messages.REGISTER in msg:
                print(f"Received registeration from worker {msg[messages.REGISTER]}")
                workers.add(websocket)
                await websocket.send(json.dumps({
                    messages.INSTRUCTION:messages.WORK,
                    messages.COMMAND:'robot --suite Suite2 --variable CALLER_ID:a0373ef82a884605b7b625f4faff1d30 --variable PABOTLIBURI:127.0.0.1:8270 --variable PABOTEXECUTIONPOOLID:1 --variable PABOTISLASTEXECUTIONINPOOL:0 --variable PABOTQUEUEINDEX:1 --variable PABOTLASTLEVEL:Tmp.Suite2 --log NONE --report NONE --xunit NONE --outputdir ./pabot_results/1 --consolecolors off --consolemarkers off .'}))
            elif messages.WORK_RESULT in msg:
                print(f"Received work results! {msg}")
                await websocket.send(json.dumps({messages.INSTRUCTION:messages.CLOSE}))
            elif messages.LOG in msg:
                print(f"Received log '{msg[messages.LOG]}'")
    finally:
        if websocket in workers:
            workers.remove(websocket)

def main(args=None):
    start_server = websockets.serve(coordinate, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    print(f'Coordinator started at localhost:8765')
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()