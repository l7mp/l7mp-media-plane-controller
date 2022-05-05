from apis.l7mp_api import L7mpAPI
from commands import Commands
import logging
import bencodepy
import socket
import json
import random
import string
import configparser
from apis.kube_api import KubeAPI
from apis.async_kube_api import AsyncKubeAPI
from apis.l7mp_api import L7mpAPI
from apis.kube_api import get_worker_pod_address

commands = Commands()

# Global list with kubernetes objects
kubernetes_apis = []

bc = bencodepy.Bencode(
    encoding='utf-8'
)

def without_keys(d, key):
    return {x: d[x] for x in d if x != key}

# Parse bencoded data and return with cookie too
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

# Parse a bencoded string
def parse_bc(bc_string):
    if isinstance(bc_string, (bytes, bytearray)):
        bc_string = bc_string.decode()
    splitted = bc_string.split(" ", 1)[1]
    logging.debug(f'Splitted string: {splitted}')
    return bc.decode(splitted)

# Create out a query message
def query_message(call_id):
    cookie = ''.join(random.choice(string.ascii_lowercase) for _ in range(5))
    return str(cookie) + " " + str(bencodepy.encode(commands.query(call_id)).decode())

# Delete a kubernetes resource with a given callid 
def delete_kube_resources(call_id):
    global kubernetes_apis
    delete_objects = []
    for a in kubernetes_apis:
        if a.call_id == call_id:
            a.delete_resources()
            delete_objects.append(a)

    for a in delete_objects:
        kubernetes_apis.remove(a)

# Create every necessarily resource for a call for both sides
def create_resource(call_id, from_tag, to_tag, config, query, client_ip):
    global kubernetes_apis
    for a in kubernetes_apis:
        if a.call_id == call_id:
            logging.debug(f'A kubernetes resource are exist with this call-id: {call_id}')
            return

    ws = True if config['protocol'] == 'ws' else False

    to_port = query['tags'][to_tag]['medias'][0]['streams'][0]['local port']
    to_c_port = query['tags'][to_tag]['medias'][0]['streams'][0]['endpoint']['port']
    
    from_port = query['tags'][from_tag]['medias'][0]['streams'][0]['local port']
    from_c_port = query['tags'][from_tag]['medias'][0]['streams'][0]['endpoint']['port']
    
    to_c_address = query['tags'][to_tag]['medias'][0]['streams'][0]['endpoint']['address']
    from_c_address = query['tags'][from_tag]['medias'][0]['streams'][0]['endpoint']['address']

    logging.debug('Every port and address is mapped.')

    from_data = {
        'callid': call_id,
        'tag': from_tag,
        'local_ip': from_c_address,
        'local_rtp_port': from_c_port,
        'local_rtcp_port': from_c_port + 1,
        'remote_rtp_port': from_port,
        'remote_rtcp_port': from_port + 1,
    }

    to_data = {
        'callid': call_id,
        'tag': to_tag,
        'local_ip': to_c_address,
        'local_rtp_port': to_c_port,
        'local_rtcp_port': to_c_port + 1,
        'remote_rtp_port': to_port,
        'remote_rtcp_port': to_port + 1,
    }

    if config['without_operator'] == 'no':
        kubernetes_apis.append(
            KubeAPI(
                call_id=call_id,
                from_data=from_data,
                to_data=to_data,
                ws=ws,
                envoy=config['envoy_operator'],
                update_owners=config['update_owners'],
                udp_mode=config['udp_mode']
            )
        )
    else:
        kubernetes_apis.append(
            L7mpAPI(
                call_id=call_id,
                from_data=from_data,
                to_data=to_data,
                udp_mode=config.get('udp_mode')
            )
        )


# Same as create_resources just async
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

    c = AsyncKubeAPI(
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

# Create offer side resources
def create_offer_resource(config, **kwargs):
    global kubernetes_apis
    for a in kubernetes_apis:
        if a.call_id == kwargs.get('callid') and a.from_data:
            logging.debug(f'A kubernetes resource are exist with this call-id: {kwargs.get("callid")}')
            return

    ws = True if config['protocol'] == 'ws' else False

    from_data = {
        'callid': kwargs.get("callid"),
        'tag': kwargs.get('from_tag'),
        'local_ip': kwargs.get('client_ip'),
        'local_rtp_port': kwargs.get('client_rtp_port'),
        'local_rtcp_port': kwargs.get('client_rtcp_port'),
        'remote_rtp_port': kwargs.get('rtpe_rtp_port'),
        'remote_rtcp_port': kwargs.get('rtpe_rtcp_port'),
    }

    if kwargs.get('without_operator') == 'no':
        kubernetes_apis.append(
            KubeAPI(
                call_id=kwargs.get('callid'),
                from_data=from_data,
                ws=ws,
                envoy=config['envoy_operator'],
                update_owners=config['update_owners'],
                udp_mode=config['udp_mode']
            )
        )
    else:
        kubernetes_apis.append(
            L7mpAPI(
                call_id=kwargs.get('callid'),
                from_data=from_data,
                udp_mode=config.get('udp_mode')
            )
        )

# Create answer side resources
def create_answer_resource(config, **kwargs):
    global kubernetes_apis
    for a in kubernetes_apis:
        if a.call_id == kwargs.get('callid') and a.to_data:
            logging.debug(f'A kubernetes resource are exist with this call-id: {kwargs.get("callid")}')
            return

    ws = True if config['protocol'] == 'ws' else False

    to_data = {
        'callid': kwargs.get("callid"),
        'tag': kwargs.get('to_tag'),
        'local_ip': kwargs.get('client_ip'),
        'local_rtp_port': kwargs.get('client_rtp_port'),
        'local_rtcp_port': kwargs.get('client_rtcp_port'),
        'remote_rtp_port': kwargs.get('rtpe_rtp_port'),
        'remote_rtcp_port': kwargs.get('rtpe_rtcp_port'),
    }

    if kwargs.get('without_operator') == 'no':
        kubernetes_apis.append(
            KubeAPI(
                call_id=kwargs.get('callid'),
                to_data=to_data,
                ws=ws,
                envoy=config['envoy_operator'],
                update_owners=config['update_owners'],
                udp_mode=config['udp_mode']
            )
        )
    else:
        kubernetes_apis.append(
            L7mpAPI(
                call_id=kwargs.get('callid'),
                to_data=to_data,
                udp_mode=config.get('udp_mode')
            )
        )

# Json creator for envoy controlplane
def create_json(caller_port, callee_port, call_id):
    return json.dumps({
        "caller_rtp": caller_port,
        "caller_rtcp": caller_port + 1,
        "callee_rtp": callee_port,
        "callee_rtcp": callee_port + 1,
        "call_id": call_id,
        "rtpe_address": get_worker_pod_address('app=worker')
    })

# Load configuration from config file
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