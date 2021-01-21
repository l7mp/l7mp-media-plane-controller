import argparse
import re


def parse(args, file):
    ''' Set arguments according to a configuration file.

    Format of the config file: 
      key1=value1
      key2=value2
      ...

    Args:
      args: Object with the user settings.
      file: Location of the config file. 
    '''

    with open(file, 'r') as f:
        Lines = f.readlines()
        for line in Lines:
            line = line.strip()
            if not line:
                continue
            if line[0] == '#':
                continue

            split_line = re.split('= | \s', line)

            if len(split_line) > 2:
                setattr(args, split_line[0], [split_line[1], split_line[2]])
            elif split_line[1].isdigit():
                setattr(args, split_line[0], int(split_line[1]))
            else:
                setattr(args, split_line[0], split_line[1])


def arguments():
    """ Handle the user settings.

    Returns:
      Ans object with the user settings.
    """

    # Init
    parser = argparse.ArgumentParser(
        description='Client for control RTPengine in kubernetes with l7mp.')

    parser.add_argument('--config_file', '-c', type=str, dest='config',
                        help='Specify the config file place.')

    # Kubernetes
    parser.add_argument('--token', '-t', type=str, dest='token',
                        help='Specify the BearerToken location.')

    # RTPengine server args
    parser.add_argument('--port', '-p', default=22222, type=int, dest='port',
                        help='RTPengine server port.')
    parser.add_argument('--address', '-addr', default='127.0.0.1', type=str,
                        dest='addr', help='RTPengine server address.')

    # Client
    parser.add_argument('--offer', '-o', type=str, dest='offer',
                        help='Offer JSON file location.')
    parser.add_argument('--answer', '-a', type=str, dest='answer',
                        help='Answer JSON file location.')
    parser.add_argument('--bind_offer', '-bo', nargs=2,
                        default=['127.0.0.1', '2000'], dest='bind_offer',
                        help='Offer source address and port.')
    parser.add_argument('--bind_answer', '-ba', nargs=2,
                        default=['127.0.0.1', '2004'], dest='bind_answer',
                        help='Answer source address and port.')
    parser.add_argument('--file', '-f', type=str, dest='file',
                        help="A simple file to list or query")
    parser.add_argument('--audio_file', '-af', type=str, dest='audio_file',
                        help="Path of the audio to ffmpeg.")
    parser.add_argument('--generate_calls', "-gc", type=int,
                        dest='generate_calls', help='Generate certain number '
                        'of parallel calls with traffic.')
    parser.add_argument('--sdpaddress', '-saddr', type=str, dest='sdpaddr',
                        default='127.0.0.1',
                        help='This the sender local address.')

    # Send incoming traffic to RTPengine
    parser.add_argument('--server', '-s', type=int, dest='server',
                        choices=[0, 1], help='1 - proxy mode, 0 - simple mode')
    parser.add_argument('--server_address', '-sa', type=str,
                        dest='server_address', help='Listening address.')
    parser.add_argument('--server_port', '-sp', type=int, dest='server_port',
                        help='Listening port.')

    # Not fully functional
    parser.add_argument('--ffmpeg', '-ff', type=int, choices=[1], dest='ffmpeg',
                        help='If specified, it will start a certain number of'
                        'ffmpeg processes.')

    args = parser.parse_args()

    if args.config:
        parse(args, args.config)

    return args
