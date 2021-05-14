import socket
import threading
import socketserver
import logging
import bencodepy
import time
import random
import string
from utils import *

bc = bencodepy.Bencode(
    encoding='utf-8'
)

config = {}

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        raw_data = str(self.request.recv(4096), 'utf-8')
        data = parse_data(raw_data)
        logging.info(f'Received {data["command"]}')
        logging.debug(f'Received message: {raw_data}')

        if config['sidecar_type'] == 'l7mp':
            raw_response = client(config['rtpe_addresss'], int(config['rtpe_address']), raw_data)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    response['sdp'] = response['sdp'].replace('127.0.0.1', config['ingress_address'])
                self.request.sendall(bytes(response, 'utf-8'))
                logging.debug("Response from rtpengine sent back to client")
                if data['command'] == 'delete':
                    delete_kube_resources(data['call-id'])
                if data['command'] == 'answer':
                    create_resource(data['call-id'], data['from-tag'], data['to-tag'], config)
        if config['sidecar_type'] == 'envoy':
            raw_response = client(config['rtpe_address'], int(config['rtpe_port']), raw_data)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    response['sdp'] = response['sdp'].replace('127.0.0.1', config['ingress_address'])
                self.request.sendall(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'))
                logging.debug("Response from rtpengine sent back to client")
                if data['command'] == 'answer':
                    cookie = ''.join(random.choice(string.ascii_lowercase) for i in range(5))
                    q_message = cookie + " " + bc.encode(commands.query(data['call-id'])).decode()
                    raw_query = client(config['rtpe_address'], int(config['rtpe_port']), q_message)
                    logging.debug(f"Query for {data['call-id']} sent out")
                    if not raw_query:
                        logging.exception('Cannot make a query to rtpengine.')
                    else:
                        query = parse_bc(raw_query)
                        logging.debug(f"Received query: {str(query)}")
                        json_data = create_json(
                            query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port'],
                            query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port'],
                            data['call-id']
                        )
                        logging.debug(f"Data to envoy: {json_data}")
                        client(config['envoy_address'], int(config['envoy_port']), json_data)

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
            logging.info(f"Server loop running in thread: {server_thread.name}")
            server_thread.run()
        except KeyboardInterrupt:
            server.shutdown()