import threading
import socketserver
import logging
import bencodepy
import time
import os
import sdp_transform
import apis.status_wrapper as statuses
from utils import *
from sockets import TCPSocket
import time

bc = bencodepy.Bencode(
    encoding='utf-8'
)

rtpe_socket = None
envoy_socket = None

config = {}

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        time_start = time.time()
        global rtpe_socket
        global envoy_socket

        raw_data = str(self.request.recv(4096), 'utf-8')
        data = parse_data(raw_data)
        call_id = ""
        client_ip, client_rtp_port = None, None
        if 'sdp' in data:
            sdp = sdp_transform.parse(data['sdp'])
            client_ip, client_rtp_port = sdp['origin']['address'], sdp['media'][0]['port']
        if "call-id" in data:
            call_id = ''.join(e for e in data['call-id'] if e.isalnum()).lower()
        logging.debug(f'Received message: {raw_data}')

        if config['sidecar_type'] == 'l7mp':
            raw_response = rtpe_socket.send(raw_data)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    address = os.getenv('NODE_IP', None)
                    if not address:
                        logging.exception("Cannot retrieve NODE_IP")
                    response['sdp'] = response['sdp'].replace('127.0.0.1', address)
                if data['command'] == 'delete':
                    delete_kube_resources(call_id)
                if data['command'] == 'offer':
                    sdp = sdp_transform.parse(response['sdp'])
                    rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                    create_offer_resource(
                        config, callid=call_id, from_tag=data['from-tag'], rtpe_rtp_port=rtp_port,
                        rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                        client_rtcp_port=client_rtp_port + 1,
                        without_operator=config.get('without_operator', 'no')
                    )
                if data['command'] == 'answer':
                    sdp = sdp_transform.parse(response['sdp'])
                    rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                    create_answer_resource(
                        config, callid=call_id, to_tag=data['to-tag'], rtpe_rtp_port=rtp_port,
                        rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                        client_rtcp_port=client_rtp_port + 1,
                        without_operator=config.get('without_operator', 'no')
                    )
                    # query = parse_bc(rtpe_socket.send(query_message(data['call-id'])))
                    # create_resource(call_id, data['from-tag'], data['to-tag'], config, query)
                # time.sleep(0.1)
                logging.info(f"{data['command']} setup time: {int((time.time() - time_start) * 1000)}")
                self.request.sendall(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'))
                logging.debug("Response from rtpengine sent back to client")
        if config['sidecar_type'] == 'envoy':
            raw_response = rtpe_socket.send(raw_data)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    address = os.getenv('NODE_IP', None)
                    if not address:
                        logging.exception("Cannot retrieve NODE_IP")
                    response['sdp'] = response['sdp'].replace('127.0.0.1', address)
                if data['command'] == 'answer' and config['envoy_operator'] == 'no':
                    raw_query = rtpe_socket.send(query_message(data['call-id']))
                    logging.debug(f"Query for {call_id} sent out")
                    if not raw_query:
                        logging.exception('Cannot make a query to rtpengine.')
                    else:
                        query = parse_bc(raw_query)
                        logging.debug(f"Received query: {str(query)}")
                        json_data = create_json(
                            query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port'],
                            query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port'],
                            call_id, config['rtpe_address']
                        )
                        logging.debug(f"Data to envoy: {json_data}")
                        envoy_socket.send(json_data, no_wait_response=True)
                        logging.debug("After envoy send")
                # elif data['command'] == 'offer':
                #     sdp = sdp_transform.parse(response['sdp'])
                #     rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                #     create_offer_resource(
                #         config, callid=call_id, from_tag=data['from-tag'], rtpe_rtp_port=rtp_port,
                #         rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                #         client_rtcp_port=client_rtp_port + 1
                #     )
                elif data['command'] == 'answer':
                    raw_query = rtpe_socket.send(query_message[data['call-id']])
                    logging.debug(f"Query for {call_id} sent out")
                    if not raw_query:
                        logging.exception('Cannot make a query to rtpengine.')
                    else:
                        query = parse_bc(raw_query)
                        create_resource(call_id, data['from-tag'], data['to-tag'], config, query)


                    # sdp = sdp_transform.parse(response['sdp'])
                    # rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                    # create_answer_resource(
                    #     config, callid=call_id, to_tag=data['to-tag'], rtpe_rtp_port=rtp_port,
                    #     rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                    #     client_rtcp_port=client_rtp_port + 1
                    # )
                elif data['command'] == 'delete' and config['envoy_operator'] == 'yes':
                    delete_kube_resources(call_id)
                
                # For non-blocking wait
                event = threading.Event()
                event.wait(0.1)
                logging.info(f"{data['command']} setup time: {int((time.time() - time_start) * 1000)}")
                self.request.sendall(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'))
                logging.debug("Response from rtpengine sent back to client")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

def serve(conf):
    global config
    global rtpe_socket
    global envoy_socket
    config = conf

    if config.get('without_operator', 'no') == 'yes':
        time.sleep(20)
        for filename in os.listdir('proxy_configs'):
            with open(f'proxy_configs/{filename}', 'r') as f:
                logging.info(f'proxy_configs/{filename}')
                statuses.statuses.post(f)


    rtpe_socket = TCPSocket(config['rtpe_address'], config['rtpe_port'], delay=45)
    if config['envoy_operator'] == 'no' and config['sidecar_type'] == 'envoy':
        envoy_socket = TCPSocket(config['envoy_address'], config['envoy_port'])

    HOST, PORT = config['local_address'], int(config['local_port'])
    # with socketserver.TCPServer((HOST, PORT), TCPRequestHandler) as server:
    #     server.serve_forever()

    if config.get('without_operator', 'no') == 'yes':
        threading.Thread(target=statuses.statuses.update, daemon=True).start()
    
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        server_thread = threading.Thread(target=server.serve_forever)
        try:
            # server_thread.daemon = True
            server_thread.start()
            logging.info(f"Server loop running in thread: {server_thread.name}")
            server_thread.run()
        except KeyboardInterrupt:
            server.shutdown()