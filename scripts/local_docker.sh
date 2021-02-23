#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"/..

registry=localhost:5000
name=rtpe-operator
tag=$registry/$name

# POD=$(kubectl get pods --namespace kube-system -l k8s-app=registry \
#            -o template --template '{{range .items}}{{.metadata.name}} {{.status.phase}}{{"\n"}}{{end}}' \
#           | grep Running | head -1 | cut -f1 -d' ')

# kubectl port-forward --namespace kube-system $POD 5000:5000 &

sudo docker build --no-cache  . -t $tag --network=host &&
sudo docker image push $tag


