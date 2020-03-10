import asyncio
import uuid
import json
import subprocess
from typing import Dict
import websockets

MY_IDENTIFIER = str(uuid.uuid4())

async def working():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # register worker
        await websocket.send(json.dumps({'worker':MY_IDENTIFIER}))
        while True:
            # wait for an order
            message:Dict[str, str] = json.loads(await websocket.recv())
            status = message['status']
            if status == 'close':
                print(f"Worker {MY_IDENTIFIER}: close signal from coordinator - closing")
                return
            if status == 'work':
                print(f"Worker {MY_IDENTIFIER}: received work")
                cmd = message['cmd']
                with subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          bufsize=1,
                          universal_newlines=True,
                          shell=True) as process:
                    for line in process.stdout:
                        line = line.rstrip()
                        await websocket.send(json.dumps({'work':message['workid'], 'log':line}))
                rc = process.wait()
                await websocket.send(json.dumps({'work':message['workid'], 'rc':rc}))


def main(args=None):
    asyncio.get_event_loop().run_until_complete(working())

if __name__ == '__main__':
    main()