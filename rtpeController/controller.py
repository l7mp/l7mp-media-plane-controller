import socket
import os
import json
from utils import send, ws_send
from commands import Commands
import time
import sdp_transform
from kube_api import KubernetesAPIClient
from pprint import pprint
import bencodepy
from websocket import create_connection
import asyncio
import websockets
from multiprocessing import Process


bc = bencodepy.Bencode(
    encoding='utf-8'
)

kubernetes_apis = []
commands = Commands()
RTPE_ADDRESS = socket.gethostbyname_ex(os.getenv('RTPE_ADDRESS'))[2][0]
RTPE_PORT = int(os.getenv('RTPE_PORT'))
RTPE_CONTROLLER = os.getenv('RTPE_CONTROLLER')
RTPE_PROTOCOL = os.getenv('RTPE_PROTOCOL')

# https://stackoverflow.com/a/7207336/12243497
def runInParallel(*fns):
  proc = []
  for fn in fns:
    p = Process(target=fn)
    p.start()
    proc.append(p)
  for p in proc:
    p.join()

def check_delete():
    # print(len(kubernetes_apis))
    for a in kubernetes_apis:
        if RTPE_PROTOCOL == 'ws':
            query = ws_send(RTPE_PROTOCOL, RTPE_PORT, commands.query(a.call_id), '127.0.0.1', 2002)
        if RTPE_PROTOCOL == 'udp':
            query = send(RTPE_ADDRESS, RTPE_PORT, commands.query(a.call_id), '127.0.0.1', 2002)
        if query['result'] == 'error':
            a.delete_resources()      
            kubernetes_apis.remove(a)

# TODO: Fix this! kubernetes_apis always empty
def ws_check_delete():
    while True:
        time.sleep(10)
        check_delete()

def parse_data(data):
    return bc.decode(data.decode().split(" ", 1)[1])

def delete_kube_resources(call_id):
    delete_objects = []
    for a in kubernetes_apis:
        if a.call_id == call_id:
            a.delete_resources()
            delete_objects.append(a)

    for a in delete_objects:
        kubernetes_apis.remove(a)

def create_resource(call_id, from_tag, to_tag):
    global kubernetes_apis
    if RTPE_PROTOCOL == 'udp':
        query = send(RTPE_ADDRESS, RTPE_PORT, commands.query(call_id), '127.0.0.1', 2998)
    if RTPE_PROTOCOL == 'ws':
        query = ws_send(RTPE_ADDRESS, RTPE_PORT, commands.query(call_id), '127.0.0.1', 2998)

    from_port = query['tags'][from_tag]['medias'][0]['streams'][0]['local port']
    from_c_address = query['tags'][from_tag]['medias'][0]['streams'][0]['endpoint']['address']
    from_c_port = query['tags'][from_tag]['medias'][0]['streams'][0]['endpoint']['port']
    to_port = query['tags'][to_tag]['medias'][0]['streams'][0]['local port']
    to_c_address = query['tags'][to_tag]['medias'][0]['streams'][0]['endpoint']['address']
    to_c_port = query['tags'][to_tag]['medias'][0]['streams'][0]['endpoint']['port']
    
    kubernetes_apis.append(
        KubernetesAPIClient(
            in_cluster=True,
            call_id=call_id,
            tag=from_tag,
            local_ip=from_c_address,
            local_rtp_port=from_c_port,
            local_rtcp_port=from_c_port + 1,
            remote_rtp_port=from_port,
            remote_rtcp_port=from_port + 1,
            without_jsonsocket=os.getenv('WITHOUT_JSONSOCKET')
        )
    )
    kubernetes_apis.append(
        KubernetesAPIClient(
            in_cluster=True,
            call_id=call_id,
            tag=to_tag,
            local_ip=to_c_address,
            local_rtp_port=to_c_port,
            local_rtcp_port=to_c_port + 1,
            remote_rtp_port=to_port,
            remote_rtcp_port=to_port + 1,
            without_jsonsocket=os.getenv('WITHOUT_JSONSOCKET')
        )
    )

def udp_processing():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 2000))
    sock.settimeout(10)
    print("Listening on %s:%d" % ('127.0.0.1', 2000))

    if RTPE_CONTROLLER == 'l7mp':
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
            if data['command'] == 'answer':
                create_resource(data['call-id'], data['from-tag'], data['to-tag'])
    if RTPE_CONTROLLER == 'envoy':
        ENVOY_MGM_ADDRESS = socket.gethostbyname_ex(os.getenv('ENVOY_MGM_ADDRESS'))[2][0]
        ENVOY_MGM_PORT = int(os.getenv('ENVOY_MGM_PORT'))
        while True:
            try:
                data, client_address = sock.recvfrom(4096)
                data = parse_data(data)
                pprint(data)
            except Exception:
                continue
        
            time.sleep(1)

            response = send(RTPE_ADDRESS, RTPE_PORT, data, '127.0.0.1', 2001)
            sock.sendto(bc.encode(response), client_address) # Send back response
            
            if data['command'] == 'answer':
                query = send(RTPE_ADDRESS, RTPE_PORT, commands.query(data['call-id']), '0.0.0.0', 2998)
                
                caller_port = query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port']
                callee_port = query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port']
                
                json_data = json.dumps({
                        "caller_rtp": caller_port,
                        "caller_rtcp": caller_port + 1,
                        "callee_rtp": callee_port,
                        "callee_rtcp": callee_port + 1
                    }).encode('utf-8')

                sock_tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock_tmp.sendto(json_data, (ENVOY_MGM_ADDRESS, ENVOY_MGM_PORT))
                sock.close()

async def ws_processing(websocket, path):
    if RTPE_CONTROLLER == 'l7mp':
        data = None
        try:
            data = parse_data(await websocket.recv())
            response = ws_send(RTPE_ADDRESS, RTPE_PORT, data, '127.0.0.1', 2001)
            time.sleep(1)
            await websocket.send(bc.encode(response))
        except websockets.exceptions.ConnectionClosedError:
            pass
        
        if data['command'] == 'delete':
            delete_kube_resources(data['call-id'])
        if data['command'] == 'answer':
            create_resource(data['call-id'], data['from-tag'], data['to-tag'])
    if RTPE_CONTROLLER == 'envoy':
        ENVOY_MGM_ADDRESS = socket.gethostbyname_ex(os.getenv('ENVOY_MGM_ADDRESS'))[2][0]
        ENVOY_MGM_PORT = int(os.getenv('ENVOY_MGM_PORT'))

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', 2000))
        try:
            data = await websocket.recv()
            data = parse_data(data)
            print(data)

            response = ws_send(RTPE_ADDRESS, RTPE_PORT, data, '127.0.0.1', 2001)
            await websocket.send(bc.encode(response))

            if data['command'] == 'answer':
                query = ws_send(RTPE_ADDRESS, RTPE_PORT, commands.query(data['call-id']), '127.0.0.1', 2998)
                
                caller_port = query['tags'][data['from-tag']]['medias'][0]['streams'][0]['local port']
                callee_port = query['tags'][data['to-tag']]['medias'][0]['streams'][0]['local port']
                
                json_data = json.dumps({
                        "caller_rtp": caller_port,
                        "caller_rtcp": caller_port + 1,
                        "callee_rtp": callee_port,
                        "callee_rtcp": callee_port + 1
                    }).encode('utf-8')

                sock.sendto(json_data, (ENVOY_MGM_ADDRESS, ENVOY_MGM_PORT))
                sock.close()
        except websockets.exceptions.ConnectionClosedError:
            print('Connection closed')

def server():
    start_server = websockets.serve(ws_processing, "127.0.0.1", 1999, subprotocols=["ng.rtpengine.com"])
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

def main():
    if RTPE_PROTOCOL == 'udp':
        udp_processing()
    if RTPE_PROTOCOL == 'ws':
        runInParallel(ws_check_delete, server)

if __name__ == '__main__':
    main()