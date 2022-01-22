"""
Wrapper for Python's argparse module
"""
# pylint: disable=E0401
import hexchat
import argparse as _argparse

import auto_xdcc.config as gconfig
from auto_xdcc.telegram_bot import TelegramBot
from auto_xdcc.printer import DirectPrinter, TelegramBotPrinter

class ArgumentParser(_argparse.ArgumentParser):
    def __init__(self, printer=None, **kwargs):
        self.printer = printer
        super().__init__(**kwargs)

    # Overrides the _print_message method in ArgumentParser
    def _print_message(self, message, file):
        # Allow messages only in configured printer
        if message:
            self.printer.error(message)
        self.printer.flush()

    def exit(self, status=0, message=None):
        # Prevent exit command from performing sys.exit
        if status:
            self._print_message(message)
            raise Exception(message)

    def error(self, message):
        # Prevent error command from performing sys.exit
        self.exit(status=2, message=message)


# Show subcommand handlers
def _list_shows(printer, items):
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


def _match_show_name(config, printer, name, t='shows'):
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
    _list_shows(printer, shows)
    return None


def listshows_handler(args):
    config = gconfig.get()
    items = sorted(config['shows'].items())

    if len(items) == 0:
        args.printer.x("No shows registered")
        return

    args.printer.x("Listing {} registered shows:".format(len(items)))
    return _list_shows(args.printer, items)


def listarchivedshows_handler(args):
    config = gconfig.get()
    items = sorted(config['archived'].items())

    if len(items) == 0:
        args.printer.x("No shows archived")
        return

    args.printer.x("Listing {} archived shows:".format(len(items)))
    return _list_shows(args.printer, items)


def addshow_handler(args):
    config = gconfig.get()
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
        args.printer.x(result + " Default directory: " + args.directory)
    else:
        args.printer.x(result)


def updateshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.printer, args.name)
    if not show_match:
        return

    name, [ep, reso, subdir] = show_match

    if args.episode is not None and args.episode != ep:
        ep = args.episode
        args.printer.info("Updated {} episode count to {}.".format(name, ep))

    if args.resolution is not None and args.resolution != reso:
        reso = int(args.resolution.strip('p'))
        args.printer.info("Updated {} resolution to {}.".format(name, reso))

    if args.directory is not None and args.directory != subdir:
        if args.directory == '/':
            subdir = ''
            args.printer.info("Updated {} subdir to main directory.".format(name))
        else:
            subdir = args.directory
            args.printer.info("Updated {} subdir to {}.".format(name, subdir))

    config['shows'][name] = [ep, reso, subdir]
    config.persist()


def removeshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.printer, args.name)
    if not show_match:
        return

    name, [ep, _reso, _subdir] = show_match

    del config['shows'][name]
    config.persist()

    if ep is not None:
        args.printer.x("Removed {} at episode {} from list.".format(name, ep))
    else:
        args.printer.x("Removed {} from list.".format(name))


def archiveshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.printer, args.name)
    if not show_match:
        return

    name, [ep, reso, subdir] = show_match

    del config['shows'][name]
    config['archived'][name] = [ep, reso, subdir]
    config.persist()

    args.printer.x("Added {} at episode {} to archive.".format(name, ep))


def restoreshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.printer, args.name, 'archived')
    if not show_match:
        args.printer.error("No show in archive named: " + args.name)
        return

    name, [ep, reso, subdir] = show_match

    del config['archived'][name]
    config['shows'][name] = [ep, reso, subdir]
    config.persist()

    args.printer.x("Restored {} at episode {} from archive.".format(name, ep))

# Bot subcommand handlers
def listbots_handler(args):
    config = gconfig.get()
    items = sorted(config['archived']) # I think here archived i meant, since 'trusted' doesn'T exist on global config object
    if len(items) == 0:
        args.printer.x("No bots archived")
        return

    args.printer.x("Listing {} bots:".format(len(items)))

    for bot in items:
        args.printer.list(bot)


def getbot_handler(args):
    hexchat.command("MSG {} XDCC SEND {}".format(args.name, args.nr))


def addbot_handler(args):
    config = gconfig.get()
    bots = set(config['trusted'])

    bots.add(args.name)

    config['trusted'] = list(bots)
    config.persist()

    args.printer.x("Added {} to trusted list".format(args.name))

def removebot_handler(args):
    config = gconfig.get()
    bots = set(config['trusted'])

    if args.name not in bots:
        args.printer.error("No such bot in trusted list: " + args.name)
        return

    bots.remove(args.name)
    config['trusted'] = list(bots)
    config.persist()

    args.printer.x("Removed {} from trusted list".format(args.name))

# Packlist handlers
def packlist_timer_handler(args):
    config = gconfig.get()
    if args.type == 'refresh':
        packlist = config.packlist_manager.packlists[args.packlist]
        packlist.refresh_timer.unregister()
        if args.off:
            args.printer.x("Refresh timer disabled for {}.".format(packlist))
        else:
            if args.interval:
                packlist.refresh_interval = args.interval
                config['packlists'][packlist.name]['refreshInterval'] = args.interval
                config.persist()

            packlist.register_refresh_timer(config.packlist_manager.refresh_timer_callback)
            args.printer.x("Refresh timer enabled for packlist {} with interval {}s.".format(packlist, packlist.refresh_interval))


def run_packlist_handler(args):
    config = gconfig.get()
    packlist = config.packlist_manager.packlists[args.packlist]
    packlist.run_once()
    args.printer.x("Packlist '{}' check started".format(packlist))


def remotecontrol_link_handler(args):
    config = gconfig.get()
    if not args.token:
        args.printer.info('To link with Telegram, you need to make a bot first. Talk to @BotFather https://t.me/botfather .')
        args.printer.info('After getting the API token, add it to the "link" command')
    else:
        telegram_bot = TelegramBot.init_from_config(config)
        bot_printer = TelegramBotPrinter(telegram_bot)
        telegram_bot.set_parser(create_argument_parser(bot_printer, prog=''))
        config.printer.add_listener(bot_printer)
        config.telegram_bot = telegram_bot
        bot_info = telegram_bot.get_me()
        args.printer.info('To link your bot with AXDCC, send message "/start" to {0} or use this URL https://t.me/{0}'.format(bot_info['username']))


def remotecontrol_unlink_handler(args):
    config = gconfig.get()
    del config['credentials']['telegram']

    if config.telegram_bot:
        config.telegram_bot.terminate()
        config.telegram_bot = None
    config.persist()
    args.printer.info('Telegram link has been removed')
    config.printer.remove_listener_by_class(TelegramBotPrinter)


def default_handler(parser):
    def _handler(args):
        # Print usage for default handlers (no associated action)
        parser.print_usage()

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

def packlist_opt(parser, packlists):
    parser.add_argument('packlist', help='Packlist to apply the action to', choices=packlists)
    return parser

def packlist_subparser(parser, packlist_manager):
    packlists = tuple(packlist_manager.packlists)
    subparsers = parser.add_subparsers()

    timer_main(packlist_opt(subparsers.add_parser('timer', printer=parser.printer), packlists), packlist_timer_handler)
    general_main(packlist_opt(subparsers.add_parser('run', printer=parser.printer), packlists), run_packlist_handler)

    return general_main(parser)


def remotecontrol_link_main(parser):
    parser.add_argument('token', help='API token of the bot', nargs='?')
    return general_main(parser, remotecontrol_link_handler)


def remotecontrol_subparser(parser):
    subparsers = parser.add_subparsers()

    remotecontrol_link_main(subparsers.add_parser('link', printer=parser.printer))
    general_main(subparsers.add_parser('unlink', printer=parser.printer), remotecontrol_unlink_handler)
    return general_main(parser)


def create_argument_parser(printer, prog='/axdcc'):
    direct_printer = DirectPrinter(printer)
    parser = ArgumentParser(prog=prog, printer=direct_printer)
    parser.set_defaults(parser=parser, printer=direct_printer)

    subparsers = parser.add_subparsers()

    shows_subparser(subparsers.add_parser('show', printer=parser.printer))
    bots_subparser(subparsers.add_parser('bot', printer=parser.printer))
    packlist_subparser(subparsers.add_parser('packlist', printer=parser.printer, aliases=['pl']), gconfig.get().packlist_manager)
    remotecontrol_subparser(subparsers.add_parser('remotecontrol', printer=parser.printer, aliases=['rc']))

    return general_main(parser)
