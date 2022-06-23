"""
Automagically checks XDCC packlists and downloads new episodes of specified shows.
"""

# pylint: disable=E0401
import hexchat
import os
import os.path
import sys
import shutil
import logging
import re
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

if hexchat.get_prefs("dcc_dir") == "":
    hexchat.command("set dcc_dir " + os.path.join(os.path.expanduser("~"), "Downloads"))

hexchat.set_pluginpref("dcc_auto_recv_save", hexchat.get_prefs('dcc_auto_recv')) # we save it always, to always restore it, # TODO make submodule for handling settings and saving, modifying of those!
if int(hexchat.get_prefs('dcc_auto_recv')) != 2: # desired is 2, but if its not that, we save it and then restore it later!
    hexchat.command("set dcc_auto_recv 2")
# TODO migrate to settings.py
default_clear_finished = hexchat.get_prefs("dcc_remove") # here we reset it only to uer default at the end, we maybe have to change it other places (for auto downloads)


def boolean_convert(value):
    return value not in ('off', '0', 'false', 'False', 'f')

def addons_path(*args):
    return os.path.join(hexchat.get_info('configdir'), 'addons', *args)

try:
    config = auto_xdcc.config.initialize(addons_path('xdcc_store.json'))
except Exception as e:
    printer.error(str(e))

config.printer = printer
hexchat.command("set dcc_remove " + (config['clear'] if config['clear'] == "off" or config['clear'] == "on" else "on")) # check for invalid user input

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
                src_dir = dm.get_dcc_completed_dir()
                target_dir = os.path.join(src_dir, subdir)
                if not os.path.exists(target_dir):
                    os.mkdir(target_dir, mode=0o755)

                shutil.move(os.path.join(src_dir, filename), os.path.join(target_dir, filename))
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


# helper class to set a string to the input, it takes care of executing the right commands  and also eventually offsetting the cursor
def hexchat_set_input(string, additional_cursor_offset = 0):
    hexchat.command("SETTEXT {}".format(string))
    hexchat.command("SETCURSOR {}".format(len(string)+ additional_cursor_offset))


# regex helper, it tries to match a regex, if it fails for some reason, it doesn't fail, or throw an Exception, but rather the returned value will reflect that, return type:
# [is_error: boolean, result : None or Array, error: Exception or None]
def try_regex_or_none(input, regex_string):
    try:
        result = re.findall(regex_string, str(input)) 
        return [False, result, None]
    except Exception as exception:
        return [True, None, exception]

#parse suggestions, it just pareses the format their in into a more suitable format
def parse_suggestions(unparsed_suggestions):
    def lambda_fn(x):
        return x.strip().replace("'","")

    parsed_suggestions =  list(map(lambda_fn, unparsed_suggestions.split(",")))
    return parsed_suggestions


# gets suggestions, every error is handled internally, 
# it also parses the return type, or at least tries it!
# the return type is:
# [type : string, ...rest : according to type]
# available types:
# "normal": [given_string: string, parses_suggestions: String List]
# "args": [required_args : String List]
# "arg_count" : [received_args_count : number, needed_args_count]
def get_suggestions_from_string(input_string):
    possibleFormats = [[0,"^usage:.*\[?.*\]?\{(.*)\} \.\.\.$"], [1,"invalid choice: '(.*)' \(choose from (.*)\)$"], [2,"^the following arguments are required: (.*)$"],[3,".* takes (\d*) positional argument but (\d*) were given"]]
    for [number, possibleFormat] in possibleFormats:
        [has_error, result, error] = try_regex_or_none(input_string, possibleFormat)
        if has_error:
            raise Exception(error)
        

        if len(result) == 0: 
            continue

        [matches] = result
        # the first regex, it only has one capture group, since no command was given (alias  an empty string '')
        if len(matches) == 0: 
            continue

        printer.info("result {}, matches {}".format(result,matches))
        match number:
            case 0:                
                unparsed_suggestions = matches
                parsed_suggestions =  parse_suggestions(unparsed_suggestions)
                return ["normal","",parsed_suggestions] 
            case 1:
                (given, unparsed_suggestions) = matches
                parsed_suggestions =  parse_suggestions(unparsed_suggestions)
                return ["normal", given, parsed_suggestions] 
            case 2:
                (unparsed_required_args) = matches
                required_args = unparsed_required_args.split(",")
                return ["args",required_args] 
            case 3:
                (received_args_count, needed_args_count) = matches
                return ["arg_count", received_args_count, needed_args_count] 
            case _: 
                raise Exception("NOT implemented, report this, this is an internal Bug")


# gets the suggestions, from invoking the parser and getting the suggestions from that string
# return type: [given : String, parsed_suggestions : String Tuple, complete: boolean]
# complete say, if this command is complete, meaning all words are ok, and you have to add a " " to get to add a new argument
def get_current_parser_output(to_parse, is_recursive = False):
        try:
            args = parser.parse_args(to_parse)
            # get suggestions for next command(s)
            usage = args.handler(args,True)
            # python spread is * instead of ..., wtf
            return [*get_suggestions_from_string(usage), True]
        except Exception as exception:
            suggestions = get_suggestions_from_string(str(exception))
            # if the error is not parsable, retry it with an extra "", namely a " " at the end
            if suggestions is None:
                if is_recursive:
                    return ["nothing", None, None, None]
                new_result = get_current_parser_output([*to_parse,""], True)
                if new_result is None:
                    return ["normal",None, None, True]
                return [new_result[0], new_result[1], True]
            return [*suggestions, False]

# helper function, to have identical suggestions for all suggestions that are emited
def hexchat_suggest(suggesting_array):
    print('Suggestions: '+ ' '.join(list(map(lambda x: x.upper(),suggesting_array))))

# Key press Parser, it handles only Tabs, and tries to autocomplete them
# According to https://hexchat.readthedocs.io/en/latest/script_python.html?highlight=Key%20Press#hexchat.hook_print
def key_press_cb(word , word_eol, userdata):
    key_value = word[0]
    state_bitfiled = word[1] # Bit field with ALt + Ctrl + Shift = 2 Bits long
    shift_key = int(state_bitfiled) & 1 # hexchat uses the pressed shift key, to automatically go to the next suggestion, we do that the same way
    is_tab = key_value == '65056' or key_value == '65289' # first is tab with shift, second only tab

    if is_tab:
        current_text =  hexchat.get_info("inputbox");
        if current_text.startswith('/axdcc '):
            
            try:
                user_input = current_text.split(" ")[1:]
                parser_response =  get_current_parser_output(user_input)
                [type, *parser_data] = parser_response
                if type == "normal":
                    # [given_string: string, parses_suggestions: String List, complete: boolean]
                    [given, available_options, complete] = parser_data
                    if complete is None:
                        # no autocompletion available
                        return hexchat.EAT_NONE
                    if complete:
                        # the shift key cycles trough options
                        if shift_key:
                            [_, _, available_options, _] =  get_current_parser_output(user_input[0:-1])
                            #  current_text.replace(given, available_options[0]) it may not only cut the last x off!
                            last_arg = user_input[-1]
                            old_index = available_options.index(last_arg)
                            new_index = (old_index +1) % len(available_options);
                            new_string = current_text[:-len(last_arg)] + available_options[new_index]
                            hexchat_set_input(new_string)
                        else:    
                            hexchat_suggest(available_options)
                            # add the " ", so that in the next turn, it's not complete
                            new_string = "{} ".format(current_text)
                            hexchat_set_input(new_string)
                    else:    
                        if user_input[-1] == "":
                            ## this should be always true!
                            assert(given == "")
                            if shift_key:
                                new_string = current_text + available_options[0]
                                hexchat_set_input(new_string)
                            else:
                                hexchat_suggest(available_options)
                        else:
                            matching_options =  [] if len(user_input[-1]) == 0 else list(filter(lambda x: x.startswith(user_input[-1]), available_options))
                            if len(matching_options) == 0:
                                if len(given) == 0:
                                    hexchat_suggest(matching_options)
                                else:
                                    #CAUTION THIS REMOVES "invalid" options, maybe don't enable this
                                    new_string = current_text[:-len(given)]
                                    hexchat_set_input(new_string)
                            elif len(matching_options) == 1:
                                new_string = current_text[:-len(given)] + available_options[0] if len(given) > 0 else current_text + matching_options[0]
                                hexchat_set_input(new_string)
                            else:
                                hexchat_suggest(matching_options)
                elif type == "args":
                    # [required_args : String List, complete: boolean]
                    [required_args, _] = parser_data
                    print('You need some arguments: '+ ' '.join(required_args))
                elif type == "arg_count":
                    # [received_args_count : number, needed_args_count, complete: boolean]
                    [received_args_count, needed_args_count, _] = parser_data
                    print("You have {} arguments, but you need {}!".format(received_args_count, needed_args_count))
                    if received_args_count < needed_args_count:
                        new_string = "{} ".format(current_text)
                        hexchat_set_input(new_string)
                elif type == "nothing":
                    # no autocompletion available
                    return hexchat.EAT_NONE        
                else: 
                    raise Exception("UNREACHABLE");

                return hexchat.EAT_ALL
            except Exception as err:
                logger = logging.getLogger('regex_logger')
                logger.error(err)
                printer.error("Internal Error, please report that, this is a bug!")
                return hexchat.EAT_NONE                

    # let hexchat handle that keypress, all EAT_ALL "consume" the event, so that no other handler gets the event!
    return hexchat.EAT_NONE


hexchat.hook_print("Message Send", dcc_msg_block_cb)
hexchat.hook_print("DCC SEND Offer", dcc_send_offer_cb)
hexchat.hook_print("DCC RECV Connect", dcc_recv_connect_cb)
hexchat.hook_print("DCC RECV Complete", dcc_recv_complete_cb)
hexchat.hook_print("DCC RECV Failed", dcc_recv_failed_cb)
hexchat.hook_print("Key Press", key_press_cb)


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


## Adding Menus According to https://hexchat.readthedocs.io/en/latest/plugins.html#controlling-the-gui
hexchat.command ("MENU DEL \"Auto XDCC\"") # to refresh it, if already existing
hexchat.command ("MENU -e1 -p-1 ADD \"Auto XDCC\"") # doesn't make sense for that to have a Keybinding
hexchat.command ("MENU -e1 ADD \"Auto XDCC/Packlists\"")
for packlist in packlist_manager.packlists.keys():
    hexchat.command("MENU ADD \"Auto XDCC/Packlists/Check {}\" \"axdcc packlist run {}\"".format(packlist,packlist))
hexchat.command ("MENU -e1 -k12,114 ADD \"Auto XDCC/Reload\" \"axdcc_reload\"") # KeyBinding Ctrl + Alt + R
hexchat.set_pluginpref("menu_added",1)


## Adding Menus According to https://hexchat.readthedocs.io/en/latest/plugins.html#controlling-the-gui
hexchat.command ("MENU DEL \"Auto XDCC\"") # to refresh it, if already existing
hexchat.command ("MENU -e1 -p-1 ADD \"Auto XDCC\"") # doesn't make sense for that to have a Keybinding
hexchat.command ("MENU -e1 ADD \"Auto XDCC/Packlists\"")
for packlist in packlist_manager.packlists.keys():
    hexchat.command("MENU ADD \"Auto XDCC/Packlists/Check {}\" \"axdcc packlist run {}\"".format(packlist,packlist))
hexchat.command ("MENU -e1 -k12,114 ADD \"Auto XDCC/Reload\" \"axdcc_reload\"") # KeyBinding Ctrl + Alt + R
hexchat.set_pluginpref("menu_added",1)

def reload_cb(word, word_eol, userdata):
    hexchat.set_pluginpref("plugin_reloaded", 1)
    hexchat_parser.printer.info("Reloading plugin...")
    hexchat.command("timer 1 py reload \"{}\"".format(__module_name__))
    return hexchat.EAT_ALL

hexchat.hook_command("axdcc_reload", reload_cb, help="/axdcc_reload reloads the Auto-XDCC plugin.")


def unloaded_cb(userdata):
    # first remove MENU entry, only if we really unload, if we reload, we don't do this, since new calls to MENU ADD update the GUI
    if hexchat.get_pluginpref("menu_added") == 0:
        hexchat.command ("MENU DEL \"Auto XDCC\"")
    hexchat.set_pluginpref("menu_added",0)

    # Force close running threads
    for packlist in packlist_manager.packlists.values():
        packlist.download_manager.terminate(True)
    
    saved_auto_recv = int(hexchat.get_pluginpref("dcc_auto_recv_save")) # restore this!
    if int(hexchat.get_prefs('dcc_auto_recv')) != saved_auto_recv:
        hexchat.command("set dcc_auto_recv {}".format(saved_auto_recv))
# TODO migrate to settings.py
    print(hexchat.get_pluginpref("dcc_auto_recv_save"))
    saved_autoopen_recv = int(hexchat.get_pluginpref("dcc_auto_recv_save")) if hexchat.get_pluginpref("dcc_auto_recv_save") != None else 0 # restore this!
    if int(hexchat.get_prefs('gui_autoopen_recv')) != saved_autoopen_recv:
        hexchat.command("set gui_autoopen_recv {}".format("on" if saved_autoopen_recv == 1 else "off"))

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
