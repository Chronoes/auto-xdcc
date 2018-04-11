import json
import os.path
import collections

import auto_xdcc.printer as printer
from auto_xdcc.hexchat import get_store_path

def get_config():
    path = get_store_path()
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)

    printer.error("Could not load configuration. Please check if \"{}\" exists and is accessible".format(path))

def save_config(conf):
    path = get_store_path()
    with open(path, 'w') as f:
        json.dump(conf, f)


class Config(collections.UserDict):
    @classmethod
    def load_from_store(cls):
        return cls(get_config())

    def persist(self):
        save_config(self.data)
