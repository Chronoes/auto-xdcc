import threading
import queue

# pylint: disable=E0401
import hexchat

import auto_xdcc.printer as printer
from auto_xdcc.packlist_item import PacklistItem

DOWNLOAD_REQUEST = 'request'
DOWNLOAD_CONNECT = 'connect'
DOWNLOAD_ABORT = 'abort'

class DownloadManager:
    class Task:
        def __init__(self, bot_name, item, status=DOWNLOAD_REQUEST, filesize=None):
            self.bot_name = bot_name
            self.item = item
            self.status = status
            self.filesize = filesize

    def __init__(self, concurrent_downloads, bot_name, trusted_bots):
        self.bot_name = bot_name
        self.concurrent_downloads = threading.Semaphore(concurrent_downloads)
        self.trusted_bots = trusted_bots
        self.awaiting = queue.Queue()
        self.ongoing = {}
        self.ongoing_lock = threading.Lock()
        self._thread = self.create_thread()

    def create_thread(self):
        return threading.Thread(target=self._run)

    def start(self):
        if not self._thread.is_alive():
            self._thread = self.create_thread()
            self._thread.start()

    def terminate(self, force=False):
        if self._thread.is_alive():
            if force:
                self.concurrent_downloads.release()
            self.awaiting.put(None)

    def _run(self):
        while True:
            self.concurrent_downloads.acquire()
            # Prevent deadlocks
            try:
                item = self.awaiting.get(timeout=30)
            except queue.Empty:
                break

            if item is None:
                break

            self.download_request(item)

    def count_awaiting(self):
        return self.awaiting.qsize()

    def count_ongoing(self):
        return len(self.ongoing)

    def is_ongoing(self, filename):
        with self.ongoing_lock:
            return filename in self.ongoing

    def finish_task(self, filename):
        with self.ongoing_lock:
            task = self.ongoing[filename]
            del self.ongoing[filename]
            self.concurrent_downloads.release()
            if self.count_ongoing() + self.count_awaiting() == 0:
                self.terminate()
            return task

    def download_request(self, item: PacklistItem):
        hexchat.command("MSG {} XDCC SEND {}".format(self.bot_name, item.packnumber))
        with self.ongoing_lock:
            task = DownloadManager.Task(self.bot_name, item)
            self.ongoing[item.filename] = task
            return task

    def download_abort(self, dcc_bot_name, filename):
        hexchat.emit_print("DCC RECV Abort", dcc_bot_name, filename)
        task = self.finish_task(filename)
        hexchat.command("MSG {} XDCC CANCEL".format(task.bot_name))
        return task

    def send_offer_callback(self, dcc_bot_name, filename, filesize, ip_addr):
        if dcc_bot_name in self.trusted_bots:
            with self.ongoing_lock:
                if filename in self.ongoing:
                    hexchat.emit_print("DCC RECV Connect", dcc_bot_name, ip_addr, filename)
                    task = self.ongoing[filename]
                    task.filesize = filesize
                    task.status = DOWNLOAD_CONNECT
                    return (DOWNLOAD_CONNECT, task.item)

            return (None, None)

        task = self.download_abort(dcc_bot_name, filename)
        return (DOWNLOAD_ABORT, task.item)

    def recv_complete_callback(self, filename):
        task = self.finish_task(filename)
        return (task.item, task.filesize)
