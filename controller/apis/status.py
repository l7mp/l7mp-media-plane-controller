import requests
import time
import logging
from kubernetes import client, config

class Operations():

    def __init__(self):
        config.load_incluster_config()
        self.api = client.CoreV1Api()

    # Find pods names and ips
    def get_pods(self, label):
        pods = self.api.list_namespaced_pod(namespace='default', label_selector=label).to_dict()
        ret = []
        for p in pods['items']:
            ret.append({
                'pod_name': p['metadata']['name'],
                'pod_ip': p['status']['pod_ip']
            })
        return ret
    
    # HTTP POST
    def post(self, pod_ip, path, data):
        logging.info(f"http://{pod_ip}:1234/api/v1/{path}")
        while True:
            try:
                response = requests.post(f"http://{pod_ip}:1234/api/v1/{path}", json=data)
                if response.status_code == 200:
                    logging.info(f'response 200')
                    break
                elif response.status_code != 200 and 'already defined' in str(response.content):
                    logging.info(f'{response.status_code}:{response.text}')
                    break
                else:
                    logging.info(f'response {response.status_code}:{response.text}')
                    continue
            except requests.exceptions.ConnectionError as e :
                logging.error(e)
                time.sleep(1)
                continue

        return response

    # HTTP DELETE
    def delete(self, label, path, res_name):
        pods = self.api.list_namespaced_pod(namespace='default', label_selector=label).to_dict()
        ret = []
        for p in pods['items']:
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
        

    # Create a resource on L7mp proxy 
    def add_resource(self, res):
        resource = {
            'label': self.label, 
            'path': res['path'], 
            'config': res['config'], # This is the json object which will be applied
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
    
    # Delete a resource from an l7mp proxy
    def delete_resource(self, res_name, recursive=False):
        for r in self.resources:
            if r['res_name'] == res_name:
                self.resources = list(filter(lambda i: i['res_name'] != res_name, self.resources))
                path = 'rules' if 'rules' in r['path'] else r['path']
                name = r['res_name'] + '?recursive=true' if recursive else r['res_name']
                return super().delete(r['label'], path, name)

    # Delete an endpoint from an L7mp cluster
    def delete_endpoint(self, pod):
        logging.info(pod)
        for r in self.resources:
            if 'endpoints_label' in r:
                ips = [e['ip'] for e in r['endpoint_ips']]
                if pod['ip'] in ips and r['path'] == 'clusters':
                    ep = None
                    for i in r['config']['cluster']['endpoints']:
                        logging.info(i)
                        if i['spec']['address'] == pod['ip']:
                            ep = i
                    if ep:
                        super().delete(r['label'], 'endpoints', ep['name'] + '?recursive=true')
                        r['config']['cluster']['endpoints'].remove(ep)
                        r['endpoint_ips'].remove(pod)

    # Add new endpoint to an L7mp cluster
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
                        r['config']['cluster']['endpoints'].append(
                            {
                            'name': cluster_name + pod_ip, 
                            'spec': {'address': pod_ip}
                            }
                        )
                        r['endpoint_ips'].append({'name': pod_name, 'ip': pod_ip})

class Statuses():

    def __init__(self):
        self.statuses = []

    def _find_obj_by_key_value(self, key, value):
        for s in self.statuses:
            if getattr(s, key) == value:
                return s
        return None
    
    # Not used
    def _containers_check(s_containers, p_containers):
        for s in s_containers:
            for p in p_containers:
                if s['name'] == p['name'] and s['restart_count'] != p['restart_time']:
                    return False
        return True

    # Add status or just a resource
    def add_status(self, pod, label, resource):
        s = self._find_obj_by_key_value('pod_name', pod['pod_name'])
        if not s:
            if pod['pod_ip']: 
                s = Status(pod['pod_name'], pod['pod_ip'], label)        
                s.add_resource(resource)
                s.present = True
                self.statuses.append(s)
        else:
            s.add_resource(resource)
            s.present = True

    # Add endpoint to statuses 
    def add_endpoint(self, pod):
        labels = []
        for k, v in pod['object'].metadata.labels.items():
            labels.append(f'{k}={v}')
        if pod['object'].status.pod_ip:
            for s in self.statuses:
                s.add_endpoint(pod['object'].metadata.name, pod['object'].status.pod_ip, labels)

    # Delete a resource from a status
    def delete_res_from_statuses(self, res_name, label, recursive=False):
        for s in self.statuses:
            if s.label == label:
                s.delete_resource(res_name, recursive)

    # Delete a complet status object. Triggered on endpoint delete
    def delete_status(self, pod_name, pod_ip):
        new_statuses = []
        for s in self.statuses:
            if s.pod_name != pod_name and 'app=l7mp-ingress' == s.label:
                s.delete_endpoint({'name': pod_name, 'ip': pod_ip})
                new_statuses.append(s)
            else:
                new_statuses.append(s)
        self.statuses = new_statuses

    # If a new worker pod created this method will copy every another 
    # worker's config to the new one
    def copy(self, pod):
        labels = []
        for k, v in pod['object'].metadata.labels.items():
            labels.append(f'{k}={v}')

        pod_dict = {
            'pod_name': pod['object'].metadata.name,
            'pod_ip': pod['object'].status.pod_ip
        }

        names = [s.pod_name for s in self.statuses]
        # if pod_dict['pod_name'] in names:
        #     return

        for s in self.statuses:
            if s.label in labels:
                for r in s.resources:
                    self.add_status(pod_dict, s.label, r)