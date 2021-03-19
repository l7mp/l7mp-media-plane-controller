from parse import arguments
from utils import send, ffmpeg, handle_oa
from call_gen import GenerateCall
from commands import Commands
from pprint import pprint
import json
import sdp_transform
import socket
import time
import os
import traceback

MULTI_PARAMETERS_COMMANDS = [
    'file', 'delete', 'start_recording', 'stop_recording', 'block_dtmf',
    'unblock_dtmf', 'block_media', 'unblock_media', 'start_forwarding',
    'stop_forwarding', 'play_media', 'stop_media', 'play_dtmf', 'statistics'
]

def options(args, commands):
    for attr, value in args.__dict__.items():
        if attr in ['ping', 'statistics'] and value:
            pprint(send(args.addr, args.port, getattr(commands, attr)() ,args.sdpaddr, 3000))
        if attr in ['list_calls', 'query'] and value:
            pprint(send(args.addr, args.port, getattr(commands, attr)(value) ,args.sdpaddr, 3000))
        if attr in MULTI_PARAMETERS_COMMANDS and value:
            print(value)
            if value[0] == '{':
                dict_value = json.loads(value)
                call_id = dict_value['call-id']; del dict_value['call-id']
                if attr == 'delete':
                    from_tag = dict_value['from-tag']; del dict_value['from-tag']
                    pprint(send(args.addr, args.port, commands.delete(call_id, from_tag, **dict_value), args.sdpaddr, 3000))
                elif attr == 'play_dtmf':
                    code = dict_value['code']; del dict_value['code']
                    pprint(send(args.addr, args.port, commands.play_dtmf(call_id, code, **dict_value), args.sdpaddr, 3000))
                else:
                    pprint(send(args.addr, args.port, getattr(commands, attr)(call_id, **dict_value), args.sdpaddr, 3000))
            else:
                with open(value, 'r') as f_value:
                    pprint(send(args.addr, args.port, json.load(f_value), args.sdpaddr, 3000)) 

def main():
    global args
    args = arguments()
    commands = Commands()
    options(args, commands)

    if args.ws_address:
        address = args.ws_address
        port = args.ws_port
        ws = True
    else:
        address = args.addr
        port = args.port
        ws = False

    if args.offer:
        offer_rtp_port = handle_oa(address, port, args.offer, args.bind_offer, "offer", ws)
    if args.answer:
        answer_rtp_port = handle_oa(address, port, args.answer, args.bind_answer, "answer", ws)
    if args.generate_calls:
        global g_calls
        if not args.sidecar_type:
            g_calls = GenerateCall(
                address=address, 
                port=port, 
                sdp_address=args.sdpaddr, 
                audio_file=args.audio_file,
                rtpsend=args.rtpsend, 
                in_cluster=args.in_cluster, 
                without_jsonsocket=args.without_jsonsocket,
                sidecar="",
                codecs=args.codecs,
                ws=ws
            )
            g_calls.generate_calls(args.generate_calls)
        elif args.sidecar_type == 'l7mp':
            g_calls = GenerateCall(
                address=address, 
                port=port, 
                sdp_address=args.sdpaddr, 
                audio_file=args.audio_file,
                rtpsend=args.rtpsend, 
                in_cluster=args.in_cluster, 
                without_jsonsocket=args.without_jsonsocket,
                sidecar=args.sidecar_type,
                codecs=args.codecs,
                ws=ws
            )
            g_calls.generate_calls(args.generate_calls)

    if args.offer and args.answer and args.ffmpeg:
        time.sleep(1)
        offer_rtp_address = [f'rtp://{address}:{str(offer_rtp_port)}?localrtpport={str(args.bind_offer[1])}']
        answer_rtp_address = [f'rtp://{address}:{str(answer_rtp_port)}?localrtpport={str(args.bind_answer[1])}']
        ffmpeg(args, 1, offer_rtp_address, answer_rtp_address, args.codecs)

def delete():
    apis = g_calls.get_apis()
    g_calls.delete_calls()
    if os.getenv('RTPE_CONTROLLER'):
        for a in apis:
            a.delete_resources()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        delete()
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        delete()
    else:
        if args.generate_calls: 
            delete()