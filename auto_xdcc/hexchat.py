"""
Isolated module for functions that use hexchat internally
"""

import os.path

import hexchat

def get_context():
    server_name = hexchat.get_info('server')
    return hexchat.find_context(channel=server_name)

def get_store_path():
    store_path = hexchat.get_info('configdir')
    return os.path.join(store_path, 'addons', 'xdcc_store.json')
