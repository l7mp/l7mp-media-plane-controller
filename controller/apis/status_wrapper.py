import json
import threading
from status import Statuses, Operations

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

    def delete(self, res_name, label, recursive=False):
        self.statuses.delete_res_from_statuses(res_name, label, recursive)

    def get_statuses(self):
        return self.statuses

    def set_statuses(self, statuses):
        self.statuses = statuses


# Needed to use this object as a "singleton"
def init():
    global statuses
    with lock:
        statuses = StatusWrapper()