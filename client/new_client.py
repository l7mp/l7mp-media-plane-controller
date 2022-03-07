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
import threading
from commands import Commands

# Required params for the linphone handling
LINPHONE_ARGS = ['ssh_linphone1', 'ssh_linphone2', 'linphone_time', 'record_filename']

log_levels = {
    'debug': logging.DEBUG, 
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

rtp_processes = []

# This will parse the config file
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

# You can wait a given amount of time before the linphone streams ends
def linphone_sleep(client1, client2, linphone_time):
    logging.info(f'sleep time: {linphone_time * 60}')
    time.sleep(linphone_time * 60)
    client1.execute(chr(3))
    client2.execute(chr(3))

# Initialize calls and store the rtp stream processes
def call(call):
    global rtp_processes
    r = call.generate_call(config.getfloat('wait', 0))
    if isinstance(r, Exception):
        return r
    rtp_processes += r
    logging.info(f'{int(len(rtp_processes)/2)} calls running')
    return None

# Start creating calls with a configurable worker number
def threaded_calls(calls): 
    # calls: A list of call objects
    try:
        with ThreadPoolExecutor(max_workers=config.getint('max_workers', 1)) as executor:
            for c in calls:
                future = executor.submit(call, c)
                if isinstance(future.result(), Exception):
                    logging.error(future.result())
                    break
    except KeyboardInterrupt:
        return

if __name__ == '__main__':
    try:
        # Parse command arguments, parse config arguments, setup logging
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

        # Generate ports for streams and create call objects
        calls = []
        ports = deque()
        number_of_calls = config.getint('number_of_calls', 0) + config.getint('transcoding_calls', 0)
        for i in range(3002, (3000 + number_of_calls * 4) + 1, 2):
            ports.append(i)

        for t in range(config.getint('transcoding_calls', 0)):
            calls.append(TranscodedCall(ports.popleft(), ports.popleft(), **config))
        for n in range(config.getint('number_of_calls', 0)):
            calls.append(NormalCall(ports.popleft(), ports.popleft(), **config))

        # Start linphone clients on two separate vm
        if config.get('linphone', 'no') == 'yes':
            for i in LINPHONE_ARGS:
                if not config.get(i, None):
                    logging.exception(f'Config parameter: {i} not found!')
            # ssh into clients username == password
            client1_config = config.get('ssh_linphone1').split('@')
            client2_config = config.get('ssh_linphone2').split('@')

            client1 = ShellHandler(client1_config[1], client1_config[0], client1_config[0])
            client2 = ShellHandler(client2_config[1], client2_config[0], client2_config[0])
        
            cmd1 = f'python app.py -p /home/user/shanty.wav -r /home/user/{config.get("record_filename")} -c "call 456" -pr 10.0.1.6:8000'
            cmd2 = f'python app.py -p /home/user/shanty.wav -r /home/user/{config.get("record_filename")} -c "answer 1" -pr 10.0.1.7:8000'

            #logging.info(cmd1)
            #logging.info(cmd2)

            # Execute commands on clients
            #client1.execute(cmd1)
            time.sleep(0.5)
            #client2.execute(cmd2)

            #time.sleep(20)

            if len(calls) > 0: # If your don't specify calls 
                command = Commands.statistics
                threaded_calls(calls)

                time.sleep(10)
                logging.info(cmd1)
                logging.info(cmd2)
                #client1.execute(cmd1)
                time.sleep(0.5)
                #client2.execute(cmd2)

                #threading.Thread(target=linphone_sleep, args=(client1, client2, config.getint('linphone_time'), ), daemon=True).start()
            else:
                logging.info(cmd1)
                logging.info(cmd2)
                client1.execute(cmd1)
                time.sleep(0.5)
                client2.execute(cmd2)
                linphone_sleep(client1, client2, config.getint('linphone_time'))
        else:
            threaded_calls(calls)

        # Needed to be able to stop the subprocesses
        for r in rtp_processes:
            r.communicate()
    except KeyboardInterrupt:
        for c in calls:
            if c.running:
                c.delete()
    except Exception as e:
        logging.exception(e)
    except:
        logging.exception("Got exception on main handler")
        raise

