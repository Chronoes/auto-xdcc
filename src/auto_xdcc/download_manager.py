import threading
import queue
import logging

# pylint: disable=E0401
import hexchat

from auto_xdcc.thread_runner import ThreadRunner
from auto_xdcc.util import is_modified_filename

DOWNLOAD_ABORT = -1
DOWNLOAD_AWAITING = 0
DOWNLOAD_REQUEST = 1
DOWNLOAD_CONNECT = 2


class DownloadManager(ThreadRunner):
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
        super().__init__(logging.getLogger('download_manager'))

    def terminate(self, force=False):
        if super().terminate(force=force) and force:
            self.concurrent_downloads.release()

    def _run(self):
        logger = logging.getLogger('download_manager.thread')

        logger.debug("Starting download manager thread")
        while not self.is_stopping():
            # Prevent deadlocks
            try:
                task = self.awaiting.get(timeout=30)
            except queue.Empty:
                break

            self.concurrent_downloads.acquire()

            if self.is_stopping():
                self.concurrent_downloads.release()
                break

            logger.debug("Sending download request for %s", task.item.filename)
            self.download_request(task)

        logger.debug("Closing download manager thread")

    def count_awaiting(self):
        return self.awaiting.qsize()

    def count_ongoing(self):
        return len(self.ongoing)

    def get_task(self, filename):
        if filename in self.ongoing:
            return self.ongoing[filename]
        else:
            for download in self.ongoing:
                if is_modified_filename(download, filename):
                    return self.ongoing[download]
        return None

    def is_ongoing(self, filename):
        return self.get_task(filename) is not None

    def queue_download(self, bot_name, item):
        task = DownloadManager.Task(bot_name, item)
        self.awaiting.put(task)

    def finish_task(self, filename):
        with self.ongoing_lock:
            task = self.get_task(filename)
            del self.ongoing[task.item.filename]
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
                task = self.get_task(filename)

                if task:
                    hexchat.emit_print("DCC RECV Connect", dcc_bot_name, ip_addr, filename)
                    task.filesize = filesize
                    task.status = DOWNLOAD_CONNECT
                    return (DOWNLOAD_CONNECT, task.item)

            return (None, None)

        task = self.download_abort(dcc_bot_name, filename)
        return (DOWNLOAD_ABORT, task.item)

    def recv_complete_callback(self, filename):
        task = self.finish_task(filename)
        return (task.item, task.filesize)
