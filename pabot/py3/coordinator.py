import socketserver
from typing import Dict, Set
from . import messages
from queue import Queue

workers: Queue = Queue()
clients: Set["CoordinatorHandler"] = set()
work_to_client: Dict["CoordinatorHandler", "CoordinatorHandler"] = dict()


class CoordinatorHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            while "connected":
                msg = messages.get_message(self.request)
                if msg.type == messages.CONNECTION_END:
                    return
                if messages.REGISTER_WORKER == msg.type:
                    print(f"Received registeration from worker")
                    workers.put(self)
                if messages.REGISTER_CLIENT == msg.type:
                    print(f"Received registeration from client")
                    clients.add(self)
                if self in clients and messages.REQUEST_TO_RUN == msg.type:
                    print("Request from client")
                    w = workers.get()
                    print("Sending to worker")
                    messages.put_message(w.request, messages.WORK, msg.data)
                    work_to_client[w] = self
                    continue
                elif messages.WORK_RESULT == msg.type:
                    print(f"Received work results!")
                    # FIXME: Forward this direclty instead of unwrapping and wrapping
                    msg.forward_to(work_to_client[self].request)
                    del work_to_client[self]
                    workers.put(self)
                    # print("Closing connection")
                    # messages.put_message(self.request, messages.CONNECTION_END, '')
                    # return
                elif messages.LOG == msg.type:
                    print(f"Received log '{msg.data}'")
                msg.flush()
        finally:
            if self in clients:
                clients.remove(self)
            print("Closed connection")


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


def main(args=None):
    HOST, PORT = "0.0.0.0", 8765
    server = ThreadedTCPServer((HOST, PORT), CoordinatorHandler)
    server.timeout = None
    print(f"Starting Coordinator server at {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
