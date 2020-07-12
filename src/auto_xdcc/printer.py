# pylint: disable=E0401
import hexchat

from auto_xdcc.timer import Timer
from auto_xdcc.telegram_bot import TelegramBot

class Printer:
    def __init__(self):
        self.listeners = set()

    def add_listener(self, listener):
        self.listeners.add(listener)

    def remove_listener(self, listener):
        self.listeners.remove(listener)

    def remove_listener_by_class(self, cls):
        for listener in self.listeners:
            if type(listener) == cls:
                self.listeners.remove(listener)
                break

    def x(self, line):
        for listener in self.listeners:
            listener.x(str(line))

    def info(self, line):
        for listener in self.listeners:
            listener.info(str(line))

    def error(self, line):
        for listener in self.listeners:
            listener.error(str(line))

    def list(self, line):
        for listener in self.listeners:
            listener.list(str(line))

    def prog(self, line):
        for listener in self.listeners:
            listener.prog(str(line))

    def complete(self, line):
        for listener in self.listeners:
            listener.complete(str(line))


class HexchatPrinter:
    def _get_context(self):
        server_name = hexchat.get_info('server')
        return hexchat.find_context(channel=server_name)

    def _print(self, line):
        srv = self._get_context()
        if srv:
            srv.prnt(line)
        else:
            print(line)

    def x(self, line):
        self._print("26»28» Auto-XDCC: " + str(line))

    def info(self, line):
        self._print("29»22» Auto-XDCC: INFO - " + str(line))

    def error(self, line):
        self._print("18»18» Auto-XDCC: Error - " + str(line))

    def list(self, line):
        self._print(" 18» " + str(line))

    def prog(self, line):
        self._print("19»19» Auto-XDCC: " + str(line))

    def complete(self, line):
        self._print("25»25» Auto-XDCC: " + str(line))


class TelegramBotPrinter:
    def __init__(self, bot: TelegramBot):
        self.bot = bot
        self.send_timer = Timer(250, self.timer_callback)
        self.lines = []

    def timer_callback(self, userdata=None):
        self.send_timer.unregister()
        if not self.bot.chat_id:
            return False

        message = '\n'.join(self.lines)
        self.lines = []

        if message:
            self.bot.send_message(message.strip())
        return False

    def _print(self, line):
        self.lines.append(line)
        if not self.send_timer.is_registered():
            self.send_timer.register()

    def x(self, line):
        self._print(line)

    def info(self, line):
        self._print('INFO - ' + line)

    def error(self, line):
        self._print('Error - ' + line)

    def list(self, line):
        self._print('  - ' + line)

    def prog(self, line):
        self._print(line)

    def complete(self, line):
        self._print(line)
