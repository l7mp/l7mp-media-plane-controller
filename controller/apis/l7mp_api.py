import logging
import json
import concurrent.futures
import os
from apis.status import Status
import status_wrapper as statuses
import threading
import time
from kubernetes import client, config, watch

lock = threading.Lock()

def init():
    statuses.init()
    time.sleep(20)
    for filename in os.listdir('proxy_configs'):
        with open(f'proxy_configs/{filename}', 'r') as f:
            logging.info(f'proxy_configs/{filename}')
            statuses.statuses.post(f)

def update():
    config.load_incluster_config()
    w = watch.Watch()
    api = client.CoreV1Api()
    s = statuses.statuses.get_statuses()
    deleted_pod = None
    for event in w.stream(api.list_namespaced_pod, namespace='default', label_selector='app=l7mp-worker'):
        if event['type'] == 'MODIFIED' and event['object'].metadata.deletion_timestamp != None:
            logging.info(f'pod name: {event["object"].metadata.name}, deleted pod name: {deleted_pod}')
            if event['object'].metadata.name != deleted_pod:
                deleted_pod = event['object'].metadata.name
                s.delete_status(event['object'].metadata.name, event['object'].status.pod_ip)
        if event['type'] == 'MODIFIED' and event['object'].metadata.deletion_timestamp == None:
            if event['object'].status.pod_ip:
                time.sleep(2)
                s.add_endpoint(event)
                s.copy(event)
                statuses.statuses.set_statuses(s)

class L7mpAPI():

    def __init__(self, **kwargs):
        self.resource_names = [] # List of tuples (kind, name)

        self.from_data = kwargs.get('from_data', None)
        if self.from_data:
            self.from_data['simple_tag'] = ''.join(e for e in self.from_data["tag"] if e.isalnum()).lower()
        
        self.to_data = kwargs.get('to_data', None)
        if self.to_data:
            self.to_data['simple_tag'] = ''.join(e for e in self.to_data["tag"] if e.isalnum()).lower()
       
        self.call_id = kwargs.get('call_id', None)
        self.simple_call_id = ''.join(e for e in self.call_id if e.isalnum()).lower()

        self.udp_mode = kwargs.get('udp_mode', 'server')

        self._create_resources()

    def _listener_conf(self, **kwargs):
        if self.udp_mode == 'singleton':
            spec = {
                "protocol": "UDP",
                "port": kwargs.get('port'),
                "connect": {
                    "address": kwargs.get('local_ip'),
                    "port": kwargs.get('local_port')
                },
                "option": {"mode": 'singleton'}
            }
        else:
            spec = {
                "protocol": "UDP",
                "port": kwargs.get('port'),
                "option": {"mode": 'server'}
            }
        return json.dumps({
            "label": "app=l7mp-ingress",
            "resource": {
                "res_name": f"{kwargs.get('res_name')}-listener",
                "path": "listeners",
                "config": {
                    "listener": {
                        "name": f"{kwargs.get('res_name')}-listener",
                        "spec": spec,
                        "rules": [{
                            "name": f"{kwargs.get('res_name')}-rule",
                            "action": {
                                "route": {
                                    "name": f"{kwargs.get('res_name')}-route",
                                    "destination": kwargs.get('destination'),
                                    "retry": { "retry_on": "always", "num_retries": 1000, "timeout": 250 }
                                },
                                "rewrite": [
                                    {"path": "/labels/callid", "value": self.call_id},
                                    {"path": "/labels/tag", "value": kwargs.get('tag')}
                                ]
                            }
                        }]
                    }
                }
            }
        })

    def _rule_conf(self, **kwargs):
        if self.udp_mode == "singleton":
            spec = {
                "protocol": "UDP",
                "port": kwargs.get('port'),
                "connect": {
                    "address": kwargs.get('local_ip'),
                    "port": kwargs.get('local_port')
                },
                "option": {"mode": 'singleton'}
            }
        return json.dumps({
            "label": "app=l7mp-worker",
            "resource": {
                "res_name": f"{kwargs.get('res_name')}-rule",
                "path": f"rulelists/{kwargs.get('rule_list')}/rules/0",
                "config": {
                    "rule": {
                        "name": f"{kwargs.get('res_name')}-rule",
                        "match": {
                            "op": "and",
                            "apply": [
                                {
                                    "op": "test",
                                    "path": "/JSONSocket/labels/callid",
                                    "value": self.call_id
                                },
                                {
                                    "op": "test",
                                    "path": "/JSONSocket/labels/tag",
                                    "value": kwargs.get('tag')
                                }
                            ]
                        },
                        "action": {
                            "route": {
                                "name": f"{kwargs.get('res_name')}-route",
                                "destination": {
                                    "name": f"{kwargs.get('res_name')}-cluster",
                                    "spec": {
                                        "protocol": "UDP",
                                        "port": kwargs.get('port')
                                    },
                                    "endpoints": [{
                                        "name": f"{kwargs.get('res_name')}-endpoint",
                                        "spec": {"address": "127.0.0.1"}
                                    }]
                                },
                                "retry": {
                                    "retry_on": "always",
                                    "num_retries": 1000,
                                    "timeout": 250
                                }
                            }
                        }
                    }
                }
            }
        })

    def _create_resources(self):
        global statuses
        resources = self._create_rule() + self._create_listener()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            for r in resources:
                executor.submit(statuses.statuses.post(r[0]))

    def delete_resources(self):
        global statuses
        for r in self.resource_names:
            statuses.statuses.delete(r[1], r[0])
            logging.info(f'{r[1]} deleted.')
    
    def _create_listener(self):
        ret = []
        if self.from_data:
            ret.append((self._listener_conf(
                res_name=f'ingress-rtp-{self.simple_call_id}-{self.from_data["simple_tag"]}',
                port=self.from_data["remote_rtp_port"], destination='ingress-rtp-target', tag=self.from_data['tag'], local_ip=self.from_data['local_ip'], local_port=self.from_data['local_rtp_port']
            ), 'app=l7mp-ingress'))
            self.resource_names.append(('app=l7mp-ingress', f'ingress-rtp-{self.simple_call_id}-{self.from_data["simple_tag"]}-listener'))

            ret.append((self._listener_conf(
                res_name=f'ingress-rtcp-{self.simple_call_id}-{self.from_data["simple_tag"]}',
                port=self.from_data["remote_rtcp_port"], destination='ingress-rtcp-target', tag=self.from_data['tag'], local_ip=self.from_data['local_ip'], local_port=self.from_data['local_rtcp_port']
            ), 'app=l7mp-ingress'))
            self.resource_names.append(('app=l7mp-ingress', f'ingress-rtcp-{self.simple_call_id}-{self.from_data["simple_tag"]}-listener'))

        if self.to_data:
            ret.append((self._listener_conf(
                res_name=f'ingress-rtp-{self.simple_call_id}-{self.to_data["simple_tag"]}',
                port=self.to_data["remote_rtp_port"], destination='ingress-rtp-target', tag=self.to_data['tag'], local_ip=self.to_data['local_ip'], local_port=self.to_data['local_rtp_port']
            ), 'app=l7mp-ingress'))
            self.resource_names.append(('app=l7mp-ingress', f'ingress-rtp-{self.simple_call_id}-{self.to_data["simple_tag"]}-listener'))

            ret.append((self._listener_conf(
                res_name=f'ingress-rtcp-{self.simple_call_id}-{self.to_data["simple_tag"]}',
                port=self.to_data["remote_rtcp_port"], destination='ingress-rtcp-target', tag=self.to_data['tag'], local_ip=self.to_data['local_ip'], local_port=self.to_data['local_rtcp_port']
            ), 'app=l7mp-ingress'))
            self.resource_names.append(('app=l7mp-ingress', f'ingress-rtcp-{self.simple_call_id}-{self.to_data["simple_tag"]}-listener'))
        return ret

    def _create_rule(self):
        ret = []
        if self.from_data:
            ret.append((self._rule_conf(
                res_name=f'worker-rtp-{self.simple_call_id}-{self.from_data["simple_tag"]}',
                rule_list='worker-rtp-rulelist', tag=self.from_data["tag"], 
                port=self.from_data["remote_rtp_port"]
            ), 'app=l7mp-worker'))
            self.resource_names.append(('app=l7mp-worker', f'worker-rtp-{self.simple_call_id}-{self.from_data["simple_tag"]}-rule'))

            ret.append((self._rule_conf(
                res_name=f'worker-rtcp-{self.simple_call_id}-{self.from_data["simple_tag"]}',
                rule_list='worker-rtcp-rulelist', tag=self.from_data["tag"], 
                port=self.from_data["remote_rtcp_port"]
            ), 'app=l7mp-worker'))
            self.resource_names.append(('app=l7mp-worker', f'worker-rtcp-{self.simple_call_id}-{self.from_data["simple_tag"]}-rule'))
        if self.to_data:
            ret.append((self._rule_conf(
                res_name=f'worker-rtp-{self.simple_call_id}-{self.to_data["simple_tag"]}',
                rule_list='worker-rtp-rulelist', tag=self.to_data["tag"], 
                port=self.to_data["remote_rtp_port"]
            ), 'app=l7mp-worker'))
            self.resource_names.append(('app=l7mp-worker', f'worker-rtp-{self.simple_call_id}-{self.to_data["simple_tag"]}-rule'))

            ret.append((self._rule_conf(
                res_name=f'worker-rtcp-{self.simple_call_id}-{self.to_data["simple_tag"]}',
                rule_list='worker-rtcp-rulelist', tag=self.to_data["tag"], 
                port=self.to_data["remote_rtcp_port"]
            ), 'app=l7mp-worker'))
            self.resource_names.append(('app=l7mp-worker', f'worker-rtcp-{self.simple_call_id}-{self.to_data["simple_tag"]}-rule'))
        return ret

    def __str__(self):
        return (
            f'call-id: {str(self.call_id)}\n'
            f'tag: {str(self.tag)}\n'
            f'local-ip: {str(self.local_ip)}\n'
            f'local-rtp-port: {str(self.local_rtp_port)}\n'
            f'local-rtcp-port: {str(self.local_rtcp_port)}\n'
            f'remote-port: {str(self.remote_rtp_port)}\n'
            f'remote-rtcp-port: {str(self.remote_rtcp_port)}\n'
        )
        