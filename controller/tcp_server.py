import socket
import threading
import socketserver
import logging

config = {}

def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
        response = str(sock.recv(1024), 'ascii')
        return response

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        data = str(self.request.recv(1024), 'ascii')
        print(f'Received data from client: {data}')
        cur_thread = threading.current_thread()
        response = client('127.0.0.1', 10001, "{}: {}".format(cur_thread.name, data))
        self.request.sendall(bytes(response, 'ascii'))

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

def serve(conf):
    global config
    config = conf

    HOST, PORT = config['local_address'], int(config['local_port'])
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        server_thread = threading.Thread(target=server.serve_forever)
        try:
            server_thread.daemon = True
            server_thread.start()
            print("Server loop running in thread:", server_thread.name)
            server_thread.run()
        except KeyboardInterrupt:
            server.shutdown()