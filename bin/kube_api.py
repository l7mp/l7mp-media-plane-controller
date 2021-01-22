from kubernetes import client, config
from pprint import pprint

class KubernetesAPIClient():
    ''' To handle every kubernetes API calls. 

    With the constructor you connect to the kubernetes cluster. For 
    that yous should provide the BearerToken.
    '''

    def __init__(self, token, host):
        ''' Constructor to set up connection with Kubernetes cluster.

        Args:
          token: Path to the BearerToken. 
        '''
        
        # Will used when the remote cluster is up!
        # TODO: Find a way to make it work!
        # self.configuration = client.Configuration()
        # # Configure API key authorization: BearerToken
        # with open(token, 'r') as ft:
        #     data = ft.read().replace('\n', '')

        # self.configuration.host = f'http://{host}:8443'

        # self.configuration.api_key_prefix['authorization'] = 'Bearer'
        # self.configuration.api_key['authorization'] = data

        config.load_kube_config()

        self.api = client.CustomObjectsApi()


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
            group="l7mp.io",
            version="v1",
            namespace="default",
            plural=plural,
            body=resource
        )

        print(f'{protocol} {kind} created!')
        
    def create_vsvc(self, participant):
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

        resource = {
            'apiVersion': 'l7mp.io/v1',
            'kind': 'VirtualService',
            'metadata': {
                'name': f'ingress-rtp-vsvc-{str(participant["call_id"])}-{str(participant["tag"])}'
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
                            'port': participant["remote_rtp_port"],
                            'connect': {
                                'address': str(participant["local_ip"]),
                                'port': participant["local_rtp_port"]
                            },
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
                                        'valueStr': str(participant["call_id"])
                                    },
                                    {
                                        'path': '/labels/tag',
                                        'valueStr': str(participant["tag"])
                                    }
                                ],
                                'route': {
                                    'destinationRef':  f'/apis/l7mp.io/v1/namespaces/default/targets/ingress-rtp-target-{str(participant["call_id"])}-{str(participant["tag"])}',
                                    'retry': {
                                        'retry_on': 'always',
                                        'num_retries': 1000,
                                        'timeout': 2000
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

        print(isinstance(resource, dict))

        self.send_custom_obj(resource, 'VirtualService', 'RTP')

        resource['metadata']['name'] = f'ingress-rtcp-vsvc-{str(participant["call_id"])}-{str(participant["tag"])}'
        resource['spec']['listener']['spec']['UDP']['port'] = participant["remote_rtcp_port"]
        resource['spec']['listener']['spec']['UDP']['connect']['port'] = participant["local_rtcp_port"]
        resource['spec']['listener']['rules'][0]['action']['route']['destinationRef'] = f'/apis/l7mp.io/v1/namespaces/default/targets/ingress-rtcp-target-{str(participant["call_id"])}-{str(participant["tag"])}'

        self.send_custom_obj(resource, 'VirtualService', 'RTCP')


    def create_target(self, participant):
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
                'name': f'ingress-rtp-target-{str(participant["call_id"])}-{str(participant["tag"])}'
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

        resource['metadata']['name'] = f'ingress-rtcp-target-{str(participant["call_id"])}-{str(participant["tag"])}'

        self.send_custom_obj(resource, 'Target', 'RTCP')


    def create_rule(self, participant):
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

        resource = {
            'apiVersion': 'l7mp.io/v1',
            'kind': 'Rule',
            'metadata': {
                'name': f'worker-rtcp-rule-{str(participant["call_id"])}-{str(participant["tag"])}'
            },
            'spec': {
                'updateOwners': True,
                'selector': {
                    'matchLabels': {
                        'app': 'l7mp-worker'
                    }
                },
                'position': 0,
                'rulelist': 'worker-rtp-rulelist',
                'rule': {
                    'match': {
                        'op': 'and',
                        'apply': [
                            {
                                'op': 'test',
                                'path': '/JSONSocket/labels/callid',
                                'value': str(participant["call_id"])
                            },
                            {
                                'op': 'test',
                                'path': '/JSONSocket/labels/tag',
                                'value': str(participant["tag"])
                            }
                        ]
                    },
                    'action': {
                        'route': {
                            'destination': {
                                'spec': {
                                    'UDP': {
                                        'port': participant["remote_rtcp_port"],
                                        'bind': {
                                            'address': '127.0.0.1',
                                            'port': participant["local_rtcp_port"]
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
                                'num_retries': 5,
                                'timeout': 200
                            }
                        }
                    }
                }
            }
        }

        self.send_custom_obj(resource, 'Rule', 'RTCP')

        resource['metadata']['name'] = f'worker-rtp-rule-{str(participant["call_id"])}-{str(participant["tag"])}'
        resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['port'] = participant["remote_rtp_port"]
        resource['spec']['rule']['action']['route']['destination']['spec']['UDP']['bind']['port'] = participant["local_rtp_port"]
        resource["spec"]["rule"]["action"]["route"]["ingress"] =  [{'clusterRef': 'ingress-metric-counter'}]
        resource["spec"]["rule"]["action"]["route"]["egress"] =  [{'clusterRef': 'egress-metric-counter'}]

        self.send_custom_obj(resource, 'Rule', 'RTP')
