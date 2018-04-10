import hexchat
import requests
from re import sub as rx

__module_name__ = "Nip-XDCC Downloader"
__module_version__ = "0.1"
__module_description__ = "Handles the Nipponsei music packlist. Works in tandem with the Auto-XDCC Downloader plugin."
__author__ = "Oosran"

#--------------------------------------
#	START OF MODIFIABLE VARIABLES
#       This is the URL of a relevant XDCC packlist.
p_url = "https://nipponsei.minglong.org/packlist/distro/"
server_name = "Rizon"
#   END OF MODIFIABLE VARIABLES
#--------------------------------------

def pprint(line):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None: srv.prnt("26»28» Nip-XDCC: "+str(line))
    else: print("26»28» Nip-XDCC: "+str(line))

def nprint(line):
    srv = hexchat.find_context(channel=server_name)
    if not srv == None: srv.prnt("  18»  "+str(line))
    else: print("  18»  "+str(line))

def get_list_cb(word, word_eol, userdata):
    r = requests.get(p_url)
    rs = [l for l in r.text.split("<td>") if not l.startswith('<')]
    rs = [l for l in rs if "zip" in l or '#' in l]
    rs = [l.split('<')[0] for l in rs]
    rs = [l.replace('\n',' ') for l in rs if l]
    i = 0
    rf = []
    while i < len(rs)-1:
        rf.append(rs[i]+' '+rs[i+1])
        i += 2

    pprint('Listing Nippon|minglong packlist')
    for l in rf:
        nprint(l)

    return hexchat.EAT_ALL

def reload_cb(word, word_eol, userdata):
    hexchat.set_pluginpref("nip_plugin_reloaded", 1)
    pprint("Reloading plugin...")
    hexchat.command("timer 1 py reload nipponsei_xdcc.py")
    return hexchat.EAT_ALL

hexchat.hook_command("nip_list", get_list_cb, help="/nip_list prints the current bot packlist.")
hexchat.hook_command("nip_reload", reload_cb, help="/nip_reload reloads the Nip-XDCC plugin.")

if not int(hexchat.get_prefs('dcc_auto_recv')) == 2:
    hexchat.command("set dcc_auto_recv 2")

if hexchat.get_pluginpref("nip_plugin_reloaded") == 1:
    pprint("Nip-XDCC plugin reloaded.")
    hexchat.set_pluginpref("nip_plugin_reloaded", 0)

# 24»23» Brown mode code
# 28»18» cyan/blue server message code