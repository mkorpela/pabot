import asyncio
import uuid
import json
import subprocess
from typing import Dict
import websockets
import tempfile
import shutil
import os
from . import messages
import tarfile

async def working():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # register worker
        await websocket.send(json.dumps({messages.REGISTER:messages.WORKER}))
        while True:
            # wait for an instruction
            message:Dict[str, object] = json.loads(await websocket.recv())
            instruction = message[messages.INSTRUCTION]
            if instruction == messages.CLOSE:
                print(f"Close signal from coordinator - closing")
                return
            if instruction == messages.WORK:
                print(f"Received work")
                cmd = message[messages.COMMAND]
                with tempfile.TemporaryDirectory() as dirpath:
                    #FIXME:Actual command should be created here
                    with subprocess.Popen(cmd.replace("%OUTPUTDIR%", dirpath),
                            stdout=subprocess.PIPE,
                            bufsize=1,
                            universal_newlines=True,
                            shell=True) as process:
                        for line in process.stdout:
                            line = line.rstrip()
                            await websocket.send(json.dumps({messages.LOG:line}))
                    rc = process.wait()
                    #FIXME:gzip output folder and send all data in binary format to coordinator in batches
                    with tarfile.open("TarName.tar.gz", "w:gz") as tar:
                        tar.add(dirpath, arcname="TarName")
                    with open(os.path.join(dirpath, 'output.xml'), 'r') as outputxml:
                        await websocket.send(json.dumps({messages.WORK_RESULT:rc,
                        messages.OUTPUT:outputxml.read()}))


def main(args=None):
    asyncio.get_event_loop().run_until_complete(working())

if __name__ == '__main__':
    main()