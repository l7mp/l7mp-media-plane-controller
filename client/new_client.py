import logging
import configparser
import argparse
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from normalcall import NormalCall
from transcodedcall import TranscodedCall
from ssh_handler import ShellHandler
from collections import deque

LINPHONE_ARGS = ['ssh_linphone1', 'ssh_linphone2', 'linphone_time', 'record_filename']

log_levels = {
    'debug': logging.DEBUG, 
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

rtp_commands = []

def load_config(conf):
    try:
        logging.info("Started!")
        parser = configparser.ConfigParser()
        if not parser.read(conf):
            raise Exception
    except Exception:
        logging.error("Cannot read or parse the configuration file.")
        return None
    config = parser['client']
    logging.info("Configuration file loaded!")
    return config

def linphone(linphone1, linphone2, linphone_time, record_filename):
        client1_config = linphone1.split('@')
        client2_config = linphone2.split('@')
        
        client1 = ShellHandler(client1_config[1], client1_config[0], client1_config[0])
        client2 = ShellHandler(client2_config[1], client2_config[0], client2_config[0])
        
        cmd1 = f'python app.py -p /home/user/shanty.wav -r /home/user/{record_filename} -c "call 456" -pr 10.0.1.6:8000'
        cmd2 = f'python app.py -p /home/user/shanty.wav -r /home/user/{record_filename} -c "answer 1" -pr 10.0.1.7:8000'
        
        logging.info(cmd1)
        logging.info(cmd2)

        client1.execute(cmd1)
        time.sleep(1)
        client2.execute(cmd2)

        time.sleep(linphone_time * 60)

        client1.execute(chr(3))
        client2.execute(chr(3))

def call(call):
    global rtp_commands
    r = call.generate_call(config.getfloat('wait', 0))
    if isinstance(r, Exception):
        return r
    rtp_commands += r
    logging.info(f'{int(len(rtp_commands)/2)} calls running')
    return None

def threaded_calls(calls): 
    # calls: A list of call objects
    try:
        with ThreadPoolExecutor(max_workers=config.getint('max_workers', 1)) as executor:
            for c in calls:
                future = executor.submit(call, c)
                if isinstance(future.result(), Exception):
                    break
    except KeyboardInterrupt:
        return

def start_rtp_streams(rtp_commands):
    processes = []
    for r in rtp_commands:
        logging.info(f'Started stream: {r}')
        processes.append(subprocess.Popen(r.split(" ")))
    for p in processes:
        p.communicate()

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='RTPengine controller.')
        parser.add_argument('--config-file', '-c', type=str, dest='config',
                            help='Location of configuration file.')
        parser.add_argument('--log-level', '-l', type=str, dest='log_level',
                            help='Log level, default is info', default='info')
        args = parser.parse_args()
        
        logging.basicConfig(
            format='%(asctime)s.%(msecs)03d [%(levelname)s] [%(filename)s:%(lineno)s - %(funcName)s()] %(message)s',
            datefmt='%H:%M:%S', 
            level=log_levels[args.log_level.lower()])

        config = load_config(args.config)
        logging.debug(config)
        calls = []
        ports = deque()
        number_of_calls = config.getint('number_of_calls', 0) + config.getint('transcoding_calls', 0)
        for i in range(3002, (3000 + number_of_calls * 4) + 1, 2):
            ports.append(i)

        for t in range(config.getint('transcoding_calls', 0)):
            calls.append(TranscodedCall(ports.popleft(), ports.popleft(), **config))
        for n in range(config.getint('number_of_calls', 0)):
            calls.append(NormalCall(ports.popleft(), ports.popleft(), **config))

        if config.get('linphone', 'no') == 'yes':
            for i in LINPHONE_ARGS:
                if not config.get(i, None):
                    logging.exception(f'Config parameter: {i} not found!')
            linphone(config['ssh_linphone1'], config['ssh_linphone2'], config['linphone_time'], config['record_filename'])
        
        threaded_calls(calls)
        # start_rtp_streams(rtp_commands)
        for r in rtp_commands:
            r.communicate()
        # for c in calls:
        #     c.delete()
    except KeyboardInterrupt:
        # for r in rtp_commands:
        #     r.kill()
        for c in calls:
            c.delete()
    except Exception as e:
        logging.exception(e)
    except:
        logging.exception("Got exception on main handler")
        raise

