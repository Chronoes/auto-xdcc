"""
Automagically checks XDCC packlists and downloads new episodes of specified shows.
"""

# pylint: disable=E0401
import hexchat
import os.path
import sys
import shutil
from time import sleep
from math import floor

# Add addons folder to path to detect auto_xdcc module
sys.path.append(os.path.join(hexchat.get_info('configdir'), 'addons'))

import auto_xdcc.argparse as argparse
import auto_xdcc.printer as printer
import auto_xdcc.download_manager as dm

from auto_xdcc.config import Config
# Best import error "solution" hue
# pylint: disable=E0611
from auto_xdcc.timer import Timer
from auto_xdcc.packlist import Packlist


__module_name__ = "Auto-XDCC Downloader"
__module_version__ = "3.1.1"
__module_description__ = "Automagically checks XDCC packlists and downloads new episodes of specified shows."
__author__ = "Oosran, Chronoes"

#--------------------------------------
#	START OF MODIFIABLE VARIABLES
# This can probably be removed soon, if not already.
server_name = "Rizon"
#   END OF MODIFIABLE VARIABLES
#--------------------------------------
default_dir = hexchat.get_prefs("dcc_dir")
if default_dir == "":
    hexchat.command("set dcc_dir " + os.path.join(os.path.expanduser("~"), "Downloads"))

default_clear_finished = hexchat.get_prefs("dcc_remove")
ongoing_dl = {}
first_load = True

def filename2namedEp(fn):
    if fn.count("_") < 2:
        full = fn.replace("_"," ").split("] ",1)[1].rsplit(" [",1)[0].rsplit(" - ",1)
        show = full[0]
    else:
        full = fn.split("]_",1)[1].rsplit("_[",1)[0].rsplit("_-_",1)
        show = full[0].replace("_"," ")
    ep = full[1]
    return show, ep

def pprint(line):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None: srv.prnt("26»28» Auto-XDCC: "+str(line))
    else: print("26»28» Auto-XDCC: "+str(line))

def nprint(origFilename,dl_size,bot_name):
    srv = hexchat.find_context(channel=server_name)
    filename = origFilename.split('_',1)[1].replace("_"," ").rsplit(".",1)[0]
    filesize = round(dl_size/1048576)
    size_ext = "MB"
    if filesize > 1029:
        filesize = round(filesize/1024, 2)
        size_ext = "GB"
    if not srv == None:
        srv.prnt("19»19» Nip-XDCC: Downloading %s (%s %s) from %s..." % (filename,str(filesize),size_ext,bot_name))
    else: print("19»19» Nip-XDCC: Downloading %s (%s %s) from %s..." % (filename,str(filesize),size_ext,bot_name))
    ongoing_dl[origFilename] = dl_size

def ndprint(origFilename,time_completed):
    srv = hexchat.find_context(channel=server_name)
    filename = origFilename.split('_',1)[1].replace("_"," ").rsplit(".",1)[0]
    total_ms = int((int(ongoing_dl.pop(origFilename))/int(time_completed))*1000)
    s = int(total_ms/1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)

    srv.prnt("25»25» Nip-XDCC: Download complete - %s | Completed in %d:%02d:%02d" % (filename, h, m, s))

def aprint(filename,botname):
    srv = hexchat.find_context(channel=server_name)
    _ = ongoing_dl.pop(filename)
    srv.prnt("20»20» Auto-XDCC: Download stalled - %s from %s" % (filename,botname))
    concurrent_dls = len(ongoing_dl)
    if concurrent_dls > 0:
        srv.prnt("19»25» Auto-XDCC: "+str(concurrent_dls)+" download(s) still remain.")

def rprint(line):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None: srv.prnt("7»7» "+str(line))
    else: print("7»7» "+str(line))

def xdcc_list_transfers_cb(word, word_eol, userdata):
    transfers = hexchat.get_list("dcc")
    if transfers:
        printer.info("Current transfers: ")
        for item in transfers:
            if item.type == 1:
                show, ep = filename2namedEp(item.file)
                perc = (0.0+item.pos)/item.size
                printer.info("Downloading {:.10s} - {:02d} | {:.2f}KB/s @ {:.2%}".format(show, str(ep), item.cps/1024, perc))
                colour = perc/100
                if colour < 0.25: colour = 20
                elif colour < 0.50: colour = 24
                else: colour = 19
                if perc < 0.1:
                    printer.info("[{}{}]".format(colour, ">".ljust(50)))
                else:
                    printer.info("[{}{}]".format(colour, str("="*((floor(perc/10)*5)-1)+">").ljust(50)))
    else: printer.info("No current transfers.")
    return hexchat.EAT_ALL

# def xdcc_last_seen_cb(word, word_eol, userdata):
#     printer.info("Last seen pack number is: {}".format(str(config['packlist']['lastPack'])))
#     return hexchat.EAT_ALL

# def xdcc_last_used_cb(word, word_eol, userdata):
#     printer.info("Last used bot is: {}".format(config['current']))
#     return hexchat.EAT_ALL

def xdcc_get_cb(word, word_eol, userdata):
    if len(word) == 3: hexchat.command("MSG {} XDCC SEND {}".format(str(word[1]), str(word[2])))
    else: printer.error("Invalid arguments: \"{}\"".format(str(word[1:])))
    return hexchat.EAT_ALL

def clear_finished_cb(word, word_eol, userdata):
    if len(word) == 2 and word[1].lower() in ["on","off"]:
        config['clear'] = word[1].lower()
        config.persist()
        printer.info("Clear finshed downloads toggled {}.".format(word[1].upper()))
    else: printer.error("Malformed request.")
    return hexchat.EAT_ALL

def reload_cb(word, word_eol, userdata):
    hexchat.set_pluginpref("plugin_reloaded", 1)
    pprint("Reloading plugin...")
    hexchat.command("timer 1 py reload \"{}\"".format(__module_name__))
    return hexchat.EAT_ALL

def no_show():
    if not config['shows']:
        pprint("No shows added to download list. You may want to add some shows to the list")

hexchat.hook_command("xdcc_transfers", xdcc_list_transfers_cb, help="/xdcc_transfers lists all currently ongoing transfers.")
# hexchat.hook_command("xdcc_lastseen", xdcc_last_seen_cb, help="/xdcc_lastseen prints the last seen pack number.")
# hexchat.hook_command("xdcc_forcerecheck", xdcc_forced_recheck_cb, help="/xdcc_forcerecheck resets lastseen and forces a recheck of the entire packlist.")
# hexchat.hook_command("xdcc_lastused", xdcc_last_used_cb, help="/xdcc_lastused prints the last used bot.")
hexchat.hook_command("xdcc_clearfinished", clear_finished_cb, help="/xdcc_clearfinshed <on|off> decides whether to clear finished downloads from transfer list.")
hexchat.hook_command("xdcc_reload", reload_cb, help="/xdcc_reload reloads the Auto-XDCC plugin.")
hexchat.hook_command("xdcc_get", xdcc_get_cb, help="/xdcc_get <bot> [packs] is a more convenient way to download a specific pack from a bot.")


def boolean_convert(value):
    return value not in ('off', '0', 'false', 'False', 'f')

# config = Config(os.path.join(os.path.dirname(__file__), 'xdcc_store.json'))
config = Config(os.path.join(hexchat.get_info('configdir'), 'addons', 'xdcc_store.json'))
hexchat.command("set dcc_remove " + config['clear'])

# Packlist management
def refresh_timer_callback(packlist):
    if packlist.check_diff():
        for item in packlist.get_new_items():
            if item.show_name in config['shows']:
                [episode_nr, resolution, _subdir] = config['shows'][item.show_name]
                if item.is_new(episode_nr, resolution):
                    packlist.download_manager.awaiting.put(item)
                    printer.prog("Queueing download of {} - {:02d}.".format(item.show_name, item.episode_nr))
        packlist.download_manager.start()

    packlist_conf = config['packlists'][packlist.name]
    packlist_conf['contentLength'] = packlist.last_request
    packlist_conf['lastPack'] = packlist.last_pack
    config.persist()

    return True


def register_packlists():
    packlists = {}
    for key in config['packlists']:
        packlist = Packlist.from_config(key, config['packlists'][key])
        packlist.register_refresh_timer(refresh_timer_callback)
        packlists[key] = packlist
    return packlists

packlists = register_packlists()

# Download management
def dcc_msg_block_cb(word, word_eol, userdata):
    if "xdcc send" in word[1].lower():
        return hexchat.EAT_HEXCHAT
    else:
        return hexchat.EAT_NONE

def _format_filesize(size):
    filesize = round(size / 1024**2)
    size_ext = "MB"
    if filesize > 1029:
        filesize = round(filesize / 1024, 2)
        size_ext = "GB"

    return (filesize, size_ext)


def dcc_send_offer_cb(word, word_eol, userdata):
    [bot_name, filename, size, ip_addr] = word

    state, item = (None, None)
    for packlist in packlists.values():
        state, item = packlist.download_manager.send_offer_callback(bot_name, filename, int(size), ip_addr)
        if item:
            break
    else:
        return hexchat.EAT_NONE

    if state == dm.DOWNLOAD_ABORT:
        printer.info("DCC Send Offer received but sender {} is not trusted - DCC Offer not accepted.".format(bot_name))
        return hexchat.EAT_ALL

    filesize, size_ext = _format_filesize(int(size))

    printer.prog("Downloading {} - {:02d} ({} {}) from {}...".format(item.show_name, item.episode_nr, filesize, size_ext, bot_name))
    return hexchat.EAT_HEXCHAT

def dcc_recv_connect_cb(word, word_eol, userdata):
    return hexchat.EAT_HEXCHAT

def dcc_recv_complete_cb(word, word_eol, userdata):
    [filename, _destination, _bot_name, time_spent] = word

    item, size = (None, None)
    for packlist in packlists.values():
        if packlist.download_manager.is_ongoing(filename):
            item, size = packlist.download_manager.recv_complete_callback(filename)
            break
    else:
        return hexchat.EAT_NONE

    total_ms = int(size / int(time_spent) * 1000)
    s = int(total_ms / 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)

    try:
        subdir = config['shows'][item.show_name][2]
        if subdir:
            shutil.move(os.path.join(default_dir, filename), os.path.join(default_dir, subdir, filename))
    except:
        pass

    if item.episode_nr > config['shows'][item.show_name][0]:
        config['shows'][item.show_name][0] = item.episode_nr
        config.persist()

    printer.complete("Download complete - {} - {:02d} | Completed in {}:{:02}:{:02}".format(item.show_name, item.episode_nr, h, m, s))
    printer.x("{} downloads remaining.".format(
        packlist.download_manager.count_awaiting() + packlist.download_manager.count_ongoing()
    ))

    return hexchat.EAT_ALL

def dcc_recv_failed_cb(word, word_eol, userdata):
    [filename, _destination, bot_name, error] = word

    for packlist in packlists.values():
        if packlist.download_manager.is_ongoing(filename):
            item = packlist.download_manager.download_abort(bot_name, filename)
            # Reset to previous packnumber
            if packlist.last_pack > item.packnumber:
                packlist.last_pack = item.packnumber - 1
            break
    else:
        return hexchat.EAT_NONE

    printer.error("Connection to {} failed, check firewall settings. Error: {}".format(bot_name, error))
    return hexchat.EAT_ALL

# TODO: Refactor this too
def dcc_recv_stall_cb(word, word_eol, userdata):
    if "RECV" in word[0].upper():
        aprint(word[1],word[2])
        return hexchat.EAT_ALL
    else: return hexchat.EAT_NONE


hexchat.hook_print("Message Send", dcc_msg_block_cb)
hexchat.hook_print("DCC SEND Offer", dcc_send_offer_cb)
hexchat.hook_print("DCC RECV Connect", dcc_recv_connect_cb)
hexchat.hook_print("DCC RECV Complete", dcc_recv_complete_cb)
hexchat.hook_print("DCC RECV Failed", dcc_recv_failed_cb)
# hexchat.hook_print("DCC Stall", dcc_recv_stall_cb)


# Argument parser
# Show subcommand handlers
def _list_shows(items):
    for show, [episode, resolution, subdir] in items:
        result = "{} @ episode {} | Resolution: {}p".format(show, episode, resolution)
        if subdir:
            printer.list(result + " in subdir " + subdir)
        else:
            printer.list(result)
    return hexchat.EAT_ALL

def _match_show_name(name, t='shows'):
    if name in config[t]:
        return (name, config[t][name])

    shows = config.partial_match(t, key=name)
    shows_len = len(shows)

    if shows_len == 0:
        printer.error("No show named: " + name)
        return None
    elif shows_len == 1:
        return shows[0]

    printer.info('Matched {} shows. Please refine your search keywords'.format(shows_len))
    _list_shows(shows)
    return None

def listshows_handler(args):
    items = sorted(config['shows'].items())

    if len(items) == 0:
        printer.x("No shows registered")
        return hexchat.EAT_ALL

    printer.x("Listing {} registered shows:".format(len(items)))
    return _list_shows(items)


def listarchivedshows_handler(args):
    items = sorted(config['archived'].items())

    if len(items) == 0:
        printer.x("No shows archived")
        return hexchat.EAT_ALL

    printer.x("Listing {} archived shows:".format(len(items)))
    return _list_shows(items)


def addshow_handler(args):
    resolution = int(args.resolution.strip('p')) if args.resolution is not None else 1080
    data = [args.episode, resolution, args.directory]

    config['shows'][args.name] = data
    config.persist()

    result = ''
    if args.episode is not None:
        result = "Added {} @ episode {} in {}p to list.".format(args.name, args.episode, resolution)
    else:
        result = "Added {} in {}p to list.".format(args.name, resolution)

    if args.directory:
        printer.x(result + " Default directory: " + args.directory)
    else:
        printer.x(result)

    printer.info("To download old episodes, reset the appropriate packlist")

    return hexchat.EAT_ALL


def updateshow_handler(args):
    show_match = _match_show_name(args.name)
    if not show_match:
        return hexchat.EAT_ALL

    name, [ep, reso, subdir] = show_match

    if args.episode is not None and args.episode != ep:
        ep = args.episode
        printer.info("Updated {} episode count to {}.".format(name, ep))

    if args.resolution is not None and args.resolution != reso:
        reso = int(args.resolution.strip('p'))
        printer.info("Updated {} resolution to {}.".format(name, reso))

    if args.directory is not None and args.directory != subdir:
        if args.directory == '/':
            subdir = ''
            printer.info("Updated {} subdir to main directory.".format(name))
        else:
            subdir = args.directory
            printer.info("Updated {} subdir to {}.".format(name, subdir))

    config['shows'][name] = [ep, reso, subdir]
    config.persist()

    return hexchat.EAT_ALL


def removeshow_handler(args):
    show_match = _match_show_name(args.name)
    if not show_match:
        return hexchat.EAT_ALL

    name, [ep, _reso, _subdir] = show_match

    del config['shows'][name]
    config.persist()

    if ep is not None:
        printer.x("Removed {} at episode {} from list.".format(name, ep))
    else:
        printer.x("Removed {} from list.".format(name))

    return hexchat.EAT_ALL


def archiveshow_handler(args):
    show_match = _match_show_name(args.name)
    if not show_match:
        return hexchat.EAT_ALL

    name, [ep, reso, subdir] = show_match

    del config['shows'][name]
    config['archived'][name] = [ep, reso, subdir]
    config.persist()

    printer.x("Added {} at episode {} to archive.".format(name, ep))

    return hexchat.EAT_ALL


def restoreshow_handler(args):
    show_match = _match_show_name(args.name, 'archived')
    if not show_match:
        printer.error("No show in archive named: " + args.name)
        return hexchat.EAT_ALL

    name, [ep, reso, subdir] = show_match

    del config['archived'][name]
    config['shows'][name] = [ep, reso, subdir]
    config.persist()

    printer.x("Restored {} at episode {} from archive.".format(name, ep))

    return hexchat.EAT_ALL

# Bot subcommand handlers
def listbots_handler(args):
    items = sorted(config['trusted'])
    if len(items) == 0:
        printer.x("No bots archived")
        return hexchat.EAT_ALL

    printer.x("Listing {} bots:".format(len(items)))

    for bot in items:
        printer.list(bot)
    return hexchat.EAT_ALL

def addbot_handler(args):
    bots = set(config['trusted'])

    bots.add(args.name)

    config['trusted'] = list(bots)
    config.persist()

    printer.x("Added {} to trusted list".format(args.name))

    return hexchat.EAT_ALL

def removebot_handler(args):
    bots = set(config['trusted'])

    if args.name not in bots:
        printer.error("No such bot in trusted list: " + args.name)
        return hexchat.EAT_ALL

    bots.remove(args.name)
    config['trusted'] = list(bots)
    config.persist()

    printer.x("Removed {} from trusted list".format(args.name))

    return hexchat.EAT_ALL


def timer_handler(args):
    if args.type == 'refresh':
        packlist = packlists[args.packlist]
        packlist.refresh_timer.unregister()
        if args.off:
            printer.x("Refresh timer disabled for {}.".format(packlist))
        else:
            interval = packlist.refresh_timer.interval
            if args.interval:
                packlist.refresh_timer.set_interval(args.interval)
                config['packlists'][packlist.name]['refreshInterval'] = args.interval
                config.persist()
                interval = args.interval

            packlist.refresh_timer.register(refresh_timer_callback)
            printer.x("Refresh timer enabled for packlist {} with interval {}s.".format(packlist, interval))


def packlist_handler(args):
    if args.action == 'reset':
        packlist = packlists[args.packlist]
        packlist.reset()

        packlist_conf = config['packlists'][packlist.name]
        packlist_conf['contentLength'] = packlist.last_request
        packlist_conf['lastPack'] = packlist.last_pack
        config.persist()

        printer.x("Packlist '{}' has been reset".format(packlist))


def default_handler(parser):
    def _handler(args):
        # Print usage for default handlers (no associated action)
        parser.print_usage()
        return hexchat.EAT_ALL

    return _handler

def show_main(parser, handler):
    parser.add_argument('name', help='Full name of the show')
    parser.set_defaults(handler=handler)
    return parser

def show_options(parser):
    parser.add_argument('-r', '--resolution', help='Resolution of episode to download')
    parser.add_argument('-e', '--episode', help='Episode number to start downloading from', type=int)
    parser.add_argument('-d', '--directory', help='Custom directory to download to')
    return parser

def listshows_subparser(parser):
    subparsers = parser.add_subparsers()

    archive = subparsers.add_parser('archived')
    archive.set_defaults(handler=listarchivedshows_handler)

    parser.set_defaults(handler=listshows_handler)
    return parser

def shows_subparser(parser):
    subparsers = parser.add_subparsers()

    listshows_subparser(subparsers.add_parser('list'))

    show_options(show_main(subparsers.add_parser('add'), addshow_handler))
    show_options(show_main(subparsers.add_parser('update'), updateshow_handler))
    show_main(subparsers.add_parser('remove'), removeshow_handler)
    show_main(subparsers.add_parser('archive'), archiveshow_handler)
    show_main(subparsers.add_parser('restore'), restoreshow_handler)

    parser.set_defaults(handler=default_handler(parser))
    return parser

def bot_main(parser, handler):
    parser.add_argument('name', help='Name of the bot')
    parser.set_defaults(handler=handler)
    return parser

def bots_subparser(parser):
    subparsers = parser.add_subparsers()

    list_parser = subparsers.add_parser('list')
    list_parser.set_defaults(handler=listbots_handler)

    bot_main(subparsers.add_parser('add'), addbot_handler)
    bot_main(subparsers.add_parser('remove'), removebot_handler)

    parser.set_defaults(handler=default_handler(parser))
    return parser


def timer_main(parser, handler):
    parser.add_argument('packlist', help='Packlist to apply the timer changes for', choices=tuple(packlists))
    parser.add_argument('type', help='Which timer', choices=('refresh',))
    parser.add_argument('--off', help='Disable the timer until restart', action='store_true')
    parser.add_argument('-i', '--interval', help='Interval to run timer at in seconds', type=int)

    parser.set_defaults(handler=handler)
    return parser

def setter_subparser(parser):
    subparsers = parser.add_subparsers()

    timer_main(subparsers.add_parser('timer'), timer_handler)

    parser.set_defaults(handler=default_handler(parser))
    return parser

def packlist_subparser(parser):
    parser.add_argument('action', help='reset: Resets packlist to parse all lines', choices=('reset',))
    parser.add_argument('packlist', help='Packlist to apply the action to', choices=tuple(packlists))

    parser.set_defaults(handler=packlist_handler)
    return parser

def argument_parser():
    parser = argparse.ArgumentParser(prog='/axdcc')

    subparsers = parser.add_subparsers()

    shows_subparser(subparsers.add_parser('show'))
    bots_subparser(subparsers.add_parser('bot'))
    setter_subparser(subparsers.add_parser('set'))
    packlist_subparser(subparsers.add_parser('packlist'))

    parser.set_defaults(handler=default_handler(parser))
    return parser


parser = argument_parser()
def axdcc_main_cb(word, word_eol, userdata):
    try:
        args = parser.parse_args(word[1:])
    except:
        return hexchat.EAT_PLUGIN
    return args.handler(args)


hexchat.hook_command('axdcc', axdcc_main_cb, help=parser.format_usage())

def unloaded_cb(userdata):
    # Force close running threads
    for packlist in packlists.values():
        packlist.download_manager.terminate(True)

    if int(hexchat.get_prefs('dcc_auto_recv')) != 0:
        hexchat.command("set dcc_auto_recv 0")
    if int(hexchat.get_prefs('dcc_remove')) != int(default_clear_finished):
        hexchat.command("set dcc_remove " + str(default_clear_finished))
    sleep(0.1)
    printer.x("Plugin unloaded")

    return hexchat.EAT_ALL

hexchat.hook_unload(unloaded_cb)
##################################################################################
# Hooks below this line are there for debug reasons and will be removed eventually

# The mysterious message issue seems to come in the form of server text messages
def server_txt_cb(word, word_eol, userdata):
    try:
        rprint("Decoded: "+word_eol[0].decode('utf-8'))
        return hexchat.EAT_NONE
    except:
        return hexchat.EAT_ALL
hexchat.hook_print("Server Text", server_txt_cb)

# No idea what no running process is, but let's find out if it happens
def noproc_cb(word, word_eol, userdata):
    rprint("[No Process msg] "+str(word))
    return hexchat.EAT_NONE
hexchat.hook_print("No Running Process", noproc_cb)

# Hooks above this line are there for debug reasons and will be removed eventually
##################################################################################


if not int(hexchat.get_prefs('dcc_auto_recv')) == 2:
    hexchat.command("set dcc_auto_recv 2")

def raw_process_cb(word, word_eol, userdata):
    word_length = len(word)
    try:
        if word_length > 8 and word[3] == ":You" and word[len(word)-1] == "away":
            global first_load
            if first_load:
                pprint("Plugin loaded.")
                first_load = False
                no_show()
    except:
        pass
    return hexchat.EAT_NONE

hexchat.hook_server("RAW LINE", raw_process_cb)

if hexchat.get_pluginpref("plugin_reloaded") == 1:
    pprint("Plugin reloaded.")
    hexchat.set_pluginpref("plugin_reloaded", 0)
    no_show()

# 24»23» Brown mode code
# 28»18» cyan/blue server message code
