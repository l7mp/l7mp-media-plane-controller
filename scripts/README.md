# Scripts

## patch.sh

## linphone.py

## local_docker.sh

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