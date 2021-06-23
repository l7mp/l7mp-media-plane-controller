import re
from kubernetes import client, config
import logging
import yaml

class Client():

    def __init__(self, **kwargs):
        config.load_incluster_config()
        logging.debug('Connected to Kubernetes.')
        
        self.api = client.CustomObjectsApi()
        logging.debug('CustomObjectsAPI is initialized.')

        self.plurals = {
            'VirtualService': 'virtualservices',
            'Target': 'targets',
            'Rule': 'rules'
        }

        self.resource_names = [] # List of tuples (kind, name)

        self.call_id = kwargs.get('call_id', None)
        self.tag = kwargs.get('tag', None)

        self.simple_call_id = ''.join(e for e in self.call_id if e.isalnum()).lower()
        self.simple_tag = ''.join(e for e in self.tag if e.isalnum()).lower()

        self.local_ip = kwargs.get('local_ip', None)
        self.local_rtp_port = kwargs.get('local_rtp_port', None)
        self.remote_rtp_port = kwargs.get('remote_rtp_port', None)
        self.local_rtcp_port = kwargs.get('local_rtcp_port', None)
        self.remote_rtcp_port = kwargs.get('remote_rtcp_port', None)
        self.without_jsonsocket = kwargs.get('without_jsonsocket', None)
        self.ws = kwargs.get('ws', None)
        self.envoy = kwargs.get('envoy', 'no')
        self.update_owners = kwargs.get('update_owners', 'no')

        self.create_resources()

    def create_object(self, resource, kind):
        self.api.create_namespaced_custom_object(
            group='l7mp.io',
            version='v1',
            namespace='default',
            plural=self.plurals[kind],
            body=resource
        )
        logging.info(f"{resource['metadata']['name']} created!")

    def create_resources(self):
        if self.envoy == 'yes':
            self.create_envoy_vsvc()
        elif self.without_jsonsocket == 'no':
            self.create_vsvc()
            self.create_rule()
        else:
            self.create_without_jsonsocket_target()
            self.create_without_jsonsocket_vsvc()

    def delete_resource(self, resource):
        self.api.delete_namespaced_custom_object(
            group='l7mp.io',
            version='v1',
            name=resource[1],
            namespace='default',
            plural=self.plurals[resource[0]],
            body=client.V1DeleteOptions(),
        )
        logging.info(f'{resource[1]} deleted.')

    def delete_resources(self):
        for r in self.resource_names:
            self.delete_resource(r)

    def create_vsvc(self):
        with open('crds/simple_vsvc.yaml', 'r') as f:
            resource = yaml.load(f)
            if self.update_owners == 'no':
                del resource['metadata']['ownerReferences']
            resource['metadata']['name'] = f'ingress-rtp-vsvc-{self.simple_call_id}-{self.simple_tag}'
            # resource['metadata']['ownerReferences'][0]['uid'] = f'ingress-rtp-vsvc-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtp_port
            resource['spec']['listener']['rules'][0]['action']['rewrite'][0]['valueStr'] = self.call_id
            resource['spec']['listener']['rules'][0]['action']['rewrite'][1]['valueStr'] = self.tag
            resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/ingress-rtp-target'
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))
            
            resource['metadata']['name'] = f'ingress-rtcp-vsvc-{self.simple_call_id}-{self.simple_tag}'
            # resource['metadata']['ownerReferences'][0]['name'] = f'ingress-rtcp-vsvc-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/ingress-rtcp-target'
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

    def create_rule(self):
        with open('crds/simple_rule.yaml', 'r') as f:
            resource = yaml.load(f)
            if self.update_owners == 'no':
                del resource['metadata']['ownerReferences']
            resource['metadata']['name'] = f'worker-rtp-rule-{self.simple_call_id}-{self.simple_tag}'
            # resource['metadata']['ownerReferences'][0]['name'] = f'worker-rtp-rule-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['rulelist'] = 'worker-rtp-rulelist'
            resource['spec']['rule']['match']['apply'][0]['value'] = self.call_id
            resource['spec']['rule']['match']['apply'][1]['value'] = self.tag
            resource['spec']['rule']['action']['route']['destination']['name'] = f'worker-rtp-cluster-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = self.remote_rtp_port
            resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = self.local_rtp_port
            self.create_object(resource, 'Rule')
            self.resource_names.append(('Rule', resource['metadata']['name']))

            resource['metadata']['name'] = f'worker-rtcp-rule-{self.simple_call_id}-{self.simple_tag}'
            # resource['metadata']['ownerReferences'][0]['name'] = f'worker-rtcp-rule-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['rulelist'] = 'worker-rtcp-rulelist'
            resource['spec']['rule']['action']['route']['destination']['name'] = f'worker-rtcp-cluster-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = self.remote_rtcp_port
            resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = self.local_rtcp_port
            self.create_object(resource, 'Rule')
            self.resource_names.append(('Rule', resource['metadata']['name']))

    def create_without_jsonsocket_vsvc(self):
        with open('crds/without_js_vsvc.yaml', 'r') as f:
            resource = yaml.load(f)
            resource['metadata']['name'] = f'rtp-ingress-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/rtp-ingress-target-{self.simple_call_id}-{self.simple_tag}'
            if self.ws:
                resource['spec']['listener']['rules'][0]['action']['rewrite'] = [
                    {
                        'path': "/metadata",
                        'value': {
                            'callid': self.call_id
                            }
                    }
                ]
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

            resource['metadata']['name'] = f'rtcp-ingress-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/rtcp-ingress-target-{self.simple_call_id}-{self.simple_tag}'
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

            if self.ws:
                del resource['spec']['listener']['rules'][0]['action']['rewrite']

            resource['spec']['selector']['matchLabels']['app'] = 'l7mp-worker'
            resource['metadata']['name'] = f'rtp-worker-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/rtp-worker-target-{self.simple_call_id}-{self.simple_tag}'
            self.create_object(resource, 'VirtualService')

            resource['metadata']['name'] = f'rtcp-worker-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/rtcp-worker-target-{self.simple_call_id}-{self.simple_tag}'
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

    def create_without_jsonsocket_target(self):
        with open('crds/without_js_target.yaml', 'r') as f:
            resource = yaml.load(f)
            resource['metadata']['name'] = f'rtp-ingress-target-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['cluster']['spec']['UDP']['port'] = self.remote_rtp_port
            if self.ws:
                resource['spec']['cluster']['loadbalancer'] = {
                    'policy': 'ConsistentHash',
                    'key': '/metadata/callid'
                }
            self.create_object(resource, 'Target')
            self.resource_names.append(('Target', resource['metadata']['name']))

            resource['metadata']['name'] = f'rtcp-ingress-target-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['cluster']['spec']['UDP']['port'] = self.remote_rtcp_port
            self.create_object(resource, 'Target')
            self.resource_names.append(('Target', resource['metadata']['name']))

            if self.ws:
                del resource['spec']['cluster']['loadbalancer']

            resource['metadata']['name'] = f'rtp-worker-target-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['cluster']['spec']['UDP']['port'] = self.remote_rtp_port
            resource['spec']['selector']['matchLabels']['app'] = 'l7mp-worker'
            resource['spec']['cluster']['endpoints'][0] = {'spec': {'address': '127.0.0.1'}}
            self.create_object(resource, 'Target')
            self.resource_names.append(('Target', resource['metadata']['name']))

            resource['metadata']['name'] = f'rtcp-worker-target-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['cluster']['spec']['UDP']['port'] = self.remote_rtcp_port
            self.create_object(resource, 'Target')
            self.resource_names.append(('Target', resource['metadata']['name']))

    def create_envoy_vsvc(self):
        with open('crds/envoy_operator/vsvc.yaml', 'r') as f:
            resource = yaml.load(f)
            resource['metadata']['name'] = f'ingress-rtp-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['selector']['matchLabels']['app'] = 'envoy-ingress'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.remote_rtp_port + 20000
            resource['spec']['listener']['rules'][0]['action']['route']['destination']['endpoints'] = [{'selector': {'matchLabels': {'app': 'worker'}}}]
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

            resource['metadata']['name'] = f'ingress-rtcp-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['selector']['matchLabels']['app'] = 'envoy-ingress'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.remote_rtcp_port + 20000
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

            resource['metadata']['name'] = f'worker-rtp-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['selector']['matchLabels']['app'] = 'worker'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtp_port + 20000
            resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.remote_rtp_port
            resource['spec']['listener']['rules'][0]['action']['route']['destination']['endpoints'] = [{'spec': {'address': '127.0.0.1'}}]
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

            resource['metadata']['name'] = f'worker-rtcp-{self.simple_call_id}-{self.simple_tag}'
            resource['spec']['selector']['matchLabels']['app'] = 'worker'
            resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port + 20000
            resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.remote_rtcp_port
            self.create_object(resource, 'VirtualService')
            self.resource_names.append(('VirtualService', resource['metadata']['name']))

    def __str__(self):
        return (
            f'call-id: {str(self.call_id)}\n'
            f'tag: {str(self.tag)}\n'
            f'local-ip: {str(self.local_ip)}\n'
            f'local-rtp-port: {str(self.local_rtp_port)}\n'
            f'local-rtcp-port: {str(self.local_rtcp_port)}\n'
            f'remote-port: {str(self.remote_rtp_port)}\n'
            f'remote-rtcp-port: {str(self.remote_rtcp_port)}\n'
            f'without-jsonsocket: {str(self.without_jsonsocket)}\n'
        )
        
    