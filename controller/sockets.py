import socket
import logging
import time
import threading
from urllib.parse import non_hierarchical

class TCPSocket():

    def __init__(self, address, port, delay=0):
        self.address = address
        self.port = port
        self.create_socket()
        self.connect(delay)
        self.lock = threading.Lock()

    # Create tcp socket with keepalive mechanism
    def create_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)

    # Send data 
    def send(self, message, no_wait_response=False):
        with self.lock:
            counter = 0
            # Try to send out 3 times
            while counter < 3:
                try:
                    self.sock.sendall(bytes(message, 'utf-8'))
                    if no_wait_response:
                        return
                    response = str(self.sock.recv(10240), 'utf-8')
                    return response.strip()
                except ConnectionResetError as e:
                    self.sock.close()
                    self.create_socket()
                    logging.error(f"Server connection closed with {e}")
                    logging.info("Trying to reconnect")
                    self.connect(0)
                    counter += 1
                except IOError as e:
                    self.sock.close()
                    self.create_socket()
                    logging.error(f'IOError: {e}')
                    logging.info("Trying to reconnect")
                    self.connect(0)
                    counter += 1
            return

    # Connect to the defined address
    def connect(self, delay):
        counter = 0
        time.sleep(delay)
        logging.info(f"Delay connection by {delay} seconds")
        while True:
            try:
                self.sock.connect((self.address, self.port))
                logging.info("Successful connection")
                break
            except socket.error as error:
                logging.debug(f"Address {self.address}:{self.port}")
                logging.error(f"Connection Failed ({self.address})**BECAUSE:** {error}")
                logging.info(f"Attempt {counter} of 3")
                time.sleep(5)
                counter += 1

class UDPSocket():

    def __init__(self, delay=0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        time.sleep(delay)

    def send(self, message, address, no_wait_response=False):
        counter = 0
        while counter < 3:
            try:
                self.sock.sendto(bytes(message, 'utf-8'), address)
                if no_wait_response:
                    return
                response = str(self.sock.recv(4096), 'utf-8')
                return response.strip()
            except OSError as e:
                logging.error(f"Error: {e}")
                logging.info(f"Send attempt {counter} of 3 to {address}")
                counter += 1
        return