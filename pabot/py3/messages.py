
import struct
import socket

REGISTER = 'register'
CLIENT = 'client'
WORKER = 'worker'
REQUEST = 'request'
CLOSE = 'close'
WORK = 'work'
INSTRUCTION = 'instruction'
COMMAND = 'cmd'
WORK_RESULT = 'rc'
LOG = 'log'
OUTPUT = 'output'

format = struct.Struct('!I')  # for messages up to 2**32 - 1 in length

def recvall(sock, length:int) -> bytes:
    data = b''
    while len(data) < length:
        more = sock.recv(length - len(data))
        if not more:
            return b''
        data += more
    return data

def get(sock):
    lendata = recvall(sock, format.size)
    if not lendata:
        return ''
    (length,) = format.unpack(lendata)
    return str(recvall(sock, length), 'utf-8')

def put(sock, message):
    sock.send(format.pack(len(message)) + bytes(message, 'utf-8'))