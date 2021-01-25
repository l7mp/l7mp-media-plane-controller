class Commands:
    def ping(self):
        return f'''
        {{
            "command": "ping"
        }}
        '''

    def offer(self, ice, call_id, from_tag, label, sdpaddr, port):
        # TODO: Somehow pass an argument that contains all the unnecessary keys 
        # and only write it to a string if it is defined, otherwise not.
        return fr'''
        {{
            "ICE": "{ice}",
            "call-id": "{str(call_id)}",
            "command": "offer",
            "from-tag": "{str(from_tag)}",
            "label": "{str(label)}",
            "sdp": "v=0\r\no=- 1607444729 1 IN IP4 {sdpaddr}\r\ns=tester\r\nt=0 0\r\nm=audio {str(port)} RTP/AVP 0\r\nc=IN IP4 {sdpaddr}\r\na=sendrecv\r\na=rtcp: {str(port + 1)}"
        }}
        '''

    def answer(self, ice, call_id, from_tag, to_tag, label, sdpaddr, port):
        # TODO: Somehow pass an argument that contains all the unnecessary keys 
        # and only write it to a string if it is defined, otherwise not.
        return fr'''
        {{
            "ICE": "{ice}",
            "call-id": "{str(call_id)}",
            "command": "answer",
            "from-tag": "{str(from_tag)}",
            "label": "{str(label)}",
            "sdp": "v=0\r\no=- 1607446271 1 IN IP4 {sdpaddr}\r\ns=tester\r\nt=0 0\r\nm=audio {str(port)} RTP/AVP 0\r\nc=IN IP4 {sdpaddr}\r\na=sendrecv\r\na=rtcp: {str(port + 1)}",
            "to-tag": "{str(to_tag)}"
        }}
        '''

    def delete(self, call_id, from_tag):
        # TODO: Add conditionally: to-tag, via-branch, flags, delete delay
        return f'''
        {{
            "command": "delete",
            "call-id": "{str(call_id)}",
            "from-tag": "{str(from_tag)}"
        }}
        '''

    def list_calls(self, limit = 32):
        ''' Get a list of call-ids

        Be careful with the limit. To high could cause error. The default 
        value is 32. 
        '''

        return f'''
        {{
            "command": "list",
            "limit": "{str(limit)}"
        }}
        '''

    def query(self, call_id, from_tag = '-1', to_tag = '-1'):
        ''' Query data about a call by call_id.

        It will contain data about packets, protcols, etc. 
        '''

        return f'''
        {{
            "command": "query",
            "call-id:" "{str(call_id)}",
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"to-tag": "' + str(to_tag) + '",' if to_tag != '-1' else ''}
        }}
        '''

    def start_recording(self, call_id, from_tag = '-1', to_tag = '-1', via_branch = '-1'):
        ''' Enables call recording for the call. 

        Either for the entire call or for only the specified call leg. 
        Currently rtpengine always enables recording for the entire call and
        does not support recording only individual call legs, therefore all
        keys other than call-id are currently ignored.
        '''

        return f'''
        {{
            "command": "start recording",
            "call-id": "{str(call_id)}",
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"to-tag": "' + str(to_tag) + '",' if to_tag != '-1' else ''}
            {'"via-branch": "' + str(via_branch) + '",' if via_branch != '-1' else ''}
        }}
        '''

    def stop_recording(self, call_id):
        ''' Disables call recording for the call. This can be sent during a
        call to immediately stop recording it.
        '''

        return f'''
        {{
            "command": "stop recording"
        }}
        '''

    def block_dtmf(self, call_id, from_tag = '-1', address = '-1', label = '-1'):
        ''' Disable DTMF events. (RFC 4733)
        
        If only the call_id is presence will block DTMF for the entire call
        but, it can be blocked for individual participants by from_tag,
        address (SDP media address) or label. 
        '''

        return f'''
        {{
            "command": "block dtmf",
            "call-id": "{str(call_id)}",
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"address": "' + str(address) + '",' if address != '-1' else ''}
            {'"label": "' + str(label) + '",' if label != '-1' else ''}
        }}
        '''

    def unblock_dtmf(self, call_id, all = False):
        ''' Unblock DTMF. 

        Unblocking packets for the entire call (i.e. only call-id is given)
        does not automatically unblock packets for participants which had 
        their packets blocked directionally, unless the string all is 
        included in the flags section of the message.
        '''

        return f'''
        {{
            "command": "unblock dtmf",
            "call-id": "{str(call_id)}",
            {'"flags": ["all"],' if all else ''}
        }}
        '''

    def block_media(self, call_id, from_tag = '-1', address = '-1', label = '-1'):
        ''' Block media packets. 

        DTMF packets can still pass through when media blocking is enabled.
        Media packets can be blocked fo an entire call, or directionally for
        individual participants.

        '''
        return f'''
        {{
            "command": "block media",
            "call-id": "{str(call_id)}",
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"address": "' + str(address) + '",' if address != '-1' else ''}
            {'"label": "' + str(label) + '",' if label != '-1' else ''}
        }}
        '''

    def unblock_media(self, call_id, all = False):
        ''' Unblock media packets. 
        
        Works like unblock_dtmf(...). 
        '''

        return f'''
        {{
            "command": "unblock media",
            "call-id": "{str(call_id)}",
            {'"flags": ["all"],' if all else ''}
        }}
        '''

    def start_forwarding(self, call_id, from_tag = '-1', address = '-1', label = '-1'):
        ''' Forward PCM via TCP/TLS.

        These messages control the recording daemon's mechanism to forward
        PCM via TCP/TLS. Unlike the call recording mechanism, forwarding can
        be enabled for individual participants (directionally) only.
        '''

        return f'''
        {{
            "command": "start forwarding",
            "call-id": "{str(call_id)}",
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"address": "' + str(address) + '",' if address != '-1' else ''}
            {'"label": "' + str(label) + '",' if label != '-1' else ''}
        }}
        '''

    def stop_forwarding(self, call_id, all = False):
        ''' Stop forwarding.

        Works like unblock_dtmf(...).
        '''

        return f'''
        {{
            "command": "stop forwarding",
            "call-id": "{str(call_id)}",
            {'"flags": ["all"],' if all else ''}
        }}
        '''

    def play_media(self, call_id, file, from_tag = '-1', address = '-1', label = '-1',
                    all = False):
        ''' Starts playback of provided media file. 

        Important: Only available if the rtpengine was compiled with 
        transcoding support. 

        You can play media only participants by identify them with these 
        keys: from-tag, address, label. Or you can play media every 
        participants by set flag to all. 

        The played media could be anything what ffmpeg supports. 
        '''

        # TODO: Add all the possible file provider keys. 
        return f'''
        {{
            "command": "play media",
            "call-id": "{str(call_id)}",
            "file": "{str(file)}",
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"address": "' + str(address) + '",' if address != '-1' else ''}
            {'"label": "' + str(label) + '",' if label != '-1' else ''}
            {'"flags": ["all"],' if all else ''}
        }}
        '''

    def stop_media(self, call_id, from_tag = '-1', address = '-1', label = '-1',
                    all = False):
        ''' Stop playback. 

        Stops the playback previously started by a play media message. Media
        playback stops automatically when the end of the media file is
        reached, so this message is only useful for prematurely stopping
        playback.
        '''

        return f'''
        {{
            "command": "stop media",
            "call-id": "{str(call_id)}"
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"address": "' + str(address) + '",' if address != '-1' else ''}
            {'"label": "' + str(label) + '",' if label != '-1' else ''}
            {'"flags": ["all"],' if all else ''}
        }}
        '''

    def play_dtmf(self, call_id, file, code, from_tag = '-1', address = '-1', 
                label = '-1', all = False):
        ''' Inject DTMF tone or event into a running audio stream.

        The selected call participant is the one generating the DTMF event, 
        not the one receiving it.
        '''

        # TODO: Add these: duration, volume, pause
        return f'''
        {{
            "command": "play dtmf",
            "call-id": "{str(call_id)}",
            "code": "{str(code)}",
            {'"from-tag": "' + str(from_tag) + '",' if from_tag != '-1' else ''}
            {'"address": "' + str(address) + '",' if address != '-1' else ''}
            {'"label": "' + str(label) + '",' if label != '-1' else ''}
            {'"flags": ["all"],' if all else ''}
        }}
        '''

    def statistics(self):
        ''' Returns a set of general statistics metrics. 
        '''
        return f'''
        {{
            "command": "statistics"
        }}
        '''