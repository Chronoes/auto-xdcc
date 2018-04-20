# pylint: disable=E0401
import hexchat

class Timer:
    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self._timer = None

    @classmethod
    def from_config(cls, config, callback):
        return cls(config['interval'], callback)

    def set_interval(self, interval):
        self.interval = interval

    def register(self):
        self._timer = hexchat.hook_timer(self.interval*1000, self.callback)

    def unregister(self):
        hexchat.unhook(self._timer)
        self._timer = None
