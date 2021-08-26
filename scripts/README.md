# Scripts

## patch.sh

Used to test kubernetes API slowness

## linphone.py

This script should be presented at each linphone client vm/machine. This will start 
a packet capture and start a linphone client with configs. 

How to start it:

```
python app.py -p <<playable wav location>> -r <<where to record file name>> -c <<linphone command>> -pr <<prometheus address>>
```

Start a call:

```
# caller vm
python app.py -p /home/user/shanty.wav -r /home/user/record.wav -c "call 456" -pr 10.0.1.6:8000
# callee vm
python app.py -p /home/user/shanty.wav -r /home/user/record.wav -c "answer 1" -pr 10.0.1.7:8000
```

- The prometheus address always the vm address and some kind of port.
- At the caller side you have to use this command  `call 456` , because the caller name is 
  `123` and the callee name is `456`
- At the callee side you have to use this command `answer 1`, because the first incoming call
  will use `1` as a identifier. 
- Always run first the caller command and after the callee command

## local_docker.sh

Created when I thought I will build images on testbed, but I never used it. 

## plot.py

For `dir` param you have to create a directory structure like this: 

```
-- dir
  -- subdir1
    -- subdir1.csv
  -- subdir2
    -- subdir2.csv
  etc.
```

A `csv` should contain these columns: 

```
MOS-LQ | MOS-CQ | R-FACTOR | RTT | MEAN-JITTER
```

To generate a proper `csv` you have to export it from a `pcap`, where you first have to 
apply the above metrics as a column, then make a filter only for `RTCP` packets and export them 
as a `csv`.

```
python plot.py --dir "/absolute/path/for/a/directory/with/csvs" -t "Title of your figure" -o "/absolute/path/for/output/figures"
```

## rtpe_cpu.py

At transcoding show the cpu usage calculated by the way how the rtpengine do it. 