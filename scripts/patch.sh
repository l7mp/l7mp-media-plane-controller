#!/bin/bash
for i in {1..100}
do
    num_string="test$i"
    patch_string="{\"metadata\":{\"annotations\":{\"$num_string\":\"$num_string\"}}}"
    time kubectl patch pod rtpe-controller-795ffd98c-rrgh6 --type merge -p $patch_string &
done