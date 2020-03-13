import socket
from typing import Dict
import json
from . import messages


def make_order():
    HOST, PORT = "localhost", 8765
    # Create a socket (SOCK_STREAM means a TCP socket)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Connect to server and send data
        sock.connect((HOST, PORT))
        messages.put(sock, json.dumps({messages.REGISTER:messages.CLIENT}))
        messages.put(sock, json.dumps({
                    messages.REQUEST:'robot --suite Suite2 --variable CALLER_ID:a0373ef82a884605b7b625f4faff1d30 --variable PABOTLIBURI:127.0.0.1:8270 --variable PABOTEXECUTIONPOOLID:1 --variable PABOTISLASTEXECUTIONINPOOL:0 --variable PABOTQUEUEINDEX:1 --variable PABOTLASTLEVEL:Tmp.Suite2 --log NONE --report NONE --xunit NONE --outputdir %OUTPUTDIR% --consolecolors off --consolemarkers off .'}
                    ))

        result = messages.get(sock)
        print(f"Received result {result}")
    finally:
        sock.close()

if __name__ == '__main__':
    make_order()