import random
import sdp_transform
import logging
import time
from callbase import CallBase
from commands import Commands


class TranscodedCall(CallBase):

    def __init__(self, start, end, **kwargs):
        super().__init__(
            local_address=kwargs.get('local_address', None),
            protocol=kwargs.get('protocol', None),
            rtpe_address=kwargs.get('rtpe_address', None),
            rtpe_port=kwargs.get('rtpe_port', None)
        )
        self.start = start
        self.end = end
        self.call_id = f'{str(self.start)}-{str(self.end)}'
        self.from_tag = f'from-tag{str(self.start)}'
        self.to_tag = f'to-tag{str(self.start)}'
        
        self.file1 = kwargs.get('file1', None)
        self.file2 = kwargs.get('file2', None)

        self.codec1 = kwargs.get('codec1', None)
        self.codec2 = kwargs.get('codec2', None)

    def generate_sdp(self, address, port, codec):
        # codec is a string like "0 101"
        # sdp_dict = {
        #     'version': 0,
        #     'origin': {
        #         'address': address,
        #         'ipVer': 4,
        #         'netType': 'IN',
        #         'sessionId': random.randint(1000000000, 9999999999),
        #         'sessionVersion': 1,
        #         'username': '-'
        #     },
        #     'name': 'tester',
        #     'connection': {'ip': address, 'version': 4},
        #     'timing': {'start': 0, 'stop': 0}
        # }

        if codec == "0 101":
            sdp_dict = {
                "version":0,
                "origin":{
                    "address": "127.0.0.1",
                    "username":123,
                    "sessionId":3092,
                    "sessionVersion":1,
                    "netType":"IN",
                    "ipVer":4,
                },
                "name":"Talk",
                "connection":{ "version":4, "ip":"127.0.0.1"},
                "timing":{"start":0,"stop":0},
                "media":[
                    {
                        "rtp":[{"payload":101,"codec":"telephone-event","rate":8000}],
                        "fmtp":[],
                        "type":"audio",
                        "port":port,
                        "protocol":"RTP/AVP",
                        "payloads":"0 101",
                    }
                ]
            }
        if codec == '96':
            sdp_dict = {
                "version":0,
                "origin":{
                    "address":"127.0.0.1",
                    "username":456,
                    "sessionId":2278,
                    "sessionVersion":1,
                    "netType":"IN",
                    "ipVer":4,
                },
                "name":"Talk",
                "connection":{"version":4,"ip":"127.0.0.1"},
                "timing":{"start":0,"stop":0},
                "media":[
                    {
                        "rtp":[{"payload":96, "codec":"speex","rate":16000}],
                        "fmtp":[{"payload":96,"config":"vbr=on"}],
                        "type":"audio",
                        "port":port,
                        "protocol":"RTP/AVP",
                        "payloads":96,
                    }
                ]
            }

        # if codec == "0 101":
        #     sdp_dict['media'] = [
        #         {
        #             "rtp":[
        #                 {
        #                 "payload":0,
        #                 "codec":"telephone-event",
        #                 "rate":8000
        #                 }
        #             ],
        #             "fmtp":[],
        #             "type":"audio",
        #             "port":port,
        #             "protocol":"RTP/AVP",
        #             "payloads":"0 101",
        #         }
        #     ]
        # elif codec == "96":
        #     sdp_dict['media'] = [
        #         {
        #             "rtp":[
        #                 {
        #                 "payload":96,
        #                 "codec":"speex",
        #                 "rate":16000
        #                 }
        #             ],
        #             "fmtp":[
        #                 {
        #                 "payload":96,
        #                 "config":"vbr=on"
        #                 }
        #             ],
        #             "type":"audio",
        #             "port": port,
        #             "protocol":"RTP/AVP",
        #             "payloads":"96 101"
        #         }
        #     ]

        return sdp_transform.write(sdp_dict)

    def offer(self):
        options = {
            "ICE": "remove", 
            "label": "caller",
            "supports": [
                "load limit"
            ],
            "flags": [
                "SIP-source-address"
            ],
            "replace": [
                "origin",
                "session-connection"
            ],
            "received-from": [
                "IP4",
                "127.0.0.1"
            ],
            "codec": { "mask": ["all"], "transcode": ["PCMU", "speex"]}
        }
        command = Commands.offer(
            self.generate_sdp('127.0.0.1', self.start, "0 101"),
            self.call_id, self.from_tag, **options
        )
        data = super().ws_send(command) if super().__getattribute__('protocol') == 'ws' else super().send(command, self.start)
        if not data:
            logging.error("No data come back from rtpengine. (offer)") 
            return None
        sdp_data = sdp_transform.parse(data["sdp"])
        return sdp_data['media'][0]['port']

    def answer(self):
        options = {
            "ICE": "remove", 
            "label": "caller",
            "supports": [
                "load limit"
            ],
            "flags": [
                "SIP-source-address"
            ],
            "replace": [
                "origin",
                "session-connection"
            ],
            "received-from": [
                "IP4",
                "127.0.0.1"
            ],
            "codec": { "mask": ["all"], "transcode": ["PCMU", "speex"]}
        }
        command = Commands.answer(
            self.generate_sdp('127.0.0.1', self.end, "96"),
            self.call_id, self.from_tag, self.to_tag, **options
        )
        data = super().ws_send(command) if super().__getattribute__('protocol') == 'ws' else super().send(command, self.end)
        if not data:
            logging.error("No data come back from rtpengine. (answer)") 
            return None
        sdp_data = sdp_transform.parse(data["sdp"])
        return sdp_data['media'][0]['port']

    def delete(self):
        super().delete(self.call_id, self.from_tag, self.start)

    def generate_call(self):
        rtpe_address = super().__getattribute__('rtpe_address')
        start_time = time.time()

        o_rtp = self.offer()
        if not o_rtp: return None
        
        a_rtp = self.answer()
        if not a_rtp: return None
        
        end_time = time.time()
        logging.info(f'Call with callid: {self.call_id} created in {int((end_time - start_time) * 1000)} ms')

        return [
            f'rtpsend -s {self.start} -f {self.file1} {rtpe_address}/{a_rtp}',
            f'rtpsend -s {self.end} -f {self.file2} {rtpe_address}/{o_rtp}'
        ]