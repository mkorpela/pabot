import asyncio
import websockets
import json
from typing import List, Dict, Set
from websockets.server import WebSocketServerProtocol

workers:Set[WebSocketServerProtocol] = set()

async def echo(websocket: WebSocketServerProtocol, path: str):
    print(f"New connection {websocket} - {path}")
    message: object
    try:
        async for message in websocket:
            msg:Dict[str, object] = json.loads(message)
            if 'worker' in msg:
                print(f"Received registeration from worker {msg['worker']}")
                workers.add(websocket)
                await websocket.send(json.dumps({
                    'status':'work',
                    'workid':'id-3',
                    'cmd':'robot .'}))
            elif 'work' in msg and 'rc' in msg:
                print(f"Received work results! {msg}")
                await websocket.send(json.dumps({'status':'close'}))
            elif 'work' in msg and 'log' in msg:
                print(f"Received log '{msg['log']}'")
    finally:
        if websocket in workers:
            workers.remove(websocket)

def main(args=None):
    start_server = websockets.serve(echo, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    print(f'Coordinator started at localhost:8765')
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()