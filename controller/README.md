# Controller

## Configuration

- **protocol**: used protocol to send ng commands (udp, tcp, ws)
- **rtpe_address**: address of rtpengine could be IP and domain
- **rtpe_port**: port of rtpengine
- **envoy_address**: address of envoy management sever, could be IP and domain
- **envoy_port**: port of envoy
- **local_address**: address used to send ng commands, only IP
- **local_port**: port used to send ng commands
- **sidecar_type**: type of used sidecars (l7mp, envoy)
- **envoy_operator**: If you want to use with envoy proxies (yes, no)
- **update_owners**: If you want to use ownerReferences (yes, no)
- **udp_mode**: You can set it to singleton or server mode.

## Kubernetes resources

### configmap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: controller-config
data:
  config.conf: |
    [controller]
    protocol=ws
    rtpe_address=127.0.0.1
    rtpe_port=22221
    envoy_address=1.0.0.0
    envoy_port=22222
    local_address=127.0.0.1
    local_port=2001
    sidecar_type=l7mp
    envoy_operator=no
    update_owners=no
```

### container

```yaml
...
spec:
  volumes:
  - name: controller-volume
      configMap:
      name: controller-config
  containers:
    - name: rtpe-controller
      image: vidarhun/rtpe-controller
      imagePullPolicy: Always
      volumeMounts:
        - name: controller-volume
          mountPath: /app/config
      command: ["python"]
      args: ["controller.py", "-c", "config/config.conf", "-l", "debug"]
      # OR 
      args: ["new_controller.py", "-c", "config/config.conf", "-l", "debug"]
...
```

## Usage

In the following you can read about how to set up a call with L7mp service-mesh. 
First of all you have to compile your own L7mp proxy image because the official image
does not handle right the websocket packets.

```
eval $(minikube docker-env)
# Building L7mp proxy
git clone https://github.com/l7mp/l7mp.git
cd l7mp
git checkout ws-subprotocol
docker build -t l7mp/l7mp:0.5.7 -t l7mp/l7mp:latest .
# Building operator
eval $(minikube docker-env -u)
git checkout selflink
./python-client/generate
eval $(minikube docker-env)
./k8s-operator/build --no-cache
# Install the service-mesh
helm repo add l7mp https://l7mp.io/charts
helm repo update
helm install --set l7mpProxyImage.pullPolicy=Never l7mp/l7mp-ingress --set l7mp-operator.image.pullPolicy=Never --generate-name
```

Now you have a fully functional L7mp service mesh. 

To apply resources in `kubernetes/l7mp/udp` your have to build a the your own rtpe-controller image

```
cd controller
docker build . -t rtpe-controller
```

Before your want to apply the `kubernetes/l7mp/udp` library you have to edit resources in 
`misc.yaml`. This resource is controller-config ConfigMap. Your have to change the 
`ingress_address` field value to your minikube ip.