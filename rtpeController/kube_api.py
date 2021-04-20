from kubernetes import client, config
from pprint import pprint

class KubernetesAPIClient():
    ''' To handle every kubernetes API calls. 

    With the constructor you connect to the kubernetes cluster. For 
    that yous should provide the BearerToken.
    '''

    def __init__(self, in_cluster=False, **kwargs):
        ''' Constructor to set up connection with Kubernetes cluster.

        Args:
          token: Path to the BearerToken. 
        '''
        
        if in_cluster:
            config.load_incluster_config()
        else:
            config.load_kube_config()

        self.api = client.CustomObjectsApi()

        self.call_id = kwargs.get('call_id', None)
        self.tag = kwargs.get('tag', None)
        self.local_ip = kwargs.get('local_ip', None)
        self.local_rtp_port = kwargs.get('local_rtp_port', None)
        self.remote_rtp_port = kwargs.get('remote_rtp_port', None)
        self.local_rtcp_port = kwargs.get('local_rtcp_port', None)
        self.remote_rtcp_port = kwargs.get('remote_rtcp_port', None)
        self.without_jsonsocket = kwargs.get('without_jsonsocket', None)
        self.ws = kwargs.get('ws', None)

        self.create_resources()

    def send_custom_obj(self, resource, kind, protocol):
        # Enter a context with an instance of the API kubernetes.client
        # TODO: With remote cluster
        # with client.ApiClient(self.configuration) as api_client:
        #     # Create an instance of the API class
        #     api_instance = client.CustomObjectsApi(api_client)
        #     group = 'l7mp.io' 
        #     version = 'v1'
        #     body = resource 
        #     pretty = 'true'

        if kind == 'VirtualService':
            plural = 'virtualservices'
        elif kind == 'Target':
            plural = 'targets'
        elif kind == 'Rule':
            plural = 'rules'

        #     try:
        #         api_response = api_instance.create_cluster_custom_object(group, 
        #                     version, plural, body, pretty=pretty)
        #         pprint(api_response)
        #     except client.ApiException as e:
        #         print(f'Cannot create {protocol} {kind}: {e}\n')

        self.api.create_namespaced_custom_object(
            group='l7mp.io',
            version='v1',
            namespace='default',
            plural=plural,
            body=resource
        )

        print(f'{protocol} {kind} created!')
        
    def create_vsvc(self):
        ''' Create a virtual service based on the participants data. 

        Args:
        participant: This is a dictionary which has to contain the 
            following keys: 
            call_id: ID of the call.
            tag: ng message from-tag. 
            local_ip: Sender or receiver local IP.
            local_rtp_port: Sender or Receiver local RTP port.
            remote_rtp_port: RTP Port given by RTPengine.
            local_rtcp_port: Sender or Receiver local RTCP port.
            remote_rtcp_port_ RTCP port given by RTPengine.
        '''

        call_id = ''.join(e for e in self.call_id if e.isalnum()).lower()
        tag = ''.join(e for e in self.tag if e.isalnum()).lower()

        resource = {
            'apiVersion': 'l7mp.io/v1',
            'kind': 'VirtualService',
            'metadata': {
                'name': f'ingress-rtp-vsvc-{call_id}-{tag}'
            },
            'spec': {
                'updateOwners': True,
                'selector': {
                    'matchLabels': {
                        'app': 'l7mp-ingress'
                    }
                },
                'listener': {
                    'spec': {
                        'UDP': {
                            'port': self.remote_rtp_port,
                            # 'connect': {
                            #     'address': str(self.local_ip),
                            #     'port': self.local_rtp_port
                            # },
                            'options': {
                                'mode': 'server'
                            }
                        }
                    },
                    'rules': [
                        {
                            'action': {
                                'rewrite': [
                                    {
                                        'path': '/labels/callid',
                                        'valueStr': str(self.call_id)
                                    },
                                    {
                                        'path': '/labels/tag',
                                        'valueStr': str(self.tag)
                                    }
                                ],
                                'route': {
                                    'destinationRef':  f'/apis/l7mp.io/v1/namespaces/default/targets/ingress-rtp-target',
                                    'retry': {
                                        'retry_on': 'always',
                                        'num_retries': 10,
                                        'timeout': 500
                                    }
                                }
                            }
                        }
                    ],
                    'options': {
                        'track': 600
                    }
                }
            }
        }
        
        self.send_custom_obj(resource, 'VirtualService', 'RTP')

        resource['metadata']['name'] = f'ingress-rtcp-vsvc-{call_id}-{tag}'
        resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port
        # resource['spec']['listener']['spec']['UDP']['connect']['port'] = self.local_rtcp_port
        resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/apis/l7mp.io/v1/namespaces/default/targets/ingress-rtcp-target'

        self.send_custom_obj(resource, 'VirtualService', 'RTCP')

    def create_target(self):
        ''' Create a Target based on the participant data. 

        Args:
        participant: This is a dictionary which has to contain the 
            following keys:
            call_id: ID of the call. 
            tag: ng message from-tag. 
        '''

        resource = {
            'apiVersion': 'l7mp.io/v1',
            'kind': 'Target',
            'metadata': {
                'name': f'ingress-rtp-target'
            },
            'spec': {
                'selector': {
                    'matchLabels': {
                        'app': 'l7mp-ingress'
                    }
                },
                'cluster': {
                    'spec': {
                        'JSONSocket': {
                            'transport': {
                                'UDP': {
                                    'port': 19000
                                }
                            },
                            'header': [
                                {
                                    'path': {
                                        'from': '/labels',
                                        'to': '/labels'
                                    }
                                }
                            ]
                        }
                    },
                    'endpoints': [
                        {
                            'selector': {
                                'matchLabels': {
                                    'app': 'l7mp-worker'
                                }
                            }
                        }
                    ],
                    'loadbalancer': {
                        'policy': 'ConsistentHash',
                        'key': '/labels/callid'
                    }
                }
            }
        }


        self.send_custom_obj(resource, 'Target', 'RTP')

        resource['metadata']['name'] = f'ingress-rtcp-target-{str(self.call_id)}-{str(self.tag)}'
        resource['spec']['cluster']['spec']['JSONSocket']['transport']['UDP']['port'] = 19001

        self.send_custom_obj(resource, 'Target', 'RTCP')

    def create_rule(self):
        ''' Create a Rule based on the participant data. 

        Args:
        participant: This is a dictionary which has to contain the 
            following keys:
            call_id: ID of the call.
            tag: ng message from-tag.
            remote_port: RTP Port given by RTPengine.
            local_port: Sender or Receiver local rtp port.
            local_rtcp_port: Sender or Receiver local rtcp port.
            remote_rtcp_port: RTCP port given by RTPengine.
        '''

        call_id = ''.join(e for e in self.call_id if e.isalnum()).lower()
        tag = ''.join(e for e in self.tag if e.isalnum()).lower()

        resource = {
            'apiVersion': 'l7mp.io/v1',
            'kind': 'Rule',
            'metadata': {
                'name': f'worker-rtcp-rule-{call_id}-{tag}'
            },
            'spec': {
                'updateOwners': True,
                'selector': {
                    'matchLabels': {
                        'app': 'l7mp-worker'
                    }
                },
                'position': 0,
                'rulelist': 'worker-rtcp-rulelist',
                'rule': {
                    'match': {
                        'op': 'and',
                        'apply': [
                            {
                                'op': 'test',
                                'path': '/JSONSocket/labels/callid',
                                'value': str(self.call_id)
                            },
                            {
                                'op': 'test',
                                'path': '/JSONSocket/labels/tag',
                                'value': str(self.tag)
                            }
                        ]
                    },
                    'action': {
                        'route': {
                            'destination': {
                                'name': f'worker-rtcp-cluster-{call_id}-{tag}',
                                'spec': {
                                    'UDP': {
                                        'port': self.remote_rtcp_port,
                                        'bind': {
                                            'address': '127.0.0.1',
                                            'port': self.local_rtcp_port
                                        }
                                    }
                                },
                                'endpoints': [
                                    {
                                        'spec': {
                                            'address': '127.0.0.1'
                                        }
                                    }
                                ]
                            },
                            'retry': {
                                'retry_on': 'always',
                                'num_retries': 10,
                                'timeout': 500
                            }
                        }
                    }
                }
            }
        }

        self.send_custom_obj(resource, 'Rule', 'RTCP')

        resource['metadata']['name'] = f'worker-rtp-rule-{call_id}-{tag}'
        resource['spec']['rulelist'] = 'worker-rtp-rulelist'
        resource['spec']['rule']['action']['route']['destination']['name'] = f'worker-rtp-cluster-{call_id}-{tag}'
        resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = self.remote_rtp_port
        resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = self.local_rtp_port
        resource['spec']['rule']['action']['route']['ingress'] =  [{'clusterRef': 'ingress-metric-counter'}]
        resource['spec']['rule']['action']['route']['egress'] =  [{'clusterRef': 'egress-metric-counter'}]

        self.send_custom_obj(resource, 'Rule', 'RTP')

    def create_without_jsonsocket_vsvc(self):
        resource = {
            'apiVersion': 'l7mp.io/v1',
            'kind': 'VirtualService',
            'metadata': {
                'name': f'rtp-ingress-{self.call_id}-{self.tag}'
            },
            'spec': {
                'selector': {
                    'matchLabels': {
                        'app': 'l7mp-ingress'
                    }
                },
                'listener': {
                    'spec': {
                        'UDP': {
                            'port': self.remote_rtp_port
                        }
                    },
                    'rules': [
                        {
                            'action': {
                                'route': {
                                    'destinationRef': f'/apis/l7mp.io/v1/namespaces/default/targets/rtp-ingress-target-{self.call_id}-{self.tag}',
                                    'retry': {
                                        'retry_on': 'always',
                                        'num_retries': 5,
                                        'timeout': 200
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }

        if self.ws:
            resource['spec']['listener']['rules'][0]['action']['rewrite'] = [
                {
                    'path': "/metadata",
                    'value': {
                        'callid': self.call_id                    }
                }
            ]
            

        self.send_custom_obj(resource, 'VirtualService', 'RTP')

        resource['metadata']['name'] = f'rtcp-ingress-{self.call_id}-{self.tag}'
        resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port
        resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/apis/l7mp.io/v1/namespaces/default/targets/rtcp-ingress-target-{self.call_id}-{self.tag}'

        self.send_custom_obj(resource, 'VirtualService', 'RTCP')

        if self.ws:
            del resource['spec']['listener']['rules'][0]['action']['rewrite']

        resource['spec']['selector']['matchLabels']['app'] = 'l7mp-worker'
        resource['metadata']['name'] = f'rtp-worker-{self.call_id}-{self.tag}'
        resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtp_port
        resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/apis/l7mp.io/v1/namespaces/default/targets/rtp-worker-target-{self.call_id}-{self.tag}'

        self.send_custom_obj(resource, 'VirtualService', 'RTP')

        resource['metadata']['name'] = f'rtcp-worker-{self.call_id}-{self.tag}'
        resource['spec']['listener']['spec']['UDP']['port'] = self.remote_rtcp_port
        resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/apis/l7mp.io/v1/namespaces/default/targets/rtcp-worker-target-{self.call_id}-{self.tag}'

        self.send_custom_obj(resource, 'VirtualService', 'RTCP')

    def create_without_jsonsocket_target(self):
        resource = {
            'apiVersion': 'l7mp.io/v1',
            'kind': 'Target',
            'metadata': {
                'name': f'rtp-ingress-target-{self.call_id}-{self.tag}'
            },
            'spec':{
                'selector': {
                    'matchLabels': {
                        'app': 'l7mp-ingress'
                    }
                },
                'cluster': {
                    'spec': {
                        'UDP': {
                            'port': self.remote_rtp_port
                        }
                    },
                    'endpoints':[
                        {
                            'selector':{
                                'matchLabels': {
                                    'app': 'l7mp-worker'
                                }
                            }
                        }
                    ]
                }
            }
        }

        if self.ws:
            resource['spec']['cluster']['loadbalancer'] = {
                'policy': 'ConsistentHash',
                'key': '/metadata/callid'
            }

        self.send_custom_obj(resource, 'Target', 'RTP')

        resource['metadata']['name'] = f'rtcp-ingress-target-{self.call_id}-{self.tag}'
        resource['spec']['cluster']['spec']['UDP']['port'] = self.remote_rtcp_port

        self.send_custom_obj(resource, 'Target', 'RTCP')

        if self.ws:
            del resource['spec']['cluster']['loadbalancer']

        resource['metadata']['name'] = f'rtp-worker-target-{self.call_id}-{self.tag}'
        resource['spec']['cluster']['spec']['UDP']['port'] = self.remote_rtp_port
        resource['spec']['selector']['matchLabels']['app'] = 'l7mp-worker'
        resource['spec']['cluster']['endpoints'][0] = {'spec': {'address': '127.0.0.1'}}

        self.send_custom_obj(resource, 'Target', 'RTP')

        resource['metadata']['name'] = f'rtcp-worker-target-{self.call_id}-{self.tag}'
        resource['spec']['cluster']['spec']['UDP']['port'] = self.remote_rtcp_port

        self.send_custom_obj(resource, 'Target', 'RTCP')

    def create_resources(self):
        ''' Create all the necessary kubernetes resources.
        '''
        if not self.without_jsonsocket:
            self.create_vsvc()
            # self.create_target()
            self.create_rule()
        else:
            self.create_without_jsonsocket_target()
            self.create_without_jsonsocket_vsvc()

    def delete_resource(self, kind, name):
        ''' Delete one Kubernetes resource.
        '''

        if kind == 'VirtualService':
            plural = 'virtualservices'
        elif kind == 'Target':
            plural = 'targets'
        elif kind == 'Rule':
            plural = 'rules'

        self.api.delete_namespaced_custom_object(
            group='l7mp.io',
            version='v1',
            name=name,
            namespace='default',
            plural=plural,
            body=client.V1DeleteOptions(),
        )

        print(f'{kind} with name: {name} deleted.')

    def delete_resources(self):
        ''' Delete all the kubernetes resources.
        '''

        call_id = ''.join(e for e in self.call_id if e.isalnum()).lower()
        tag = ''.join(e for e in self.tag if e.isalnum()).lower()

        print("Call to delete")
        print(call_id)
        print(tag)

        if not self.without_jsonsocket:
            self.delete_resource('VirtualService', f'ingress-rtp-vsvc-{call_id}-{tag}')
            self.delete_resource('VirtualService', f'ingress-rtcp-vsvc-{call_id}-{tag}')
            # self.delete_resource('Target', f'ingress-rtp-target-{str(self.call_id)}-{str(self.tag)}')
            # self.delete_resource('Target',f'ingress-rtcp-target-{str(self.call_id)}-{str(self.tag)}')
            self.delete_resource('Rule', f'worker-rtcp-rule-{call_id}-{tag}')
            self.delete_resource('Rule', f'worker-rtp-rule-{call_id}-{tag}')
        else:
            self.delete_resource('VirtualService', f'rtp-ingress-{self.call_id}-{self.tag}')
            self.delete_resource('VirtualService', f'rtcp-ingress-{self.call_id}-{self.tag}')
            self.delete_resource('VirtualService', f'rtp-worker-{self.call_id}-{self.tag}')
            self.delete_resource('VirtualService', f'rtcp-worker-{self.call_id}-{self.tag}')
            self.delete_resource('Target', f'rtp-ingress-target-{self.call_id}-{self.tag}')
            self.delete_resource('Target', f'rtcp-ingress-target-{self.call_id}-{self.tag}')
            self.delete_resource('Target', f'rtp-worker-target-{self.call_id}-{self.tag}')
            self.delete_resource('Target', f'rtcp-worker-target-{self.call_id}-{self.tag}')

    def __str__(self):
        return f'''
        call-id: {str(self.call_id)}
        tag: {str(self.tag)}
        local-ip: {str(self.local_ip)}
        local-rtp-port: {str(self.local_rtp_port)}
        local-rtcp-port: {str(self.local_rtcp_port)}
        remote-port: {str(self.remote_rtp_port)}
        remote-rtcp-port: {str(self.remote_rtcp_port)}
        without-jsonsocket: {str(self.without_jsonsocket)}'''