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
            old_data = ''
            while 'connected':
                if '\n' not in old_data:
                    print("Waiting for data")
                    data = self.request.recv(4048)
                    if not data:
                        return
                    print(f"Data {data}")
                    d, n = str(data, "utf-8").split('\n', 1)
                else:
                    print("Handling old data")
                    d, n = old_data.split('\n', 1)
                    old_data = ''
                msg:Dict[str, object] = json.loads(old_data+d)
                old_data = n
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
                        w.send(json.dumps({
                            messages.INSTRUCTION:messages.WORK,
                            messages.COMMAND:msg[messages.REQUEST]
                            }))
                        work_to_client[w] = self
                        continue
                elif messages.WORK_RESULT in msg:
                    print(f"Received work results!")
                    work_to_client[self].send(json.dumps(msg))
                    print("Closing connection")
                    self.send(json.dumps({messages.INSTRUCTION:messages.CLOSE}))
                    return
                elif messages.LOG in msg:
                    print(f"Received log '{msg[messages.LOG]}'")
        finally:
            if self in workers:
                workers.remove(self)
            if self in clients:
                clients.remove(self)
            print("Closed connection")

    def send(self, data:str):
        self.request.sendall(bytes(data + "\n", "utf-8"))


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

def main(args=None):
    HOST, PORT = "localhost", 8765
    server = ThreadedTCPServer((HOST, PORT), CoordinatorHandler)
    print(f"Starting Coordinator server at {HOST}:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    main()