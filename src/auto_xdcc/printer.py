# pylint: disable=E0401
import hexchat
import queue

class Printer:
    def __init__(self):
        self.listeners = set()
        self.message_queue = queue.Queue(-1)

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
            self.message_queue.put((listener, listener.x(str(line))))

    def info(self, line):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.info(str(line))))

    def error(self, line):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.error(str(line))))

    def list(self, line):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.list(str(line))))

    def prog(self, line):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.prog(str(line))))

    def complete(self, line):
        for listener in self.listeners:
            self.message_queue.put((listener, listener.complete(str(line))))

    def print_all(self):
        while self.message_queue.qsize() > 0:
            try:
                pr, msg = self.message_queue.get_nowait()
                pr.print_msg(msg)
                self.message_queue.task_done()
            except queue.Empty:
                break

class HexchatPrinter:
    def _get_context(self):
        server_name = hexchat.get_info('server')
        return hexchat.find_context(channel=server_name)

    def print_msg(self, line):
        srv = self._get_context()
        if srv:
            srv.prnt(line)
        else:
            print(line)

    def x(self, line):
        return "26»28» Auto-XDCC: " + str(line)

    def info(self, line):
        return "29»22» Auto-XDCC: INFO - " + str(line)

    def error(self, line):
        return "18»18» Auto-XDCC: Error - " + str(line)

    def list(self, line):
        return " 18» " + str(line)

    def prog(self, line):
        return "19»19» Auto-XDCC: " + str(line)

    def complete(self, line):
        return "25»25» Auto-XDCC: " + str(line)
