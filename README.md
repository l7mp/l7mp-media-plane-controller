# Client

This is a python client to make it possible to configure RTPengine in 
kubernetes. The SIP server will see as the same as RTPengine. 

## TODO

- [x] Somehow configure a kubernetes cluster with this code.
    - Sort of done, but require some testing and maybe some modification to
    become readable and easily modifiable. 
- [ ] Make the right function to create the right resources in the cluster. 
- [ ] Generate RTP streams for testing in a way where we can see the RTCP
    packets. 

Test git ssh.