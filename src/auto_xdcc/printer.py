# pylint: disable=E0401
import hexchat
import queue
from abc import ABC, abstractmethod

from auto_xdcc.telegram_bot import TelegramBot

class AbstractPrinter(ABC):
    """
    Base class for all printers
    """
    @abstractmethod
    def x(self, line: str):
        pass

    @abstractmethod
    def info(self, line: str):
        pass

    @abstractmethod
    def error(self, line: str):
        pass

    @abstractmethod
    def list(self, line: str):
        pass

    @abstractmethod
    def prog(self, line: str):
        pass

    @abstractmethod
    def complete(self, line: str):
        pass

    @abstractmethod
    def flush(self):
        pass

class Printer(AbstractPrinter):
    def __init__(self):
        self.listeners = set()
        self.message_queue = queue.Queue(-1)

    def add_listener(self, listener: AbstractPrinter):
        self.listeners.add(listener)

    def remove_listener(self, listener: AbstractPrinter):
        self.listeners.remove(listener)

    def remove_listener_by_class(self, cls):
        for listener in self.listeners:
            if type(listener) == cls:
                self.listeners.remove(listener)
                break

    def x(self, line: str):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.x(str(line))))

    def info(self, line: str):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.info(str(line))))

    def error(self, line: str):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.error(str(line))))

    def list(self, line: str):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.list(str(line))))

    def prog(self, line: str):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.prog(str(line))))

    def complete(self, line: str):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.complete(str(line))))

    def flush(self):
        while self.message_queue.qsize() > 0:
            try:
                pr, msg = self.message_queue.get_nowait()
                pr.print_msg(msg)
                self.message_queue.task_done()
            except queue.Empty:
                break
        for listener in self.listeners:
            listener.flush()

class DirectPrinter(AbstractPrinter):
    def __init__(self, printer: AbstractPrinter):
        self.printer = printer

    def x(self, line: str):
        self.printer.print_msg(self.printer.x(line))

    def info(self, line: str):
        self.printer.print_msg(self.printer.info(line))

    def error(self, line: str):
        self.printer.print_msg(self.printer.error(line))

    def list(self, line: str):
        self.printer.print_msg(self.printer.list(line))

    def prog(self, line: str):
        self.printer.print_msg(self.printer.prog(line))

    def complete(self, line: str):
        self.printer.print_msg(self.printer.complete(line))

    def flush(self):
        self.printer.flush()

class HexchatPrinter(AbstractPrinter):
    def _get_context(self):
        server_name = hexchat.get_info('server')
        return hexchat.find_context(channel=server_name)

    def print_msg(self, line: str):
        srv = self._get_context()
        if srv:
            srv.prnt(line)
        else:
            print(line)

    def x(self, line: str):
        return "26»28» Auto-XDCC: " + str(line)

    def info(self, line: str):
        return "29»22» Auto-XDCC: INFO - " + str(line)

    def error(self, line: str):
        return "18»18» Auto-XDCC: Error - " + str(line)

    def list(self, line: str):
        return " 18» " + str(line)

    def prog(self, line: str):
        return "19»19» Auto-XDCC: " + str(line)

    def complete(self, line: str):
        return "25»25» Auto-XDCC: " + str(line)

    def flush(self):
        # Nothing to do here
        pass

class TelegramBotPrinter(AbstractPrinter):
    def __init__(self, bot: TelegramBot):
        self.bot = bot
        # Limit to 10 lines, must be flushed when limit is reached
        self.buffer = queue.Queue(10)

    def print_msg(self, line: str):
        try:
            self.buffer.put_nowait(line)
        except queue.Full:
            self.flush()
            self.buffer.join()
            self.print_msg(line)

    def x(self, line: str):
        return line

    def info(self, line: str):
        return 'INFO - ' + line

    def error(self, line: str):
        return 'Error - ' + line

    def list(self, line: str):
        return '  - ' + line

    def prog(self, line: str):
        return line

    def complete(self, line: str):
        return line

    def flush(self):
        messages = []
        while self.buffer.qsize() > 0:
            try:
                messages.append(self.buffer.get_nowait())
                self.buffer.task_done()
            except queue.Empty:
                break
        if messages:
            self.bot.send_message('\n'.join(messages))
