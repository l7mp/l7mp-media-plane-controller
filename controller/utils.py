from kubernetes.client.models import v1_label_selector
from commands import Commands
import logging
import bencodepy
import socket
import json
import random
import string
import configparser
from kube_api import Client
from async_kube_api import Client as async_client

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
    logging.debug(type(data))
    if isinstance(data, (bytes, bytearray)):
        data = data.decode()
    logging.debug(data)
    data_list = data.split(" ", 1)
    return {
        'cookie': data_list[0],
        **bc.decode(data_list[1])
    }

def parse_bc(bc_string):
    if isinstance(bc_string, (bytes, bytearray)):
        bc_string = bc_string.decode()
    splitted = bc_string.split(" ", 1)[1]
    logging.debug(f'Splitted string: {splitted}')
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

    from_data = {
        'tag': from_tag,
        'local_ip': from_c_address,
        'local_rtp_port': from_c_port,
        'local_rtcp_port': from_c_port + 1,
        'remote_rtp_port': from_port,
        'remote_rtcp_port': from_port + 1,
    }

    to_data = {
        'tag': to_tag,
        'local_ip': to_c_address,
        'local_rtp_port': to_c_port,
        'local_rtcp_port': to_c_port + 1,
        'remote_rtp_port': to_port,
        'remote_rtcp_port': to_port + 1,
    }

    kubernetes_apis.append(
        Client(
            call_id=call_id,
            from_data=from_data,
            to_data=to_data,
            ws=ws,
            envoy=config['envoy_operator'],
            update_owners=config['update_owners'],
            udp_mode=config['udp_mode']
        )
    )

async def async_create_resource(call_id, from_tag, to_tag, config, query):
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

    from_data = {
        'tag': from_tag,
        'local_ip': from_c_address,
        'local_rtp_port': from_c_port,
        'local_rtcp_port': from_c_port + 1,
        'remote_rtp_port': from_port,
        'remote_rtcp_port': from_port + 1,
    }

    to_data = {
        'tag': to_tag,
        'local_ip': to_c_address,
        'local_rtp_port': to_c_port,
        'local_rtcp_port': to_c_port + 1,
        'remote_rtp_port': to_port,
        'remote_rtcp_port': to_port + 1,
    }

    c = async_client(
            call_id=call_id,
            from_data=from_data,
            to_data=to_data,
            ws=ws,
            envoy=config['envoy_operator'],
            update_owners=config['update_owners'],
            udp_mode=config['udp_mode']
        )
    await c.asnyc_create_resources()
    kubernetes_apis.append(c)


def create_offer_resource(config, **kwargs):
    global kubernetes_apis
    for a in kubernetes_apis:
        if a.call_id == kwargs.get('callid') and a.from_data:
            logging.debug(f'A kubernetes resource are exist with this call-id: {kwargs.get("callid")}')
            return

    ws = True if config['protocol'] == 'ws' else False

    from_data = {
        'tag': kwargs.get('from_tag'),
        'local_ip': kwargs.get('client_ip'),
        'local_rtp_port': kwargs.get('client_rtp_port'),
        'local_rtcp_port': kwargs.get('client_rtcp_port'),
        'remote_rtp_port': kwargs.get('rtpe_rtp_port'),
        'remote_rtcp_port': kwargs.get('rtpe_rtcp_port'),
    }

    kubernetes_apis.append(
        Client(
            call_id=kwargs.get('callid'),
            from_data=from_data,
            ws=ws,
            envoy=config['envoy_operator'],
            update_owners=config['update_owners'],
            udp_mode=config['udp_mode']
        )
    )

def create_answer_resource(config, **kwargs):
    global kubernetes_apis
    for a in kubernetes_apis:
        if a.call_id == kwargs.get('callid') and a.to_data:
            logging.debug(f'A kubernetes resource are exist with this call-id: {kwargs.get("callid")}')
            return

    ws = True if config['protocol'] == 'ws' else False

    to_data = {
        'tag': kwargs.get('to_tag'),
        'local_ip': kwargs.get('client_ip'),
        'local_rtp_port': kwargs.get('client_rtp_port'),
        'local_rtcp_port': kwargs.get('client_rtcp_port'),
        'remote_rtp_port': kwargs.get('rtpe_rtp_port'),
        'remote_rtcp_port': kwargs.get('rtpe_rtcp_port'),
    }

    kubernetes_apis.append(
        Client(
            call_id=kwargs.get('callid'),
            to_data=to_data,
            ws=ws,
            envoy=config['envoy_operator'],
            update_owners=config['update_owners'],
            udp_mode=config['udp_mode']
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
        if "udp_mode" not in config:
            config['udp_mode'] = 'server'
    except Exception:
        logging.error('Some key in configuration file is given wrong.')
        return None
    return config