import argparse

def arguments():

    # Init
    parser = argparse.ArgumentParser(description='Client for control RTPengine in kubernetes with l7mp.')

    # RTPengine server args
    parser.add_argument('--port', '-p', default=22222, type=int, dest='port', 
                        help='RTPengine server port.')
    parser.add_argument('--address', '-addr', default='127.0.0.1', type=str, dest='addr',
                        help='RTPengine server address.')

    # Client
    parser.add_argument('--offer', '-o', type=str, dest='offer', help='Offer JSON file location.')
    parser.add_argument('--answer', '-a', type=str, dest='answer', help='Answer JSON file location.')
    parser.add_argument('--bind_offer', '-bo', nargs=2, default=['127.0.0.1', '2000'], dest='bind_offer',
                        help='Offer source address and port.')
    parser.add_argument('--bind_answer', '-ba', nargs=2, default=['127.0.0.1', '2004'], dest='bind_answer',
                        help='Answer source address and port.')
    parser.add_argument('--file', '-f', type=str, dest='file', help="A simple file to list or query")
    parser.add_argument('--audio_file', '-af', type=str, dest='audio_file', help="Path of the audio to ffmpeg.")
    parser.add_argument('--generate_calls', "-gc", type=int, dest='generate_calls', 
                        help='Generate certain number of parallel calls with traffic.')
    parser.add_argument('--sdpaddress', '-saddr', type=str, dest='sdpaddr', default='127.0.0.1',
                        help='This the sender local address.')

    # Send incoming traffic to RTPengine
    parser.add_argument('--server', '-s', type=int, dest='server', choices=[0,1], 
                        help='1 - proxy mode, 0 - simple mode')
    parser.add_argument('--server_address', '-sa', type=str, dest='server_address', 
                        help='Listening address.')
    parser.add_argument('--server_port', '-sp', type=int, dest='server_port', 
                        help='Listening port.')

    # Not fully functional
    parser.add_argument('--pcap', type=str, dest='pcap', help='pcap file for analyze.')
    parser.add_argument('--tcpdump', '-t', type=str, dest='tcpdump', help='tcpdump interface.')
    parser.add_argument('--ffmpeg', '-ff', type=int, choices=[1], dest='ffmpeg', 
                        help="If specified, it will start a certain number of ffmpeg processes.")

    return args = parser.parse_args()