"""
Automagically checks XDCC packlists and downloads new episodes of specified shows.
"""

# pylint: disable=E0401
import hexchat
import requests, threading
import os.path
from json import load, dump
from platform import system as sysplat
from re import sub as rx
from os import getcwd, remove
from os.path import expanduser, isfile
from shutil import move
from time import sleep
from math import floor

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
#   900000 ms = 15 min
default_period = 900000
server_name = "Rizon"
max_concurrent_downloads = 2
#   END OF MODIFIABLE VARIABLES
#--------------------------------------
default_dir = hexchat.get_prefs("dcc_dir")
if default_dir == "":
    hexchat.command("set dcc_dir "+expanduser("~")+"\\Downloads\\")
elif not default_dir[-1:] == "\\":
    default_dir += "\\"
timed_refresh = None
default_clear_finished = hexchat.get_prefs("dcc_remove")
ongoing_dl = {}
dl_queue = []
first_load = True

def get_store_path():
    store_path = hexchat.get_info('configdir')
    if sysplat() == 'Windows':
        store_path += "\\addons\\"
    else:
        store_path += "/addons/"
    return store_path

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

def eprint(line):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None: srv.prnt("18»18» Auto-XDCC: Error - "+str(line))
    else: print("18»18» Auto-XDCC: Error - "+str(line))

def iprint(line):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None: srv.prnt("29»22» Auto-XDCC: INFO - "+str(line))
    else: print("29»22» Auto-XDCC: INFO - "+str(line))

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

def qprint(show_name, show_episode):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None:
        srv.prnt("19»19» Auto-XDCC: Download slots full, putting %s - %s in queue." % (show_name, str(show_episode)))
    else: print("19»19» Auto-XDCC: Download slots full, putting %s - %s in queue." % (show_name, str(show_episode)))

def dprint(filename,time_completed):
    srv = hexchat.find_context(channel=server_name)
    total_ms = int((int(ongoing_dl.pop(filename))/int(time_completed))*1000)
    s, ms = divmod(total_ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)

    show_name, show_ep = filename2namedEp(filename)
    shows = get_shows()
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

    if len(dl_queue) > 0:
        queue_pop()

def ndprint(origFilename,time_completed):
    srv = hexchat.find_context(channel=server_name)
    filename = origFilename.split('_',1)[1].replace("_"," ").rsplit(".",1)[0]
    total_ms = int((int(ongoing_dl.pop(origFilename))/int(time_completed))*1000)
    s, ms = divmod(total_ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)

    try:
        move(default_dir+origFilename, default_dir+"music"+"\\"+origFilename)
    except: pass

    srv.prnt("25»25» Nip-XDCC: Download complete - %s | Completed in %d:%02d:%02d" % (filename, h, m, s))

def aprint(filename,botname):
    srv = hexchat.find_context(channel=server_name)
    lost = ongoing_dl.pop(filename)
    srv.prnt("20»20» Auto-XDCC: Download stalled - %s from %s" % (filename,botname))
    concurrent_dls = len(ongoing_dl)
    if concurrent_dls > 0:
        srv.prnt("19»25» Auto-XDCC: "+str(concurrent_dls)+" download(s) still remain.")

def rprint(line):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None: srv.prnt("7»7» "+str(line))
    else: print("7»7» "+str(line))


def get_store():
    store = {}
    try:
        with open(get_store_path()+'xdcc_store.json', 'r') as f:
            store = load(f)
        hexchat.command("set dcc_remove "+store['clear'])
    except:
        store = {'trusted':["CR-HOLLAND|NEW"], 'shows':{}, 'current':"CR-HOLLAND|NEW", 'last':0, 'content-length':0, 'clear':hexchat.get_prefs("dcc_remove")}
        s_path = get_store_path()
        if not isfile(s_path+'xdcc_store.json'):
            with open(s_path+'xdcc_store.json', 'w') as f:
                dump(store, f)
            eprint("Could not load configuration. New configuration has been created.")
    return store

store = get_store()

def get_shows():
    return store['shows']
def get_trusted():
    return store['trusted']
def get_last_used():
    return store['current']
def get_last_pack():
    return int(store['last'])
def get_last_length():
    return int(store['content-length'])
def get_server_context():
    return hexchat.find_context(channel=server_name)

def set_shows(shows):
    store['shows'] = shows
def set_trusted(nicks):
    store['trusted'] = nicks
def set_last_used(nick):
    store['current'] = nick
def set_last_pack(num):
    store['last'] = num
def set_last_length(num):
    store['content-length'] = num
def set_clear_toggle(tog):
    store['clear'] = tog

def update_show(show, episode):
    shows = get_shows()
    shows[show][0] = int(episode)
    set_shows(shows)

def save_config():
    with open(get_store_path()+'xdcc_store.json', 'w') as f:
        dump(store, f)

def refresh_head():
    try:
        r = requests.head(p_url, timeout=5)
        if int(r.headers['content-length']) > get_last_length()+30:
            refresh_packlist()
            set_last_length(int(r.headers['content-length']))
            save_config()
    except Exception as e:
        eprint(e)

def refresh_packlist():
    previously_last_seen_pack = get_last_pack()
    latest_pack = "1"
    trusted = get_trusted()
    shows = get_shows()
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
                                iprint("This episode has more than one part, you may have to download manually.")
                            p_res = p_full[1].split(" ")[1].split(".")[0]
                        else:
                            eprint("Something doesn't seem quite right with the format of the file name.\n\t"+str(p_full))

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
            set_last_pack(previously_last_seen_pack)
            save_config()
        else:
            eprint("Packlist has been reset and needs to be re-checked. Current: "+latest_pack+" | old: "+str(previously_last_seen_pack))
            set_last_pack(0)
            save_config()
            refresh_packlist()
    except Exception as e:
        eprint(e)

def if_file(filename, dir_ext, is_v2):
    if is_v2:
        if dir_ext == "": old_file = (default_dir+filename).replace("v2","").replace("v3","")
        else: old_file = (default_dir+dir_ext+"\\"+filename).replace("v2","").replace("v3","")
        if isfile(old_file):
            remove(old_file)
    if dir_ext == "": return isfile(default_dir+filename)
    else: return isfile(default_dir+dir_ext+"\\"+filename)

def queue_request(packnumber, show_name, show_episode):
    if len(ongoing_dl) >= max_concurrent_downloads:
        qprint(show_name, show_episode)
        dl_queue.append((packnumber, show_name, show_episode))
    else:
        dl_request(packnumber, show_name, show_episode)

def queue_pop():
    next_ep = dl_queue.pop(0)
    dl_request(next_ep[0], next_ep[1], next_ep[2])

def dl_request(packnumber, show_name, show_episode):
    hexchat.command("MSG " + get_last_used() + " XDCC SEND " + packnumber)
    update_show(show_name, show_episode)

def xdcc_refresh_cb(word, word_eol, userdata):
    if len(word) == 1:
        refresh_head()
    elif word[1] == "now":
        refresh_packlist()
    else: eprint("Malformed request.")
    return hexchat.EAT_ALL

def xdcc_list_transfers_cb(word, word_eol, userdata):
    transfers = hexchat.get_list("dcc")
    if transfers:
        iprint("Current transfers: ")
        for item in transfers:
            if item.type == 1:
                show, ep = filename2namedEp(item.file)
                perc = round((item.pos/item.size)*100)
                iprint("Downloading %10s - %s | %.2fKB/s @ %d%%" % (show, str(ep), item.cps/1024, perc))
                colour = perc/100
                if colour < 0.25: colour = 20
                elif colour < 0.50: colour = 24
                else: colour = 19
                if perc < 10:
                    iprint("[%d%s]" % (colour, ">".ljust(50)))
                else:
                    iprint("[%d%s]" % (colour, str("="*((floor(perc/10)*5)-1)+">").ljust(50)))
    else: iprint("No current transfers.")
    return hexchat.EAT_ALL

def xdcc_list_shows_cb(word, word_eol, userdata):
    shows = get_shows()
    pprint("Listing registered shows:")
    for show, epresdir in sorted(shows.items()):
        if epresdir[3] is not "a":
            if epresdir[2]:
                print("  18»  "+show+" @ episode "+str(epresdir[0])+" | Resolution: "+str(epresdir[1])+"p"+" in subdir "+epresdir[2])
            else:
                print("  18»  "+show+" @ episode "+str(epresdir[0])+" | Resolution: "+str(epresdir[1])+"p")
    return hexchat.EAT_ALL

def xdcc_list_archived_cb(word, word_eol, userdata):
    shows = get_shows()
    pprint("Listing archived shows:")
    for show, epresdir in sorted(shows.items()):
        if epresdir[3] is "a":
            if epresdir[2]:
                print("  18»  "+show+" ("+str(epresdir[0])+" episodes in "+str(epresdir[1])+"p)"+" in subdir "+epresdir[2])
            else:
                print("  18»  "+show+" ("+str(epresdir[0])+" episodes in "+str(epresdir[1])+"p)")
    return hexchat.EAT_ALL

def xdcc_add_show_cb(word, word_eol, userdata):
    shows = get_shows()
    if len(word) == 4:
        name, ep, res = word[1], word[2], word[3].strip("p")
        shows[name] = [int(ep), int(res), "", "o"]
        pprint("Added "+name+" @ episode "+str(ep)+" in "+str(res)+"p to list.")
        set_shows(shows)
        save_config()
    elif len(word) > 4:
        length = len(word)
        try:
            res = int(word[length-1].strip("p"))
            ep = int(word[length-2])
            positional = 2
            def_dir = ""
        except:
            ep, res = word[length-3], word[length-2].strip("p")
            positional = 3
            def_dir = word[length-1]
        name = ""
        i = 1
        while i < length-positional:
            name += word[i]
            if i != length-(positional+1): name += " "
            i += 1
        shows[name] = [int(ep), int(res), def_dir, "o"]
        if def_dir:
            pprint("Added "+name+" @ episode "+str(ep)+" in "+str(res)+"p to list. Default directory: "+str(def_dir))
        else:
            pprint("Added "+name+" @ episode "+str(ep)+" in "+str(res)+"p to list.")
        set_shows(shows)
        save_config()
    else: eprint("Malformed request.")
    return hexchat.EAT_ALL

def xdcc_remove_show_cb(word, word_eol, userdata):
    shows = get_shows()
    if len(word) >= 2:
        del_epres = shows.pop(word_eol[1], None)
        if not del_epres is None:
            pprint("Removed "+word_eol[1]+" at episode "+str(del_epres[0])+" from list.")
            set_shows(shows)
            save_config()
    else: eprint("Malformed request.")
    return hexchat.EAT_ALL

def xdcc_update_show_cb(word, word_eol, userdata):
    if len(word) < 3:
        eprint("Argument error: Too few arguments.")
    else:
        shows = get_shows()
        editable = word[len(word)-1]
        if len(word) == 3:
            this_show = word[1]
        else:
            this_show = ""
            for i in range(1,len(word)-1):
                this_show += word[i]+" "
            this_show = this_show.rstrip()
        if this_show in shows:
            try:
                if int(editable) in [480,720,1080]:
                    shows[this_show][1] = int(editable)
                    iprint("Updated "+this_show+" resolution to "+str(editable)+".")
                else:
                    shows[this_show][0] = int(editable)
                    iprint("Updated "+this_show+" episode count to "+str(editable)+".")
            except:
                if editable is '/':
                    shows[this_show][2] = ""
                    iprint("Updated "+this_show+" subdir to main directory.")
                else:
                    shows[this_show][2] = editable
                    iprint("Updated "+this_show+" subdir to "+str(editable)+".")
            set_shows(shows)
            save_config()
        else:
            eprint("Show not in list or mispelled (\""+this_show+"\"). Add show first before making changes to it.")

    return hexchat.EAT_ALL

def xdcc_archive_show_cb(word, word_eol, userdata):
    if len(word) < 2:
        eprint("Argument error: Must name a show to archive.")
    else:
        shows = get_shows()
        if len(word) == 2: this_show = word[1]
        else: this_show = word_eol[1]
        if this_show in shows:
            if shows[this_show][3] in ["o","O"]:
                shows[this_show][3] = "a"
                iprint("Show "+this_show+" is now set to archived.")
                set_shows(shows)
                save_config()
            elif shows[this_show][3] in ["a","A"]:
                eprint("Show "+this_show+" has already been archived.")
        else: eprint("Show not in list or mispelled (\""+this_show+"\").")
    return hexchat.EAT_ALL

def xdcc_unarchive_show_cb(word, word_eol, userdata):
    if len(word) < 2:
        eprint("Argument error: Must name a show to de-archive.")
    else:
        shows = get_shows()
        if len(word) == 2: this_show = word[1]
        else: this_show = word_eol[1]
        if this_show in shows:
            if shows[this_show][3] in ["a","A"]:
                shows[this_show][3] = "o"
                iprint("Show "+this_show+" is now set to ongoing.")
                set_shows(shows)
                save_config()
            elif shows[this_show][3] in ["o","O"]:
                eprint("Show "+this_show+" already set to ongoing.")
        else: eprint("Show not in list or mispelled (\""+this_show+"\").")
    return hexchat.EAT_ALL

def change_directory_cb(word, word_eol, userdata):
    shows = get_shows()
    return hexchat.EAT_ALL

def xdcc_forced_recheck_cb(word, word_eol, userdata):
    set_last_length(0)
    set_last_pack(0)
    save_config()
    return hexchat.EAT_ALL

def xdcc_last_seen_cb(word, word_eol, userdata):
    iprint("Last seen pack number is: "+str(get_last_pack()))
    return hexchat.EAT_ALL

def xdcc_last_used_cb(word, word_eol, userdata):
    iprint("Last used bot is: "+get_last_used())
    return hexchat.EAT_ALL

def xdcc_trusted_cb(word, word_eol, userdata):
    pprint("List of trusted bots:")
    for nick in sorted(get_trusted()):
        print("\t"+nick)
    return hexchat.EAT_ALL

def xdcc_set_bot_cb(word, word_eol, userdata):
    if len(word) == 2 and word[1] in get_trusted():
        set_last_used(word[1])
        pprint(word[1]+" set as default bot.")
        save_config()
    else: eprint("Either malformed request or nick is not trusted.")
    return hexchat.EAT_ALL

def xdcc_add_trusted_cb(word, word_eol, userdata):
    trusted = get_trusted()
    if len(word) == 2 and word[1] not in trusted:
        trusted.append(word[1])
        pprint(word[1]+" is now trusted.")
        set_trusted(trusted)
        save_config()
    else: eprint("Malformed request.")
    return hexchat.EAT_ALL

def xdcc_remove_trusted_cb(word, word_eol, userdata):
    trusted = get_trusted()
    if len(word) == 2 and word[1] in trusted:
        trusted.remove(word[1])
        pprint(word[1]+" is no longer trusted.")
        set_trusted(trusted)
        save_config()
    else: eprint("Malformed request.")
    return hexchat.EAT_ALL

def xdcc_get_cb(word, word_eol, userdata):
    if len(word) == 3: hexchat.command("MSG " + str(word[1]) + " XDCC SEND " + str(word[2]))
    else: eprint("Invalid arguments: \""+str(word[1:])+"\"")
    return hexchat.EAT_ALL

def xdcc_show_queue_cb(word, word_eol, userdata):
    if dl_queue:
        print("Currently queued downloads:")
        for item in dl_queue:
            if len(item) == 3:
                print("{} - {}".format(item[1], item[2]))
            else:
                print(item)

def clear_finished_cb(word, word_eol, userdata):
    if len(word) == 2 and word[1].lower() in ["on","off"]:
        set_clear_toggle(word[1])
        iprint("Clear finshed downloads toggled "+word[1].upper()+".")
        save_config()
    else: eprint("Malformed request.")
    return hexchat.EAT_ALL

def dcc_msg_block_cb(word, word_eol, userdata):
    if "xdcc send" in word[1].lower():
        #pprint("Requesting pack "+str(word[1].rsplit(" ",1)[1])+" from "+str(word[0])+".")
        return hexchat.EAT_HEXCHAT
    else:
        return hexchat.EAT_NONE

def dcc_snd_offer_cb(word, word_eol, userdata):
    trusted = get_trusted()
    if word[0] in trusted:
        hexchat.emit_print("DCC RECV Connect", word[0], word[3], word[1])
        if "Nipponsei" in word[1]: nprint(word[1],int(word[2]), word[0])
        else: pdprint(word[1], int(word[2]), word[0])
        return hexchat.EAT_HEXCHAT
    else:
        iprint("DCC Send Offer received but sender "+word[0]+" is not trusted - DCC Offer not accepted.")
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
    eprint("Connection to {} failed, check firewall settings.".format(word[2]))
    hexchat.emit_print("DCC RECV Abort", word[2], word[0])
    hexchat.command("MSG {} XDCC CANCEL".format(word[2]))
    return hexchat.EAT_ALL

def dcc_recv_stall_cb(word, word_eol, userdata):
    if "RECV" in word[0].upper():
        aprint(word[1],word[2])
        return hexchat.EAT_ALL
    else: return hexchat.EAT_NONE

def print_info_cb(word, word_eol, userdata):
    iprint("Last seen pack number was: "+str(get_last_pack()))
    return hexchat.EAT_ALL

def stopstart_timed_cb(word, word_eol, userdata):
    global timed_refresh
    if timed_refresh is not None and word[1] == "stop":
        hexchat.unhook(timed_refresh)
        timed_refresh = None
        iprint("Periodic refresh disabled.")
    elif timed_refresh is None and word[1] == "start":
        timed_refresh = hexchat.hook_timer(default_period, timed_cb)
        iprint("Periodic refresh enabled. ("+str(int(default_period/60000))+" minutes)")
    return hexchat.EAT_ALL

def change_timer_cb(word, word_eol, userdata):
    global timed_refresh
    if timed_refresh is not None and len(word) == 2:
        try:
            hexchat.unhook(timed_refresh)
            new_timer = int(word[1])*60000
            timed_refresh = hexchat.hook_timer(new_timer, timed_cb)
            iprint("Timer set to "+str(new_timer)+" minutes.")
        except:
            eprint("Timer not running or malformed request.")
        return hexchat.EAT_ALL

def timed_cb(userdata):
    refresh_head()
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
    if get_shows() == {}:
        pprint("No shows added to download list. You may want to add some shows to the list")

hexchat.hook_command("xdcc_refresh", xdcc_refresh_cb, help="/xdcc_refresh refreshes the packlist and checks for new episodes.")
hexchat.hook_command("xdcc_transfers", xdcc_list_transfers_cb, help="/xdcc_transfers lists all currently ongoing transfers.")
# hexchat.hook_command("xdcc_queued", xdcc_show_queue_cb, help="/xdcc_queued shows currently queued downloads.")
hexchat.hook_command("xdcc_shows", xdcc_list_shows_cb, help="/xdcc_shows lists all currently registered shows.")
hexchat.hook_command("xdcc_archived", xdcc_list_archived_cb, help="/xdcc_archived lists all previously archived shows.")
hexchat.hook_command("xdcc_addshow", xdcc_add_show_cb, help="/xdcc_addshow <name> <last episode> <resolution> <directory> adds specified show to the list. Custom directory is optional.")
hexchat.hook_command("xdcc_removeshow", xdcc_remove_show_cb, help="/xdcc_removeshow <name> removes specified show from list.")
hexchat.hook_command("xdcc_updateshow", xdcc_update_show_cb, help="/xdcc_updateshow <name> <episode|resolution|directory> manually updates the specified show's episode count, resolution or directory.")
hexchat.hook_command("xdcc_archiveshow", xdcc_archive_show_cb, help="/xdcc_archiveshow <name> sets the specified show to archived.")
hexchat.hook_command("xdcc_unarchiveshow", xdcc_unarchive_show_cb, help="/xdcc_unarchiveshow <name> sets the specified show to ongoing, removing it from the archive.")
hexchat.hook_command("xdcc_lastseen", xdcc_last_seen_cb, help="/xdcc_lastseen prints the last seen pack number.")
hexchat.hook_command("xdcc_forcerecheck", xdcc_forced_recheck_cb, help="/xdcc_forcerecheck resets lastseen and forces a recheck of the entire packlist.")
# hexchat.hook_command("xdcc_lastused", xdcc_last_used_cb, help="/xdcc_lastused prints the last used bot.")
hexchat.hook_command("xdcc_trusted", xdcc_trusted_cb, help="/xdcc_trusted lists all currently trusted nicks.")
# hexchat.hook_command("xdcc_setbot", xdcc_set_bot_cb, help="/xdcc_set_bot <nick> sets nick to default if nick is trusted.")
hexchat.hook_command("xdcc_addtrusted", xdcc_add_trusted_cb, help="/xdcc_add_trusted <nick> adds nick to list of trusted nicks")
hexchat.hook_command("xdcc_removetrusted", xdcc_remove_trusted_cb, help="/xdcc_remove_trusted <nick> removes nick from the list of trusted nicks.")
hexchat.hook_command("xdcc_timer", stopstart_timed_cb, help="/xdcc_timer <start|stop> starts or stops the periodic XDCC packlist refresh.")
hexchat.hook_command("xdcc_changetimer", change_timer_cb, help="/xdcc_changetimer <time> sets the periodic timer to <time> minutes.")
hexchat.hook_command("xdcc_changedirectory", change_directory_cb, help="/xdcc_changedirectory <name> <directory> changes the directory of one show.")
hexchat.hook_command("xdcc_clearfinished", clear_finished_cb, help="/xdcc_clearfinshed <on|off> decides whether to clear finished downloads from transfer list.")
# hexchat.hook_command("xdcc_info", print_info_cb, help="/xdcc_info prints some potentially relevant information. Currently only last seen pack number.")
hexchat.hook_command("xdcc_reload", reload_cb, help="/xdcc_reload reloads the Auto-XDCC plugin.")
hexchat.hook_command("xdcc_get", xdcc_get_cb, help="/xdcc_get <bot> [packs] is a more convenient way to download a specific pack from a bot.")

import sys

# Add addons folder to path to detect auto_xdcc module
sys.path.append(os.path.join(hexchat.get_info('configdir'), 'addons'))

import auto_xdcc.argparse as argparse

import auto_xdcc.printer as printer
from auto_xdcc.config import Config

config = Config.load_from_store()

def listshows_handler(args):
    printer.x("Listing registered shows:")
    items = sorted(config['shows'].items())
    for show, [episode, resolution, subdir] in items:
        result = "{} @ episode {} | Resolution: {}p".format(show, episode, resolution)
        if subdir:
            printer.list(result + " in subdir " + subdir)
        else:
            printer.list(result)
    printer.x("{} shows in list".format(len(items)))
    return hexchat.EAT_ALL

def addshow_handler(args):
    if not args.name:
        return hexchat.EAT_ALL

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

def default_handler(args):
    return hexchat.EAT_ALL


def show_main(parser, handler):
    parser.add_argument('name', help='Full name of the show')
    parser.set_defaults(handler=handler)
    return parser

def show_options(parser):
    parser.add_argument('-r', '--resolution', help='Resolution of episode to download', default='1080p')
    parser.add_argument('-e', '--episode', help='Episode number to start downloading from', type=int)
    parser.add_argument('-d', '--directory', help='Custom directory to download to')
    return parser


def shows_subparser(parser):
    subparsers = parser.add_subparsers()

    list_parser = subparsers.add_parser('list')
    list_parser.set_defaults(handler=listshows_handler)

    show_options(show_main(subparsers.add_parser('add'), addshow_handler))
    # show_options(show_main(subparsers.add_parser('update')))
    # show_main(subparsers.add_parser('remove'))
    # show_main(subparsers.add_parser('archive'))
    # show_main(subparsers.add_parser('restore'))

    parser.set_defaults(handler=default_handler)
    return parser

def argument_parser():
    parser = argparse.ArgumentParser(prog='/axdcc')
    subparsers = parser.add_subparsers()
    shows_subparser(subparsers.add_parser('show'))

    parser.set_defaults(handler=default_handler)
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

timed_refresh = hexchat.hook_timer(default_period, timed_cb)

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
