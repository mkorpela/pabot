import asyncio
import websockets
from typing import List
from websockets.server import WebSocketServerProtocol

workers:List[WebSocketServerProtocol] = []

async def echo(websocket: WebSocketServerProtocol, path: str):
    print(f"New connection {websocket} - {path}")
    message: object
    async for message in websocket:
        if message == 'Worker ready for work':
            workers.append(websocket)
        await websocket.send('close')

def main(args=None):
    start_server = websockets.serve(echo, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    print(f'Coordinator started at localhost:8765')
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()