from urllib.parse import non_hierarchical
from kubernetes import client, config
import logging
from kubernetes.client.exceptions import ApiException
from six import with_metaclass
import yaml
import time
import requests
import concurrent.futures
import copy

class Client():

    def __init__(self, **kwargs):
        config.load_incluster_config()
        logging.debug('Connected to Kubernetes.')
        
        self.api = client.CustomObjectsApi()
        self.l7mp_api = client.CoreV1Api()
        logging.debug('CustomObjectsAPI is initialized.')

        self.plurals = {
            'VirtualService': 'virtualservices',
            'Target': 'targets',
            'Rule': 'rules'
        }

        self.resource_names = [] # List of tuples (kind, name)

        self.from_data = kwargs.get('from_data', None)
        if self.from_data:
            self.from_data['simple_tag'] = ''.join(e for e in self.from_data["tag"] if e.isalnum()).lower()
        
        self.to_data = kwargs.get('to_data', None)
        if self.to_data:
            self.to_data['simple_tag'] = ''.join(e for e in self.to_data["tag"] if e.isalnum()).lower()
       
        logging.info(self.to_data)

        self.call_id = kwargs.get('call_id', None)
        self.simple_call_id = ''.join(e for e in self.call_id if e.isalnum()).lower()

        self.without_jsonsocket = kwargs.get('without_jsonsocket', None)
        self.ws = kwargs.get('ws', None)
        self.envoy = kwargs.get('envoy', 'no')
        self.update_owners = kwargs.get('update_owners', 'no')
        self.udp_mode = kwargs.get('udp_mode', 'server')

        self.create_resources()

    def get_l7mp_config(self, url):
        # The url should contain the port number url:port
        response = requests.get(url)
        if response.status_code != 200:
            logging.warning(f"During {url} fetch got this code {response.status_code}. Retry")
            return response.status_code
        return 200

    def create_object(self, resource, kind):
        api = client.CustomObjectsApi()
        api.create_namespaced_custom_object(
            group='l7mp.io',
            version='v1',
            namespace='default',
            plural=self.plurals[kind],
            body=resource
        )
        # logging.info("After")
        # if self.envoy == 'no':
        #     logging.info(f"{resource['metadata']['name']} created!")
        #     label = resource['spec']['selector']['matchLabels']['app']

        #     items = self.l7mp_api.list_namespaced_pod(namespace='default', label_selector=f'app={label}')
        #     logging.info("get pods")
        #     items_dict = items.to_dict()

        #     route = None 
        #     if self.plurals[kind] == 'virtualservices':
        #         name = f'/l7mp.io/v1/VirtualService/default/{resource["metadata"]["name"]}'.replace("/", "%2F")
        #         route = f'listeners/{name}'
        #     elif self.plurals[kind] == 'rules':
        #         name = f'/l7mp.io/v1/Rule/default/{resource["metadata"]["name"]}'.replace("/", "%2F")
        #         route = f'rules/{name}'
    
        #     for i in items_dict['items']:
        #         url = f"http://{i['status']['pod_ip']}:1234/api/v1/{route}"
        #         while True:
        #             time.sleep(0.25)
        #             response = self.get_l7mp_config(url)
        #             if response == 200:
        #                 break;
        # else:
        while(True):
            time.sleep(0.1)
            try:
                obj = api.get_namespaced_custom_object(
                    group='l7mp.io',
                    version='v1',
                    namespace='default',
                    plural=self.plurals[kind],
                    name=resource['metadata']['name']
                )
            except ApiException as e: 
                logging.error("Exception when calling CustomObjectsApi->get_cluster_custom_object: %s" % e)
            if 'annotations' in obj['metadata']:
                break
        logging.info(f"{resource['metadata']['name']} created!")

    def threaded_create_objects(self, resources): # args=[(resource, kind), (resource, kind)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for res in resources:
                executor.submit(lambda p: self.create_object(*p), res)

    def create_resources(self):
        if self.envoy == 'yes':
            self.threaded_create_objects(self.create_envoy_vsvc())
        elif self.without_jsonsocket == 'no':
            self.threaded_create_objects(self.create_rule() + self.create_vsvc())
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
            ret = []
            resource = yaml.load(f, Loader=yaml.FullLoader)
            if self.update_owners == 'no':
                del resource['metadata']['ownerReferences']
            
            if self.from_data:
                resource['metadata']['name'] = f'ingress-rtp-vsvc-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['listener']['spec']['UDP']['port'] = self.from_data["remote_rtp_port"]
                if self.udp_mode == 'singleton':
                    resource['spec']['listener']['spec']['UDP']['connect'] = {'address': self.from_data["local_ip"], 'port': self.from_data["local_rtp_port"]}
                    resource['spec']['listener']['spec']['UDP']['options']['mode'] = self.udp_mode
                resource['spec']['listener']['rules'][0]['action']['rewrite'][0]['valueStr'] = self.call_id
                resource['spec']['listener']['rules'][0]['action']['rewrite'][1]['valueStr'] = self.from_data["tag"]
                resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/ingress-rtp-target'
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                # self.create_object(resource, 'VirtualService')
                self.resource_names.append(('VirtualService', resource['metadata']['name']))
                
                resource['metadata']['name'] = f'ingress-rtcp-vsvc-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                if self.udp_mode == 'singleton':
                    resource['spec']['listener']['spec']['UDP']['connect'] = {'address': self.from_data["local_ip"], 'port': self.from_data["local_rtcp_port"]}
                    resource['spec']['listener']['spec']['UDP']['options']['mode'] = self.udp_mode
                resource['spec']['listener']['spec']['UDP']['port'] = self.from_data["remote_rtcp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/ingress-rtcp-target'
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                # self.create_object(resource, 'VirtualService')
                self.resource_names.append(('VirtualService', resource['metadata']['name']))

            
            if self.to_data:
                resource['metadata']['name'] = f'ingress-rtp-vsvc-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['listener']['spec']['UDP']['port'] = self.to_data["remote_rtp_port"]
                if self.udp_mode == 'singleton':
                    resource['spec']['listener']['spec']['UDP']['connect'] = {'address': self.to_data["local_ip"], 'port': self.to_data["local_rtp_port"]}
                    resource['spec']['listener']['spec']['UDP']['options']['mode'] = self.udp_mode
                resource['spec']['listener']['rules'][0]['action']['rewrite'][0]['valueStr'] = self.call_id
                resource['spec']['listener']['rules'][0]['action']['rewrite'][1]['valueStr'] = self.to_data["tag"]
                resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/ingress-rtp-target'
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                # self.create_object(resource, 'VirtualService')
                self.resource_names.append(('VirtualService', resource['metadata']['name']))
                
                resource['metadata']['name'] = f'ingress-rtcp-vsvc-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                if self.udp_mode == 'singleton':
                    resource['spec']['listener']['spec']['UDP']['connect'] = {'address': self.to_data["local_ip"], 'port': self.to_data["local_rtcp_port"]}
                    resource['spec']['listener']['spec']['UDP']['options']['mode'] = self.udp_mode
                resource['spec']['listener']['spec']['UDP']['port'] = self.to_data["remote_rtcp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/l7mp.io/v1/Target/default/ingress-rtcp-target'
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                # self.create_object(resource, 'VirtualService')
                self.resource_names.append(('VirtualService', resource['metadata']['name']))
            return ret

    def create_rule(self):
        with open('crds/simple_rule.yaml', 'r') as f:
            ret = []
            resource = yaml.load(f, Loader=yaml.FullLoader)
            if self.update_owners == 'no':
                del resource['metadata']['ownerReferences']

            if self.from_data:
                resource['metadata']['name'] = f'worker-rtp-rule-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['rulelist'] = 'worker-rtp-rulelist'
                resource['spec']['rule']['match']['apply'][0]['value'] = self.call_id
                resource['spec']['rule']['match']['apply'][1]['value'] = self.from_data["tag"]
                resource['spec']['rule']['action']['route']['destination']['name'] = f'worker-rtp-cluster-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = self.from_data["remote_rtp_port"]
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = self.from_data["local_rtp_port"]
                ret.append((copy.deepcopy(resource), 'Rule'))
                # self.create_object(resource, 'Rule')
                self.resource_names.append(('Rule', resource['metadata']['name']))

                resource['metadata']['name'] = f'worker-rtcp-rule-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['rulelist'] = 'worker-rtcp-rulelist'
                resource['spec']['rule']['action']['route']['destination']['name'] = f'worker-rtcp-cluster-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = self.from_data["remote_rtcp_port"]
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = self.from_data["local_rtcp_port"]
                ret.append((copy.deepcopy(resource), 'Rule'))
                # self.create_object(resource, 'Rule')
                self.resource_names.append(('Rule', resource['metadata']['name']))


            if self.to_data:
                resource['metadata']['name'] = f'worker-rtp-rule-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['rulelist'] = 'worker-rtp-rulelist'
                resource['spec']['rule']['match']['apply'][0]['value'] = self.call_id
                resource['spec']['rule']['match']['apply'][1]['value'] = self.to_data["tag"]
                resource['spec']['rule']['action']['route']['destination']['name'] = f'worker-rtp-cluster-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = self.to_data["remote_rtp_port"]
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = self.to_data["local_rtp_port"]
                ret.append((copy.deepcopy(resource), 'Rule'))
                # self.create_object(resource, 'Rule')
                self.resource_names.append(('Rule', resource['metadata']['name']))

                resource['metadata']['name'] = f'worker-rtcp-rule-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['rulelist'] = 'worker-rtcp-rulelist'
                resource['spec']['rule']['action']['route']['destination']['name'] = f'worker-rtcp-cluster-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = self.to_data["remote_rtcp_port"]
                resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = self.to_data["local_rtcp_port"]
                ret.append((copy.deepcopy(resource), 'Rule'))
                # self.create_object(resource, 'Rule')
                self.resource_names.append(('Rule', resource['metadata']['name']))
            return ret

    def create_without_jsonsocket_vsvc(self):
        with open('crds/without_js_vsvc.yaml', 'r') as f:
            resource = yaml.load(f, Loader=yaml.FullLoader)
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
            resource = yaml.load(f, Loader=yaml.FullLoader)
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
            ret = []
            resource = yaml.load(f, Loader=yaml.FullLoader)
            if self.from_data:
                resource['metadata']['name'] = f'ingress-rtp-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'envoy-ingress'
                resource['spec']['listener']['spec']['UDP']['port'] = self.from_data["remote_rtp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.from_data["remote_rtp_port"] + 20000
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['endpoints'] = [{'selector': {'matchLabels': {'app': 'worker'}}}]
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                self.resource_names.append(('VirtualService', resource['metadata']['name']))

                resource['metadata']['name'] = f'ingress-rtcp-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'envoy-ingress'
                resource['spec']['listener']['spec']['UDP']['port'] = self.from_data["remote_rtcp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.from_data["remote_rtcp_port"] + 20000
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                self.resource_names.append(('VirtualService', resource['metadata']['name']))

                resource['metadata']['name'] = f'worker-rtp-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'worker'
                resource['spec']['listener']['spec']['UDP']['port'] = self.from_data["remote_rtp_port"] + 20000
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.from_data["remote_rtp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['endpoints'] = [{'spec': {'address': '127.0.0.1'}}]
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                self.resource_names.append(('VirtualService', resource['metadata']['name']))

                resource['metadata']['name'] = f'worker-rtcp-{self.simple_call_id}-{self.from_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'worker'
                resource['spec']['listener']['spec']['UDP']['port'] = self.from_data["remote_rtcp_port"] + 20000
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.from_data["remote_rtcp_port"]
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                self.resource_names.append(('VirtualService', resource['metadata']['name']))
            
            if self.to_data:
                resource['metadata']['name'] = f'ingress-rtp-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'envoy-ingress'
                resource['spec']['listener']['spec']['UDP']['port'] = self.to_data["remote_rtp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.to_data["remote_rtp_port"] + 20000
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['endpoints'] = [{'selector': {'matchLabels': {'app': 'worker'}}}]
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                self.resource_names.append(('VirtualService', resource['metadata']['name']))

                resource['metadata']['name'] = f'ingress-rtcp-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'envoy-ingress'
                resource['spec']['listener']['spec']['UDP']['port'] = self.to_data["remote_rtcp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.to_data["remote_rtcp_port"] + 20000
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                self.resource_names.append(('VirtualService', resource['metadata']['name']))

                resource['metadata']['name'] = f'worker-rtp-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'worker'
                resource['spec']['listener']['spec']['UDP']['port'] = self.to_data["remote_rtp_port"] + 20000
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.to_data["remote_rtp_port"]
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['endpoints'] = [{'spec': {'address': '127.0.0.1'}}]
                ret.append((copy.deepcopy(resource), 'VirtualService'))
                self.resource_names.append(('VirtualService', resource['metadata']['name']))

                resource['metadata']['name'] = f'worker-rtcp-{self.simple_call_id}-{self.to_data["simple_tag"]}'
                resource['spec']['selector']['matchLabels']['app'] = 'worker'
                resource['spec']['listener']['spec']['UDP']['port'] = self.to_data["remote_rtcp_port"] + 20000
                resource['spec']['listener']['rules'][0]['action']['route']['destination']['spec']['UDP']['port'] = self.to_data["remote_rtcp_port"]
                ret.append((copy.deepcopy(resource), 'VirtualService'))
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
        
    