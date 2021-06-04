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
- **ssh_pass**: ssh password for linphone
- **transcoding**: turn on the transcoding (yes, no)
- **codec1**: supported codec by caller
- **codec2**: supported codec by callee
- **rtpe_dump_codec1_location**: location of rtp file which has codec1 payload
type 
- **rtpe_dump_codec2_location**: location of rtp file which has codec1 payload
type 

## How to run

```
python3 client.py -c config/config.conf -l info
```

### Supported log levels

- debug
- info
- warning
- error
- critical