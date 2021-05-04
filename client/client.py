import configparser
import logging
import argparse
import bencodepy
import socket
import random
import string
import subprocess
import sdp_transform
import time
import os
from websocket import create_connection
from commands import Commands
from paramiko import SSHClient

log_levels = {
    'debug': logging.DEBUG, 
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

bc = bencodepy.Bencode(
    encoding='utf-8'
)

commands = Commands()
config = None
calls = []
sock = None

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
    config = parser._sections['client']
    return config

def create_udp_socket(local_address, local_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((local_address, local_port))
    except Exception:
        logging.error(f'Cannot bind UDP socket to {local_address}:{local_port}.')
        return None
    sock.settimeout(10)
    logging.debug(f'Socket created on udp:{local_address}:{local_port}.')
    return sock

def create_tcp_socket(local_address, local_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if config['protocol'] != 'ws':
        try:
            sock.bind((local_address, local_port))
        except Exception:
            logging.error(f'Cannot bind TCP socket to {local_address}:{local_port}.')
            return None
        logging.info(f'Listening on tcp:{local_address}:{local_port}.')
    if config['protocol'] == 'ws':
        try:
            sock.connect((config["rtpe_address"], int(config["rtpe_port"])))
        except Exception:
            logging.error('Cannot make a new connection with this address: '
            f'{config["rtpe_address"]}:{config["rtpe_port"]}')
            return None
    sock.settimeout(10)
    return sock

def create_ws_socket(sock):
    return create_connection(
        f'ws://{config["rtpe_address"]}:{config["rtpe_port"]}',
        subprotocols=["ng.rtpengine.com"],
        origin=config['local_address'],
        socket=sock
    )

def send(data, port):
    local_sock = create_udp_socket(config['local_address'], port)
    cookie = ''.join(random.choice(string.ascii_lowercase) for i in range(5))
    data = bencodepy.encode(data).decode()
    message = str(cookie) + " " + str(data)
    logging.debug('message: ' + message)
    local_sock.sendto(message.encode('utf-8'), (config['rtpe_address'], int(config['rtpe_port'])))
    logging.debug('Command sent to rtpengine.')
    try:
        response = local_sock.recv(4096)
        logging.debug(f'Received from rtpengine: {str(response)}')
    except Exception:
        logging.error('After 10 seconds not received any response.')
        local_sock.close()
        return None
    try:
        data = response.decode()
        data = data.split(" ", 1)
        logging.debug(f"Return with: {data[1]}")
        local_sock.close()
        return bc.decode(data[1])
    except Exception:
        logging.error(f'Received response is not a string. {str(response)}.')
        local_sock.close()
        return None

def ws_send(command):
    sock.send(command)
    logging.info('Command sent to rtpengine.')
    response = sock.recv()
    logging.debug(f'Received from rtpengine: {str(response)}')
    try:
        data = response.decode()
        data = data.split(" ", 1)
        logging.debug(f"Return with: {data[1]}")
        return bc.decode(data[1])
    except Exception:
        logging.error(f'Received response is not a string. {str(response)}.')
        return None

def ffmpeg(calls):
    logging.info('Start every ffmpeg process')
    processes = []
    for value in calls:
        processes.append(
            subprocess.Popen(
                ["ffmpeg", "-re", "-i", config['wav_location'], "-ar", "8000", "-ac", "1",
                "-acodec", "pcm_mulaw", "-f", "rtp", value]
            )
        )
    logging.info(f'{str(len(processes))} ffmpeg process are running.')
    for process in processes:
        process.communicate()

def rtpsend(calls):
    logging.info('Start every rtpsend process')
    processes = []
    for key, value in calls.items():
        processes.append(
            subprocess.Popen(
                ["rtpsend", "-l", "-s", value, "-f", 
                config['rtp_dump_location'], key]
            )
        )
    logging.info(f'{str(len(processes))} rtpsend process are running.')
    for process in processes:
        process.communicate()

def generate_sdp(address, port, **kwargs):
    return sdp_transform.write({
        'version': 0,
        'origin': {
            'address': address,
            'ipVer': 4,
            'netType': 'IN',
            'sessionId': random.randint(1000000000, 9999999999),
            'sessionVersion': 1,
            'username': '-'
        },
        'name': 'tester',
        'timing': {'start': 0, 'stop': 0},
        'media': [
            {
                'connection': {'ip': address, 'version': 4},
                'direction': 'sendrecv',
                'fmtp': [],
                'payloads': 0,
                'port': port,
                'protocol': 'RTP/AVP',
                'rtp': [],
                'type': 'audio'
            }
        ]
    })

def offer(start, end):
    global calls
    options = {
        "ICE": "remove",
        "label": "caller",
        "generate RTCP": "on"
    }
    command = commands.offer(
        generate_sdp('127.0.0.1', start),
        f'{str(start)}-{str(end)}',
        f'from-tag{str(start)}',
        **options
    )
    if config['protocol'] == 'ws':
        res = ws_send(command)
    else:
        res = send(command, int(start))
    
    if not res:
        return None

    calls.append({
        'call-id': f'{str(start)}-{str(end)}',
        'from-tag': f'from-tag{str(start)}'
    })
    logging.info(f'Offers sent with call-id: {str(start)}-{str(end)}')
    return res

def answer(start, end):
    options = {
        "ICE": "remove",
        "label": "callee",
        "generate RTCP": "on"
    }
    command = commands.answer(
        generate_sdp('127.0.0.1', end),
        f'{str(start)}-{str(end)}',
        f'from-tag{str(start)}',
        f'to-tag{str(start)}',
        **options
    )
    if config['protocol'] == 'ws':
        res = ws_send(command)
    else:
        res = send(command, end)

    if not res:
        return None
    logging.info(f'Answer sent with call-id: {str(start)}-{str(end)}')
    return res

def query(start, end):
    if config['protocol'] == 'ws':
        query = ws_send(commands.query(f'{str(start)}-{str(end)}'))
    else:
        query = send(commands.query(f'{str(start)}-{str(end)}'), 3000)

    return {
        'offer_rtp_port': query['tags']["from-tag" + str(start)]['medias'][0]['streams'][0]['local port'],
        'offer_rtcp_port': query['tags']["from-tag" + str(start)]['medias'][0]['streams'][1]['local port'],
        'answer_rtp_port': query['tags']["to-tag" + str(start)]['medias'][0]['streams'][0]['local port'],
        'answer_rtcp_port': query['tags']["to-tag" + str(start)]['medias'][0]['streams'][1]['local port']
    }

def ssh_user(linphone):
    data = config[linphone].split("@")
    user = SSHClient()
    user.load_system_host_keys()
    user.connect(data[1], username=data[0], password=data[2])
    stdin, stdout, stderr = user.exec_command('linphonec')
    print(type(stdin))  # <class 'paramiko.channel.ChannelStdinFile'>
    print(type(stdout))  # <class 'paramiko.channel.ChannelFile'>
    print(type(stderr))  # <class 'paramiko.channel.ChannelStderrFile'>
    logging.info(f'STDOUT: {stderr.read().decode("utf8")}')

    stdin.write('soundcard use files')
    # stdin.write(f'play {config["linphone_wav_location"]}')
    # stdin.channel.shutdown_write()

    return stdin, stdout, stderr, user

def linphone():
    stdin1, stdout1, stderr1, user1 = ssh_user('ssh_linphone1')
    logging.debug('Setup linphone1')
    stdin2, stdout2, stderr2, user2 = ssh_user('ssh_linphone2')
    logging.debug('Setup linphone2')
    stdin1.write('call 456')
    logging.debug('after write')
    stdin1.channel.shutdown_write()
    time.sleep(2)
    stdin2.write('answer 1')
    stdin2.channel.shutdown_write()
    time.sleep(180)
    stdin1.write('terminate 1')
    stdin2.channel.shutdown_write()

    stdin1.close(), stdout1.close(); stderr1.close(), user1.close()
    stdin2.close(), stdout2.close(); stderr2.close(), user2.close()



def generate_calls():
    ffmpeg_addresses = []
    rtpsend_addresses = {}
    ids = {}
    for i in range(3002, 3000 + int(config['number_of_calls']) * 4, 4):
        ids[str(i)] = i + 2

    logging.debug(ids)

    for start, end in ids.items():
        out = offer(int(start), end)
        if not out:
            return
        out = answer(int(start), end)
        if not out:
            return
        q = query(int(start), end)
        logging.info(f"Offer side rtpengine ports: {q['offer_rtp_port']}-{q['offer_rtcp_port']}")
        logging.info(f"Answer side rtpengine ports: {q['answer_rtp_port']}-{q['answer_rtcp_port']}")
        if config['sender_method'] == 'ffmpeg':
            ffmpeg_addresses.append(
                f'rtp://{config["rtpe_address"]}:{str(q["offer_rtp_port"])}'
                f'?localrtpport={str(start)}'
            )
            ffmpeg_addresses.append(
                f'rtp://{config["rtpe_address"]}:{str(q["answer_rtp_port"])}'
                f'?localrtpport={str(end)}'
            )
            logging.debug('ffmpeg address added both offer and answer side.')
        if config['sender_method'] == 'rtpsend':
            dest = f'{config["rtpe_address"]}/{str(q["offer_rtp_port"])}'
            rtpsend_addresses[dest] = str(start)
            dest = f'{config["rtpe_address"]}/{str(q["answer_rtp_port"])}'
            rtpsend_addresses[dest] = str(end)
            logging.debug('rtpsend address added bot offer and answer side.')
    
    if config['sender_method'] == 'ffmpeg':
        ffmpeg(ffmpeg_addresses)
    if config['sender_method'] == 'rtpsend':
        rtpsend(rtpsend_addresses)
    if config['sender_method'] == 'wait':
        logging.info('Waiting for 10 minutes, before delete calls.')
        time.sleep(600)

def delete():
    for call in calls:
        if config['protocol'] == 'ws':
            ws_send(commands.delete(call['call_id'], call['from-tag']))
        else:
            send(commands.delete(call['call-id'], call['from-tag']), 3001)
            time.sleep(5)

def ping():
    if config['protocol'] == 'ws':
        res = ws_send(commands.ping())
    else:
        res = send(commands.ping(), 3000)
    logging.info(f'Result of ping: {res}')

def main(conf):
    global config
    global sock
    base_sock = None
    config = load_config(conf)
    if not config:
        os._exit(1)
    logging.debug(config)
    if config['sender_method'] == 'linphone':
        linphone()
        os._exit(1)
    if config['protocol'] == "ws":
        base_sock = create_tcp_socket(config['local_address'], 3000)
        sock = create_ws_socket(base_sock)
    if config['protocol'] == "udp":
        sock = create_udp_socket(config['local_address'], 3000)
    if config['protocol'] == "tcp":
        logging.info(config['protocol'])
        sock = create_tcp_socket(config['local_address'], 3000)
    if config['ping'] == 'yes':
        ping()
        os._exit(1)
    generate_calls()
    if base_sock:
        base_sock.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RTPengine controller.')
    parser.add_argument('--config-file', '-c', type=str, dest='config',
                        help='Location of configuration file.')
    parser.add_argument('--log-level', '-l', type=str, dest='log_level',
                        help='Log level, default is info', default='info')
    args = parser.parse_args()
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s', 
        datefmt='%H:%M:%S', 
        level=log_levels[args.log_level.lower()])
    try:
        main(args.config)
        delete()
        sock.close()
    except KeyboardInterrupt:
        delete()
        sock.close()
    except:
        logging.exception("Got exception on main handler.")
        delete()
        sock.close()