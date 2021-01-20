from utils import send, ffmpeg
import commands
import sdp_transform
import time
import json

def generate_calls(args, cnt):
    ''' Generate a given number of calls.

    The first call will have these ports: offer - 3002 and answer - 
    3004 and it will increase always by two. This is important to debug
    if somethin went wrong. 

    It will use the ffmpeg command to create subprocesses which runs 
    almost side-by-side. 

    Watch out for the cnt because it can produce a huge load cause the 
    ffmpeg memory usage. 

    Args:
      args: An object with the user settings.
      cnt: Number of concurrent calls. 
    '''

    start_port = 3000
    offers = []; answers = []
    
    for _ in range(cnt):
        # Offer
        start_port += 2
        sdp_offer = json.loads(
            commands.offer("remove", str(start_port) + "-" + str(start_port + 2), 
            "from-tag" + str(start_port), "caller" + str(start_port), 
            args.sdpaddr, start_port)
        )
        offer = send(args, sdp_offer, args.sdpaddr, start_port)

        # Answer
        start_port += 2
        sdp_answer = json.loads(
            commands.answer("remove", str(start_port - 2) + "-" + str(start_port),
            "from-tag" + str(start_port - 2), "to-tag" + str(start_port), 
            "callee" + str(start_port), args.sdpaddr, start_port)
        )
        answer = send(args, sdp_answer,args.sdpaddr, start_port)
        
        parsed_offer = sdp_transform.parse(offer.get('sdp'))
        parsed_answer = sdp_transform.parse(answer.get('sdp'))
        
        offer_port = parsed_offer.get('media')[0].get('port')
        answer_port = parsed_answer.get('media')[0].get('port')
        
        offers.append(f'rtp://{args.addr}:{str(offer_port)}?localrtpport={str(start_port - 2)}')
        answers.append(f'rtp://{args.addr}:{str(answer_port)}?localrtpport={str(start_port)}')

    time.sleep(1)
    ffmpeg(args, cnt, offers, answers)