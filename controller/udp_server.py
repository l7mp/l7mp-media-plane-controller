import threading
import socketserver
import logging
import bencodepy
import time
import sdp_transform
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
        time_start = time.time()
        global rtpe_socket
        global envoy_socket

        rtpe_address = (config['rtpe_address'], int(config["rtpe_port"]))
        envoy_address = (config['envoy_address'], int(config['envoy_port']))

        raw_data = self.request[0].decode().strip()
        socket = self.request[1]
        
        data = parse_data(raw_data)
        call_id = " "
        client_ip, client_rtp_port = None, None
        if 'sdp' in data:
            sdp = sdp_transform.parse(data['sdp'])
            client_ip, client_rtp_port = sdp['origin']['address'], sdp['media'][0]['port']
        if "call-id" in data:
            call_id = ''.join(e for e in data['call-id'] if e.isalnum()).lower()
        logging.info(f'Received {data["command"]}')
        logging.debug(f'Received message: {raw_data}')

        if config['sidecar_type'] == 'l7mp':
            raw_response = rtpe_socket.send(raw_data, rtpe_address)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    address = os.getenv('NODE_IP', config['ingress_address'])
                    response['sdp'] = response['sdp'].replace('127.0.0.1', address)
                if data['command'] == 'delete':
                    delete_kube_resources(call_id)
                if data['command'] == 'offer':
                    sdp = sdp_transform.parse(response['sdp'])
                    rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                    create_offer_resource(
                        config, callid=call_id, from_tag=data['from-tag'], rtpe_rtp_port=rtp_port,
                        rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                        client_rtcp_port=client_rtp_port + 1
                    )
                if data['command'] == 'answer':
                    sdp = sdp_transform.parse(response['sdp'])
                    rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                    create_answer_resource(
                        config, callid=call_id, to_tag=data['to-tag'], rtpe_rtp_port=rtp_port,
                        rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                        client_rtcp_port=client_rtp_port + 1
                    )
                
                logging.info(f"Call setup time: {int((time.time() - time_start) * 1000)}")
                socket.sendto(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'), self.client_address)
                logging.debug("Response from rtpengine sent back to client")
        if config['sidecar_type'] == 'envoy':
            raw_response = rtpe_socket.send(raw_data, rtpe_address)
            if raw_response:
                response = parse_bc(raw_response)
                if 'sdp' in response:
                    address = os.getenv('NODE_IP', config['ingress_address'])
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
                            call_id
                        )
                        logging.debug(f"Data to envoy: {json_data}")
                        envoy_socket.send(json_data, envoy_address, no_wait_response=True)
                        logging.debug("After envoy send")
                elif data['command'] == 'offer':
                    sdp = sdp_transform.parse(response['sdp'])
                    rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                    create_offer_resource(
                        config, callid=call_id, from_tag=data['from-tag'], rtpe_rtp_port=rtp_port,
                        rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                        client_rtcp_port=client_rtp_port + 1
                    )
                elif data['command'] == 'answer':
                    sdp = sdp_transform.parse(response['sdp'])
                    rtp_port, rtcp_port = sdp['media'][0]['port'], sdp['media'][0]['rtcp']['port']
                    create_answer_resource(
                        config, callid=call_id, to_tag=data['to-tag'], rtpe_rtp_port=rtp_port,
                        rtpe_rtcp_port=rtcp_port, client_ip=client_ip, client_rtp_port=client_rtp_port,
                        client_rtcp_port=client_rtp_port + 1
                    )
                elif data['command'] == 'delete' and config['envoy_operator'] == 'yes':
                    delete_kube_resources(call_id)
                
                logging.info(f"Call setup time: {int((time.time() - time_start) * 1000)}")
                socket.sendto(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'), self.client_address)
                logging.debug("Response from rtpengine sent back to client")

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
            # server_thread.daemon = True
            server_thread.start()
            logging.info(f"Server loop running in thread: {server_thread.name}")
            server_thread.run()
        except KeyboardInterrupt:
            server.shutdown()