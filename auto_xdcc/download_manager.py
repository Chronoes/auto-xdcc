import threading
import queue

import hexchat


class DownloadManager:
    def __init__(self, config):
        self.config = config
        self.awaiting = queue.Queue()
        self.ongoing = queue.Queue()
        self.concurrent_downloads = threading.BoundedSemaphore(int(config['maxConcurrentDownloads']))
        self._thread = threading.Thread(target=self._run)

    def start(self):
        self._thread.start()

    def _run(self):
        while True:
            with self.concurrent_downloads:
                item = self.awaiting.get()
                self.download_request(item)
                self.ongoing.put(item)
                self.awaiting.task_done()

    def download_request(self, item):
        hexchat.command("MSG {} XDCC SEND {}".format(self.config['current'], item.packnumber))

    def send_offer_callback(self, bot_name):
        pass
