import socket
import os
from . import messages
import tarfile


def make_order(hive: str, order: str, outputdir: str):
    HOST, p = hive.split(":")
    PORT = int(p)
    # Create a socket (SOCK_STREAM means a TCP socket)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(None)
    try:
        # Connect to server and send data
        sock.connect((HOST, PORT))
        messages.put_message(sock, messages.REGISTER_CLIENT, "")
        print(repr(order))
        messages.put_message(sock, messages.REQUEST_TO_RUN, order)
        data = messages.get_bytes(sock)
        curdir = os.getcwd()
        os.chdir(outputdir)
        with open("Tardistan.tar.gz", "wb") as outputs:
            outputs.write(data[1:])
        tar = tarfile.open("Tardistan.tar.gz")
        tar.extractall()
        tar.close()
        os.remove("Tardistan.tar.gz")
        print(f"Received result")
        os.chdir(curdir)
    finally:
        sock.close()


if __name__ == "__main__":
    make_order(
        "localhost:8765",
        "robot --suite Suite2 --variable CALLER_ID:a0373ef82a884605b7b625f4faff1d30 --variable PABOTLIBURI:127.0.0.1:8270 --variable PABOTEXECUTIONPOOLID:1 --variable PABOTISLASTEXECUTIONINPOOL:0 --variable PABOTQUEUEINDEX:1 --variable PABOTLASTLEVEL:Tmp.Suite2 --log NONE --report NONE --xunit NONE --outputdir %OUTPUTDIR% --consolecolors off --consolemarkers off .",
        "foobarzoo",
    )
