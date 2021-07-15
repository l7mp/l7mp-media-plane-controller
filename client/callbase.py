import logging
import socket
import bencodepy
import random
import string
import subprocess
from websocket import create_connection
from commands import Commands


class CallBase:

    def __init__(self, **kwargs):
        self.local_address = kwargs.get("local_address", None)
        self.protocol = kwargs.get("protocol", None)
        self.rtpe_address = kwargs.get("rtpe_address", None)
        self.rtpe_port = kwargs.get("rtpe_port", None)

        self._bc = bencodepy.Bencode(encoding='utf-8')

    def __getattr__(self, name):
        return getattr(self._obj, name)

    def _create_udp_socket(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.local_address, port))
        except Exception:
            sock.close()
            logging.error(f'Cannot bind UDP socket to {self.local_address}:{port}.')
            return None
        # sock.settimeout(10)
        logging.debug(f'Socket created on udp:{self.local_address}:{port}.')
        return sock

    def _create_tcp_socket(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.local_address, port))
        except Exception as e:
            sock.close()
            logging.exception(e)
            logging.error(f'Cannot bind TCP socket to {self.local_address}:{port}.')
            return None
        try:
            sock.connect((self.rtpe_address, int(self.rtpe_port)))
        except Exception:
            sock.close()
            logging.error('Cannot make a new connection with this address: '
            f'{self.rtpe_address}:{self.rtpe_port}')
            return None
        # sock.settimeout(10)
        logging.debug(f'Socket created on tcp:{self.local_address}:{port}')
        return sock

    def _create_ws_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.connect((self.rtpe_address, int(self.rtpe_port)))
        except Exception:
            sock.close()
            logging.error('Cannot make a new connection with this address: '
            f'{self.rtpe_address}:{self.rtpe_port}')
            return None
        conn = create_connection(
            f'ws://{self.rtpe_address}:{self.rtpe_port}',
            subprotocols=["ng.rtpengine.com"],
            origin=self.local_address,
            socket=sock
        )
        logging.debug(f'WebSocket connection established')
        return conn

    def send(self, data, port):
        sock = self._create_udp_socket(port) if self.protocol == 'udp' else self._create_tcp_socket(port)
        if not sock: return None

        cookie = ''.join(random.choice(string.ascii_lowercase) for _ in range(5))
        data = bencodepy.encode(data).decode()
        message = str(cookie) + " " + str(data)
        
        sock.sendto(message.encode('utf-8'), (self.rtpe_address, int(self.rtpe_port)))
        logging.debug(f'Data sent to rtpengine: {data}')
        
        try:
            response = sock.recv(10240)
            logging.debug(f'Received from rtpengine: {str(response)}')
        except Exception as e:
            logging.error(f'After 10 seconds not received any response. Error: {e}')
            sock.close()
            return None
        try:
            data = response.decode()
            data = data.split(" ", 1)
            sock.close()
            return self._bc.decode(data[1])
        except Exception as e:
            logging.error(f'Received response is not a string. {str(response)}. Error: {e}')
            sock.close()
            return None

    def ws_send(self, command):
        sock = self._create_ws_socket()
        if not sock: return None
        sock.send(command)
        logging.info(f'Command sent to rtpengine: {command}')
        response = sock.recv()
        logging.debug(f'Received from rtpengine: {str(response)}')
        try:
            data = response.decode()
            data = data.split(" ", 1)
            logging.debug(f"Return with: {data[1]}")
            return self._bc.decode(data[1])
        except Exception as e:
            logging.error(f'Received response is not a string. {str(response)}. Error: {e}')
            return None

    def start_rtp_stream(self, command1, command2): # For both rtpsend and ffmpeg
        # command is a list
        p1, p2 = subprocess.Popen(command1.split(" ")), subprocess.Popen(command2.split(" "))
        logging.info(f'rtpstream command1: {command1}')
        logging.info(f'rtpstream command2: {command2}')
        p1.communicate()
        p2.communicate()

    def delete(self, call_id, from_tag, port):
        command = Commands.delete(call_id, from_tag)
        self.ws_send(command) if self.protocol == 'ws' else self.send(command, port)
        logging.info(f'Call id {call_id} with tag {from_tag} is deleted.')

    def ping(self, port):
        res = self.ws_send(Commands.ping()) if self.protocol == 'ws' else self.send(Commands.ping(), port)
        logging.info(f'Result of ping: {res}')