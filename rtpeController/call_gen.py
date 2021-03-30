from utils import send, ffmpeg, generate_sdp, rtpsend, ws_send
from commands import Commands
from kube_api import KubernetesAPIClient
import sdp_transform
import time
import json
from pprint import pprint

class GenerateCall():
    ''' With this class you can generate calls.
    '''

    def __init__(self, **kwargs):
        self.address = kwargs['address']
        self.port = kwargs['port']
        self.sdp_address = kwargs['sdp_address']
        self.audio_file = kwargs['audio_file']
        self.in_cluster = kwargs['in_cluster']
        self.apis = []
        self.calls = []
        self.commands = Commands()
        self.rtpsend = kwargs['rtpsend']
        self.without_jsonsocket = kwargs['without_jsonsocket']
        self.sidecar = kwargs['sidecar']
        self.codecs = kwargs['codecs']
        self.ws = kwargs['ws']

    def send_offer(self, start_port, payload):
        options = {
            "ICE": "remove",
            "label": "caller",
            "generate RTCP": "on"
        }
        sdp_offer = self.commands.offer(
            generate_sdp('127.0.0.1', start_port, payload=payload),
            # generate_sdp(self.sdp_address, start_port),
            str(start_port) + "-" + str(start_port + 2),
            "from-tag" + str(start_port),
            **options
        )
        
        if not self.ws:
            send(self.address, self.port, sdp_offer, self.sdp_address, start_port)
        else:
            ws_send(self.address, self.port, sdp_offer, bind_address=self.sdp_address, bind_port=start_port)

        self.calls.append({
            'call_id': str(start_port) + "-" + str(start_port + 2), 
            'from-tag': "from-tag" + str(start_port)
        })

    def send_answer(self, start_port, payload):
        options = {
            "ICE": "remove",
            "label": "callee",
            "generate RTCP": "on"
        }
        sdp_answer = self.commands.answer(
            generate_sdp('127.0.0.1', start_port, payload=payload),
            # generate_sdp(self.sdp_address, start_port),
            str(start_port - 2) + "-" + str(start_port),
            "from-tag" + str(start_port - 2), "to-tag" + str(start_port - 2),
            **options
        ) 

        if not self.ws:
            send(self.address, self.port, sdp_answer, self.sdp_address, start_port)
        else:
            ws_send(self.address, self.port, sdp_answer, bind_address=self.sdp_address, bind_port=start_port)

    def generate_calls(self, cnt):
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
        caller_source_ports = []; callee_source_ports = []
        caller_destinations = []; callee_destinations = []
        
        for _ in range(cnt):
            # Offer
            start_port += 2
            self.send_offer(start_port, self.codecs[0])

            # Answer
            start_port += 2
            self.send_answer(start_port, self.codecs[1])

            if not self.ws:
                query = send(
                    self.address, self.port, 
                    self.commands.query(str(start_port - 2) + "-" + str(start_port)),
                    self.sdp_address, 2998
                )
            else:
                query = ws_send(
                    self.address, self.port, 
                    self.commands.query(str(start_port - 2) + "-" + str(start_port)),
                    bind_address=self.sdp_address, bind_port=2998, delay=5
                )

            offer_rtp_port = query['tags']["from-tag" + str(start_port - 2)]['medias'][0]['streams'][0]['local port']
            answer_rtp_port = query['tags']["to-tag" + str(start_port - 2)]['medias'][0]['streams'][0]['local port']
            
            offer_rtcp_port = query['tags']["from-tag" + str(start_port - 2)]['medias'][0]['streams'][1]['local port']
            answer_rtcp_port = query['tags']["to-tag" + str(start_port - 2)]['medias'][0]['streams'][1]['local port']

            print(f'Offer RTP port: {offer_rtp_port}, RTCP port {offer_rtcp_port}!')
            print(f'Answer RTP port: {answer_rtp_port}, RTCP port {answer_rtcp_port}!')

            if not self.rtpsend:
                offers.append(f'rtp://{self.address}:{str(offer_rtp_port)}?localrtpport={str(start_port - 2)}')
                answers.append(f'rtp://{self.address}:{str(answer_rtp_port)}?localrtpport={str(start_port)}')
            else:
                caller_source_ports.append(str(start_port - 2))
                callee_source_ports.append(str(start_port))
                caller_destinations.append(self.address + '/' + str(offer_rtp_port))
                callee_destinations.append(self.address + '/' + str(answer_rtp_port))
            
            if not self.sidecar:
                # Offer
                self.apis.append(
                    KubernetesAPIClient(
                        self.in_cluster,
                        call_id=str(start_port - 2) + "-" + str(start_port),
                        tag="from-tag" + str(start_port - 2),
                        # local_ip='127.0.0.1',
                        local_ip=self.sdp_address,
                        local_rtp_port=start_port - 2,
                        local_rtcp_port=start_port - 1,
                        remote_rtp_port=offer_rtp_port,
                        remote_rtcp_port=offer_rtcp_port,
                        without_jsonsocket=self.without_jsonsocket
                    )
                )
                
                # Answer
                self.apis.append(
                    KubernetesAPIClient(
                        self.in_cluster,
                        call_id=str(start_port - 2) + "-" + str(start_port),
                        tag="to-tag" + str(start_port - 2),
                        # local_ip='127.0.0.1',
                        local_ip=self.sdp_address,
                        local_rtp_port=start_port,
                        local_rtcp_port=start_port + 1,
                        remote_rtp_port=answer_rtp_port,
                        remote_rtcp_port=answer_rtcp_port,
                        without_jsonsocket=self.without_jsonsocket
                    )
                )

        # time.sleep(1)
        if self.audio_file: 
            ffmpeg(self.audio_file, cnt, offers, answers, self.codecs)
        elif self.rtpsend:
            rtpsend(self.rtpsend, cnt, caller_source_ports, caller_destinations, 
                    callee_source_ports, callee_destinations)
        else:
            time.sleep(600)

    def get_apis(self):
        ''' Return with the generated KubernetesAPIs 
        '''
        return self.apis

    def delete_calls(self):
        ''' Delete calls from rtpengine

        Iterate through the generated calls and delete them from 
        rtpengine based on their call_id and from-tag. 
        '''
        
        if not self.ws:
            for call in self.calls:
                send(
                    self.address, self.port, 
                    self.commands.delete(call['call_id'], call['from-tag']), 
                    self.sdp_address, 3000
                )
        else:
            for call in self.calls:
                ws_send(
                    self.address, self.port, 
                    self.commands.delete(call['call_id'], call['from-tag']), 
                    bind_address=self.sdp_address, bind_port=3000
                )