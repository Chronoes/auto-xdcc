"""
Automagically checks XDCC packlists and downloads new episodes of specified shows.
"""

# pylint: disable=E0401
from pprint import isreadable
import hexchat
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
from auto_xdcc.printer import Printer, HexchatPrinter
from auto_xdcc.packlist_manager import PacklistManager
from auto_xdcc.packlist_item import PacklistItem
from auto_xdcc.timer import Timer


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
    datefmt='%Y-%m-%d %H:%M:%S'
)

packlist_manager = PacklistManager()
packlist_manager.register_packlists()
config.packlist_manager = packlist_manager

def printing_callback(userdata=None):
    printer.print_all()
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
    return hexchat.EAT_HEXCHAT

def dcc_recv_connect_cb(word, word_eol, userdata):
    [bot_name, ip_addr, filename] = word
    logger = logging.getLogger('dcc_recv_connect')
    logger.debug("DCC RECV connect: %s (%s) %s", bot_name, ip_addr, filename)
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
        item = packlist.download_manager.download_abort(bot_name, filename)
        # Reset to previous packnumber
        if type(item) == PacklistItem and packlist.last_pack > item.packnumber:
            packlist.last_pack = item.packnumber - 1
            config['packlists'][packlist.name]['lastPack'] = packlist.last_pack
            config.persist()
        logger.info("Aborting download of %s", filename)
    else:
        logger.error("Could not find a match for %s", filename)
        return hexchat.EAT_NONE

    logger.error("Connection failed: %s. Error: %s", bot_name, error)
    printer.error("Connection to {} failed, check firewall settings. Error: {}".format(bot_name, error))
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
# type:
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


# Argument parser
# Show subcommand handlers
def _list_shows(items):
    for show, [episode, resolution, subdir] in items:
        result = show
        if episode is None:
            result += " @ NEW"
        else:
            result += " @ episode " + str(episode)

        result += " | resolution {}p".format(resolution)
        if subdir:
            result += " in subdir " + subdir

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
    items = sorted(config['archived']) # I think here archived i meant, since 'trusted' doesn'T exist on global config object
    if len(items) == 0:
        printer.x("No bots archived")
        return hexchat.EAT_ALL

    printer.x("Listing {} bots:".format(len(items)))

    for bot in items:
        printer.list(bot)
    return hexchat.EAT_ALL

def getbot_handler(args):
    hexchat.command("MSG {} XDCC SEND {}".format(args.name, args.nr))
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

# Packlist handlers
def reset_packlist_handler(args):
    packlist = packlist_manager.packlists[args.packlist]
    packlist.reset()

    packlist_conf = config['packlists'][packlist.name]
    packlist_conf['lastPack'] = packlist.last_pack
    config.persist()

    printer.x("Packlist '{}' has been reset".format(packlist))


def packlist_timer_handler(args):
    if args.type == 'refresh':
        packlist = packlist_manager.packlists[args.packlist]
        packlist.refresh_timer.unregister()
        if args.off:
            printer.x("Refresh timer disabled for {}.".format(packlist))
        else:
            if args.interval:
                packlist.refresh_interval = args.interval
                config['packlists'][packlist.name]['refreshInterval'] = args.interval
                config.persist()

            packlist.register_refresh_timer(packlist_manager.refresh_timer_callback)
            printer.x("Refresh timer enabled for packlist {} with interval {}s.".format(packlist, packlist.refresh_interval))

def run_packlist_handler(args):
    packlist = packlist_manager.packlists[args.packlist]
    packlist.run_once()
    printer.x("Packlist '{}' check started".format(packlist))

def download_handler(args):
    if args.clear:
        packlist_manager.clear_download_queue()
        printer.x('Cleared download queue')
        return
    return default_handler(args)

def default_handler(parser):
    def _handler(args, format = False):
        if format:
            return parser.format_usage();
        else:
            # Print usage for default handlers (no associated action)
            parser.print_usage()
            return hexchat.EAT_ALL
    return _handler

# Argument parser and subparsers
def general_main(parser, handler=None):
    if handler:
        parser.set_defaults(handler=handler)
    else:
        parser.set_defaults(handler=default_handler(parser))
    return parser

def show_main(parser, handler):
    def join_args_name(args):
        if args.name:
            args.name = ' '.join(args.name)
            return handler(args)
        return None
    parser.add_argument('name', help='Full name of the show', nargs='+')
    return general_main(parser, join_args_name)

def show_options(parser):
    parser.add_argument('-r', '--resolution', help='Resolution of episode to download')
    parser.add_argument('-e', '--episode', help='Episode number to start downloading from', type=int)
    parser.add_argument('-d', '--directory', help='Custom directory to download to')
    return parser

def listshows_subparser(parser):
    subparsers = parser.add_subparsers()

    archive = subparsers.add_parser('archived', printer=parser.printer)
    archive.set_defaults(handler=listarchivedshows_handler)

    return general_main(parser, listshows_handler)

def shows_subparser(parser):
    subparsers = parser.add_subparsers()

    listshows_subparser(subparsers.add_parser('list', printer=parser.printer))

    show_options(show_main(subparsers.add_parser('add', printer=parser.printer), addshow_handler))
    show_options(show_main(subparsers.add_parser('update', printer=parser.printer), updateshow_handler))
    show_main(subparsers.add_parser('remove', printer=parser.printer), removeshow_handler)
    show_main(subparsers.add_parser('archive', printer=parser.printer), archiveshow_handler)
    show_main(subparsers.add_parser('restore', printer=parser.printer), restoreshow_handler)

    return general_main(parser)

def bot_main(parser, handler):
    parser.add_argument('name', help='Name of the bot')
    return general_main(parser, handler)

def getbot_options(parser):
    parser.add_argument('nr', help='Number of the item in bot\'s packlist')
    return parser

def bots_subparser(parser):
    subparsers = parser.add_subparsers()

    list_parser = subparsers.add_parser('list', printer=parser.printer)
    list_parser.set_defaults(handler=listbots_handler)

    getbot_options(bot_main(subparsers.add_parser('get', printer=parser.printer), getbot_handler))
    bot_main(subparsers.add_parser('add', printer=parser.printer), addbot_handler)
    bot_main(subparsers.add_parser('remove', printer=parser.printer), removebot_handler)

    return general_main(parser)

def timer_main(parser, handler):
    parser.add_argument('type', help='Which timer', choices=('refresh',))
    parser.add_argument('--off', help='Disable the timer until restart', action='store_true')
    parser.add_argument('-i', '--interval', help='Interval to run timer at in seconds', type=int)

    return general_main(parser, handler)

def packlist_opt(parser):
    parser.add_argument('packlist', help='Packlist to apply the action to', choices=tuple(packlist_manager.packlists))
    return parser

def packlist_subparser(parser):
    subparsers = parser.add_subparsers()

    general_main(packlist_opt(subparsers.add_parser('reset', printer=parser.printer)), reset_packlist_handler)
    timer_main(packlist_opt(subparsers.add_parser('timer', printer=parser.printer)), packlist_timer_handler)
    general_main(packlist_opt(subparsers.add_parser('run', printer=parser.printer)), run_packlist_handler)

    return general_main(parser)

def download_subparser(parser):
    parser.add_argument('--clear', help='Clears current download queue', action='store_true')

    return general_main(parser, download_handler)

def argument_parser():
    parser = argparse.ArgumentParser(prog='/axdcc', printer=printer)

    subparsers = parser.add_subparsers()

    shows_subparser(subparsers.add_parser('show', printer=parser.printer))
    bots_subparser(subparsers.add_parser('bot', printer=parser.printer))
    packlist_subparser(subparsers.add_parser('packlist', printer=parser.printer, aliases=['pl']))
    download_subparser(subparsers.add_parser('download', printer=parser.printer, aliases=['dl']))

    return general_main(parser)


parser = argument_parser()
def axdcc_main_cb(word, word_eol, userdata):
    try:
        args = parser.parse_args(word[1:])
    except Exception as e:
        if e.args[0]:
            printer.error(e)
        return hexchat.EAT_PLUGIN
    return_code = args.handler(args)
    if return_code:
        return return_code

    return hexchat.EAT_ALL

hexchat.hook_command('axdcc', axdcc_main_cb, help=parser.format_usage())


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
    printer.info("Reloading plugin...")
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

    if int(hexchat.get_prefs('dcc_remove')) != int(default_clear_finished):
        hexchat.command("set dcc_remove " + str(default_clear_finished))
    sleep(0.1)
    printer.x("Plugin unloaded")

    return hexchat.EAT_ALL

hexchat.hook_unload(unloaded_cb)
