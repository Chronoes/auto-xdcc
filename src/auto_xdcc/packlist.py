import re
import requests

import auto_xdcc.printer as printer
from auto_xdcc.timer import Timer
from auto_xdcc.download_manager import DownloadManager
from auto_xdcc.packlist_item import PacklistItem

class Packlist:
    pack_format = re.compile(r"^#([0-9]+)\s+[0-9]+x \[([ \.0-9]+[MG])\] (\[.+\] (.+) - ([0-9]{2})(v[0-9])? \[(480|720|1080)p\]\.[a-z]+)$")

    def __init__(self, name, url, current, trusted, last_request=0, last_pack=0, refresh_interval=900, concurrent_downloads=1):
        self.name = name
        self.url = url
        self.last_request = last_request
        self.last_pack = last_pack
        self.refresh_interval = refresh_interval
        self.concurrent_downloads = concurrent_downloads
        self.current = current
        self.trusted = trusted
        self.refresh_timer = None
        self.download_manager = self.create_manager()

    @classmethod
    def from_config(cls, name, config):
        return cls(
            name,
            config['url'], config['current'], config['trusted'],
            config['contentLength'], config['lastPack'],
            config['refreshInterval'], config['maxConcurrentDownloads']
        )

    def __str__(self):
        return self.name

    def reset(self):
        self.last_request = 0
        self.last_pack = 0

    def create_manager(self):
        return DownloadManager(self.concurrent_downloads, self.current, self.trusted)

    @staticmethod
    def retry_connection(request_fn, retries):
        if retries <= 0:
            return None

        try:
            return request_fn()
        except (requests.Timeout, requests.ConnectionError):
            return __class__.retry_connection(request_fn, retries - 1)

    def check_diff(self):

        r = self.retry_connection(lambda: requests.head(self.url, timeout=5), 3)

        if r is None:
            return False

        content_len = int(r.headers['content-length'])
        if content_len > self.last_request + 30:
            self.last_request = content_len
            return True

        return False

    def __iter__(self):
        r = self.retry_connection(lambda: requests.get(self.url, stream=True, timeout=10), 3)
        if r is None:
            yield None
        for line in r.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("#"):

                    match = self.pack_format.fullmatch(line)
                    if match:
                        packnumber, size, filename, show_name, episode_nr, version, resolution = match.groups()
                        if version:
                            version = int(version.strip('v'))
                        item = PacklistItem(int(packnumber), size.strip(), filename, show_name, int(episode_nr), version, int(resolution))

                        yield item

    def get_new_items(self):
        for item in self:
            if item and item.packnumber > self.last_pack:
                self.last_pack = item.packnumber
                yield item

    def register_refresh_timer(self, on_refresh):
        self.refresh_timer = Timer(self.refresh_interval, on_refresh)
        self.refresh_timer.register(self)
