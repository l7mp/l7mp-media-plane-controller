from parse import arguments
import json
from utils import send, ffmpeg
import sdp_transform
import socket
from call_gen import generate_calls
import time

args = arguments()

# if args.tcpdump:
#     tcpdump_proc = tcpdump()

if not args.server:
    if args.file:
        with open(args.file) as f:
            file = json.load(f)
        response = send(args, file, args.sdpaddr, 3000)
        print(response)
    # Read files
    if args.offer:
        with open(args.offer) as o:
            offer = json.load(o)
        response = send(args, offer, args.bind_offer[0], int(args.bind_offer[1]))
        parsed_sdp_dict = sdp_transform.parse(response.get('sdp'))
        offer_rtp_port = parsed_sdp_dict.get('media')[0].get('port')
        offer_rtcp_port = parsed_sdp_dict.get('media')[0].get('rtcp').get('port')
        print("RTP port from offer: %d" % offer_rtp_port)
        print("RTCP port from offer: %d" % offer_rtcp_port)
    if args.answer:
        with open(args.answer) as a:
            answer = json.load(a)
        response = send(args, answer, args.bind_answer[0], int(args.bind_answer[1]))
        parsed_sdp_dict = sdp_transform.parse(response.get('sdp'))
        answer_rtp_port = parsed_sdp_dict.get('media')[0].get('port')
        answer_rtcp_port = parsed_sdp_dict.get('media')[0].get('rtcp').get('port')
        print("RTP port from answer: %d" % answer_rtp_port )
        print("RTCP port from answer: %d" % answer_rtcp_port)
    if args.generate_calls:
        generate_calls(args, args.generate_calls)
else:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.server_address, args.server_port))
    print("Listening on %s:%d" % (args.server_address, args.server_port))
    while True:
        data, addr = sock.recvfrom(1024)
        time.sleep(1)
        response = send(args, json.loads(data.decode()), addr[0], int(addr[1]))
        parsed_sdp_dict = sdp_transform.parse(response.get('sdp'))
        print("RTP port from rtpengine: %d" % parsed_sdp_dict.get('media')[0].get('port'))
        print("RTCP port from rtpengine: %d\n" % parsed_sdp_dict.get('media')[0].get('rtcp').get('port'))

if args.offer and args.answer and args.ffmpeg:
    time.sleep(1)
    offer_rtp_address = ["rtp://" + args.addr + ":" + str(offer_rtp_port) + "?localrtpport=" + str(args.bind_offer[1])]
    answer_rtp_address = ["rtp://" + args.addr + ":" + str(answer_rtp_port) + "?localrtpport=" + str(args.bind_answer[1])]
    ffmpeg(args, 1, offer_rtp_address, answer_rtp_address)

# if args.tcpdump:
#     tcpdump_proc.terminate()