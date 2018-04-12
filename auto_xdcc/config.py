import json
import os.path
import collections

import auto_xdcc.printer as printer

def get_config(path):
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)

    printer.error("Could not load configuration. Please check if \"{}\" exists and is accessible".format(path))
    return {}

def save_config(path, conf):
    with open(path, 'w') as f:
        json.dump(conf, f, indent=2)


class Config(collections.UserDict):
    def __init__(self, path):
        self.path = path
        super().__init__(get_config(path))

    def persist(self):
        save_config(self.path, self.data)
