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
- **without_jsonsocket**: define which type of crds have to apply (yes, no)
- **ingress_address**: Kubernetes node IP address

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
    # envoy_address=1.0.0.0
    # envoy_port=22222
    local_address=127.0.0.1
    local_port=2001
    without_jsonsocket=no
    ingress_address=192.168.99.113
    sidecar_type=l7mp
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
...
```