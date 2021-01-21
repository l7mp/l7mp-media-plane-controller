from utils import send, ffmpeg
import commands
import sdp_transform
import time
import json
from kube_api import KubernetesAPIClient

def generate_calls(address, port, sdp_address, audio_file, token, cnt):
    ''' Generate a given number of calls.

    The first call will have these ports: offer - 3002 and answer - 
    3004 and it will increase always by two. This is important to debug
    if somethin went wrong. 

    It will use the ffmpeg command to create subprocesses which runs 
    almost side-by-side. 

    Watch out for the cnt because it can produce a huge load cause the 
    ffmpeg memory usage. 

    Args:
      cnt: Number of concurrent calls. 
    '''

    start_port = 3000
    offers = []; answers = []
    if token:
        api = KubernetesAPIClient(token)
    
    for _ in range(cnt):
        # Offer
        start_port += 2
        sdp_offer = json.loads(
            commands.offer("remove", str(start_port) + "-" + str(start_port + 2), 
            "from-tag" + str(start_port), "caller" + str(start_port), 
            sdp_address, start_port)
        )
        offer = send(address, port, sdp_offer, sdp_address, start_port)

        # Answer
        start_port += 2
        sdp_answer = json.loads(
            commands.answer("remove", str(start_port - 2) + "-" + str(start_port),
            "from-tag" + str(start_port), "to-tag" + str(start_port), 
            "callee" + str(start_port), sdp_address, start_port)
        )
        answer = send(address, port, sdp_answer, sdp_address, start_port)
        
        parsed_offer = sdp_transform.parse(offer.get('sdp'))
        parsed_answer = sdp_transform.parse(answer.get('sdp'))
        
        offer_rtp_port = parsed_offer.get('media')[0].get('port')
        answer_rtp_port = parsed_answer.get('media')[0].get('port')

        offer_rtcp_port = parsed_offer.get('media')[0].get('rtcp').get('port')
        answer_rtcp_port = parsed_answer.get('media')[0].get('rtcp').get('port')

        offers.append(f'rtp://{address}:{str(offer_rtp_port)}?localrtpport={str(start_port - 2)}')
        answers.append(f'rtp://{address}:{str(answer_rtp_port)}?localrtpport={str(start_port)}')

        if token:
            api.create_vsvc({
                "call_id": str(start_port - 2) + "-" + str(start_port),
                "tag": "from-tag" + str(start_port - 2),
                "local_ip": sdp_address,
                "local_rtp_port": start_port - 2,
                "remote_rtp_port": offer_rtp_port,
                "local_rtcp_port": start_port - 1,
                "remote_rtcp_port": offer_rtcp_port
            })
            api.create_vsvc({
                "call_id": str(start_port - 2) + "-" + str(start_port),
                "tag": "from-tag" + str(start_port),
                "local_ip": sdp_address,
                "local_rtp_port": start_port,
                "remote_rtp_port": answer_rtp_port,
                "local_rtcp_port": start_port + 1,
                "remote_rtcp_port": answer_rtcp_port
            })

            api.create_target({
                "call_id": str(start_port - 2) + "-" + str(start_port),
                "tag": "from-tag" + str(start_port - 2)
            })
            api.create_target({
                "call_id": str(start_port - 2) + "-" + str(start_port),
                "tag": "from-tag" + str(start_port - 2)
            })

            api.create_rule({
                "call_id": str(start_port - 2) + "-" + str(start_port),
                "tag": "from-tag" + str(start_port - 2),
                "local_rtp_port": start_port - 2,
                "remote_rtp_port": offer_rtp_port,
                "local_rtcp_port": start_port - 1,
                "remote_rtcp_port": offer_rtcp_port
            })
            api.create_rule({
                "call_id": str(start_port - 2) + "-" + str(start_port),
                "tag": "from-tag" + str(start_port),
                "local_rtp_port": start_port,
                "remote_rtp_port": answer_rtp_port,
                "local_rtcp_port": start_port + 1,
                "remote_rtcp_port": answer_rtcp_port
            })


    time.sleep(1)
    ffmpeg(audio_file, cnt, offers, answers)