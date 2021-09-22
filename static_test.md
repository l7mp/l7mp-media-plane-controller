# How to test or how I make the tests

First of all, which server will be used for what: 

- **rhea**: Kubernetes master, apply configs, delete configs, etc. 
- **dione, titan**: These are the workers. But recently I only works with dione. 
- **tethys**: Traffic generator

## Adding images if they are not in a repository

1. On your local machine build the docker image
2. Save it into a tar file, like this : `docker save -o image.tar image`
3. Load up to dione, tethys (if you use it), rhea, like this: `scp image.tar server_name:/home/user`
4. Load tar into docker images, like this: `sudo docker load -i image.tar`

## Configs locations (rhea)

Every config file location in rhea is the `controller_recourses` directory.

## Kubespray usage (rhea)

The kubespray configs are located in `/opt/kubespray`. 

To change configuration edit `inventory/l7mp/hosts.yaml`.

Apply new configs: 

```
ansible-playbook -i inventory/l7mp/hosts.yaml --become --become-user=root cluster.yml
```

Delete cluster: 

```
ansible-playbook -i inventory/l7mp/hosts.yaml reset.yml
```

## Baseline testing

For this you have to use the rtpengine on dione. There is some rtpengine configs, 
for testing. Simply modify them as needed. 

## VMs (tethys)

The vms are using virtualbox. To edit them use this command `virtualbox &` and it will
start a window where you can edit the vms properties. 

Use these vms: **client_a** (10.0.1.6), **client_b** (10.0.1.7), **kamailio1** (10.0.1.5)

## kamailio settings

First of all the kamailio cannot use tcp ng messages, so you have to use an L7mp proxy
which will transfer every kamailio UDP ng message to TCP and send them to the cluster
or rtpengine. This config: 

``` javascript
admin:
  log_level: silly
  log_file: stdout
  access_log_path: /tmp/admin_access.log
listeners:
  - name: controller-listener
    spec:
      protocol: HTTP
      port: 1234
    rules:
      - action:
          route:
            destination:
              name: l7mp-controller
              spec:
                protocol: L7mpController
  - name: udp_control
    spec:
      protocol: UDP
      port: 22222
    rules:
      - action:
          route:
            destination:
              spec:
                protocol: TCP
                port: 2000
              endpoints:
                - spec:
                    address: 10.0.1.2

```

Run like this: 

```
node l7mp-proxy.js -c config/udp-tcp.yaml -l silly -s
```

### Kamailio config files

Kamailio config locations are in the `/etc/kamailio` folder. 

To modify something on kamailio you have to edit `kamailio.cfg` file and
restart the kamailio `systemctl restart kamailio`. 

Important part of the config: 

```
#!ifdef WITH_RTPENGINE
	if(nat_uac_test("8")) {
		rtpengine_manage("SIP-source-address replace-origin replace-session-connection");
		# rtpengine_manage("SIP-source-address replace-origin replace-session-connection codec-mask=all codec-transcode=PCMU codec-transcode=speex");
	} else {
		rtpengine_manage("replace-origin replace-session-connection");
		# rtpengine_manage("replace-origin replace-session-connection codec-mask=all codec-transcode=PCMU codec-transcode=speex");
	}
```

The commented part used when you want to make transcoded calls. 

### Adding new users

If you want or needed: `kamctl add username password`

### Useful links:

Installing use these links: 

- https://websiteforstudents.com/how-to-install-kamailio-sip-server-on-ubuntu-18-04-16-04/
- https://www.atlantic.net/vps-hosting/how-to-install-kamailio-sip-server-on-ubuntu-20-04/

Cookbook for config files:

- https://www.kamailio.org/wiki/cookbooks/5.5.x/core
- https://www.kamailio.org/wiki/cookbooks/5.5.x/pseudovariables
- https://www.kamailio.org/wiki/cookbooks/5.5.x/transformations

Used modules descriptions: https://kamailio.org/docs/modules/5.5.x/

## Linphone settings

With linphone you can generate a fully fledged voip call. 

Basic commands with linphone: 

- Start: `linphonec`
- Register a user: `register <<username>> <<Kamailio address>> <<password>>`
- Use sound file instead of microphone: `soundcard use files`
- Use a wav file: `play /home/user/shanty.wav`
- Record the call into a wav: `record /home/user/record.wav`
- Call another user: `call 456`
- Answer a call: `answer 1`

## Client 

In the `rtpe-controller/client/configs`  folder you can find the configs file or here you 
can add new configs. Once you made your own you can start the client via this command: 

```
python new_client.py -c config/new_config.conf -l info
```

## Static Test

1. Setup the cluster as you need. 
2. On kamailio start the L7mp proxy and restart kamailio.
3. Make your configuration for the client. Don't forget to name your record file
   for the linphone clients.
4. Monitor the worker(s) and watch how the calls are being initialized. 
5. If the linphone call are deleted you can stop the client. The linphone calls 
   ids will be much different than the client made ids so you will now which one is
   the linphone call. 
6. With scp copy out the records and the pcaps from the linphone clients and you can 
   analyze them.

## Resiliency test

1. Setup the cluster as you need. 
2. Start a packet capture for udp.
3. Make one call with the client. 
4. Find out which worker handles the traffic. 
5. Delete that worker pod
6. Check if the other worker started to handle the traffic. 
7. Stop the call and analyze the pcap. 