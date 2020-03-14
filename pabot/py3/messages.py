
import struct
import socket
from typing import Tuple

CONNECTION_END = 0
REGISTER_CLIENT = 1
REQUEST_TO_RUN = 2
REGISTER_WORKER = 3
WORK = 4
WORK_RESULT = 5
LOG = 6

format = struct.Struct('!I')  # for messages up to 2**32 - 1 in length

def recvall(sock, length:int) -> bytes:
    data = b''
    while len(data) < length:
        more = sock.recv(length - len(data))
        if not more:
            return b''
        data += more
    return data

def get(sock) -> str:
    return str(get_bytes(sock), 'utf-8')

def get_message(sock) -> Tuple[int, str]:
    bs = get_bytes(sock)
    if not bs:
        return CONNECTION_END, ''
    return int(bs[0]), str(bs[1:], 'utf-8')

def put_message(sock, msg_type:int, message:str):
    put_bytes(sock, bytes([msg_type]) + bytes(message, 'utf-8'))

def put(sock, message:str):
    put_bytes(sock, bytes(message, 'utf-8'))

def put_bytes(sock, bytes_msg:bytes):
    sock.send(format.pack(len(bytes_msg)) + bytes_msg)

def get_bytes(sock) -> bytes:
    lendata = recvall(sock, format.size)
    if not lendata:
        return b''
    (length,) = format.unpack(lendata)
    return recvall(sock, length)