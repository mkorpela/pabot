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
                print("Waiting for data")
                data = messages.get(self.request)
                if not data:
                    return
                msg:Dict[str, object] = json.loads(data)
                print(f"Message {msg}")
                if messages.REGISTER in msg:
                    if msg[messages.REGISTER] == messages.WORKER:
                        print(f"Received registeration from worker {msg[messages.REGISTER]}")
                        workers.add(self)
                    if msg[messages.REGISTER] == messages.CLIENT:
                        print(f"Received registeration from client {msg[messages.REGISTER]}")
                        clients.add(self)
                if self in clients and messages.REQUEST in msg:
                    print("Request from client")
                    for w in workers:
                        print("Sending to worker")
                        messages.put(w.request, json.dumps({
                            messages.INSTRUCTION:messages.WORK,
                            messages.COMMAND:msg[messages.REQUEST]
                            }))
                        work_to_client[w] = self
                        continue
                elif messages.WORK_RESULT in msg:
                    print(f"Received work results!")
                    messages.put(work_to_client[self].request, json.dumps(msg))
                    print("Closing connection")
                    messages.put(self.request, json.dumps({messages.INSTRUCTION:messages.CLOSE}))
                    return
                elif messages.LOG in msg:
                    print(f"Received log '{msg[messages.LOG]}'")
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