import threading
import queue
import logging
import os.path
from typing import Optional

# pylint: disable=E0401
import hexchat

from auto_xdcc.packlist_item import PacklistItem
from auto_xdcc.util import is_modified_filename

DOWNLOAD_ABORT = -1
DOWNLOAD_AWAITING = 0
DOWNLOAD_REQUEST = 1
DOWNLOAD_CONNECT = 2
DOWNLOAD_COMPLETE = 10


class DownloadManager:
    class Task:
        def __init__(self, bot_name, item, status=DOWNLOAD_AWAITING, filesize=None):
            self.bot_name = bot_name
            self.item = item
            self.status = status
            self.filesize = filesize
            self.filename = ''

        def __str__(self):
            if type(self.item) == PacklistItem:
                return "{} ({}) - {}".format(self.bot_name, self.status, self.item.show_name)
            else:
                return "{} ({}) - {}".format(self.bot_name, self.status, self.item)

        def get_key(self) -> str:
            if type(self.item) == PacklistItem:
                return self.item.filename
            return str(self.item)

        def get_filename(self) -> str:
            if type(self.item) == PacklistItem:
                return self.item.filename
            return self.filename

        def get_filepath(self) -> str:
            return os.path.join(hexchat.get_prefs('dcc_dir'), self.get_filename())

    def __init__(self, concurrent_downloads, trusted_bots):
        self.concurrent_downloads = threading.Semaphore(concurrent_downloads)
        self.trusted_bots = trusted_bots
        self.awaiting = queue.Queue()
        self.ongoing = {}
        self.ongoing_lock = threading.Lock()
        self._thread = self.create_thread()
        self.logger = logging.getLogger('download_manager')
        self.request_list_task = None
        self.request_list_event = None

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
                task = self.awaiting.get(timeout=60)
            except queue.Empty:
                break

            self.concurrent_downloads.acquire()

            if self._thread_stop:
                self.concurrent_downloads.release()
                break

            logger.debug("Sending download request for %s", task.get_key())
            self.download_request(task)

        logger.debug("Closing download manager thread")

    def count_awaiting(self):
        return self.awaiting.qsize()

    def count_ongoing(self):
        return len(self.ongoing)

    def get_task(self, filename: str) -> Optional[Task]:
        if filename in self.ongoing:
            return self.ongoing[filename]
        elif self.request_list_task and 'xdcc.txt' in filename:
            task = self.request_list_task
            task.filename = filename
            return self.request_list_task
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
            task.status = DOWNLOAD_COMPLETE
            if task == self.request_list_task:
                self.request_list_event.set()
                self.request_list_task = None
            else:
                del self.ongoing[task.get_key()]
                self.concurrent_downloads.release()
            self.logger.debug("Finishing task for %s", task)
        return task

    def download_request(self, task: Task):
        hexchat.command("MSG {} XDCC SEND {}".format(task.bot_name, task.item.packnumber))
        task.status = DOWNLOAD_REQUEST
        with self.ongoing_lock:
            self.ongoing[task.get_key()] = task
        return task

    def request_list(self, bot_name: str, packlist_name: str, event: threading.Event):
        task = DownloadManager.Task(bot_name, '{} packlist'.format(packlist_name))
        hexchat.command("MSG {} XDCC SEND LIST".format(task.bot_name))
        self.logger.debug('Requesting packlist from %s', task.bot_name)
        task.status = DOWNLOAD_REQUEST
        self.request_list_task = task
        self.request_list_event = event
        return task

    def download_abort(self, dcc_bot_name, filename):
        hexchat.emit_print("DCC RECV Abort", dcc_bot_name, filename)
        task = self.finish_task(filename)
        task.status = DOWNLOAD_ABORT
        hexchat.command("MSG {} XDCC CANCEL".format(task.bot_name))
        return task

    def send_offer_callback(self, dcc_bot_name, filename, filesize, ip_addr):
        if dcc_bot_name in self.trusted_bots:
            with self.ongoing_lock:
                task = self.get_task(filename)

                if task:
                    self.logger.debug('Found task %s for filename %s', str(task), filename)
                    hexchat.emit_print("DCC RECV Connect", dcc_bot_name, ip_addr, filename)
                    task.filesize = filesize
                    task.status = DOWNLOAD_CONNECT
                    return (DOWNLOAD_CONNECT, task.item)
                else:
                    self.logger.error('No task for filename %s', filename)
            return (None, None)

        task = self.download_abort(dcc_bot_name, filename)
        return (DOWNLOAD_ABORT, task.item)

    def recv_complete_callback(self, filename):
        task = self.finish_task(filename)
        return (task.item, task.filesize)
