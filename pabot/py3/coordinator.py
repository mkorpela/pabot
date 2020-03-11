import asyncio
import websockets
import json
from typing import List, Dict, Set
from websockets.server import WebSocketServerProtocol
from . import messages

workers:Set[WebSocketServerProtocol] = set()
clients:Set[WebSocketServerProtocol] = set()
work_to_client:Dict[WebSocketServerProtocol,WebSocketServerProtocol] = dict()

async def coordinate(websocket: WebSocketServerProtocol, path: str):
    print(f"New connection {websocket} - {path}")
    message: object
    try:
        async for message in websocket:
            msg:Dict[str, object] = json.loads(message)
            if messages.REGISTER in msg:
                if msg[messages.REGISTER] == messages.WORKER:
                    print(f"Received registeration from worker {msg[messages.REGISTER]}")
                    workers.add(websocket)
                if msg[messages.REGISTER] == messages.CLIENT:
                    print(f"Received registeration from client {msg[messages.REGISTER]}")
                    clients.add(websocket)
            if websocket in clients and messages.REQUEST in msg:
                for w in workers:
                    await w.send(json.dumps({
                        messages.INSTRUCTION:messages.WORK,
                        messages.COMMAND:msg[messages.REQUEST]
                        }))
                    work_to_client[w] = websocket
                    continue
            elif messages.WORK_RESULT in msg:
                print(f"Received work results!")
                await work_to_client[websocket].send(json.dumps(msg))
                await websocket.send(json.dumps({messages.INSTRUCTION:messages.CLOSE}))
            elif messages.LOG in msg:
                print(f"Received log '{msg[messages.LOG]}'")
    finally:
        if websocket in workers:
            workers.remove(websocket)
        if websockets in clients:
            clients.remove(websocket)

def main(args=None):
    start_server = websockets.serve(coordinate, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    print(f'Coordinator started at localhost:8765')
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()