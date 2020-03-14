import socketserver
import json
from typing import List, Dict, Set
from . import messages
from queue import Queue

workers:Queue = Queue()
clients:Set['CoordinatorHandler'] = set()
work_to_client:Dict['CoordinatorHandler','CoordinatorHandler'] = dict()

class CoordinatorHandler(socketserver.BaseRequestHandler):

    def handle(self):
        try:
            while 'connected':
                raw_data = messages.get_bytes(self.request)
                if not raw_data:
                    return
                msg_type = int(raw_data[0])
                if msg_type == messages.CONNECTION_END:
                    return
                if messages.REGISTER_WORKER == msg_type:
                    print(f"Received registeration from worker")
                    workers.put(self)
                if messages.REGISTER_CLIENT == msg_type:
                    print(f"Received registeration from client")
                    clients.add(self)
                if self in clients and messages.REQUEST_TO_RUN == msg_type:
                    print("Request from client")
                    w = workers.get()
                    print("Sending to worker")
                    messages.put_message(w.request, messages.WORK, str(raw_data[1:], 'utf-8'))
                    work_to_client[w] = self
                    continue
                elif messages.WORK_RESULT == msg_type:
                    print(f"Received work results!")
                    #FIXME: Forward this direclty instead of unwrapping and wrapping
                    messages.put_bytes(work_to_client[self].request, raw_data)
                    del work_to_client[self]
                    workers.put(self)
                    #print("Closing connection")
                    #messages.put_message(self.request, messages.CONNECTION_END, '')
                    #return
                elif messages.LOG == msg_type:
                    print(f"Received log '{str(raw_data[1:], 'utf-8')}'")
        finally:
            if self in clients:
                clients.remove(self)
            print("Closed connection")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

def main(args=None):
    HOST, PORT = "localhost", 8765
    server = ThreadedTCPServer((HOST, PORT), CoordinatorHandler)
    server.timeout = None
    print(f"Starting Coordinator server at {HOST}:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    main()