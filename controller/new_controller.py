import argparse
import logging
import asyncio
from utils import load_config
from servers.tcp_server import serve as tcp_serve
from servers.udp_server import serve as udp_serve
from servers.ws_server import serve as ws_serve

log_levels = {
    'debug': logging.DEBUG, 
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='RTPengine controller.')
        parser.add_argument('--config-file', '-c', type=str, dest='config',
                            help='Location of configuration file.')
        parser.add_argument('--log-level', '-l', type=str, dest='log_level',
                            help='Log level, default is info', default='info')
        args = parser.parse_args()
        logging.basicConfig(
            format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s', 
            datefmt='%H:%M:%S', 
            level=log_levels[args.log_level.lower()])
        
        config = load_config(args.config)
        if not config:
            raise ValueError
        logging.debug(config)

        if config['protocol'] == 'ws':
            asyncio.run(ws_serve(config))
        if config['protocol'] == 'udp':
            udp_serve(config)
        if config['protocol'] == 'tcp':
            tcp_serve(config)
    except ValueError:
        logging.exception('There is no configuration')
    