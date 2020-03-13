import uuid
import json
import subprocess
from typing import Dict
import socket
import tempfile
import shutil
import os
from . import messages
import tarfile

def working():
    HOST, PORT = "localhost", 8765
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
        messages.put(sock, json.dumps({messages.REGISTER:messages.WORKER}))
        while 'connected':
            data = messages.get(sock)
            if not data:
                return
            print(f"Data {data}")
            message:Dict[str, object] = json.loads(data)
            instruction = message[messages.INSTRUCTION]
            if instruction == messages.CLOSE:
                print("Close signal from coordinator - closing")
                return
            if instruction == messages.WORK:
                print("Received work")
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
                            messages.put(sock, json.dumps({messages.LOG:line}))
                    rc = process.wait()
                    #FIXME:gzip output folder and send all data in binary format to coordinator in batches
                    with tarfile.open("TarName.tar.gz", "w:gz") as tar:
                        tar.add(dirpath, arcname="TarName")
                    with open(os.path.join(dirpath, 'output.xml'), 'r') as outputxml:
                        messages.put(sock, json.dumps({messages.WORK_RESULT:rc,
                        messages.OUTPUT:outputxml.read()}))
    finally:
        sock.close()
        print("Closed worker")


def main(args=None):
    working()

if __name__ == '__main__':
    main()