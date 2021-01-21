from parse import arguments
from utils import send, ffmpeg, handle_oa
from call_gen import generate_calls
import json
import sdp_transform
import socket
import time

def main():
    args = arguments()

    if not args.server:
        if args.file:
            with open(args.file) as f:
                file = json.load(f)
            response = send(args.addr, args.port, file, args.sdpaddr, 3000)
            print(response)
        # Read files
        if args.offer:
            offer_rtp_port = handle_oa(
                args.addr, args.port, 
                args.offer, args.bind_offer, "offer")
        if args.answer:
            answer_rtp_port = handle_oa(
                args.addr, args.port, 
                args.answer, args.bind_answer, "answer")
        if args.generate_calls:
            generate_calls(args.addr, args.port, args.sdpaddr, args.audio_file,
            args.token, args.generate_calls)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((args.server_address, args.server_port))
        print("Listening on %s:%d" % (args.server_address, args.server_port))
        while True:
            data, addr = sock.recvfrom(1024)
            time.sleep(1)
            response = send(args.addr, args.port, json.loads(data.decode()), addr[0], int(addr[1]))
            parsed_sdp_dict = sdp_transform.parse(response.get('sdp'))
            print("RTP port from rtpengine: %d" % parsed_sdp_dict.get('media')[0]
                .get('port'))
            print("RTCP port from rtpengine: %d\n" % parsed_sdp_dict.get('media')[0]
                .get('rtcp').get('port'))

    if args.offer and args.answer and args.ffmpeg:
        time.sleep(1)
        offer_rtp_address = [f'rtp://{args.addr}:{str(offer_rtp_port)}?localrtpport={str(args.bind_offer[1])}']
        answer_rtp_address = [f'rtp://{args.addr}:{str(answer_rtp_port)}?localrtpport={str(args.bind_answer[1])}']
        ffmpeg(args, 1, offer_rtp_address, answer_rtp_address)

if __name__ == '__main__':
    main()