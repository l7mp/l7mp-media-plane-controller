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
print(os.getenv('RTPE_ADDRESS'))
print(os.getenv('RTPE_PORT'))
print(os.getenv('WITHOUT_JSONSOCKET'))
RTPE_ADDRESS = os.getenv('RTPE_ADDRESS')
RTPE_PORT = int(os.getenv('RTPE_PORT'))

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
    sock.bind(('127.0.0.1', 2000))
    sock.settimeout(10)
    print("Listening on %s:%d" % ('127.0.0.1', 2000))
    while True:
        # Check if some calls are destroyed or not. 
        for a in kubernets_apis:
            print(a.call_id)
            query = send(
                RTPE_ADDRESS, RTPE_PORT,
                commands.query(a.call_id), '127.0.0.1', 2002 
            )
            if query['result'] == 'error':
                a.delete_resources()      
                kubernets_apis.remove(a)         

        try:
            data, client_address = sock.recvfrom(4096)
            data = data.decode()
            data = data.split(" ", 1)
            data = bc.decode(data[1])
            pprint(data)
            print('Client Address:')
            print(client_address,sep=';')
        except Exception:
            continue
        
        time.sleep(1)

        # NOTE: Send received data to rtpengine
        # RTPE_ADDRESS = rtpengine address 
        # RTPE_PORT = rtpengine ng port
        response = send(RTPE_ADDRESS, RTPE_PORT, data, '127.0.0.1', 2001)

        # Send back the response

        # Check this out
        sock.sendto(bc.encode(response), client_address)

        # Check whenever is delete command
        if data['command'] == 'delete':
            for a in kubernets_apis:
                if a.call_id == data['call-id']:
                    a.delete_resources()
                    kubernets_apis.remove(a)
        if data['command'] == 'offer':
            query = send(
                RTPE_ADDRESS, RTPE_PORT, 
                commands.query(data['call-id']),
                '127.0.0.1', 2998
            )
            print("query OK")
            port = query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port']
            kubernets_apis.append(
                KubernetesAPIClient(
                    in_cluster=True,
                    call_id=data['call-id'],
                    tag=data['from-tag'],
                    local_ip=client_address[0],
                    local_rtp_port=int(client_address[1]),
                    local_rtcp_port=int(client_address[1] + 1),
                    remote_rtp_port=port,
                    remote_rtcp_port=port + 1,
                    without_jsonsocket=os.getenv('WITHOUT_JSONSOCKET')
                )
            )
            print('API OK')
        if data['command'] == 'answer':
            query = send(
                RTPE_ADDRESS, RTPE_PORT, 
                commands.query(data['call-id']),
                '127.0.0.1', 2998
            )
            print('Query OK')
            port = query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port']
            kubernets_apis.append(
                KubernetesAPIClient(
                    in_cluster=True,
                    call_id=data['call-id'],
                    tag=data['to-tag'],
                    local_ip=client_address[0],
                    local_rtp_port=int(client_address[1]),
                    local_rtcp_port=int(client_address[1] + 1),
                    remote_rtp_port=port,
                    remote_rtcp_port=port + 1,
                    without_jsonsocket=os.getenv('WITHOUT_JSONSOCKET')
                )
            )
            print('API OK')

if __name__ == '__main__':
    main()