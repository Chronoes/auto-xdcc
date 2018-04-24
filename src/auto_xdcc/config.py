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

    def partial_match(self, *keypath, key):
        """
        Attempts to match key against keys in the config in given keypath
        using case insensitive substring match.

        Returns: list of matched (key, value) pairs
        """
        data = self.data
        for kp in keypath:
            if type(data) is not dict:
                raise TypeError('Value at keypath {} is not a dictionary'.format(' -> '.join(keypath)))
            elif kp not in data:
                raise KeyError('Check the keypath: {} does not exist in config'.format(' -> '.join(keypath)))
            data = data[kp]

        if key in data.keys():
            return [(key, data[key])]

        search_key = key.lower().replace(' ','')
        return [(k, v) for k, v in data.items() if search_key in k.lower().replace(' ', '')]
