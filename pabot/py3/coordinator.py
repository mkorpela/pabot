import asyncio
import websockets

async def echo(websocket, path):
    async for message in websocket:
        print(f'echoing message {message}')
        await websocket.send(message)

def main(args=None):
    start_server = websockets.serve(echo, "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()