# Client

## Configuration

- **local_address**: address used to send (only works with IP addresses)
- **protocol**: used protocol to send ng commands. (udp, tcp, ws)
- **rtpe_address**: address of rtpengine (only works with IP addresses)
- **rtpe_port**: port of rtpengine
- **ping**: Send ping command to rtpengine. (yes, no). If yes the client
  will send a ping command and exit. 
- **number_of_calls**: define how many call you want concurrently
- **send_method**: define which the traffic generator tool (ffmpeg, rtpsend, linphone)
- **wav_location**: if you choose ffmpeg you have to provide a wav file location
- **rtp_dump_location**: if you chosse rtpsend you have to provide a dump file location
- **ssh_linpone1**: if you choose linphone, then you have to provide ssh access to the
  machine which has a cli linphone (user@10.0.0.1)
- **ssh_linphone2**: same as above
- **transcoding**: turn on the transcoding (yes, no)
- **codec1**: supported codec by caller
- **codec2**: supported codec by callee
- **rtpe_dump_codec1_location**: location of rtp file which has codec1 payload
type 
- **rtpe_dump_codec2_location**: location of rtp file which has codec1 payload
type

## New Configuration

- **protocol**: used protocol to send ng commands. (udp, tcp, ws)
- **local_address**: address used to send (only works with IP addresses)
- **rtpe_address**: address of rtpengine (only works with IP addresses)
- **rtpe_port**: port of rtpengine
- **number_of_calls**: define how many call you want concurrently
- **sender_method**: define which the traffic generator tool (ffmpeg, rtpsend, wait)
- **file**: Used wav or rtp file with normal calls. 
- **tanscoding_calls**: Number of transcoded calls
- **codec1**: supported codec by caller (codec numbers)
- **codec2**: supported codec by callee (codec numbers)
- **file1**: For transcoded calls you have to provide 2 different media file
- **file2**: For transcoded calls you have to provide 2 different media file
- **linphone**: Enable linphone call or not (yes, no)
- **ssh_linpone1**: if you choose linphone, then you have to provide ssh access to the
  machine which has a cli linphone (user@10.0.0.1). Be aware because the ssh user and 
  password have to match.
- **ssh_linphone2**: same as above
- **record_filename**: For linphones the recorded file name
- **linphone_time**: For linphones the duration of the calls 

## How to run

```
python new_client.py -c config/new_config.conf -l info
```

### Supported log levels

- debug
- info
- warning
- error
- critical

## Couple of words about the code architecture

Further information in the comments. 

### new_client.py 

- Thats the `main` file.
- This implements the config file parsing.
- This implements the linphone client startups.
- This implements the threaded call creations with the rtp streams.

### ssh_handler.py

Create ssh connection and execute commands as shell commands. 

### commands.py

In this you can find all of the ng protocols commands. 

### callbase.py

The base class of the `NormalCall` and `TranscodedCall` classes. 

- Handles (udp, tcp, ws) socket creations.
- Implements sender methods. For udp and tcp use the `send`, for ws use `ws_send`.
- Also implements `delete` and `ping` methods.

### normalcall.py

Setup a call with a proper sdp and start the rtp stream process.
For a normal call the codec will be PCMU. 

### transcodedcall.py

setup a call with proper transcoded sdp and start the rtp stream process.
Used codecs are PCMU, speex.

## Obsolete files:

client.py
