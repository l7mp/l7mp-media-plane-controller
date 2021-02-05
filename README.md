# Client

This is a python client to make it possible to configure RTPengine in 
kubernetes. The SIP server will see as the same as RTPengine. 

## Warning

The docker image will not work properly because the kubernetes operator
is not separated from the client. 

## TODO

- [x] Somehow configure a kubernetes cluster with this code.
    - Sort of done, but require some testing and maybe some modification to
    become readable and easily modifiable. 
- [x] Make the right function to create the right resources in the cluster. 
- [x] Generate RTP streams for testing in a way where we can see the RTCP
    packets.
- [x] Finish every possible ng-command.
- [ ] Create a script which can analyze traffic.
- [ ] Add ServiceAccount support. 
    - I have to be able to create resources inside the cluster. 
    - Currently I do it outside, with ./kube/config file which is not 
    the best solution in a real cluster. 
    - Maybe not the ServiceAccount the key.
- [x] Create docker image. 
- [x] Automate image release
- [ ] Automate tests
- [ ] Write some unit test.  