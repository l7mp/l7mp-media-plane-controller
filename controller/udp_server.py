import threading
import socketserver
import logging
import bencodepy
import time
import random
import string
from utils import *
from sockets import UDPSocket

bc = bencodepy.Bencode(
    encoding='utf-8'
)

rtpe_socket = None
envoy_socket = None

config = {}

class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        global rtpe_socket
        global envoy_socket

        rtpe_address = (config['rtpe_address'], int(config["rtpe_port"]))
        envoy_address = (config['envoy_address'], int(config['envoy_port']))

        raw_data = self.request[0].strip()
        socket = self.request[1]
        data = parse_data(raw_data)
        logging.info(f'Received {data["command"]}')
        logging.debug(f'Received message: {raw_data}')

        if config['sidecar_type'] == 'l7mp':
            raw_response = rtpe_socket.send(raw_data, rtpe_address)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    response['sdp'] = response['sdp'].replace('127.0.0.1', config['ingress_address'])
                socket.sendto(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'), self.client_address)
                logging.debug("Response from rtpengine sent back to client")
                if data['command'] == 'delete':
                    delete_kube_resources(data['call-id'])
                if data['command'] == 'answer':
                    query = parse_bc(rtpe_socket.send(query_message(data['call-id']), rtpe_address))
                    create_resource(data['call-id'], data['from-tag'], data['to-tag'], config, query)
        if config['sidecar_type'] == 'envoy':
            raw_response = rtpe_socket.send(raw_data, rtpe_address)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    response['sdp'] = response['sdp'].replace('127.0.0.1', config['ingress_address'])
                socket.sendto(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'), self.client_address)
                logging.debug("Response from rtpengine sent back to client")
                if data['command'] == 'answer':
                    raw_query = rtpe_socket.send(query_message(data['call-id']))
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
                        envoy_socket.send(json_data, envoy_address)

class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass

def serve(conf):
    global config
    global rtpe_socket
    global envoy_socket
    config = conf

    rtpe_socket = UDPSocket(delay=10)
    envoy_socket = UDPSocket()

    HOST, PORT = config['local_address'], int(config['local_port'])
    server = ThreadedUDPServer((HOST, PORT), ThreadedUDPRequestHandler)
    with server:
        server_thread = threading.Thread(target=server.serve_forever)
        try:
            server_thread.daemon = True
            server_thread.start()
            logging.info(f"Server loop running in thread: {server_thread.name}")
            server_thread.run()
        except KeyboardInterrupt:
            server.shutdown()