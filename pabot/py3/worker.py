import asyncio
import websockets

async def working():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        while True:
            await websocket.send("Worker ready for work")
            message:object = await websocket.recv()
            if message == 'close':
                return
            print(f"new message {message}")


def main(args=None):
    asyncio.get_event_loop().run_until_complete(working())

if __name__ == '__main__':
    main()