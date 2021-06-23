from kubernetes.client.models import v1_label_selector
from commands import Commands
import logging
import bencodepy
import socket
import json
import random
import string
from kube_api import Client

commands = Commands()
kubernetes_apis = []

bc = bencodepy.Bencode(
    encoding='utf-8'
)

def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        counter = 0
        while counter < 3:
            try:            
                sock.connect((ip, port))
                break
            except socket.error as error:
                logging.debug(f"IP {ip}, PORT {port}")
                logging.info(f"Connection Failed **BECAUSE:** {error}")
                logging.info(f"Attempt {counter} of 3")
                counter += 1
        sock.sendall(bytes(message, 'utf-8'))
        response = str(sock.recv(4096), 'utf-8')
        return response.strip()


def parse_data(data):
    logging.info(data)
    data_list = data.split(" ", 1)
    logging.info(data_list)
    return {
        'cookie': data_list[0],
        **bc.decode(data_list[1])
    }

def parse_bc(bc_string):
    splitted = bc_string.split(" ", 1)[1]
    logging.debug(fr'Splitted string: {splitted}')
    return bc.decode(splitted)

def query_message(call_id):
    cookie = ''.join(random.choice(string.ascii_lowercase) for i in range(5))
    return str(cookie) + " " + str(bencodepy.encode(commands.query(call_id)).decode())

def delete_kube_resources(call_id):
    global kubernetes_apis
    delete_objects = []
    for a in kubernetes_apis:
        if a.call_id == call_id:
            a.delete_resources()
            delete_objects.append(a)

    for a in delete_objects:
        kubernetes_apis.remove(a)

def create_resource(call_id, from_tag, to_tag, config, query):
    global kubernetes_apis
    for a in kubernetes_apis:
        if a.call_id == call_id:
            logging.debug(f'A kubernetes resource are exist with this call-id: {call_id}')
            return

    ws = True if config['protocol'] == 'ws' else False

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
            ws=ws,
            envoy=config['envoy_operator'],
            update_owners=config['update_owners']
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
            ws=ws,
            envoy=config['envoy_operator'],
            update_owners=config['update_owners']
        )
    )

def create_json(caller_port, callee_port, call_id):
    return json.dumps({
        "caller_rtp": caller_port,
        "caller_rtcp": caller_port + 1,
        "callee_rtp": callee_port,
        "callee_rtcp": callee_port + 1,
        "call_id": call_id
    })