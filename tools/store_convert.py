#!/usr/bin/env python3
import argparse
import itertools
import json
import sys
import urllib.parse as urlparse

from copy import deepcopy


def list_partition(pred, iterable):
    """Use a predicate to partition entries into false entries and true entries"""
    # list_partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = itertools.tee(iterable)
    return itertools.filterfalse(pred, t1), filter(pred, t2)


def migrate_2_7(old_conf):
    conf = {
        "storeVer": "2.7",
        "content-length": 0,
        "trusted": ["CR-HOLLAND|NEW", "CR-ARCHIVE|1080p", "KareRaisu", "Ginpachi-Sensei", "Gintoki", "Ginpa3", "Ginpa2", "Nippon|zongzing", "Nippon|minglong"],
        "current": "CR-HOLLAND|NEW",
        "clear": "on",
        "last": 0,
        "shows": {}
    }
    conf.update(old_conf)
    return conf

def migrate_3_0(old_conf):
    conf = {
        'storeVer': '3.0',
        'packlist': {
            'url':"http://arutha.info:1337/txt",
            'contentLength': int(old_conf['content-length']),
            'lastPack': int(old_conf['last'])
        },
        'timers': {
            'refresh': {
                'interval': 900
            }
        },
        'maxConcurrentDownloads': 3,
        'trusted': old_conf['trusted'],
        'current': old_conf['current'],
        'clear': old_conf['clear']
    }

    shows, archived = list_partition(lambda x: x[1][3] == 'a', old_conf['shows'].items())
    conf['archived'] = dict([(name, x[:3]) for name, x in archived])
    conf['shows'] = dict([(name, x[:3]) for name, x in shows])

    return conf

def migrate_3_2(old_conf):
    conf = {
        'storeVer': '3.2',
        'packlists': {},
        'shows': old_conf['shows'],
        'archived': old_conf['archived'],
        'clear': old_conf['clear']
    }

    packlist = old_conf['packlist']

    components = urlparse.urlparse(packlist['url'])

    name = components.hostname.split('.')[-2]

    conf['packlists'][name] = {
        'url': packlist['url'],
        'type': 'episodic',
        'contentLength': packlist['contentLength'],
        'lastPack': packlist['lastPack'],
        'maxConcurrentDownloads': old_conf['maxConcurrentDownloads'],
        'trusted': old_conf['trusted'],
        'current': old_conf['current'],
        'refreshInterval': old_conf['timers']['refresh']['interval']
    }

    return conf

def migrate_3_3(old_conf):
    conf = {
        'storeVer': '3.3',
        'packlists': old_conf['packlists'],
        'shows': old_conf['shows'],
        'archived': old_conf['archived'],
        'clear': old_conf['clear']
    }

    for key in conf['packlists']:
        conf['packlists'][key]['metaType'] = ['text']

    return conf


versions = [
    ('2.7', migrate_2_7),
    ('3.0', migrate_3_0),
    ('3.2', migrate_3_2),
    ('3.3', migrate_3_3)
]

def run_migrations(old_conf, from_ver):
    # Make new deep copy to modify
    new_conf = deepcopy(old_conf)
    for ver, fn in versions:
        if ver > from_ver:
            new_conf = fn(old_conf)

    return new_conf


def argument_parser():
    parser = argparse.ArgumentParser(description="Auto-XDCC store converter tool.")
    parser.add_argument('filename', help="Filename of the store to convert. Defaults to standard input.", nargs='?', default='-')
    parser.add_argument('-nb', '--nobackup', help="Don't make backup of old store.", action='store_true')
    parser.add_argument('-o', '--output', help="Output filename. Defaults to standard output", default='-')
    return parser


def main():
    parser = argument_parser()
    args = parser.parse_args()

    input_file = sys.stdin if args.filename == '-' else open(args.filename)

    with input_file:
        content = json.load(input_file)

    store_ver = content['storeVer'] if 'storeVer' in content else "0.1"

    if not args.nobackup:
        backup_filename = 'xdcc_store.json' if args.filename == '-' else args.filename
        with open('{}.v{}.bak'.format(backup_filename, store_ver.replace('.', '_')), 'w') as bak:
            json.dump(content, bak)

    new_content = run_migrations(content, store_ver)

    output_file = sys.stdout if args.output == '-' else open(args.output, 'w')

    with output_file:
        json.dump(new_content, output_file, indent=2)


if __name__ == '__main__':
	main()
