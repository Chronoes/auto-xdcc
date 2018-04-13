import threading
from collections import deque

import hexchat

from auto_xdcc.packlist import PacklistItem

DOWNLOAD_REQUEST = 'request'
DOWNLOAD_CONNECT = 'connect'
DOWNLOAD_ABORT = 'abort'

class DownloadManager:
    def __init__(self, config):
        self.config = config
        self.awaiting = deque()
        self.ongoing = {}
        self.ongoing_lock = threading.Lock()
        self.concurrent_downloads = threading.BoundedSemaphore(int(config['maxConcurrentDownloads']))
        self.item_available = threading.Condition()
        self._thread = threading.Thread(target=self._run)

    def start(self):
        self._thread.daemon = True
        self._thread_running = True
        self._thread.start()

    def terminate(self):
        self._thread_running = False
        self.item_available.notify_all()

    def _run(self):
        while self._thread_running:
            with self.concurrent_downloads, self.item_available:
                self.item_available.wait()

                if not self._thread_running:
                    break

                item = self.awaiting.popleft()
                self.download_request(item)

    def count_awaiting(self):
        return len(self.awaiting)

    def count_ongoing(self):
        return len(self.ongoing)

    def download_request(self, item: PacklistItem):
        bot = self.config['current']
        hexchat.command("MSG {} XDCC SEND {}".format(bot, item.packnumber))
        with self.ongoing_lock:
            self.ongoing[item.filename] = [bot, item, None, DOWNLOAD_REQUEST]

    def download_abort(self, bot_name, filename):
        hexchat.emit_print("DCC RECV Abort", bot_name, filename)
        hexchat.command("MSG {} XDCC CANCEL".format(bot_name))
        with self.ongoing_lock:
            item = self.ongoing[filename][1]
            del self.ongoing[filename]
            return item

    def check_packlist(self, packlist):
        for item in packlist.get_new_items():
            show_info = self.config['shows'].get(item.show_name)
            if show_info and item.episode_nr > show_info[0] and item.resolution == show_info[1]:
                self.awaiting.append(item)
                self.item_available.notify_all()


    def send_offer_callback(self, bot_name, filename, filesize, ip_addr):
        if bot_name in self.config['trusted']:
            with self.ongoing_lock:
                if filename in self.ongoing:
                    hexchat.emit_print("DCC RECV Connect", bot_name, ip_addr, filename)
                    self.ongoing[filename][2] = filesize
                    self.ongoing[filename][3] = DOWNLOAD_CONNECT
                    return (DOWNLOAD_CONNECT, self.ongoing[filename][1])

            return (None, None)

        item = self.download_abort(bot_name, filename)
        return (DOWNLOAD_ABORT, item)

    def recv_complete_callback(self, filename):
        with self.ongoing_lock:
            [_bot, item, size, _status] = self.ongoing[filename]
            del self.ongoing[filename]
            return (item, size)
