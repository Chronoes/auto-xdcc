# pylint: disable=E0401
import hexchat

class Timer:
    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self._timer = None

    def set_interval(self, interval):
        self.interval = interval

    def is_registered(self):
        return self._timer is not None

    def register(self, userdata=None):
        self.unregister()
        self._timer = hexchat.hook_timer(self.interval, self.callback, userdata)

    def unregister(self):
        if self.is_registered():
            hexchat.unhook(self._timer)
            self._timer = None

    def trigger_once(self, userdata=None, interval=1):
        def callback(data):
            self.callback(data)
            return False

        hexchat.hook_timer(interval, callback, userdata)
