import json
import os.path
import collections

import auto_xdcc.printer as printer


class Config(collections.UserDict):
    def __init__(self, path):
        self.path = path
        super().__init__(Config.load_config(path))

    @staticmethod
    def load_config(path):
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f)

        printer.error("Could not load configuration. Please check if \"{}\" exists and is accessible".format(path))
        return {}

    @staticmethod
    def save_config(path, data):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def persist(self):
        Config.save_config(self.path, self.data)

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

        search_key = key.lower().replace(' ','')
        return [(k, v) for k, v in data.items() if search_key in k.lower().replace(' ', '')]


config = None

def initialize(path):
    global config
    config = Config(path)
    return config


def get():
    global config
    return config
