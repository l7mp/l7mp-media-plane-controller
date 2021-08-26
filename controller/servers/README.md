## Couple of words about the code architecture

Further information is in the comments. 

### /apis directory

[apis](apis/README.md)

### /servers directory

[servers](servers/README.md)

### commands.py

In this, you can find all of the ng protocols commands. 

### new_controller.py

Parse the config file, set the logging, and start a server depending on the protocol. 

### sockets.py

Handle udp and tcp sockets for the servers.

#### TCPSocket

Create a TCP socket with a keep-alive mechanism. It has a sender method and it can reconnect
if the connection is lost. 

#### UDPSocket

With udp, I don't think that we need to reconnect because of the udp characteristic. 

### utils.py

Implements every method that is needed, but does not fit in any other class. 

## Obsolete files

controller.py