# pylint: disable=E0401
import hexchat
import queue
from auto_xdcc.colors import getColor, Color, ControlChars
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

    def getName(self, withColor = True):
        if(withColor):
            return getColor(Color.black) +  ControlChars.reverse.value + getColor(Color.lightGreen) + "Auto" + getColor(Color.white) + "-" + getColor(Color.blue2) + "XDCC" + ControlChars.reset.value
        else:
            return "Auto-XDCC"

    def formatMessage(self, colors, line, additionalText = "", withColor = True):
        if(len(colors) == 0):
            return "»» " + self.getName(withColor) + ": " + additionalText + " - " + str(line)
        elif (len(colors) == 2):
            return getColor(colors[0]) + "»" + getColor(colors[1]) + "» " + self.getName(withColor) + ": " + additionalText + " - " + str(line)
        elif (len(colors) == 3): 
            return getColor(colors[0]) + "»" + getColor(colors[1]) + "» " + self.getName(withColor) + ": " + getColor(colors[2]) + additionalText + ControlChars.reset.value + " - " + str(line)
        elif (len(colors) == 4): 
            return getColor(colors[0]) + "»" + getColor(colors[1]) + "» " + self.getName(withColor) + ": " + getColor(colors[2]) + additionalText + ControlChars.reset.value + " - " + getColor(colors[3]) + str(line) + ControlChars.reset.value
        else:
            raise Exception('Not the right amount of Arguments for formating the Message!') 

    def x(self, line):
        return self.formatMessage([Color.aqua2,Color.blue4], line)

    def info(self, line):
        return self.formatMessage([Color.lightPurple2,Color.purple2, Color.blue], line, "INFO")

    def error(self, line):
        return self.formatMessage([Color.red,Color.red, Color.red2], line, "Error")

    def list(self, line):
        return getColor(Color.blue3) + "» " + self.getName() + ": " + str(line)

    def prog(self, line):
        return self.formatMessage([Color.green2,Color.green2], line)

    def complete(self, line):
        return self.formatMessage([Color.lightGreen2,Color.lightGreen2], line)
