"""
Automagically checks XDCC packlists and downloads new episodes of specified shows.
"""

# pylint: disable=E0401
import hexchat
import os.path
import sys
import shutil
import logging
from time import sleep

# Add addons folder to path to detect auto_xdcc module
sys.path.append(os.path.join(hexchat.get_info('configdir'), 'addons'))

import auto_xdcc.argparse as argparse
# Best import error "solution" hue
# pylint: disable=E0611
import auto_xdcc.download_manager as dm
import auto_xdcc.config
from auto_xdcc.printer import Printer, HexchatPrinter, TelegramBotPrinter
from auto_xdcc.packlist_manager import PacklistManager
from auto_xdcc.packlist_item import PacklistItem
from auto_xdcc.timer import Timer
from auto_xdcc.telegram_bot import TelegramBot


__module_name__ = "Auto-XDCC Downloader"
__module_version__ = "3.3.4"
__module_description__ = "Automagically checks XDCC packlists and downloads new episodes of specified shows."
__author__ = "Oosran, Chronoes"


printer = Printer()
hexchat_printer = HexchatPrinter()
printer.add_listener(hexchat_printer)


if hexchat.get_pluginpref("plugin_reloaded") == 1:
    printer.info("Plugin reloaded.")
    hexchat.set_pluginpref("plugin_reloaded", 0)

default_dir = hexchat.get_prefs("dcc_dir")
if default_dir == "":
    hexchat.command("set dcc_dir " + os.path.join(os.path.expanduser("~"), "Downloads"))

if int(hexchat.get_prefs('dcc_auto_recv')) != 2:
    hexchat.command("set dcc_auto_recv 2")

default_clear_finished = hexchat.get_prefs("dcc_remove")


def boolean_convert(value):
    return value not in ('off', '0', 'false', 'False', 'f')

def addons_path(*args):
    return os.path.join(hexchat.get_info('configdir'), 'addons', *args)

try:
    config = auto_xdcc.config.initialize(addons_path('xdcc_store.json'))
except Exception as e:
    printer.error(str(e))

config.printer = printer
hexchat.command("set dcc_remove " + config['clear'])

logging.basicConfig(
    filename=addons_path('axdcc.log'),
    level=logging.INFO,
    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s',
)
logging.raiseExceptions = False

packlist_manager = PacklistManager()
packlist_manager.register_packlists()
config.packlist_manager = packlist_manager

def printing_callback(userdata=None):
    printer.flush()
    return True

printing_timer = Timer(200, printing_callback)
printing_timer.register()


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

    logger = logging.getLogger('dcc_send_offer')
    logger.debug("DCC Offer received: Bot: %s (%s) File: %s (%s)", bot_name, ip_addr, filename, size)

    packlist = packlist_manager.get_packlist_by(filename)
    if not packlist:
        logger.warning("No matching request found: Bot: %s (%s) File: %s (%s)", bot_name, ip_addr, filename, size)
        return hexchat.EAT_NONE

    state, item = packlist.download_manager.send_offer_callback(bot_name, filename, int(size), ip_addr)
    if not item:
        logger.warning("No matching request found: Bot: %s (%s) File: %s (%s)", bot_name, ip_addr, filename, size)
        return hexchat.EAT_NONE

    logger.debug("DCC Offer accepted: Bot: %s (%s) File: %s (%s)", bot_name, ip_addr, filename, size)

    if state == dm.DOWNLOAD_ABORT:
        logger.warning("DCC Offer rejected from: %s (%s)", bot_name, ip_addr)
        printer.info("DCC Send Offer received but sender {} is not trusted - DCC Offer not accepted.".format(bot_name))
        return hexchat.EAT_ALL

    if type(item) == PacklistItem:
        filesize, size_ext = _format_filesize(int(size))
        printer.prog("Downloading {} - {:02d} ({} {}) from {}...".format(item.show_name, item.episode_nr, filesize, size_ext, bot_name))
    printer.flush()
    return hexchat.EAT_HEXCHAT

def dcc_recv_connect_cb(word, word_eol, userdata):
    [bot_name, ip_addr, filename] = word
    logger = logging.getLogger('dcc_recv_connect')
    logger.debug("DCC RECV connect: %s (%s) %s", bot_name, ip_addr, filename)
    printer.flush()
    return hexchat.EAT_HEXCHAT

def dcc_recv_complete_cb(word, word_eol, userdata):
    [filename, _destination, _bot_name, time_spent] = word

    logger = logging.getLogger('dcc_recv_complete')
    logger.debug("DCC RECV complete: %s", filename)

    packlist = packlist_manager.get_packlist_by(filename)

    if not packlist:
        logger.error("Could not find a match for %s", filename)
        return hexchat.EAT_NONE

    if packlist.download_manager.is_ongoing(filename):
        item, size = packlist.download_manager.recv_complete_callback(filename)
    else:
        logger.error("Could not find a match for %s", filename)
        return hexchat.EAT_NONE

    if type(item) == PacklistItem:
        total_ms = int(size / int(time_spent) * 1000)
        s = int(total_ms / 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)

        [prev_episode_nr, _resolution, subdir] = config['shows'][item.show_name]
        try:
            if subdir:
                shutil.move(os.path.join(default_dir, filename), os.path.join(default_dir, subdir, filename))
        except:
            pass

        if prev_episode_nr is None or item.episode_nr > prev_episode_nr:
            config['shows'][item.show_name][0] = item.episode_nr
            config.persist()

        printer.complete("Download complete - {} - {:02d} | Completed in {}:{:02}:{:02}".format(item.show_name, item.episode_nr, h, m, s))
        printer.x("{} downloads remaining.".format(
            packlist.download_manager.count_awaiting() + packlist.download_manager.count_ongoing()
        ))

    printer.flush()
    return hexchat.EAT_ALL

def dcc_recv_failed_cb(word, word_eol, userdata):
    [filename, _destination, bot_name, error] = word

    logger = logging.getLogger('dcc_recv_failed')
    logger.debug("DCC RECV failed: %s %s", bot_name, filename)

    packlist = packlist_manager.get_packlist_by(filename)

    if not packlist:
        logger.error("Could not find a match for %s", filename)
        return hexchat.EAT_NONE

    if packlist.download_manager.is_ongoing(filename):
        packlist.download_manager.download_abort(bot_name, filename)
        logger.info("Aborting download of %s", filename)
    else:
        logger.error("Could not find a match for %s", filename)
        return hexchat.EAT_NONE

    logger.error("Connection failed: %s. Error: %s", bot_name, error)
    printer.error("Connection to {} failed, check firewall settings. Error: {}".format(bot_name, error))
    printer.flush()
    return hexchat.EAT_ALL

hexchat.hook_print("Message Send", dcc_msg_block_cb)
hexchat.hook_print("DCC SEND Offer", dcc_send_offer_cb)
hexchat.hook_print("DCC RECV Connect", dcc_recv_connect_cb)
hexchat.hook_print("DCC RECV Complete", dcc_recv_complete_cb)
hexchat.hook_print("DCC RECV Failed", dcc_recv_failed_cb)

if 'telegram' in config['credentials']:
    telegram_bot = TelegramBot.init_from_config(config)
    bot_printer = TelegramBotPrinter(telegram_bot)
    telegram_bot.set_parser(argparse.create_argument_parser(bot_printer, prog=''))
    config.printer.add_listener(bot_printer)
    config.telegram_bot = telegram_bot

hexchat_parser = argparse.create_argument_parser(hexchat_printer)

def axdcc_main_cb(word, word_eol, userdata):
    try:
        args = hexchat_parser.parse_args(word[1:])
    except Exception:
        return hexchat.EAT_ALL
    return_code = args.handler(args)
    if return_code:
        return return_code

    return hexchat.EAT_ALL


hexchat.hook_command('axdcc', axdcc_main_cb, help=hexchat_parser.format_usage())

def reload_cb(word, word_eol, userdata):
    hexchat.set_pluginpref("plugin_reloaded", 1)
    hexchat_parser.printer.info("Reloading plugin...")
    hexchat.command("timer 1 py reload \"{}\"".format(__module_name__))
    return hexchat.EAT_ALL

hexchat.hook_command("axdcc_reload", reload_cb, help="/axdcc_reload reloads the Auto-XDCC plugin.")


def unloaded_cb(userdata):
    # Force close running threads
    for packlist in packlist_manager.packlists.values():
        packlist.download_manager.terminate(True)

    if config.telegram_bot:
        config.telegram_bot.terminate(True)

    if int(hexchat.get_prefs('dcc_auto_recv')) != 0:
        hexchat.command("set dcc_auto_recv 0")
    if int(hexchat.get_prefs('dcc_remove')) != int(default_clear_finished):
        hexchat.command("set dcc_remove " + str(default_clear_finished))
    sleep(0.1)
    hexchat_parser.printer.x("Plugin unloaded")

    return hexchat.EAT_ALL

hexchat.hook_unload(unloaded_cb)
