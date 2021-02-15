from client.parse import arguments
from client.utils import send, ffmpeg, handle_oa
from client.call_gen import GenerateCall
from client.commands import Commands
from pprint import pprint
import json
import sdp_transform
import socket
import time

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
    if not args.server:
        if args.offer:
            offer_rtp_port = handle_oa(
                args.addr, args.port, 
                args.offer, args.bind_offer, "offer")
        if args.answer:
            answer_rtp_port = handle_oa(
                args.addr, args.port, 
                args.answer, args.bind_answer, "answer")
        if args.generate_calls:
            global g_calls
            g_calls = GenerateCall(
                args.addr, args.port, args.sdpaddr, args.audio_file,
                args.rtpsend, args.in_cluster, args.without_jsonsocket)
            g_calls.generate_calls(args.generate_calls)
        

    if args.offer and args.answer and args.ffmpeg:
        time.sleep(1)
        offer_rtp_address = [f'rtp://{args.addr}:{str(offer_rtp_port)}?localrtpport={str(args.bind_offer[1])}']
        answer_rtp_address = [f'rtp://{args.addr}:{str(answer_rtp_port)}?localrtpport={str(args.bind_answer[1])}']
        ffmpeg(args, 1, offer_rtp_address, answer_rtp_address)

def delete():
    apis = g_calls.get_apis()
    g_calls.delete_calls()
    for a in apis:
        a.delete_resources()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        delete()
    except:
        delete()
    else:
        if args.generate_calls: 
            delete()