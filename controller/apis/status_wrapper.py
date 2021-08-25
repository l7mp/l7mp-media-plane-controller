import time
import json
import threading
import logging
from status import Status, Statuses, Operations
from kubernetes import client, config, watch

lock = threading.Lock()

class StatusWrapper():
    
    def __init__(self):
        self.statuses = Statuses()
        self.op = Operations()

    def post(self, json_config):
        config = json.loads(json_config) if isinstance(json_config, str) else json.load(json_config)
        pods = self.op.get_pods(config['label'])
        for p in pods:
            self.statuses.add_status(p, config['label'], config['resource'])

    def delete(self, res_name, label):
        self.statuses.delete_res_from_statuses(res_name, label)

    def get_statuses(self):
        return self.statuses

    def set_statuses(self, statuses):
        self.statuses = statuses


def init():
    global statuses
    with lock:
        statuses = StatusWrapper()