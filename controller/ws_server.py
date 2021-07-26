import asyncio
import websockets
from websocket import create_connection
import logging
import sdp_transform
import time
import os
from utils import *
from sockets import TCPSocket
import socket

config = None

def create_sockets(uri, call_id=""):
    rtpe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rtpe_socket.connect((config["rtpe_address"], config["rtpe_port"]))
    ws_socket = create_connection(
        uri,
        subprotocols=["ng.rtpengine.com"],
        origin=config['local_address'],
        socket=rtpe_socket,
        header=[f'callid: {call_id}'] if call_id != "" else ['callid: " "']
    )
    return (rtpe_socket, ws_socket)
    
def ws_send(message, ws_socket):
    ws_socket.send(message)
    response = ws_socket.recv()
    try:
        return parse_bc(response)
    except Exception:
        logging.error(f'Received response is not a string {str(response)}.')
        return None


async def handle(websocket, path):
    URI = f'ws://{config["rtpe_address"]}:{config["rtpe_port"]}'
    time_start = time.time()
    try:
        raw_data = await websocket.recv()
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"Probably the rtpengine instance closed the connection: {e}")
        return
    data = parse_data(raw_data)
    call_id = ""
    client_ip, client_rtp_port = None, None
    if 'sdp' in data:
        sdp = sdp_transform.parse(data['sdp'])
        client_ip, client_rtp_port = sdp['origin']['address'], sdp['media'][0]['port']
    if "call-id" in data:
        call_id = ''.join(e for e in data['call-id'] if e.isalnum()).lower()
    logging.debug(f'Received message: {raw_data}')
    rtpe_socket, ws_socket = create_sockets(URI, call_id)

    if config['sidecar_type'] == 'l7mp':
            # raw_response = asyncio.get_event_loop().run_until_complete(ws_send(URI, raw_data, call_id))
            response = ws_send(raw_data, ws_socket)
            if response:
                if 'sdp' in response:
                    address = os.getenv('NODE_IP', None)
                    if not address:
                        logging.exception("Cannot retrieve NODE_IP")
                    response['sdp'] = response['sdp'].replace('127.0.0.1', address)
                if data['command'] == 'delete':
                    delete_kube_resources(call_id)
                if data['command'] == 'answer':
                    query = ws_send(query_message(data['call-id']), ws_socket)
                    await async_create_resource(call_id, data['from-tag'], data['to-tag'], config, query)
                # time.sleep(0.1)
                logging.info(f"Call setup time: {int((time.time() - time_start) * 1000)}")
                await websocket.send(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'))
                logging.debug("Response from rtpengine sent back to client")
    if config['sidecar_type'] == 'envoy':
        response = ws_send(raw_data, ws_socket)
        if response:
            if 'sdp' in response:
                address = os.getenv('NODE_IP', None)
                if not address:
                    logging.exception("Cannot retrieve NODE_IP")
                response['sdp'] = response['sdp'].replace('127.0.0.1', address)
            if data['command'] == 'answer' and config['envoy_operator'] == 'no':
                raw_query = ws_send(query_message(data['call-id']), ws_socket)
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
                    
                    envoy_socket = TCPSocket(config['envoy_address'], config['envoy_port'])
                    envoy_socket.send(json_data, no_wait_response=True)
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
            await websocket.send(bytes(data['cookie'] + " " + bc.encode(response).decode(), 'utf-8'))
            logging.debug("Response from rtpengine sent back to client")
    rtpe_socket.close()
    ws_socket.close()

async def serve(conf):
    global config
    config = conf        
    
    async with websockets.serve(handle, conf['local_address'], 1999, subprotocols=["ng.rtpengine.com"]):
        await asyncio.Future()  # run forever