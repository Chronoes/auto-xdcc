# pylint: disable=E0401
import hexchat
import queue
from auto_xdcc.colors import get_color, Color, ControlChars
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

    def debug(self, line):
        # TODO get the debug setting, from settings.py
        for listener in self.listeners:
            self.message_queue.put((listener, listener.debug(str(line))))


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

    def getName(self, with_color = True):
        if(with_color):
            return get_color(Color.black) +  ControlChars.reverse.value + get_color(Color.light_green) + "Auto" + get_color(Color.blue) + "-" + get_color(Color.white) + "XDCC" + ControlChars.reset.value
        else:
            return "Auto-XDCC"

    def format_message(self, colors, line, additional_text = "", with_color = True):
        if(len(colors) == 0):
            return "»» " + self.getName(with_color) + ": " + additional_text + " - " + str(line)
        elif (len(colors) == 2):
            return get_color(colors[0]) + "»" + get_color(colors[1]) + "» " + self.getName(with_color) + ": " + additional_text + " - " + str(line)
        elif (len(colors) == 3): 
            return get_color(colors[0]) + "»" + get_color(colors[1]) + "» " + self.getName(with_color) + ": " + get_color(colors[2]) + additional_text + ControlChars.reset.value + " - " + str(line)
        elif (len(colors) == 4): 
            return get_color(colors[0]) + "»" + get_color(colors[1]) + "» " + self.getName(with_color) + ": " + get_color(colors[2]) + additional_text + ControlChars.reset.value + " - " + get_color(colors[3]) + str(line) + ControlChars.reset.value
        else:
            raise Exception('Not the right amount of Arguments for formating the Message!') 

    def x(self, line):
        return self.format_message([Color.aqua2,Color.blue_grey2], line)

    def info(self, line):
        return self.format_message([Color.light_purple2,Color.purple2, Color.blue], line, "INFO")

    def debug(self, line):
        return self.format_message([Color.light_red,Color.orange, Color.orange2], line, "DEBUG")

    def error(self, line):
        return self.format_message([Color.red,Color.red, Color.red2], line, "Error")

    def list(self, line):
        return get_color(Color.blue2) + "» " + self.getName() + ": " + str(line)

    def prog(self, line):
        return self.format_message([Color.green2,Color.green2], line)

    def complete(self, line):
        return self.format_message([Color.light_green2,Color.light_green2], line)
