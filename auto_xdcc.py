"""
Automagically checks XDCC packlists and downloads new episodes of specified shows.
"""

# pylint: disable=E0401
import hexchat
import requests, threading
import os.path
import sys
from json import load, dump
from platform import system as sysplat
from re import sub as rx
from os import getcwd, remove
from os.path import expanduser, isfile
from collections import deque
from shutil import move
from time import sleep
from math import floor

# Add addons folder to path to detect auto_xdcc module
sys.path.append(os.path.join(hexchat.get_info('configdir'), 'addons'))

import auto_xdcc.argparse as argparse
import auto_xdcc.printer as printer

from auto_xdcc.config import Config


__module_name__ = "Auto-XDCC Downloader"
__module_version__ = "3.0"
__module_description__ = "Automagically checks XDCC packlists and downloads new episodes of specified shows."
__author__ = "Oosran, Chronoes"

#--------------------------------------
#	START OF MODIFIABLE VARIABLES
#       This is the URL of a relevant XDCC packlist.
p_url = "http://arutha.info:1337/txt"
u_url = "https://kae.re/kareraisu.txt"
sleep_between_requests = 1
#   refresh packlist every 900000 ms = 15 min
default_refresh_rate = 900000
#   check download queue every 600000 ms = 10 min
default_dl_rate = 600000
#   time unit multipliers
MS_MINUTES = 60000
MS_SECONDS = 1000

server_name = "Rizon"
max_concurrent_downloads = 3
#   END OF MODIFIABLE VARIABLES
#--------------------------------------
default_dir = hexchat.get_prefs("dcc_dir")
if default_dir == "":
    hexchat.command("set dcc_dir "+expanduser("~")+"\\Downloads\\")
elif not default_dir[-1:] == "\\":
    default_dir += "\\"
timed_refresh = None
timed_dl = None
default_clear_finished = hexchat.get_prefs("dcc_remove")
ongoing_dl = {}
dl_queue = deque([])
first_load = True

# def get_store_path():
#     store_path = hexchat.get_info('configdir')
#     if sysplat() == 'Windows':
#         store_path += "\\addons\\"
#     else:
#         store_path += "/addons/"
#     return store_path

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

# def eprint(line):
#     srv = hexchat.find_context(channel=server_name)
#     if not srv == None: srv.prnt("18»18» Auto-XDCC: Error - "+str(line))
#     else: print("18»18» Auto-XDCC: Error - "+str(line))

# def iprint(line):
#     srv = hexchat.find_context(channel=server_name)
#     if not srv == None: srv.prnt("29»22» Auto-XDCC: INFO - "+str(line))
#     else: print("29»22» Auto-XDCC: INFO - "+str(line))

def pdprint(filename,dl_size,bot_name):
    srv = hexchat.find_context(channel=server_name)
    show_name, show_ep = filename2namedEp(filename)
    filesize = round(dl_size/1048576)
    size_ext = "MB"
    if filesize > 1029:
        filesize = round(filesize/1024, 2)
        size_ext = "GB"
    if not srv == None:
        srv.prnt("19»19» Auto-XDCC: Downloading %s - %s (%s %s) from %s..." % (show_name,str(show_ep),str(filesize),size_ext,bot_name))
    else: print("19»19» Auto-XDCC: Downloading %s - %s (%s %s) from %s..." % (show_name,str(show_ep),str(filesize),size_ext,bot_name))
    ongoing_dl[filename] = dl_size

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

# def qprint(show_name, show_episode):
#     srv = hexchat.find_context(channel=server_name)
#     if not srv == None:
#         srv.prnt("19»19» Auto-XDCC: Queueing download of %s - %s." % (show_name, str(show_episode)))
#     else: print("19»19» Auto-XDCC: Queueing download of %s - %s." % (show_name, str(show_episode)))

def dprint(filename,time_completed):
    srv = hexchat.find_context(channel=server_name)
    total_ms = int((int(ongoing_dl.pop(filename))/int(time_completed))*1000)
    s = int(total_ms/1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)

    show_name, show_ep = filename2namedEp(filename)
    shows = config['shows']
    try:
        f_ext = shows[show_name][2]
        if not f_ext == "":
            move(default_dir+filename, default_dir+f_ext+"\\"+filename)
    except: pass


    srv.prnt("25»25» Auto-XDCC: Download complete - %s - %s | Completed in %d:%02d:%02d" % (show_name, show_ep, h, m, s))
    concurrent_dls = len(ongoing_dl)
    if concurrent_dls == 1:
        srv.prnt("19»25» Auto-XDCC: "+str(concurrent_dls)+" download remaining.")
    elif concurrent_dls > 1:
        srv.prnt("19»25» Auto-XDCC: "+str(concurrent_dls)+" downloads remaining.")

    global dl_queue
    if len(dl_queue) > 0:
        queue_pop()

def ndprint(origFilename,time_completed):
    srv = hexchat.find_context(channel=server_name)
    filename = origFilename.split('_',1)[1].replace("_"," ").rsplit(".",1)[0]
    total_ms = int((int(ongoing_dl.pop(origFilename))/int(time_completed))*1000)
    s = int(total_ms/1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)

    try:
        move(default_dir+origFilename, default_dir+"music"+"\\"+origFilename)
    except: pass

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


# def get_store():
#     store = {}
#     try:
#         with open(get_store_path()+'xdcc_store.json', 'r') as f:
#             store = load(f)
#         hexchat.command("set dcc_remove "+store['clear'])
#     except:
#         store = {'trusted':["CR-HOLLAND|NEW"], 'shows':{}, 'current':"CR-HOLLAND|NEW", 'last':0, 'content-length':0, 'clear':hexchat.get_prefs("dcc_remove")}
#         s_path = get_store_path()
#         if not isfile(s_path+'xdcc_store.json'):
#             with open(s_path+'xdcc_store.json', 'w') as f:
#                 dump(store, f)
#             eprint("Could not load configuration. New configuration has been created.")
#     return store

# store = get_store()

def get_server_context():
    return hexchat.find_context(channel=server_name)

def update_show(show, episode):
    config['shows'][show][0] = int(episode)
    config.persist()

def refresh_head():
    try:
        r = requests.head(p_url, timeout=5)
        if int(r.headers['content-length']) > int(config['content-length'])+30:
            refresh_packlist()
            config['content-length'] = int(r.headers['content-length'])
            config.persist()
    except Exception as e:
        printer.error(e)

def refresh_packlist():
    previously_last_seen_pack = config['last']
    latest_pack = "1"
    shows = config['shows']
    try:
        r = requests.get(p_url, stream=True, timeout=10)
        for line in r.iter_lines():
            if line:
                line = line.decode("utf-8")
                if not line.startswith("#"): pass
                else:
                    p_nr = line.split(" ",1)[0][1:]
                    latest_pack = p_nr
                    is_v2 = False
                    if int(p_nr) <= (previously_last_seen_pack): pass
                    else:
                        if line.count('_') == 1:
                            line = rx(r"\s\s+", ' ', line).replace("[ ", "[").split(" ", 4)
                        # Next line will have to be fixed at some point. It works for now though.
                        else:
                            line = rx(r"\s\s+", ' ', line).replace("[ ", "[").replace("_", " ").split(" ", 4)
                        p_nr = line[0][1:]
                        p_filename = line[4]
                        p_full = p_filename.rsplit(" - ",1)
                        # This will typically catch movies with no numbering, screw those
                        if len(p_full) == 1: pass
                        elif len(p_full) == 2:
                            p_name = p_full[0]
                            p_ep = p_full[1].split(" ")[0]
                            if "v2" in p_ep or "v3" in p_ep:
                                is_v2 = True
                            p_ep = rx(r"v\d", '', p_ep)
                            if p_ep.endswith(("A","B")):
                                printer.info("This episode has more than one part, you may have to download it manually. {} - {}".format(p_name, p_ep))
                            p_res = p_full[1].split(" ")[1].split(".")[0]
                        else:
                            printer.error("Something doesn't seem quite right with the format of the file name.\n\t"+str(p_full))

                        # Don't care about recaps which are generally the only ones with . in the number (i.e. 06.5)
                        if "." in p_ep:
                            previously_last_seen_pack = int(p_nr)
                            # Only do one request per refresh
                            if sleep_between_requests < 0:
                                break
                        elif p_name in shows and int(p_ep) > shows[p_name][0] and int(p_res.strip("[]p")) == shows[p_name][1]:
                            if not if_file(p_filename, shows[p_name][2], is_v2):
                                queue_request(p_nr, p_name, p_ep)
                                previously_last_seen_pack = int(p_nr)
                                if sleep_between_requests >= 0: sleep(sleep_between_requests)
                                else: break

        if not previously_last_seen_pack > int(latest_pack):
            previously_last_seen_pack = int(latest_pack)
            config['last'] = previously_last_seen_pack
            config.persist()
        else:
            printer.error("Packlist has been reset and needs to be re-checked. Current: {} | old: {}".format(latest_pack, str(previously_last_seen_pack)))
            config['last'] = 0
            config.persist()
            refresh_packlist()
    except Exception as e:
        printer.error(e)

def if_file(filename, dir_ext, is_v2):
    if is_v2:
        if dir_ext == "": old_file = (default_dir+filename).replace("v2","").replace("v3","")
        else: old_file = (default_dir+dir_ext+"\\"+filename).replace("v2","").replace("v3","")
        if isfile(old_file):
            remove(old_file)
    if dir_ext == "": return isfile(default_dir+filename)
    else: return isfile(default_dir+dir_ext+"\\"+filename)

def queue_request(packnumber, show_name, show_episode):
    printer.x("19»19» Auto-XDCC: Queueing download of {} - {}.".format(show_name, show_episode))
    dl_queue.append((packnumber, show_name, show_episode))

def check_queue():
    global dl_queue, ongoing_dl
    if len(ongoing_dl) < max_concurrent_downloads and dl_queue:
        queue_pop()

def queue_pop():
    global dl_queue
    if dl_queue:
        next_ep = dl_queue.pop()
        if len(next_ep) == 3:
            dl_request(next_ep[0], next_ep[1], next_ep[2])
        else: printer.error("Queued item not correctly formatted: {}".format(str(next_ep)))

def dl_request(packnumber, show_name, show_episode):
    hexchat.command("MSG {} XDCC SEND {}".format(config['current'], packnumber))
    update_show(show_name, show_episode)

def xdcc_refresh_cb(word, word_eol, userdata):
    if len(word) == 1:
        refresh_head()
    elif word[1] == "now":
        refresh_packlist()
    else: printer.error("Malformed request.")
    return hexchat.EAT_ALL

def xdcc_list_transfers_cb(word, word_eol, userdata):
    transfers = hexchat.get_list("dcc")
    if transfers:
        printer.info("Current transfers: ")
        for item in transfers:
            if item.type == 1:
                show, ep = filename2namedEp(item.file)
                perc = (0.0+item.pos)/item.size
                printer.info("Downloading {:.10s} - {} | {:.2f}KB/s @ {:.2%}".format(show, str(ep), item.cps/1024, perc))
                colour = perc/100
                if colour < 0.25: colour = 20
                elif colour < 0.50: colour = 24
                else: colour = 19
                if perc < 10:
                    printer.info("[{}{}]".format(colour, ">".ljust(50)))
                else:
                    printer.info("[{}{}]".format(colour, str("="*((floor(perc/10)*5)-1)+">").ljust(50)))
    else: printer.info("No current transfers.")
    return hexchat.EAT_ALL

def xdcc_forced_recheck_cb(word, word_eol, userdata):
    config['content-length'] = 0
    config['last'] = 0
    config.persist()
    return hexchat.EAT_ALL

def xdcc_last_seen_cb(word, word_eol, userdata):
    printer.info("Last seen pack number is: {}".format(str(config['last'])))
    return hexchat.EAT_ALL

def xdcc_last_used_cb(word, word_eol, userdata):
    printer.info("Last used bot is: {}".format(config['current']))
    return hexchat.EAT_ALL

def xdcc_get_cb(word, word_eol, userdata):
    if len(word) == 3: hexchat.command("MSG {} XDCC SEND {}".format(str(word[1]), str(word[2])))
    else: printer.error("Invalid arguments: \"{}\"".format(str(word[1:])))
    return hexchat.EAT_ALL

def xdcc_show_queue_cb(word, word_eol, userdata):
    global dl_queue
    if dl_queue:
        printer.info("Currently queued downloads:")
        for item in dl_queue:
            if len(item) == 3:
                rprint("{} - {}".format(item[1], item[2]))
            else:
                rprint(item)
    else: printer.info("Queue is empty.")

def clear_finished_cb(word, word_eol, userdata):
    if len(word) == 2 and word[1].lower() in ["on","off"]:
        config['clear'] = word[1].lower()
        config.persist()
        printer.info("Clear finshed downloads toggled {}.".format(word[1].upper()))
    else: printer.error("Malformed request.")
    return hexchat.EAT_ALL

def dcc_msg_block_cb(word, word_eol, userdata):
    if "xdcc send" in word[1].lower():
        return hexchat.EAT_HEXCHAT
    else:
        return hexchat.EAT_NONE

def dcc_snd_offer_cb(word, word_eol, userdata):
    trusted = config['trusted']
    if word[0] in trusted:
        hexchat.emit_print("DCC RECV Connect", word[0], word[3], word[1])
        if "Nipponsei" in word[1]: nprint(word[1],int(word[2]), word[0])
        else: pdprint(word[1], int(word[2]), word[0])
        return hexchat.EAT_HEXCHAT
    else:
        printer.info("DCC Send Offer received but sender {} is not trusted - DCC Offer not accepted.".format(word[0]))
        hexchat.emit_print("DCC RECV Abort", word[0], word[1])
        hexchat.command("MSG " + word[0] + " XDCC CANCEL")
        return hexchat.EAT_ALL

def dcc_rcv_con_cb(word, word_eol, userdata):
    return hexchat.EAT_HEXCHAT

def dcc_cmp_con_cb(word, word_eol, userdata):
    if "Nipponsei" in word[0]: ndprint(word[0], word[3])
    else: dprint(word[0], word[3])
    return hexchat.EAT_ALL

def dcc_rcv_fail_cb(word, word_eol, userdata):
    printer.error("Connection to {} failed, check firewall settings.".format(word[2]))
    hexchat.emit_print("DCC RECV Abort", word[2], word[0])
    hexchat.command("MSG {} XDCC CANCEL".format(word[2]))
    return hexchat.EAT_ALL

def dcc_recv_stall_cb(word, word_eol, userdata):
    if "RECV" in word[0].upper():
        aprint(word[1],word[2])
        return hexchat.EAT_ALL
    else: return hexchat.EAT_NONE

def refresh_timed_cb(userdata):
    refresh_head()
    return True

def dl_timed_cb(userdata):
    check_queue()
    return True

def unloaded_cb(userdata):
    if not int(hexchat.get_prefs('dcc_auto_recv')) == 0:
        hexchat.command("set dcc_auto_recv 0")
    if not int(hexchat.get_prefs('dcc_remove')) == int(default_clear_finished):
        hexchat.command("set dcc_remove "+str(default_clear_finished))
    sleep(0.1)
    pprint("Plugin unloaded.")
    return hexchat.EAT_ALL

def reload_cb(word, word_eol, userdata):
    hexchat.set_pluginpref("plugin_reloaded", 1)
    pprint("Reloading plugin...")
    hexchat.command("timer 1 py reload \"{}\"".format(__module_name__))
    return hexchat.EAT_ALL

def no_show():
    if not config['shows']:
        pprint("No shows added to download list. You may want to add some shows to the list")

hexchat.hook_command("xdcc_refresh", xdcc_refresh_cb, help="/xdcc_refresh refreshes the packlist and checks for new episodes.")
hexchat.hook_command("xdcc_transfers", xdcc_list_transfers_cb, help="/xdcc_transfers lists all currently ongoing transfers.")
hexchat.hook_command("xdcc_queued", xdcc_show_queue_cb, help="/xdcc_queued shows currently queued downloads.")
hexchat.hook_command("xdcc_lastseen", xdcc_last_seen_cb, help="/xdcc_lastseen prints the last seen pack number.")
hexchat.hook_command("xdcc_forcerecheck", xdcc_forced_recheck_cb, help="/xdcc_forcerecheck resets lastseen and forces a recheck of the entire packlist.")
hexchat.hook_command("xdcc_lastused", xdcc_last_used_cb, help="/xdcc_lastused prints the last used bot.")
hexchat.hook_command("xdcc_clearfinished", clear_finished_cb, help="/xdcc_clearfinshed <on|off> decides whether to clear finished downloads from transfer list.")
hexchat.hook_command("xdcc_reload", reload_cb, help="/xdcc_reload reloads the Auto-XDCC plugin.")
hexchat.hook_command("xdcc_get", xdcc_get_cb, help="/xdcc_get <bot> [packs] is a more convenient way to download a specific pack from a bot.")


def boolean_convert(value):
    return value not in ('off', '0', 'false', 'False', 'f')

config = Config.load_from_store()
hexchat.command("set dcc_remove " + config['clear'])

# Show subcommand handlers

def _list_shows(items, t='default'):
    if len(items) == 0:
        if t == 'archive':
            printer.x("No shows archived")
        else:
            printer.x("No shows registered")
        return hexchat.EAT_ALL

    if t == 'archive':
        printer.x("Listing {} archived shows:".format(len(items)))
    else:
        printer.x("Listing {} registered shows:".format(len(items)))

    for show, [episode, resolution, subdir] in items:
        result = "{} @ episode {} | Resolution: {}p".format(show, episode, resolution)
        if subdir:
            printer.list(result + " in subdir " + subdir)
        else:
            printer.list(result)
    return hexchat.EAT_ALL


def listshows_handler(args):
    items = sorted(config['shows'].items())
    return _list_shows(items)


def listarchivedshows_handler(args):
    items = sorted(config['archived'].items())
    return _list_shows(items, 'archive')


def addshow_handler(args):
    resolution = int(args.resolution.strip('p'))
    data = [args.episode, resolution, args.directory]

    config['shows'][args.name] = data
    config.persist()

    result = ''
    if args.episode:
        result = "Added {} @ episode {} in {}p to list.".format(args.name, args.episode, resolution)
    else:
        result = "Added {} in {}p to list.".format(args.name, resolution)

    if args.directory:
        printer.x(result + " Default directory: " + args.directory)
    else:
        printer.x(result)

    return hexchat.EAT_ALL


def updateshow_handler(args):
    show = config['shows'].get(args.name)
    if not show:
        printer.error("No show named: " + args.name)
        return hexchat.EAT_ALL

    [ep, reso, subdir] = show
    if args.episode:
        ep = args.episode
        printer.info("Updated {} episode count to {}.".format(args.name, ep))

    if args.resolution:
        reso = int(args.resolution.strip('p'))
        printer.info("Updated {} resolution to {}.".format(args.name, reso))

    if args.directory:
        if args.directory == '/':
            subdir = ''
            printer.info("Updated {} subdir to main directory.".format(args.name))
        else:
            subdir = args.directory
            printer.info("Updated {} subdir to {}.".format(args.name, subdir))

    config['shows'][args.name] = [ep, reso, subdir]
    config.persist()

    return hexchat.EAT_ALL


def removeshow_handler(args):
    show = config['shows'].get(args.name)
    if not show:
        printer.error("No show named: " + args.name)
        return hexchat.EAT_ALL

    del config['shows'][args.name]
    config.persist()

    if show[0] is not None:
        printer.x("Removed {} at episode {} from list.".format(args.name, show[0]))
    else:
        printer.x("Removed {} from list.".format(args.name))

    return hexchat.EAT_ALL


def archiveshow_handler(args):
    show = config['shows'].get(args.name)
    if not show:
        printer.error("No show named: " + args.name)
        return hexchat.EAT_ALL

    del config['shows'][args.name]
    config['archived'][args.name] = show
    config.persist()

    printer.x("Added {} at episode {} to archive.".format(args.name, show[0]))

    return hexchat.EAT_ALL


def restoreshow_handler(args):
    show = config['archived'].get(args.name)
    if not show:
        printer.error("No show in archive named: " + args.name)
        return hexchat.EAT_ALL

    del config['archived'][args.name]
    config['shows'][args.name] = show
    config.persist()

    printer.x("Restored {} at episode {} from archive.".format(args.name, show[0]))

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
    # TODO: Once the download logic has been (re)implemented, finish this
    if args.type == 'refresh':
        # do refresh timer stuff
        global timed_refresh
        if not boolean_convert(args.state):
            # disable refresh timer
            if timed_refresh is not None: hexchat.unhook(timed_refresh)
            timed_refresh = None
            printer.x("Refresh timer disabled.")
        elif args.interval:
            # enable refresh timer with interval
            timed_refresh = hexchat.hook_timer(args.interval*MS_SECONDS, refresh_timed_cb)
            printer.x("Refresh timer enabled with interval {}s.".format(args.interval))
        else:
            timed_refresh = hexchat.hook_timer(default_refresh_rate, refresh_timed_cb)
            printer.x("Refresh timer enabled with default interval.")

    elif args.type == 'dl':
        # do dl timer stuff
        global timed_dl
        if not boolean_convert(args.state):
            if timed_dl is not None: hexchat.unhook(timed_dl)
            timed_dl = None
            printer.x("Download timer disabled.")
        elif args.interval:
            timed_dl = hexchat.hook_timer(args.interval*MS_SECONDS, dl_timed_cb)
            printer.x("Download timer enabled with interval {}s.".format(args.interval))
        else:
            timed_dl = hexchat.hook_timer(default_dl_rate, dl_timed_cb)
            printer.x("Download timer enabled with default interval.")


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
    parser.add_argument('-r', '--resolution', help='Resolution of episode to download', default='1080p')
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
    parser.add_argument('type', help='Which timer', choices=('refresh', 'dl'))
    parser.add_argument('state', help='State of timer', choices=('on', 'off'))
    parser.add_argument('-i', '--interval', help='Interval to run timer at in seconds', type=int)

    parser.set_defaults(handler=handler)
    return parser

def setter_subparser(parser):
    subparsers = parser.add_subparsers()

    timer_main(subparsers.add_parser('timer'), timer_handler)

    parser.set_defaults(handler=default_handler(parser))
    return parser

def argument_parser():
    parser = argparse.ArgumentParser(prog='/axdcc')

    subparsers = parser.add_subparsers()

    shows_subparser(subparsers.add_parser('show'))
    bots_subparser(subparsers.add_parser('bot'))
    setter_subparser(subparsers.add_parser('set'))

    parser.set_defaults(handler=default_handler(parser))
    return parser


parser = argument_parser()
def axdcc_main_cb(word, word_eol, userdata):
    try:
        args = parser.parse_args(word[1:])
    except:
        return hexchat.EAT_PLUGIN
    return args.handler(args)


hexchat.hook_command('axdcc', axdcc_main_cb, help='/axdcc <command>')

hexchat.hook_print("Message Send", dcc_msg_block_cb)
hexchat.hook_print("DCC SEND Offer", dcc_snd_offer_cb)
hexchat.hook_print("DCC RECV Connect", dcc_rcv_con_cb)
hexchat.hook_print("DCC RECV Complete", dcc_cmp_con_cb)
hexchat.hook_print("DCC RECV Failed", dcc_rcv_fail_cb)
hexchat.hook_print("DCC Stall", dcc_recv_stall_cb)

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

timed_refresh = hexchat.hook_timer(default_refresh_rate, refresh_timed_cb)
timed_dl = hexchat.hook_timer(default_dl_rate, dl_timed_cb)

hexchat.hook_unload(unloaded_cb)

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
