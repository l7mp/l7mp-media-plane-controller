import sdp_transform
import logging
import time
import subprocess
import threading
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
        self.running = False

    # Transcoded specific sdp PCMU, speex
    def generate_sdp(self, address, port, codec):
        if codec == "0 101":
            sdp_dict = {
                "version":0,
                "origin":{
                    "address": address,
                    "username":123,
                    "sessionId":3092,
                    "sessionVersion":1,
                    "netType":"IN",
                    "ipVer":4,
                },
                "name":"Talk",
                "connection":{ "version":4, "ip":address},
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
                    "address":address,
                    "username":456,
                    "sessionId":2278,
                    "sessionVersion":1,
                    "netType":"IN",
                    "ipVer":4,
                },
                "name":"Talk",
                "connection":{"version":4,"ip":address},
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

        return sdp_transform.write(sdp_dict)

    # Send offer to rtpengine
    def offer(self):
        options = {
            "ICE": "remove", 
            "label": "caller",
            "supports": ["load limit"],
            "flags": ["SIP-source-address"],
            "replace": ["origin", "session-connection"],
            "received-from": ["IP4", "127.0.0.1"],
            "codec": { "mask": ["all"], "transcode": ["PCMU", "speex"]}
        }
        command = Commands.offer(
            self.generate_sdp('127.0.0.1', self.start, "0 101"),
            self.call_id, self.from_tag, **options
        )
        data = super().ws_send(command) if super().__getattribute__('protocol') == 'ws' else super().send(command, self.start)
        if not data: return Exception("No data come back from rtpengine (answer)")
        if 'sdp' not in data: return Exception(f'There is no sdp part in response: {data}')
        sdp_data = sdp_transform.parse(data["sdp"])
        return sdp_data['media'][0]['port']

    # Send answer to rtpengine
    def answer(self):
        options = {
            "ICE": "remove", 
            "label": "caller",
            "supports": ["load limit"],
            "flags": ["SIP-source-address"],
            "replace": ["origin", "session-connection"],
            "received-from": ["IP4", "127.0.0.1"],
            "codec": { "mask": ["all"], "transcode": ["PCMU", "speex"]}
        }
        command = Commands.answer(
            self.generate_sdp('127.0.0.1', self.end, "96"),
            self.call_id, self.from_tag, self.to_tag, **options
        )
        data = super().ws_send(command) if super().__getattribute__('protocol') == 'ws' else super().send(command, self.end)
        if not data: return Exception("No data come back from rtpengine (answer)")
        if 'sdp' not in data: return Exception(f'There is no sdp part in response: {data}')
        sdp_data = sdp_transform.parse(data["sdp"])
        return sdp_data['media'][0]['port']

    def delete(self):
        super().delete(self.call_id, self.from_tag, self.start)

    # Set up a call 
    def generate_call(self, wait):
        self.running = True
        rtpe_address = super().__getattribute__('rtpe_address')
        start_time = time.time()

        o_rtp = self.offer()
        if isinstance(o_rtp, Exception): return o_rtp
        logging.debug(f'Offer with callid: {self.call_id} created in {int((time.time() - start_time) * 1000)} ms')
        
        a_rtp = self.answer()
        if isinstance(a_rtp, Exception): return a_rtp
        logging.info(f'Call with callid: {self.call_id} created in {int((time.time() - start_time) * 1000)} ms')

        # Start rtp processes
        ret = [
            subprocess.Popen(["rtpsend", "-s", str(self.start), "-f", self.file1, f'{rtpe_address}/{a_rtp}']),
            subprocess.Popen(["rtpsend", "-s", str(self.end), "-f", self.file2, f'{rtpe_address}/{o_rtp}'])
        ]

        # For non-blocking wait
        event = threading.Event()
        event.wait(wait)

        return ret
