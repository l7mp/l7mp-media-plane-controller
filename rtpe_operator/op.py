import socket
import os
import json
from client.utils import send
from client.commands import Commands
import time
import sdp_transform
from rtpe_operator.kube_api import KubernetesAPIClient

kubernets_apis = []
commands = Commands()
RTPE_ADDRESS = os.getenv('RTPE_ADDRESS')
RTPE_PORT = int(os.getenv('RTPE_PORT'))

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 22222))
    sock.settimeout(10)
    print("Listening on %s:%d" % ('127.0.0.1', 22221))
    while True:
        # Check if some calls are destroyed or not. 
        for a in kubernets_apis:
            query = send(
                RTPE_ADDRESS, RTPE_PORT,
                commands.query(a.call_id), '127.0.0.1', 2998 
            )
            if query['result'] == 'error':
                a.delete_resources()               

        try:
            data, client_address = sock.recvfrom(4096)
        except Exception:
            continue

        time.sleep(1)

        # NOTE: Send received data to rtpengine
        # RTPE_ADDRESS = rtpengine address 
        # RTPE_PORT = rtpengine ng port
        response = send(RTPE_ADDRESS, RTPE_PORT, data, '127.0.0.1', 10000)

        # Send back the response

        sock.sendto(response, (client_address[0], int(client_address[1])))

        if data['command'] == 'offer':
            query = send(
                RTPE_ADDRESS, RTPE_PORT, 
                commands.query(data['call-id']),
                '127.0.0.1', 2998
            )
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
        if data['command'] == 'answer':
            query = send(
                RTPE_ADDRESS, RTPE_PORT, 
                commands.query(data['call-id']),
                '127.0.0.1', 2998
            )
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

if __name__ == '__main__':
    main()