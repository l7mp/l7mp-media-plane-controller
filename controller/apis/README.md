# API files

Between these API files have a lot of duplications because I don't know how to do it
in one file without a lot of conditional statements.  

## async_kube_api.py

This kind of Kubernetes API is only used when you want to handle ws traffic, because 
you cannot use traditional threading when the WebSocket server is asyncio, because they
will make a big mess, when they are used together.

## kube_api.py

Used with simple L7mp operator and Envoy operator. 

## l7mp_api.py

This will not create any CR, it is only communicating with L7mp proxies in the cluster
and configure them through HTTP. 

## status.py

### Operations class

Implements the connectivity with the Kubernetes cluster and HTTP POST and DELETE 
methods. 

### Status class

Store information from a pod and also stores the configs which are applied to the
pod L7mp proxy. 

### Statuses class 

Handle a list of `Status` objects and modify them as needed. 

## status_wrapper.py

Create a global object which ensures we only have one object which contains 
the configs and pod's information. 