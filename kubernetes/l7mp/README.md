# L7mp configs

## jsonsocket

Old, probably used in the early stages of development. Not recommended
to use it, but it could be helpful somehow. 

## kernel 

Latest offload configs without operator, use these when you want to test
how the offload is working. 

## kernel_tcp, kernel_udp

Offload testing with L7mp operator. 

## udp 

I used this for my thesis with L7mp operator. This configs change protocols like
this:

- *ingress*: udp -> ws (ng commands)
- *ingress*: udp -> jsonsocket (rtp, rtcp packets)
- *worker*: ws -> udp (ng commands)

## without_crd

L7mp operator less configs

## without_operator 

L7mp ingress without operator