import json

class Commands:
    ''' This class contain the RTPengine ng protocol commands.
    '''

    def ping(self):
        ''' Test connection with rptengine.

        If the rtpengine is reachable will return a pong.
        '''

        data = {
            'command': 'ping'
        }
        return data

    def offer(self, sdp, call_id, from_tag, **kwargs):
        ''' Send an offer message.
        
        Args:
            sdp: Session Description Protocol string.
            call_id: Id of the call. 
            from_tag: The SIP From tag as string.
            kwargs:
                via-branch: The SIP Via branch as string.
                label: string.
                flags: List of strings.
                replace: List of strings.
                direction: List of two string.
                received-from: List of two strings.
                drop-traffic: "start" or "stop".
                ICE: string.
                ICE-lite: string.
                transport-protocol: string.
                media-address: string. 
                address-family: string.
                rtcp-mux: List of strings.
                TOS: Integer. 
                DTLS: string.
                DTLS-reverse: string.
                DTLS-fingerprint: string.
                SDES: List of strings.
                OSRTP: string.
                record-call: string. 
                metadata: string.
                codec: dictionary. 
                ptime: integer.
                ptime-reverse: integer.
                T.38: List of strings.
                supports: List of strings. 
                xmlrpc-callback: string.
        '''

        data = {
            'command': 'offer',
            'sdp': sdp,
            'call-id': str(call_id),
            'from-tag': str(from_tag)
        }

        for arg in kwargs:
            data[arg] = kwargs.get(arg)

        return data

    def answer(self, sdp, call_id, from_tag, to_tag, **kwargs):
        ''' Send an answer message.
        
        Args:
            sdp: Session Description Protocol string.
            call_id: Id of the call. 
            from_tag: The SIP From tag as string.
            kwargs:
                via-branch: The SIP Via branch as string.
                label: string.
                flags: List of strings.
                replace: List of strings.
                direction: List of two string.
                received-from: List of two strings.
                drop-traffic: "start" or "stop".
                ICE: string.
                ICE-lite: string.
                transport-protocol: string.
                media-address: string. 
                address-family: string.
                rtcp-mux: List of strings.
                TOS: Integer. 
                DTLS: string.
                DTLS-reverse: string.
                DTLS-fingerprint: string.
                SDES: List of strings.
                OSRTP: string.
                record-call: string. 
                metadata: string.
                codec: dictionary. 
                ptime: integer.
                ptime-reverse: integer.
                T.38: List of strings.
                supports: List of strings. 
                xmlrpc-callback: string.
        '''

        data = {
            'command': 'answer',
            'sdp': sdp,
            'call-id': str(call_id),
            'from-tag': str(from_tag),
            'to-tag': str(to_tag)
        }

        for arg in kwargs:
            data[arg] = kwargs.get(arg)

        return data

    def delete(self, call_id, from_tag, **kwargs):
        ''' Delete a call session from rtpengine.

        Args:
            call_id: ID of the call. 
            from_tag: The SIP message from tag.
            kwargs:
                to-tag: string.
                via-branch: string.
                flags: List of strings. ['fatal']
        '''
        
        data = {
            'command': 'delete',
            'call-id': str(call_id),
            'from-tag': str(from_tag)
        }

        for arg in kwargs:
            data[arg] = kwargs.get(arg)
                    
        return data

    def list_calls(self, limit = 32):
        ''' Get a list of call-ids.

        Be careful with the limit. To high could cause error. The 
        default value is 32. 

        Args:
            limit: How many calls should return.
        '''

        data = {
            'command': 'list',
            'limit': str(limit)
        }

        return data

    def query(self, call_id, **kwargs):
        ''' Query data about a call by call_id.

        It will contain data about packets, protcols, etc.

        Args:
            call_id: ID of the call.
            kwargs:
                from-tag: string.
                to-tag: string.
        '''

        data = {
            'command': 'query',
            'call-id': str(call_id),
        }

        for arg in kwargs:
            data[arg] = arg.get(arg)
        
        return data

    def start_recording(self, call_id, **kwargs):
        ''' Enables call recording for the call. 

        Either for the entire call or for only the specified call leg. 
        Currently rtpengine always enables recording for the entire call
        and does not support recording only individual call legs, 
        therefore all keys other than call-id are currently ignored.

        Args:
            call_id: Id of the call.
            kwargs:
                from-tag: string.
                to-tag: string.
                via-branch: string.
        '''

        data = {
            'command': 'start-recording',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            data[arg] = kwargs.get(arg) 

        return data

    def stop_recording(self, call_id, **kwargs):
        ''' Disables call recording for the call. 
        
        This can be sent during a call to immediately stop recording it.
        
        Args:
            call_id: ID of the call.
        '''

        data = {
            'command': 'stop-recording',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            if arg == 'all':
                data['flags'] = [kwargs.get(arg)]

        return data

    def block_dtmf(self, call_id, **kwargs):
        ''' Disable DTMF events. (RFC 4733)
        
        If only the call_id is presence will block DTMF for the entire 
        call but, it can be blocked for individual participants by 
        from_tag, address (SDP media address) or label. 

        Args:
            call_id: ID of the call.
            kwargs:
                from-tag: string.
                address: string.
                label: string.
        '''

        data = {
            'command': 'block-dtmf',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            data[arg] = kwargs.get(arg)

        return data

    def unblock_dtmf(self, call_id, **kwargs):
        ''' Unblock DTMF. 

        Unblocking packets for the entire call (i.e. only call-id is 
        given) does not automatically unblock packets for participants
        which had their packets blocked directionally, unless the string
        all is included in the flags section of the message.
        
        Args:
            call_id: ID of the call.
            kwargs:
                flags: List of strings. ['all'].
        '''

        data = {
            'command': 'unblock-dtmf',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            if arg == 'all':
                data['flags'] = [kwargs.get(arg)]

        return data

    def block_media(self, call_id, **kwargs):
        ''' Block media packets. 

        DTMF packets can still pass through when media blocking is 
        enabled. Media packets can be blocked fo an entire call, or 
        directionally for individual participants.

        Args:
            call_id: ID of the call.
            kwargs:
                from-tag: string.
                address: string.
                label: string.
        '''

        data = {
            'command': 'block-media',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            data[arg] = kwargs.get(arg)

        return data

    def unblock_media(self, call_id, **kwargs):
        ''' Unblock media packets. 
        
        Works like unblock_dtmf(...).

        Args:
            call_id: ID of the call.
            kwargs:
                flags: List of strings. ['all'].
        '''

        data = {
            'command': 'unblock-media',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            if arg == 'all':
                data['flags'] = [kwargs.get(arg)]

        return data

    def start_forwarding(self, call_id, **kwargs):
        ''' Forward PCM via TCP/TLS.

        These messages control the recording daemon's mechanism to 
        forward PCM via TCP/TLS. Unlike the call recording mechanism,
        forwarding can be enabled for individual participants 
        (directionally) only.

        Args:
            call_id: ID of the call.
            kwargs:
                from-tag: string.
                address: string.
                label: string.
        '''

        data = {
            'command': 'start-forwarding',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            data[arg] = kwargs.get(arg)

        return data

    def stop_forwarding(self, call_id, **kwargs):
        ''' Stop forwarding.

        Works like unblock_dtmf(...).

        Args:
            call_id: ID of the call.
            kwargs:
                flags: List of strings. ['all'].
        '''

        data = {
            'command': 'stop-forwarding',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            if arg == 'all':
                data['flags'] = [kwargs.get(arg)]

        return data

    def play_media(self, call_id, file, **kwargs):
        ''' Starts playback of provided media file. 

        Important: Only available if the rtpengine was compiled with 
        transcoding support. 

        You can play media only participants by identify them with these 
        keys: from-tag, address, label. Or you can play media every 
        participants by set flag to all. 

        The played media could be anything what ffmpeg supports. 

        Args:
            call_id: ID of the call.
            kwargs:
                from-tag: string.
                address: string.
                label: string.
                flags: List of Strings. ['all']
                file: string.
                blob: binary blob. string
                db-id: integer (mysql or MariaDB)
                repeat-times: integer
                result: string response directory.
                duration: integer (ms)
        '''

        data = {
            'command': 'play-media',
            'call-id': str(call_id)
        }

        for arg in kwargs:
            if arg == 'all':
                data['flags'] = [kwargs.get(arg)]
            else:
                data[arg] = kwargs.get(arg)

        return data
        
    def stop_media(self, call_id, **kwargs):
        ''' Stop playback. 

        Stops the playback previously started by a play media message. 
        Media playback stops automatically when the end of the media 
        file is reached, so this message is only useful for prematurely
        stopping playback.

        Args:
            call_id: ID of the call.
        '''

        data = {
            'command': 'stop-media',
            'call-id': str(call_id),
        }

        for arg in kwargs:
            if arg == 'all':
                data['flags'] = [kwargs.get(arg)]
            else:
                data[arg] = kwargs.get(arg)

        return data

    def play_dtmf(self, call_id, code, **kwargs):
        ''' Inject DTMF tone or event into a running audio stream.

        The selected call participant is the one generating the DTMF 
        event, not the one receiving it.

        Args:
            call_id: ID of the call.
            code: Indicating the DTMF event to be generated. It can be 
                either an integer with values 0-15, or a string 
                containing a single character (0 - 9, *, #, A - D).
            kwargs:
                from-tag: string.
                address: string.
                label: string.
                flags: List of Strings. ['all']
                duration: integer (ms)
                volume: integer (dB)
                pause: integer (ms)
        '''

        data = {
            'command': 'play-dtmf',
            'call-id': str(call_id),
            'code': str(code)
        }

        for arg in kwargs:
            if arg == 'all':
                data['flags'] = kwargs.get(arg)
            else:
                data[arg] = kwargs.get(arg)

        return data

    def statistics(self):
        ''' Returns a set of general statistics metrics. 
        '''

        data = {
            'command': 'statistics'
        }

        return data