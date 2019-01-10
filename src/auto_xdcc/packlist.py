import json
import re
import requests
import urllib.parse
from typing import Optional, Callable, Iterator

from auto_xdcc.timer import Timer
from auto_xdcc.download_manager import DownloadManager
from auto_xdcc.packlist_item import PacklistItem

class Packlist:
    class Request:
        def __init__(self, url: str):
            self.url = url
            self.query_template = ''
            self.method = 'GET'

            self._request_cache = None

        @staticmethod
        def retry_connection(request_fn: Callable[[], requests.Request], retries: int) -> Optional[requests.Request]:
            if retries <= 0:
                return None

            try:
                return request_fn()
            except (requests.Timeout, requests.ConnectionError):
                return __class__.retry_connection(request_fn, retries - 1)


        def _do_request(self, params: dict, stream: bool = False) -> Optional[requests.Request]:
            return self.retry_connection(lambda: requests.get(self.url, stream=stream, timeout=10, params=self.compose_query(params)), 3)

        def compose_query(self, params: dict) -> Optional[requests.Request]:
            if not self.query_template:
                return {}
            query = self.query_template.format_map(params)
            return urllib.parse.parse_qs(query)

        def fetch_content_len(self, **params) -> Optional[int]:
            if self.method == 'HEAD':
                r = self.retry_connection(lambda: requests.head(self.url, timeout=5, params=self.compose_query(params)), 3)
                if r is None:
                    return None

                content_len = int(r.headers['content-length'])
            else:
                r = self._do_request(params)
                if r is None:
                    return None

                content_len = len(r.content)
                # Cache GET request for efficient iteration over content
                self._request_cache = r

            return content_len

        def fetch_content(self, **params) -> Optional[requests.Request]:
            if self._request_cache:
                r = self._request_cache
                # Remove request from cache
                self._request_cache = None
                return r

            return self._do_request(params)


    def __init__(self, name: str, url: str, current: str, trusted: list,
                last_request: int = 0, last_pack: int = 0, refresh_interval: int = 900, concurrent_downloads: int = 1):
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

        self.request = Packlist.Request(self.url)

    @classmethod
    def from_config(cls, name: str, config: dict):
        return cls(
            name,
            config['url'], config['current'], config['trusted'],
            config['contentLength'], config['lastPack'],
            config['refreshInterval'], config['maxConcurrentDownloads']
        )

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        return self.name == other.name

    def reset(self):
        self.last_request = 0
        self.last_pack = 0

    def create_manager(self) -> DownloadManager:
        return DownloadManager(self.concurrent_downloads, self.trusted)

    def check_diff(self) -> bool:
        content_len = self.request.fetch_content_len(bot_name=self.current)

        if content_len is None:
            return False

        if content_len > self.last_request + 30:
            self.last_request = content_len
            return True

        return False

    def convert_line(self, line: str) -> Optional[PacklistItem]:
        raise NotImplementedError('Must be implemented in subclass')

    def __iter__(self) -> Iterator[PacklistItem]:
        r = self.request.fetch_content(bot_name=self.current)

        if r is None:
            return iter([])

        for line in r.iter_lines():
            if line:
                line = line.decode("utf-8")
                item = self.convert_line(line)
                if item:
                    yield item

    def get_new_items(self) -> Iterator[PacklistItem]:
        for item in self:
            if item and item.packnumber > self.last_pack:
                self.last_pack = item.packnumber
                yield item

    def register_refresh_timer(self, on_refresh: Callable[[object], bool]):
        self.refresh_timer = Timer(self.refresh_interval, on_refresh)
        self.refresh_timer.register(self)

    def set_query_template(self, qstring: str):
        self.request.query_template = qstring

    def set_request_method(self, method: str):
        self.request.method = method


class TextPacklist(Packlist):
    pack_format = re.compile(r"^#([0-9]+)\s+[0-9]+x \[([ \.0-9]+[MG])\] (\[.+\] (.+) - ([0-9]{2})(v[0-9])? \[(480|720|1080)p\]\.[a-z]+)$")

    def convert_line(self, line: str) -> Optional[PacklistItem]:
        if line.startswith("#"):
            match = self.pack_format.fullmatch(line)
            if match:
                packnumber, size, filename, show_name, episode_nr, version, resolution = match.groups()
                if version:
                    version = int(version.strip('v'))
                return PacklistItem(int(packnumber), size.strip(), filename, show_name, int(episode_nr), version, int(resolution))
        return None


class JSPacklist(Packlist):
    line_format = re.compile(r"(\{.*\})")
    file_format = re.compile(r"^(\[.+\] (.+) - ([0-9]{2})(v[0-9])? \[(480|720|1080)p\]\.[a-z]+)$")
    unquoted_keys = re.compile(r'([^\{\}])\s*:')
    quote_keys = r'"\1":'

    required_keys = set(['bot_name', 'packnumber', 'size', 'filename'])

    def set_json_keys(self, **keys):
        if set(keys) < self.required_keys:
            raise RuntimeError("Missing required keys {}".format(', '.join(self.required_keys)))
        self.keys = keys

    def convert_line(self, line: str) -> Optional[PacklistItem]:
        stripped_line = re.search(self.line_format, line)
        if stripped_line:
            json_line = self.unquoted_keys.sub(self.quote_keys, stripped_line.group(0))
            j = json.loads(json_line)
            match = self.file_format.fullmatch(j.get(self.keys['filename']))
            if match:
                filename, show_name, episode_nr, version, resolution = match.groups()
                if version:
                    version = int(version.strip('v'))
                return PacklistItem(
                    int(j.get(self.keys['packnumber'])), j.get(self.keys['size']),
                    filename, show_name, int(episode_nr), version, int(resolution)
                )
        return None


def create_packlist(name: str, config: dict) -> Packlist:
    meta_type = set(config['metaType'])
    if 'text' in meta_type:
        meta_type.remove('text')
        packlist = TextPacklist.from_config(name, config)
    elif 'js' in meta_type:
        meta_type.remove('js')
        packlist = JSPacklist.from_config(name, config)
        packlist.set_json_keys(**config['jsonKeys'])
    else:
        raise RuntimeError('No appropriate meta types given for packlist {}'.format(name))

    for t in meta_type:
        if t.startswith('query:'):
            packlist.set_query_template(t.replace('query:', '', 1))
        elif t.startswith('request:'):
            packlist.set_request_method(t.replace('request:', '', 1))

    return packlist
