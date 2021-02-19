#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"/..

registry=master:5000
name=vidarhun/rtpe-operator
tag=$registry/$name

sudo docker build --no-cache  . -t $tag &&
sudo docker push $tag:latest
