import struct
from typing import Optional

CONNECTION_END = 0
REGISTER_CLIENT = 1
REQUEST_TO_RUN = 2
REGISTER_WORKER = 3
WORK = 4
WORK_RESULT = 5
LOG = 6

format = struct.Struct("!I")  # for messages up to 2**32 - 1 in length


def recvall(sock, length: int) -> bytes:
    data = b""
    while len(data) < length:
        more = sock.recv(length - len(data))
        if not more:
            return b""
        data += more
    return data


def forward_vall(sock_from, sock_to, length: int):
    while length > 0:
        data = sock_from.recv(length)
        sock_to.send(data)
        length -= len(data)


def get(sock) -> str:
    return str(get_bytes(sock), "utf-8")


class Message:

    _type: Optional[int]
    _length: int
    _data: Optional[str]
    _forwarded: bool

    def __init__(self, sock):
        self._socket = sock
        self._length = 0
        self._data = None
        self._forwarded = False
        self._type = None

    @property
    def type(self):
        if not self._type:
            lendata = recvall(self._socket, format.size)
            if not lendata:
                self._type = CONNECTION_END
                return self._type
            (self._length,) = format.unpack(lendata)
            self._type = int(recvall(self._socket, 1)[0])
        return self._type

    @property
    def data(self):
        if self._data is None:
            self.type  # Ensure type byte has been processed
            self._data = str(recvall(self._socket, self._length - 1), "utf-8")
        return self._data

    def forward_to(self, receiver):
        if self._data is None:
            receiver.send(format.pack(self._length) + bytes([self.type]))
            forward_vall(self._socket, receiver, self._length - 1)
        else:
            put_bytes(receiver, bytes([self.type]) + bytes(self._data, "utf-8"))
        self._forwarded = True

    def flush(self):
        # Ensure that all bytes have been processed
        self.type
        if not self._forwarded:
            self.data


def get_message(sock) -> Message:
    return Message(sock)


def put_message(sock, msg_type: int, message: str):
    put_bytes(sock, bytes([msg_type]) + bytes(message, "utf-8"))


def put(sock, message: str):
    put_bytes(sock, bytes(message, "utf-8"))


def put_bytes(sock, bytes_msg: bytes):
    sock.send(format.pack(len(bytes_msg)) + bytes_msg)


def get_bytes(sock) -> bytes:
    lendata = recvall(sock, format.size)
    if not lendata:
        return b""
    (length,) = format.unpack(lendata)
    return recvall(sock, length)
