import socket
import os
import json
from client.utils import send
from client.commands import Commands
import time
import sdp_transform
from rtpe_operator.kube_api import KubernetesAPIClient
from pprint import pprint
import bencodepy

bc = bencodepy.Bencode(
    encoding='utf-8'
)

kubernets_apis = []
commands = Commands()
RTPE_ADDRESS = os.getenv('RTPE_ADDRESS')
RTPE_PORT = int(os.getenv('RTPE_PORT'))
RTPE_OPERATOR = os.getenv('RTPE_OPERATOR')

def check_delete():
    for a in kubernets_apis:
        query = send(
            RTPE_ADDRESS, RTPE_PORT,
            commands.query(a.call_id), '127.0.0.1', 2002 
        )
        if query['result'] == 'error':
            a.delete_resources()      
            kubernets_apis.remove(a)

def parse_data(data):
    return bc.decode(data.decode().split(" ", 1)[1])

def delete_kube_resources(call_id):
    for a in kubernets_apis:
        if a.call_id == call_id:
            a.delete_resources()
            kubernets_apis.remove(a)

def create_resource(call_id, tag, c_address, c_port):
    query = send(
        RTPE_ADDRESS, RTPE_PORT, 
        commands.query(call_id),
        '127.0.0.1', 2998
    )
    port = query['tags'][tag]['medias'][0]['streams'][0]['local port']
    kubernets_apis.append(
        KubernetesAPIClient(
            in_cluster=True,
            call_id=call_id,
            tag=tag,
            local_ip=c_address,
            local_rtp_port=c_port,
            local_rtcp_port=c_port,
            remote_rtp_port=port,
            remote_rtcp_port=port + 1,
            without_jsonsocket=os.getenv('WITHOUT_JSONSOCKET')
        )
    )

def main():
    if RTPE_OPERATOR == 'l7mp':
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
        sock.bind(('127.0.0.1', 2000))
        sock.settimeout(10)
        print("Listening on %s:%d" % ('127.0.0.1', 2000))
        while True:
            check_delete()
            try:
                data, client_address = sock.recvfrom(4096)
                data = parse_data(data)
                print(data)
            except Exception:
                continue
            
            time.sleep(1)
            response = send(RTPE_ADDRESS, RTPE_PORT, data, '127.0.0.1', 2001)
            sock.sendto(bc.encode(response), client_address) # Send back response

            if data['command'] == 'delete':
                delete_kube_resources(data['call-id'])
            if data['command'] == 'offer':
                sdp = sdp_transform.parse(data['sdp'])
                create_resource(
                    data['call-id'], data['from-tag'], 
                    sdp['origin']['address'], 
                    sdp['media'][0]['port']
                )
            if data['command'] == 'answer':
                sdp = sdp_transform.parse(data['sdp'])
                create_resource(
                    data['call-id'], data['to-tag'], 
                    sdp['origin']['address'], 
                    sdp['media'][0]['port']
                )
    if RTPE_OPERATOR == 'envoy':
        print('test1')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
        sock.bind(('0.0.0.0', 2000))
        sock.settimeout(10)
        print("Listening on %s:%d" % ('0.0.0.0', 2000))
        while True:
            print('listening')
            try:
                data, client_address = sock.recvfrom(4096)
                data = parse_data(data)
                pprint(data)
            except Exception:
                continue
        
            time.sleep(1)
            response = send(RTPE_ADDRESS, RTPE_PORT, data, '0.0.0.0', 2001)
            sock.sendto(bc.encode(response), client_address) # Send back response
            a = socket.gethostbyname_ex(os.getenv('ENVOY_MGM_ADDRESS'))
            print(a)
            envoy_address = (a[2][0], int(os.getenv('ENVOY_MGM_PORT')))
            print(envoy_address)
            print(type(envoy_address))
            if data['command'] == 'answer':
                query = send(
                    RTPE_ADDRESS, RTPE_PORT, 
                    commands.query(data['call-id']),
                    '0.0.0.0', 2998
                )
                pprint(query)
                caller_port = query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port']
                callee_port = query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port']
                print("caller_port: " + str(caller_port))
                print("callee_port: " + str(callee_port))
                json_data = json.dumps({
                        "caller_rtp": caller_port,
                        "caller_rtcp": caller_port + 1,
                        "callee_rtp": callee_port,
                        "callee_rtcp": callee_port + 1
                    }).encode('utf-8')
                sock.sendto(json_data,  envoy_address)

if __name__ == '__main__':
    main()