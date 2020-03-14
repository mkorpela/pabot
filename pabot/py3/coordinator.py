import socketserver
import json
from typing import List, Dict, Set
from . import messages

workers:Set['CoordinatorHandler'] = set()
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
                    workers.add(self)
                if messages.REGISTER_CLIENT == msg_type:
                    print(f"Received registeration from client")
                    clients.add(self)
                if self in clients and messages.REQUEST_TO_RUN == msg_type:
                    print("Request from client")
                    for w in workers:
                        print("Sending to worker")
                        messages.put_message(w.request, messages.WORK, str(raw_data[1:], 'utf-8'))
                        work_to_client[w] = self
                        continue
                elif messages.WORK_RESULT == msg_type:
                    print(f"Received work results!")
                    messages.put_bytes(work_to_client[self].request, raw_data)
                    print("Closing connection")
                    messages.put_message(self.request, messages.CONNECTION_END, '')
                    return
                elif messages.LOG == msg_type:
                    print(f"Received log '{str(raw_data[1:], 'utf-8')}'")
        finally:
            if self in workers:
                workers.remove(self)
            if self in clients:
                clients.remove(self)
            print("Closed connection")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

def main(args=None):
    HOST, PORT = "localhost", 8765
    server = ThreadedTCPServer((HOST, PORT), CoordinatorHandler)
    print(f"Starting Coordinator server at {HOST}:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    main()