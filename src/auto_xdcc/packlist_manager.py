import logging
import threading
from typing import Dict

import auto_xdcc.config as gconfig
from auto_xdcc.packlist_item import PacklistItem
from auto_xdcc.util import is_modified_filename
from auto_xdcc.packlist import Packlist, create_packlist


class PacklistManager:
    def __init__(self):
        self.packlists: Dict[str, Packlist] = {}
        self.queued_downloads: Dict[str, Packlist] = {}
        self.refresh_lock = threading.Lock()
        self.search_cache = []

    def register_packlists(self):
        config = gconfig.get()
        for key in config['packlists']:
            packlist = create_packlist(key, config['packlists'][key])
            self.register_timers(packlist)
            self.packlists[key] = packlist
        return self.packlists

    def _refresh_thread(self, packlist: Packlist):
        config = gconfig.get()
        logger = logging.getLogger('refresh_timer')
        logger.info("Starting packlist check for %s", packlist.name)
        with self.refresh_lock:
            for item in packlist:
                if item.show_name in config['shows']:
                    [episode_nr, resolution, _subdir] = config['shows'][item.show_name]
                    if item.is_new(episode_nr, resolution) and item.filename not in self.queued_downloads:
                        packlist.download_manager.queue_download(packlist.current, item)
                        self.queued_downloads[item.filename] = packlist
                        logger.info("Queueing download of %s - %02d", item.show_name, item.episode_nr)
                        config.printer.prog("Queueing download of {} - {:02d}.".format(item.show_name, item.episode_nr))

            packlist.download_manager.start()
            config.printer.flush()

        logger.info("Ending packlist check for %s", packlist.name)

        return True

    def refresh_timer_callback(self, packlist: Packlist):
        t = threading.Thread(target=self._refresh_thread, args=(packlist,))
        t.start()
        return True

    def get_packlist_by(self, filename: str):
        if filename in self.queued_downloads:
            return self.queued_downloads.get(filename)

        for packlist in self.packlists.values():
            # Check if download managers have task for this
            if packlist.download_manager.get_task(filename):
                return packlist

        for download in self.queued_downloads.keys():
            if is_modified_filename(download, filename):
                return self.queued_downloads.get(download)

        return None

    def register_timers(self, packlist: Packlist):
        packlist.register_refresh_timer(self.refresh_timer_callback)

    def clear_download_queue(self):
        self.queued_downloads.clear()

    def clear_search_cache(self):
        self.search_cache.clear()

    def update_search_cache(self, item: PacklistItem):
        self.search_cache.append(item)
        return len(self.search_cache)

    def get_from_search_cache(self, idx: int):
        if len(self.search_cache) < idx:
            return None
        return self.search_cache[idx - 1]
