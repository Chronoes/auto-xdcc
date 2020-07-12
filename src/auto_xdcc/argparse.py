"""
Wrapper for Python's argparse module
"""
# pylint: disable=E0401
import hexchat
import argparse as _argparse
import sys as _sys
import functools
from math import floor

import auto_xdcc.config as gconfig
from auto_xdcc.telegram_bot import TelegramBot
from auto_xdcc.printer import TelegramBotPrinter


class ArgumentParser(_argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        # Allow messages only in stdout
        if message:
            _sys.stdout.write(message)

    def exit(self, status=0, message=None):
        # Prevent exit command from performing sys.exit
        self._print_message(message)
        raise Exception(message)


# Show subcommand handlers
def _list_shows(config, items):
    for show, [episode, resolution, subdir] in items:
        result = show
        if episode is None:
            result += " @ NEW"
        else:
            result += " @ episode " + str(episode)

        result += " | resolution {}p".format(resolution)
        if subdir:
            result += " in subdir " + subdir

        config.printer.list(result)


def _match_show_name(config, name, t='shows'):
    if name in config[t]:
        return (name, config[t][name])

    shows = config.partial_match(t, key=name)
    shows_len = len(shows)

    if shows_len == 0:
        config.printer.error("No show named: " + name)
        return None
    elif shows_len == 1:
        return shows[0]

    config.printer.info('Matched {} shows. Please refine your search keywords'.format(shows_len))
    _list_shows(config, shows)
    return None


def listshows_handler(args):
    config = gconfig.get()
    items = sorted(config['shows'].items())

    if len(items) == 0:
        config.printer.x("No shows registered")
        return

    config.printer.x("Listing {} registered shows:".format(len(items)))
    return _list_shows(config, items)


def listarchivedshows_handler(args):
    config = gconfig.get()
    items = sorted(config['archived'].items())

    if len(items) == 0:
        config.printer.x("No shows archived")
        return

    config.printer.x("Listing {} archived shows:".format(len(items)))
    return _list_shows(config, items)


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
        config.printer.x(result + " Default directory: " + args.directory)
    else:
        config.printer.x(result)

    config.printer.info("To download old episodes, reset the appropriate packlist")


def updateshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.name)
    if not show_match:
        return

    name, [ep, reso, subdir] = show_match

    if args.episode is not None and args.episode != ep:
        ep = args.episode
        config.printer.info("Updated {} episode count to {}.".format(name, ep))

    if args.resolution is not None and args.resolution != reso:
        reso = int(args.resolution.strip('p'))
        config.printer.info("Updated {} resolution to {}.".format(name, reso))

    if args.directory is not None and args.directory != subdir:
        if args.directory == '/':
            subdir = ''
            config.printer.info("Updated {} subdir to main directory.".format(name))
        else:
            subdir = args.directory
            config.printer.info("Updated {} subdir to {}.".format(name, subdir))

    config['shows'][name] = [ep, reso, subdir]
    config.persist()


def removeshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.name)
    if not show_match:
        return

    name, [ep, _reso, _subdir] = show_match

    del config['shows'][name]
    config.persist()

    if ep is not None:
        config.printer.x("Removed {} at episode {} from list.".format(name, ep))
    else:
        config.printer.x("Removed {} from list.".format(name))


def archiveshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.name)
    if not show_match:
        return

    name, [ep, reso, subdir] = show_match

    del config['shows'][name]
    config['archived'][name] = [ep, reso, subdir]
    config.persist()

    config.printer.x("Added {} at episode {} to archive.".format(name, ep))


def restoreshow_handler(args):
    config = gconfig.get()
    show_match = _match_show_name(config, args.name, 'archived')
    if not show_match:
        config.printer.error("No show in archive named: " + args.name)
        return

    name, [ep, reso, subdir] = show_match

    del config['archived'][name]
    config['shows'][name] = [ep, reso, subdir]
    config.persist()

    config.printer.x("Restored {} at episode {} from archive.".format(name, ep))

# Bot subcommand handlers
def listbots_handler(args):
    config = gconfig.get()
    items = sorted(config['trusted'])
    if len(items) == 0:
        config.printer.x("No bots archived")
        return

    config.printer.x("Listing {} bots:".format(len(items)))

    for bot in items:
        config.printer.list(bot)


def getbot_handler(args):
    hexchat.command("MSG {} XDCC SEND {}".format(args.name, args.nr))


def addbot_handler(args):
    config = gconfig.get()
    bots = set(config['trusted'])

    bots.add(args.name)

    config['trusted'] = list(bots)
    config.persist()

    config.printer.x("Added {} to trusted list".format(args.name))

def removebot_handler(args):
    config = gconfig.get()
    bots = set(config['trusted'])

    if args.name not in bots:
        config.printer.error("No such bot in trusted list: " + args.name)
        return

    bots.remove(args.name)
    config['trusted'] = list(bots)
    config.persist()

    config.printer.x("Removed {} from trusted list".format(args.name))

# Packlist handlers
def reset_packlist_handler(args):
    config = gconfig.get()
    packlist = config.packlist_manager.packlists[args.packlist]
    packlist.reset()

    packlist_conf = config['packlists'][packlist.name]
    packlist_conf['contentLength'] = packlist.last_request
    packlist_conf['lastPack'] = packlist.last_pack
    config.persist()

    config.printer.x("Packlist '{}' has been reset".format(packlist))


def packlist_timer_handler(args):
    config = gconfig.get()
    if args.type == 'refresh':
        packlist = config.packlist_manager.packlists[args.packlist]
        packlist.refresh_timer.unregister()
        if args.off:
            config.printer.x("Refresh timer disabled for {}.".format(packlist))
        else:
            if args.interval:
                packlist.refresh_interval = args.interval
                config['packlists'][packlist.name]['refreshInterval'] = args.interval
                config.persist()

            packlist.register_refresh_timer(config.packlist_manager.refresh_timer_callback)
            config.printer.x("Refresh timer enabled for packlist {} with interval {}s.".format(packlist, packlist.refresh_interval))


def run_packlist_handler(args):
    config = gconfig.get()
    packlist = config.packlist_manager.packlists[args.packlist]
    packlist.run_once()
    config.printer.x("Packlist '{}' check started".format(packlist))


def remotecontrol_link_handler(args):
    config = gconfig.get()
    if not args.token:
        config.printer.info('To link with Telegram, you need to make a bot first. Talk to @BotFather https://t.me/botfather .')
        config.printer.info('After getting the API token, add it to the "link" command')
    else:
        telegram_bot = TelegramBot(args.token)
        bot_info = telegram_bot.get_me()
        telegram_bot.set_chat_id_cb(config).set_arg_parser(args.parser).start()
        config.telegram_bot = telegram_bot
        config.printer.info('To link your bot with AXDCC, send message "/start" to {0} or use this URL https://t.me/{0}'.format(bot_info['username']))
        config.printer.add_listener(TelegramBotPrinter(telegram_bot))


def remotecontrol_unlink_handler(args):
    config = gconfig.get()
    del config['credentials']['telegram']

    if config.telegram_bot:
        config.telegram_bot.terminate()
        config.telegram_bot = None
    config.persist()
    config.printer.info('Telegram link has been removed')
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
    def join_args_name(handler, args):
        args.name = ' '.join(args.name)
        return handler(args)
    parser.add_argument('name', help='Full name of the show', nargs='+')
    return general_main(parser, functools.partial(join_args_name, handler))


def show_options(parser):
    parser.add_argument('-r', '--resolution', help='Resolution of episode to download')
    parser.add_argument('-e', '--episode', help='Episode number to start downloading from', type=int)
    parser.add_argument('-d', '--directory', help='Custom directory to download to')
    return parser


def listshows_subparser(parser):
    subparsers = parser.add_subparsers()

    archive = subparsers.add_parser('archived')
    archive.set_defaults(handler=listarchivedshows_handler)

    return general_main(parser, listshows_handler)


def shows_subparser(parser):
    subparsers = parser.add_subparsers()

    listshows_subparser(subparsers.add_parser('list'))

    show_options(show_main(subparsers.add_parser('add'), addshow_handler))
    show_options(show_main(subparsers.add_parser('update'), updateshow_handler))
    show_main(subparsers.add_parser('remove'), removeshow_handler)
    show_main(subparsers.add_parser('archive'), archiveshow_handler)
    show_main(subparsers.add_parser('restore'), restoreshow_handler)

    return general_main(parser)


def bot_main(parser, handler):
    parser.add_argument('name', help='Name of the bot')
    return general_main(parser, handler)


def getbot_options(parser):
    parser.add_argument('nr', help='Number of the item in bot\'s packlist')
    return parser


def bots_subparser(parser):
    subparsers = parser.add_subparsers()

    list_parser = subparsers.add_parser('list')
    list_parser.set_defaults(handler=listbots_handler)

    getbot_options(bot_main(subparsers.add_parser('get'), getbot_handler))
    bot_main(subparsers.add_parser('add'), addbot_handler)
    bot_main(subparsers.add_parser('remove'), removebot_handler)

    return general_main(parser)


def timer_main(parser, handler):
    parser.add_argument('type', help='Which timer', choices=('refresh',))
    parser.add_argument('--off', help='Disable the timer until restart', action='store_true')
    parser.add_argument('-i', '--interval', help='Interval to run timer at in seconds', type=int)

    return general_main(parser, handler)


def packlist_subparser(parser, packlist_manager):
    parser.add_argument('packlist', help='Packlist to apply the action to', choices=tuple(packlist_manager.packlists))
    subparsers = parser.add_subparsers()

    general_main(subparsers.add_parser('reset'), reset_packlist_handler)
    timer_main(subparsers.add_parser('timer'), packlist_timer_handler)
    general_main(subparsers.add_parser('run'), run_packlist_handler)

    return general_main(parser)


def remotecontrol_link_main(parser):
    parser.add_argument('token', help='API token of the bot', nargs='?')
    return general_main(parser, remotecontrol_link_handler)


def remotecontrol_subparser(parser):
    subparsers = parser.add_subparsers()

    remotecontrol_link_main(subparsers.add_parser('link'))
    general_main(subparsers.add_parser('unlink'), remotecontrol_unlink_handler)
    return general_main(parser)


def create_argument_parser():
    parser = ArgumentParser(prog='/axdcc')
    parser.set_defaults(parser=parser)

    subparsers = parser.add_subparsers()

    shows_subparser(subparsers.add_parser('show'))
    bots_subparser(subparsers.add_parser('bot'))
    packlist_subparser(subparsers.add_parser('packlist', aliases=['pl']), gconfig.get().packlist_manager)
    remotecontrol_subparser(subparsers.add_parser('remotecontrol', aliases=['rc']))

    return general_main(parser)
