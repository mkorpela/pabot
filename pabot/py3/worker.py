import asyncio
import uuid
import json
import subprocess
from typing import Dict
import websockets
from . import messages

MY_IDENTIFIER = str(uuid.uuid4())

async def working():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # register worker
        await websocket.send(json.dumps({messages.REGISTER:MY_IDENTIFIER}))
        while True:
            # wait for an instruction
            message:Dict[str, object] = json.loads(await websocket.recv())
            instruction = message[messages.INSTRUCTION]
            if instruction == messages.CLOSE:
                print(f"Worker {MY_IDENTIFIER}: close signal from coordinator - closing")
                return
            if instruction == messages.WORK:
                print(f"Worker {MY_IDENTIFIER}: received work")
                cmd = message[messages.COMMAND]
                #FIXME:Actual command should be created here
                #FIXME:output folder should be tmpdir created by this process
                with subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          bufsize=1,
                          universal_newlines=True,
                          shell=True) as process:
                    for line in process.stdout:
                        line = line.rstrip()
                        await websocket.send(json.dumps({messages.LOG:line}))
                rc = process.wait()
                #FIXME:gzip output folder and send all data in binary format to coordinator in batches
                with open('pabot_results/1/output.xml', 'r') as outputxml:
                    await websocket.send(json.dumps({messages.WORK_RESULT:rc,
                    messages.OUTPUT:outputxml.read()}))


def main(args=None):
    asyncio.get_event_loop().run_until_complete(working())

if __name__ == '__main__':
    main()