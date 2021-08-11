from contextlib import contextmanager
import requests
import json
import time
import logging
from kubernetes import client, config
from urllib3 import exceptions

class Operations():

    def __init__(self):
        config.load_incluster_config()
        self.api = client.CoreV1Api()

    def get_pods(self, label):
        pods = self.api.list_namespaced_pod(namespace='default', label_selector=label).to_dict()
        ret = []
        for p in pods['items']:
            ret.append({
                'pod_name': p['metadata']['name'],
                'pod_ip': p['status']['pod_ip']
            })
        return ret

    def post(self, pod_ip, path, data):
        logging.info(f"http://{pod_ip}:1234/api/v1/{path}")
        while True:
            try:
                response = requests.post(f"http://{pod_ip}:1234/api/v1/{path}", json=data)
                break
            except requests.exceptions.ConnectionError as e :
                logging.error(e)
                time.sleep(1)
                continue

        if response.status_code != 200:
            logging.info(f'{response.status_code}:{response.text}')
        return response

    def delete(self, label, path, res_name):
        pods = self.api.list_namespaced_pod(namespace='default', label_selector=label).to_dict()
        ret = []
        containers = []
        for p in pods['items']:
            # for c in p['status']['container_statuses']:
            #     containers.append({'name': c['name'], 'restart_count': c['restart_count']})
            logging.info(f"http://{p['status']['pod_ip']}:1234/api/v1/{path}/{res_name}")
            response = requests.delete(f"http://{p['status']['pod_ip']}:1234/api/v1/{path}/{res_name}")
            if response.status_code != 200:
                logging.info(f'{response.status_code}:{response.text}')
            ret.append(response)
        return ret

class Status(Operations):

    def __init__(self, pod_name, pod_ip, label):
        self.pod_name = pod_name # Pod name
        self.pod_ip = pod_ip # Pod IP
        self.present = False # Is it configured
        self.label = label # Pod label
        # self.containers = [{'name': containers['name'], 'restart_count': containers['restart_count']}]
        self.resources = [] # Proxy resources
        super().__init__()

    def __str__(self):
        return "".join((
        f'pod_name: {self.pod_name}\n'
        f'pod_ip: {self.pod_ip}\n',
        f'present: {self.present}\n'
        f'label: {self.label}\n'
        f'resources: {self.resources}'
        ))
        

    def add_resource(self, res):
        resource = {
            'label': self.label, 
            'path': res['path'], 
            'config': res['config'], 
            'res_name': res['res_name'],
        }

        # Add endpoints by IP
        if 'endpoints_label' in res:
            resource['endpoints_label'] = res['endpoints_label']
            pods = super().get_pods(res['endpoints_label'])
            resource['endpoint_ips'] = [{'name': p['pod_name'], 'ip': p['pod_ip']} for p in pods]
            resource['config']['cluster']['endpoints'] = []
            for e in resource['endpoint_ips']:
                resource['config']['cluster']['endpoints'].append({'name': res['res_name'] + e['ip'], 'spec': {'address': e['ip']}})

        response = super().post(self.pod_ip, resource['path'], resource['config'])
        if response.status_code == 200:
            self.resources.append(resource)
    
    def delete_resource(self, res_name):
        for r in self.resources:
            logging.info(f'{r["res_name"]}, {res_name}')
            if r['res_name'] == res_name:
                self.resources = list(filter(lambda i: i['res_name'] != res_name, self.resources))
                path = 'rules' if 'rules' in r['path'] else r['path']
                return super().delete(r['label'], path, r['res_name'])

    def delete_endpoint(self, pod_ip):
        for r in self.resources:
            if 'endpoints_label' in r:
                new_endpoint_ips = []
                for e in r['endpoint_ips']:
                    if e['ip'] == pod_ip:
                        super().delete(r['label'], 'endpoints', r['res_name'] + pod_ip)
                        continue
                    new_endpoint_ips.append(e)
                r['endpoint_ips'] = new_endpoint_ips

    def add_endpoint(self, pod_name, pod_ip, labels):
        for r in self.resources:
            if 'endpoints_label' in r:
                if r['endpoints_label'] in labels:
                    e_names = [e['name'] for e in r['endpoint_ips']]
                    if pod_name not in e_names:
                        cluster_name = r['config']['cluster']['name']
                        super().post(self.pod_ip, f'clusters/{cluster_name}/endpoints', 
                        {'endpoint': {
                            'name': cluster_name + pod_ip, 
                            'spec': {'address': pod_ip}
                            }
                        })
                        r['endpoint_ips'].append({'name': pod_name, 'ip': pod_ip})


    def update_endpoints(self, pod):
        endpoints = {}
        for r in self.resources:
            if 'endpoints_label' in r:
                if r['endpoints_label']:
                    endpoints[r['endpoints_label']] = []
                    # Get new IPs for endpoints
                    labels = [f'{k}={v}' for k, v in pod['object'].metadata.labels.items()]
                    if r['endpoints_label'] in labels:
                        endpoints[r['endpoints_label']].append(pod['object'].status.pod_ip)
                    # Delete old not existing endpoints
                    deleted_eps = []
                    for ei in r['endpoint_ips']:
                        if ei not in endpoints[r['endpoints_label']]:
                            super().delete(r['endpoints_label'], 'endpoints', ei)
                            deleted_eps.append(ei)
                    # Keep only the existing endpoints
                    r['endpoint_ips'] = list(filter(lambda i: i not in deleted_eps, r['endpoint_ips']))
                    # Filter to the new not setted endpoints
                    endpoints[r['endpoints_label']] = list(filter(lambda i: i not in r['endpoint_ips'], endpoints[r['endpoints_label']]))
                    logging.info(endpoints)
                    # Append and set the new endpoints
                    for ei in endpoints[r['endpoints_label']]:
                        r['endpoint_ips'].append(ei)
                        super().post(
                            r['endpoints_label'], 
                            f'clusters/{r["res_name"]}/endpoints', 
                            json.dumps({
                                'endpoint': {
                                    'name': ei,
                                    'spec': {'address': ei}
                                }
                            })
                        )

class Statuses():

    def __init__(self):
        self.statuses = []

    def _find_obj_by_key_value(self, key, value):
        for s in self.statuses:
            if getattr(s, key) == value:
                return s
        return None
    
    def _containers_check(s_containers, p_containers):
        for s in s_containers:
            for p in p_containers:
                if s['name'] == p['name'] and s['restart_count'] != p['restart_time']:
                    return False
        return True

    def add_status(self, pod, label, resource):
        s = self._find_obj_by_key_value('pod_name', pod['pod_name'])
        if not s: 
            s = Status(pod['pod_name'], pod['pod_ip'], label)
        
            # ret, containers = s.add_resource(resource['path'], resource['config'], resource['res_name'])
            s.add_resource(resource)
            # s.containers += containers
            s.present = True
            self.statuses.append(s)
        else:
            s.add_resource(resource)
            # s.containers += containers
            s.present = True
        # for s in self.statuses:
        #     logging.info(s)
        # for st in self.statuses:
        #     logging.info(st)

    def add_endpoint(self, pod):
        labels = []
        for k, v in pod['object'].metadata.labels.items():
            labels.append(f'{k}={v}')
        if pod['object'].status.pod_ip:
            for s in self.statuses:
                s.add_endpoint(pod['object'].metadata.name, pod['object'].status.pod_ip, labels)

    def delete_res_from_statuses(self, res_name, label):
        for s in self.statuses:
            if s.label == label:
                s.delete_resource(res_name)

    def delete_status(self, pod_name, pod_ip):
        new_statuses = []
        for s in self.statuses:
            if s.pod_name != pod_name:
                s.delete_endpoint(pod_ip)
                new_statuses.append(s)
        self.statuses = new_statuses

    def copy(self, pod):
        labels = []
        for k, v in pod['object'].metadata.labels.items():
            labels.append(f'{k}={v}')

        pod_dict = {
            'pod_name': pod['object'].metadata.name,
            'pod_ip': pod['object'].status.pod_ip
        }

        names = [s.pod_name for s in self.statuses]
        if pod_dict['pod_name'] in names:
            return

        logging.info(pod_dict)

        logging.info(f'len of statuses {len(self.statuses)}')
        for s in self.statuses:
            if s.label in labels:
                for r in s.resources:
                    logging.info(f'len of resources {len(s.resources)}')
                    logging.info(r)
                    self.add_status(pod_dict, s.label, r)

    def update(self, pod):
        # args = list of pods
        for s in self.statuses:
            s.present = False
        
        pod_names = [i.pod_name for i in self.statuses]
        new_resources = []
        # if the pod already present there is no more work to do
        if pod['object'].metadata.name in pod_names:
            for s in self.statuses:
                if s.pod_name == pod['object'].metadata.name:
                    s.present = True
                    logging.info(f'{pod["object"].metadata.name}: {pod["object"].status.pod_ip}')
                # if a container restarted then reapply every resource
                # if self._containers_check(s.containers, pod['object'].status.container_statuses):
                #     s.containers = []
                #     for r in s.resources:
                #         _, containers = r.add_resource(r['path'], r['config'], r['res_name'])
                #         s.containers += containers                            
        else:
            # save every new pod into a different array
            r = {
                'pod_name': pod['object'].metadata.name,
                'pod_ip': pod['object'].status.pod_ip,
                'labels': []
            }
            # logging.info(pod['object'].metadata.labels)
            for k, v in pod['object'].metadata.labels.items():
                r['labels'].append(f'{k}={v}')
            logging.info(r)
            new_resources.append(r)

            # "copy" the old pods proxy configuration into the new ones if their have
            # a matching label
            self._copy_resources(new_resources)
        
        # update endpoints in cluster
        for s in self.statuses:
            s.update_endpoints(pod)
        
        # delete every pods which is not found
        self.statuses = list(filter(lambda i: i.present == True, self.statuses))