import asyncio
import websockets
from websockets.server import WebSocketServerProtocol

async def echo(websocket: WebSocketServerProtocol, path: str):
    message: object
    async for message in websocket:
        print(f'echoing message {message}')
        await websocket.send(message)

def main(args=None):
    start_server = websockets.serve(echo, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    print(f'Coordinator started at localhost:8765')
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()