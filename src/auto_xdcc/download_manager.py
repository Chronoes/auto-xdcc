import threading
import queue
import logging

# pylint: disable=E0401
import hexchat

import auto_xdcc.printer as printer
from auto_xdcc.packlist_item import PacklistItem

DOWNLOAD_ABORT = -1
DOWNLOAD_AWAITING = 0
DOWNLOAD_REQUEST = 1
DOWNLOAD_CONNECT = 2


class DownloadManager:
    class Task:
        def __init__(self, bot_name, item, status=DOWNLOAD_AWAITING, filesize=None):
            self.bot_name = bot_name
            self.item = item
            self.status = status
            self.filesize = filesize

        def __str__(self):
            return "{} ({}) - {}".format(self.bot_name, self.status, self.item.show_name)

    def __init__(self, concurrent_downloads, trusted_bots):
        self.concurrent_downloads = threading.Semaphore(concurrent_downloads)
        self.trusted_bots = trusted_bots
        self.awaiting = queue.Queue()
        self.ongoing = {}
        self.ongoing_lock = threading.Lock()
        self._thread = self.create_thread()
        self.logger = logging.getLogger('download_manager')

    def create_thread(self):
        return threading.Thread(target=self._run)

    def start(self):
        if not self._thread.is_alive():
            self.logger.debug("Creating and starting thread")
            self._thread = self.create_thread()
            self._thread.start()

    def terminate(self, force=False):
        if self._thread.is_alive():
            self.logger.debug("Terminating running thread")
            self._thread_stop = True
            if force:
                self.concurrent_downloads.release()

    def _run(self):
        self._thread_stop = False
        logger = logging.getLogger('download_manager.thread')

        logger.debug("Starting download manager thread")
        while not self._thread_stop:
            # Prevent deadlocks
            try:
                task = self.awaiting.get(timeout=30)
            except queue.Empty:
                break

            self.concurrent_downloads.acquire()

            if self._thread_stop:
                self.concurrent_downloads.release()
                break

            logger.debug("Sending download request for %s", task.item.filename)
            self.download_request(task)

        logger.debug("Closing download manager thread")

    def count_awaiting(self):
        return self.awaiting.qsize()

    def count_ongoing(self):
        return len(self.ongoing)

    def is_ongoing(self, filename):
        with self.ongoing_lock:
            return filename in self.ongoing

    def queue_download(self, bot_name, item):
        task = DownloadManager.Task(bot_name, item)
        self.awaiting.put(task)

    def finish_task(self, filename):
        with self.ongoing_lock:
            task = self.ongoing[filename]
            del self.ongoing[filename]
            self.concurrent_downloads.release()
            self.logger.debug("Finishing task for %s", task)
            return task

    def download_request(self, task: Task):
        hexchat.command("MSG {} XDCC SEND {}".format(task.bot_name, task.item.packnumber))
        with self.ongoing_lock:
            task.status = DOWNLOAD_REQUEST
            self.ongoing[task.item.filename] = task
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
