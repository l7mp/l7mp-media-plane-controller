import configparser
import logging
import argparse
import bencodepy
import socket
import json
import time
import os
import asyncio
import websockets
import random
import string
from commands import Commands
from kube_api import Client
from pprint import pprint
from websocket import create_connection
from tcp_server import serve as tcp_serve
from udp_server import serve as udp_serve

log_levels = {
    'debug': logging.DEBUG, 
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

bc = bencodepy.Bencode(
    encoding='utf-8'
)

kubernetes_apis = []
commands = Commands()
config = None
ws_socket = None

def parse_data(data):
    return {
        'cookie': data.decode().split(" ", 1)[0],
        **bc.decode(data.decode().split(" ", 1)[1])
    }

def create_json(caller_port, callee_port, call_id):
    return json.dumps({
        "caller_rtp": caller_port,
        "caller_rtcp": caller_port + 1,
        "callee_rtp": callee_port,
        "callee_rtcp": callee_port + 1,
        "call_id": call_id
    }).encode('utf-8')

def delete_kube_resources(call_id):
    global kubernetes_apis
    delete_objects = []
    for a in kubernetes_apis:
        if a.call_id == call_id:
            a.delete_resources()
            delete_objects.append(a)

    for a in delete_objects:
        kubernetes_apis.remove(a)

def create_udp_socket(local_address, local_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((local_address, local_port))
    except Exception:
        logging.error(f'Cannot bind UDP socket to {local_address}:{local_port}.')
        return None
    sock.settimeout(10)
    logging.info(f'Listening on udp:{local_address}:{local_port}.')
    return sock

def create_tcp_socket(local_address, local_port, ws = True):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if not ws:
        try:
            sock.bind((local_address, local_port))
        except Exception:
            logging.error(f'Cannot bind TCP socket to {local_address}:{local_port}.')
            return None
        logging.info(f'Listening on tcp:{local_address}:{local_port}.')
    if config['protocol'] == 'ws' and ws:
        try:
            sock.connect((config["rtpe_address"], config["rtpe_port"]))
        except Exception:
            logging.error('Cannot make a new connection with this address: '
            f'{config["rtpe_address"]}:{config["rtpe_port"]}')
            return None
    # sock.settimeout(10)
    return sock
    
def create_ws_socket(sock, header):
    return create_connection(
        f'ws://{config["rtpe_address"]}:{config["rtpe_port"]}',
        subprotocols=["ng.rtpengine.com"],
        origin=config['local_address'],
        socket=sock,
        header=header
    )

def send(command, sock, destination):
    sock.sendto(command.encode('utf-8'), destination)
    logging.info('Command sent to rtpengine.')
    try:
        response = sock.recv(4096)
        logging.debug(f'Received from rtpengine: {str(response)}')
    except Exception:
        logging.error('After 10 seconds not received any response.')
        return None
    try:
        data = response.decode()
        data = data.split(" ", 1)
        logging.debug(f"Return with: {data[1]}")
        return bc.decode(data[1])
    except Exception:
        logging.error(f'Received response is not a string. {str(response)}.')
        return None

def ws_send(command, sock):
    sock.send(command)
    logging.info('Command sent to rtpengine.')
    response = sock.recv()
    logging.debug(f'Received from rtpengine: {str(response)}')
    try:
        data = response.decode()
        data = data.split(" ", 1)
        logging.debug(f"Return with: {data[1]}")
        return bc.decode(data[1])
    except Exception:
        logging.error(f'Received response is not a string {str(response)}.')
        return None

def create_resource(call_id, from_tag, to_tag, sock):
    global kubernetes_apis
    for a in kubernetes_apis:
        if a.call_id == call_id:
            logging.debug(f'A kubernetes resource are exist with this call-id: {call_id}')
            return
    
    cookie = ''.join(random.choice(string.ascii_lowercase) for i in range(5))
    message = str(cookie) + " " + str(bencodepy.encode(commands.query(call_id)).decode())
    ws = False
    if config["protocol"] == "ws":
        query = ws_send(message, sock)
        ws = True
    else: 
        send(message, sock, (config['rtpe_address'], int(config['rtpe_port'])))
    logging.debug(f'Received query: {str(query)}')

    to_port = query['tags'][to_tag]['medias'][0]['streams'][0]['local port']
    to_c_address = query['tags'][to_tag]['medias'][0]['streams'][0]['endpoint']['address']
    to_c_port = query['tags'][to_tag]['medias'][0]['streams'][0]['endpoint']['port']
    from_port = query['tags'][from_tag]['medias'][0]['streams'][0]['local port']
    from_c_address = query['tags'][from_tag]['medias'][0]['streams'][0]['endpoint']['address']
    from_c_port = query['tags'][from_tag]['medias'][0]['streams'][0]['endpoint']['port']
    logging.debug('Every port and address is mapped.')

    kubernetes_apis.append(
        Client(
            call_id=call_id,
            tag=from_tag,
            local_ip=from_c_address,
            local_rtp_port=from_c_port,
            local_rtcp_port=from_c_port + 1,
            remote_rtp_port=from_port,
            remote_rtcp_port=from_port + 1,
            without_jsonsocket=config['without_jsonsocket'],
            ws=ws
        )
    )
    kubernetes_apis.append(
        Client(
            call_id=call_id,
            tag=to_tag,
            local_ip=to_c_address,
            local_rtp_port=to_c_port,
            local_rtcp_port=to_c_port + 1,
            remote_rtp_port=to_port,
            remote_rtcp_port=to_port + 1,
            without_jsonsocket=config['without_jsonsocket'],
            ws=ws
        )
    )

def load_config(conf):
    try:
        logging.info("Started!")
        parser = configparser.ConfigParser()
        if not parser.read(conf):
            raise Exception
    except Exception:
        logging.error("Cannot read or parse the configuration file.")
        return None
    logging.info("Configuration file loaded!")
    config = parser._sections['controller']
    try:
        if "rtpe_address" in config:
            config['domain_rtpe_address'] = config['rtpe_address']
            config['rtpe_address'] = socket.gethostbyname_ex(config['rtpe_address'])[2][0]
            config['rtpe_port'] = int(config['rtpe_port'])
        if "envoy_address" in config:
            config['domain_envoy_address'] = config['envoy_address']
            config['envoy_address'] = socket.gethostbyname_ex(config['envoy_address'])[2][0]
            config['envoy_port'] = int(config['envoy_port'])
        if "local_address" in config:
            config['local_address'] = socket.gethostbyname_ex(config['local_address'])[2][0]
            config['local_port'] = int(config['local_port'])
    except Exception:
        logging.error('Some key in configuration file is given wrong.')
        return None
    return config

def processing(sock, rtpe_sock):
    logging.info(f'Used sidecars: {config["sidecar_type"]}')
    while True:
        try:
            raw_data, client_address = sock.recvfrom(4096)
            data = parse_data(raw_data)
            logging.info(f'Received {data["command"]} with call-id: {data["call-id"]}')
            logging.debug(f'Received message: {raw_data}')
        except Exception:
            if config['protocol'] == 'udp':
                logging.debug('Not received anything within 10 seconds.')
            continue
        time.sleep(1)
        if config['sidecar_type'] == 'l7mp':
            while True:
                response = send(raw_data, rtpe_sock, (config['rtpe_address'], int(config['rtpe_port'])))
                if response:
                    if 'sdp' in response:
                        response['sdp'] = response['sdp'].replace('127.0.0.1', config['ingress_address'])
                    sock.sendto(bc.encode(response), client_address)
                    logging.debug("Response from rtpengine sent back to client.")
                    if data['command'] == 'delete':
                        delete_kube_resources(data['call-id'])
                    if data['command'] == 'answer':
                        create_resource(data['call-id'], data['from-tag'], data['to-tag'], rtpe_sock)
                    break
        if config['sidecar_type'] == 'envoy':
            while True:
                response = send(raw_data, rtpe_sock, (config['rtpe_address'], int(config['rtpe_port'])))
                if response:
                    if 'sdp' in response:
                        response['sdp'] = response['sdp'].replace('127.0.0.1', config['ingress_address'])
                    sock.sendto(bc.encode(response), client_address)
                    logging.debug("Response from rtpengine sent back to client.")
                    if data['command'] == 'answer':
                        query = send(commands.query(data['call-id']), rtpe_sock, (config['rtpe_address'], int(config['rtpe_port'])))
                        if not query:
                            logging.error('Cannot make a query to rtpengine. Retry.')
                            continue
                        json_data = create_json(
                            query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port'],
                            query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port'],
                            data['call-id']
                        )
                        logging.debug(f"Data to envoy: {json_data}")
                        rtpe_sock.sendto(json_data, (config['envoy_address'], int(config['envoy_port'])))
                        break
                    break

async def ws_processing(websocket, path):
    ws_socket = create_tcp_socket(config['local_address'], int(config['local_port']))
    if not ws_socket:
        return
    logging.info(f'Used sidecars: {config["sidecar_type"]}')
    try:
        raw_data = await websocket.recv()
        data = parse_data(raw_data)
        logging.debug(f'Received message: {raw_data}')
        if "call-id" in data:
            logging.info(f'Received {data["command"]} with call-id: {data["call-id"]}')
            ws_sock = create_ws_socket(ws_socket, [f'callid: {data["call-id"]}'])
        else:
            ws_sock = create_ws_socket(ws_socket, ['callid: " "'])
        response = ws_send(raw_data, ws_sock)
        if 'sdp' in response:
            response['sdp'] = response['sdp'].replace('127.0.0.1', config['ingress_address'])
        time.sleep(1)
        await websocket.send(data['cookie'] + " " + bc.encode(response).decode())
    except websockets.exceptions.ConnectionClosedError:
        logging.error("Connection closed")
        pass

    if config['sidecar_type'] == 'l7mp':
        if data['command'] == 'delete':
            delete_kube_resources(data['call-id'])
        if data['command'] == 'answer':
            create_resource(data['call-id'], data['from-tag'], data['to-tag'], ws_sock)
    if config['sidecar_type'] == 'envoy':
        if data['command'] == 'answer':
            query = ws_send(commands.query(data['call-id']), ws_sock)
            json_data = create_json(
                query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port'],
                query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port'],
                data['call-id']
            )
            logging.debug(f"Data to envoy: {json_data}")
            envoy_sock = create_tcp_socket(config['local_address'], int(config['local_port']) + 1, ws = False)
            envoy_sock.sendto(json_data, (config['envoy_address'], int(config['envoy_port'])))
            envoy_sock.close()
    time.sleep(1)
    ws_sock.close()
    ws_socket.close()

def udp_server():
    logging.info('UDP processing begins.')
    sock = create_udp_socket(config['local_address'], int(config['local_port']))
    rtpe_sock = create_udp_socket(config['local_address'], int(config['local_port']) + 1)
    logging.info(f'Used sidecars: {config["sidecar_type"]}')
    processing(sock, rtpe_sock)

def tcp_server():
    logging.info('TCP processing begins.')
    sock = create_tcp_socket(config['local_address'], int(config['local_port']))
    rtpe_sock = create_tcp_socket(config['local_address'], int(config['local_port']) + 1)
    logging.info(f'Used sidecars: {config["sidecar_type"]}')
    processing(sock, rtpe_sock)

def ws_server():
    start_server = websockets.serve(
        ws_processing, 
        config['local_address'], 
        1999, 
        subprotocols=["ng.rtpengine.com"]
    )
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

def main(conf):
    global config
    global ws_socket
    config = load_config(conf)
    if not config:
        return
    logging.debug(config)
 
    if config['protocol'] == 'ws':
        logging.info("WebSocket processing begins.")
        while True:
            ws_server()
    if config['protocol'] == 'udp':
        udp_serve(config)
    if config['protocol'] == 'tcp':
        tcp_serve(config)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RTPengine controller.')
    parser.add_argument('--config-file', '-c', type=str, dest='config',
                        help='Location of configuration file.')
    parser.add_argument('--log-level', '-l', type=str, dest='log_level',
                        help='Log level, default is info', default='info')
    args = parser.parse_args()
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s', 
        datefmt='%H:%M:%S', 
        level=log_levels[args.log_level.lower()])
    main(args.config)