import json
import os.path

import hexchat

import auto_xdcc.printer as printer

def get_store_path():
    store_path = hexchat.get_info('configdir')
    return os.path.join(store_path, 'addons', 'xdcc_store.json')

def get_config():
    path = get_store_path()
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)

    printer.error("Could not load configuration. Please check if \"{}\" exists and is accessible".format(path))
