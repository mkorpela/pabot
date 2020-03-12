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
        sock.send(bytes(json.dumps({messages.REGISTER:messages.WORKER}) + "\n", "utf-8"))
        while 'connected':
            data = sock.recv(1024)
            if not data:
                return
            print(f"Data {data}")
            message:Dict[str, object] = json.loads(str(data, "utf-8"))
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
                            sock.sendall(bytes(json.dumps({messages.LOG:line}) + "\n", "utf-8"))
                    rc = process.wait()
                    #FIXME:gzip output folder and send all data in binary format to coordinator in batches
                    with tarfile.open("TarName.tar.gz", "w:gz") as tar:
                        tar.add(dirpath, arcname="TarName")
                    with open(os.path.join(dirpath, 'output.xml'), 'r') as outputxml:
                        sock.sendall(bytes(json.dumps({messages.WORK_RESULT:rc,
                        messages.OUTPUT:outputxml.read()}) + "\n", "utf8"))
    finally:
        sock.close()
        print("Closed worker")


def main(args=None):
    working()

if __name__ == '__main__':
    main()