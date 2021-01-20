def create_vsvc(api, participant, rtcp = False):
    ''' Create a virtual service based on the participants data. 

    Args:
      participant: This is a dictionary which has to contain the 
        following keys: 
          call_id: ID of the call.
          tag: ng message from-tag. 
          local_ip: Sender or receiver local IP.
          local_port: Sender or receiver local port.
          remote_port: Port given by RTPengine. 
      rtcp: When it is True will create RTCP objects. 
    '''

    if rtcp:
        name = f'ingress-rtcp-vsvc-{str(participant["call_id"])}-{str(participant["tag"])}'
        destination_ref = f'/apis/l7mp.io/v1/namespaces/default/targets/ingress-rtcp-target-{str(participant["call_id"])}-{str(participant["tag"])}'
    else:
        name = f'ingress-rtp-vsvc-{str(participant["call_id"])}-{str(participant["tag"])}'
        destination_ref = f'/apis/l7mp.io/v1/namespaces/default/targets/ingress-rtp-target-{str(participant["call_id"])}-{str(participant["tag"])}'

    resource = {
        'apiVersion': 'l7mp.io/v1',
        'kind': 'VirtualService',
        'metadata': {
            'name': name
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
                        'port': {str(participant["remote_port"])},
                        'connect': {
                            'address': {str(participant["local_ip"])},
                            'port': {str(participant["local_port"])}
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
                                    'valueStr': {str(participant["call_id"])}
                                },
                                {
                                    'path': '/labels/tag',
                                    'valueStr': {str(participant["tag"])}
                                }
                            ],
                            'route': {
                                'destinationRef': destination_ref,
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

    api.create_namespaced_custom_object(
        group="l7mp.io",
        version="v1",
        namespace="default",
        plural="virtualservices",
        body=resource
    )

    print("VirtualService created!")


def create_target(api, participant, rtcp = False):
    ''' Create a Target based on the participant data. 

    Args:
      participant: This is a dictionary which has to contain the 
        following keys:
          call_id: ID of the call. 
          tag: ng message from-tag. 
      rtcp: When it is True will create RTCP objects.
    '''

    if rtcp:
        name = f'ingress-rtcp-target-{str(participant["callid"])}-{str(participant["tag"])}'
    else:
        name = f'ingress-rtp-target-{str(participant["callid"])}-{str(participant["tag"])}'

    resource = {
        'apiVersion': 'l7mp.io/v1',
        'kind': 'Target',
        'metadata': {
            'name': name
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

    api.create_namespaced_custom_object(
        group="l7mp.io",
        version="v1",
        namespace="default",
        plural="targets",
        body=resource
    )

    print("Target created!")


def create_rule(api, participant, rtcp = False):
    ''' Create a Rule based on the participant data. 

    Args:
      participant: This is a dictionary which has to contain the 
        following keys:
          call_id: ID of the call.
          tag: ng message from-tag.
          remote_port: Port given by RTPengine.
          local_port: Sender or Receiver local port.
      rtcp: When it is True will create RTCP objects.
    '''

    if rtcp:
        name = f'worker-rtcp-rule-{str(participant["call_id"])}-{str(participant["tag"])}'
    else:
        name = f'worker-rtp-rule-{str(participant["call_id"])}-{str(participant["tag"])}'

    resource = {
        'apiVersion': 'l7mp.io/v1',
        'kind': 'Rule',
        'metadata': {
            'name': name
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
                                    'port': {str(participant["remote_port"])},
                                    'bind': {
                                        'address': '127.0.0.1',
                                        'port': {str(participant["local_port"])}
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

    if not rtcp:
        resource["spec"]["rule"]["action"]["route"]["ingress"] =  [{'clusterRef': 'ingress-metric-counter'}]
        resource["spec"]["rule"]["action"]["route"]["egress"] =  [{'clusterRef': 'egress-metric-counter'}]

    api.create_namespaced_custom_object(
        group="l7mp.io",
        version="v1",
        namespace="default",
        plural="rules",
        body=resource
    )

    print("Rule created!")
