import uuid
import json
import subprocess
import socket
import tempfile
import sys
from . import messages
import tarfile


def working(hive_address: str):
    HOST, p = hive_address.split(":")
    PORT = int(p)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(None)
    try:
        sock.connect((HOST, PORT))
        messages.put_message(sock, messages.REGISTER_WORKER, "")
        while "connected":
            msg = messages.get_message(sock)
            if msg.type == messages.CONNECTION_END:
                print("Close signal from coordinator - closing")
                return
            print(f"Data {msg.data}")
            if msg.type == messages.WORK:
                print("Received work")
                cmd = msg.data
                with tempfile.TemporaryDirectory() as dirpath:
                    # FIXME:Actual command should be created here
                    with subprocess.Popen(
                        cmd.replace("%OUTPUTDIR%", dirpath), shell=True
                    ) as process:
                        process.wait()
                    with tarfile.open("TarName.tar.gz", "w:gz") as tar:
                        tar.add(dirpath, arcname=".")
                    with open("TarName.tar.gz", "rb") as outputs:
                        messages.put_bytes(
                            sock, bytes([messages.WORK_RESULT]) + outputs.read()
                        )
            msg.flush()
    finally:
        sock.close()
        print("Closed worker")


def main():
    working(sys.argv[1])


if __name__ == "__main__":
    working(sys.argv[1])
