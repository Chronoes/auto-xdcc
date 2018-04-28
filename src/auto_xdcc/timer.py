# pylint: disable=E0401
import hexchat

class Timer:
    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self._timer = None

    def set_interval(self, interval):
        self.interval = interval

    def register(self, userdata=None):
        self._timer = hexchat.hook_timer(self.interval*1000, self.callback, userdata)

    def unregister(self):
        hexchat.unhook(self._timer)
        self._timer = None
