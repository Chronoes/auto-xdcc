import threading
import queue
import logging
import os.path
from typing import Optional

# pylint: disable=E0401
import hexchat

from auto_xdcc.thread_runner import ThreadRunner
from auto_xdcc.packlist_item import PacklistItem
from auto_xdcc.util import get_dcc_completed_dir, is_modified_filename

DOWNLOAD_ABORT = -1
DOWNLOAD_AWAITING = 0
DOWNLOAD_REQUEST = 1
DOWNLOAD_CONNECT = 2
DOWNLOAD_COMPLETE = 10


class DownloadManager(ThreadRunner):
    class Task:
        def __init__(self, bot_name, item, task_type='regular', status=DOWNLOAD_AWAITING, filesize=None):
            self.bot_name = bot_name
            self.item = item
            self.task_type = task_type
            self.status = status
            self.filesize = filesize
            self.filename = ''
            self.completion_event = threading.Event()

        def __str__(self):
            if type(self.item) == PacklistItem:
                return "{} ({}) - {}".format(self.bot_name, self.status, self.item.show_name)
            else:
                return "{} ({}) - {}".format(self.bot_name, self.status, self.item)

        def get_key(self) -> str:
            if type(self.item) == PacklistItem:
                return self.item.filename
            return '{} {}'.format(self.task_type, self.item)

        def get_filename(self) -> str:
            if not self.filename and type(self.item) == PacklistItem:
                return self.item.filename
            return self.filename

        def get_filepath(self) -> str:
            return os.path.join(get_dcc_completed_dir(), self.get_filename())

        def is_complete(self) -> bool:
            return self.status == DOWNLOAD_COMPLETE

    def __init__(self, concurrent_downloads, trusted_bots):
        self.concurrent_downloads = threading.Semaphore(concurrent_downloads)
        self.trusted_bots = trusted_bots
        self.awaiting = queue.Queue()
        self.ongoing = {}
        self.ongoing_lock = threading.Lock()
        self._thread = self.create_thread()
        self.request_list_task = None
        super().__init__(logging.getLogger('download_manager'))

    def terminate(self, force=False):
        if super().terminate(force=force) and force:
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
        elif 'xdcc.txt' in filename:
            for task in self.ongoing.values():
                if task.task_type == 'packlist':
                    task.filename = filename
                    return task
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
            task.completion_event.set()
            del self.ongoing[task.get_key()]
            if task.task_type == 'regular':
                self.concurrent_downloads.release()
            self.logger.debug("Finishing task for %s", task)
        return task

    def _download_task(self, task: Task):
        task.status = DOWNLOAD_REQUEST
        with self.ongoing_lock:
            self.ongoing[task.get_key()] = task

    def download_request(self, task: Task):
        self._download_task(task)
        hexchat.command("MSG {} XDCC SEND {}".format(task.bot_name, task.item.packnumber))
        return task

    def request_list(self, bot_name: str, packlist_name: str):
        task = DownloadManager.Task(bot_name, packlist_name, task_type='packlist')
        self._download_task(task)
        hexchat.command("MSG {} XDCC SEND LIST".format(task.bot_name))
        self.logger.debug('Requesting packlist from %s', task.bot_name)
        return task

    def download_abort(self, dcc_bot_name, filename):
        hexchat.emit_print("DCC RECV Abort", dcc_bot_name, filename)
        task = self.finish_task(filename)
        task.status = DOWNLOAD_ABORT
        task.completion_event.set()
        hexchat.command("MSG {} XDCC CANCEL".format(task.bot_name))
        return task

    def send_offer_callback(self, dcc_bot_name, filename, filesize, ip_addr):
        if dcc_bot_name in self.trusted_bots:
            with self.ongoing_lock:
                task = self.get_task(filename)

                if task:
                    self.logger.debug('Found task %s for filename %s', str(task), filename)
                    hexchat.emit_print("DCC RECV Connect", dcc_bot_name, ip_addr, filename)
                    task.filename = filename
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
