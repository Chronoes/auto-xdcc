import json
import logging
import re
import threading
import requests
import os
import urllib.parse
from typing import Optional, Callable, Iterator

from auto_xdcc.timer import Timer
from auto_xdcc.download_manager import DownloadManager
from auto_xdcc.packlist_item import PacklistItem
from auto_xdcc.util import get_dcc_completed_dir

class Packlist:
    class HTTPRequest:
        def __init__(self, filepath: str, url: str):
            self.filepath = filepath
            self.url = url
            self.query_template = ''
            self.logger = logging.getLogger('packlist.http_request')

        @staticmethod
        def retry_connection(request_fn: Callable[[], requests.Request], retries: int) -> Optional[requests.Response]:
            if retries <= 0:
                return None

            try:
                return request_fn()
            except (requests.Timeout, requests.ConnectionError):
                return Packlist.HTTPRequest.retry_connection(request_fn, retries - 1)

        def _do_request(self, params: dict, stream: bool = False) -> Optional[requests.Response]:
            return self.retry_connection(lambda: requests.get(self.url, stream=stream, timeout=10, params=self.compose_query(params)), 3)

        def compose_query(self, params: dict) -> dict:
            if not self.query_template:
                return {}
            query = self.query_template.format_map(params)
            return urllib.parse.parse_qs(query)

        def fetch_content(self, bot_name='', fresh: bool = True) -> iter:
            if not fresh and os.path.exists(self.filepath):
                with open(self.filepath) as f:
                    return f.readlines()
            r = self._do_request({'bot_name': bot_name})

            if not r:
                return iter([])

            self.logger.debug('Updating %s with content from %s', self.filepath, self.url)
            with open(self.filepath, 'w') as f:
                f.write(r.text)

            return r.iter_lines(decode_unicode=True)

    class BotRequest:
        def __init__(self, filepath: str, packlist_name: str, download_manager: DownloadManager):
            self.filepath = filepath
            self.packlist_name = packlist_name
            self.download_manager = download_manager
            self.logger = logging.getLogger('packlist.bot_request')

        def _do_request(self, bot_name: str):
            self.logger.debug('Requesting packlist from %s for %s', bot_name, self.packlist_name)
            task = self.download_manager.request_list(bot_name, self.packlist_name)
            # Wait for download task completion
            task.completion_event.wait(120)
            return task

        def fetch_content(self, bot_name='', fresh: bool = True):
            if not fresh and os.path.exists(self.filepath):
                self.logger.debug('Returning existing content from %s', self.filepath)
                with open(self.filepath) as f:
                    return f.readlines()
            task = self._do_request(bot_name)

            if not (task and task.is_complete()):
                self.logger.error('Failed to fetch packlist %s', self.packlist_name)
                return []

            with open(task.get_filepath()) as f:
                lines = f.readlines()

            self.logger.debug('Updating %s with %s', self.filepath, task.get_filepath())
            os.replace(task.get_filepath(), self.filepath)
            return lines

    def __init__(self, name: str, current: str, trusted: list,
                    refresh_interval: int = 900, concurrent_downloads: int = 1):
        self.name = name
        self.refresh_interval = refresh_interval
        self.concurrent_downloads = concurrent_downloads
        self.current = current
        self.trusted = trusted
        self.refresh_timer = None
        self.download_manager = self.create_manager()
        self.url = None
        self.request = Packlist.BotRequest(self.get_packlist_filepath(), self.name, self.download_manager)

    @classmethod
    def from_config(cls, name: str, config: dict):
        new_pl = cls(
            name, config['current'], config['trusted'],
            refresh_interval=config['refreshInterval'], concurrent_downloads=config['maxConcurrentDownloads']
        )

        if config.get('url'):
            new_pl.init_request_params(config['url'])
        return new_pl

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        return self.name == other.name

    def get_packlist_filepath(self) -> str:
        return os.path.join(get_dcc_completed_dir(), '{}-packlist.txt'.format(self.name))

    def init_request_params(self, url: str):
        self.url = url
        self.request = Packlist.HTTPRequest(self.get_packlist_filepath(), self.url)

    def create_manager(self) -> DownloadManager:
        return DownloadManager(self.concurrent_downloads, self.trusted)

    def convert_line(self, line: str) -> Optional[PacklistItem]:
        raise NotImplementedError('Must be implemented in subclass')

    def __iter__(self) -> Iterator[PacklistItem]:
        return self.get_items()

    def get_items(self, fresh: bool = True) -> Iterator[PacklistItem]:
        lines = self.request.fetch_content(bot_name=self.current, fresh=fresh)
        for line in lines:
            if line:
                item = self.convert_line(line.strip())
                if item:
                    yield item

    def register_refresh_timer(self, on_refresh: Callable[[object], bool]):
        self.refresh_timer = Timer(self.refresh_interval*1000, on_refresh)
        self.refresh_timer.register(self)

    def run_once(self, time=1):
        assert self.refresh_timer is not None
        self.refresh_timer.callback(self)

    def set_query_template(self, qstring: str):
        if type(self.request) == Packlist.HTTPRequest:
            self.request.query_template = qstring

    def search(self, search_str: str, callback):
        def run_thread():
            matching = {}
            for item in self.get_items(fresh=False):
                show_name = item.show_name.lower()
                if search_str.lower() in show_name:
                    match = matching.setdefault(show_name, [])
                    match.append(item)

            callback(matching)
        t = threading.Thread(target=run_thread)
        t.start()


filename_pattern = r"""
(   \[.+\]\          # Start of filename, fansub group name
    (.+)\ -\         # show name, delimiter
    ([0-9]{2,4}) \s* # Episode nr
    (?: \[?(v[0-9])\] ?)? \s* # Optional version of episode
    (\(.+\)|\[.+\])  # Tags delimited by round or square brackets
    .*\.[a-z]+       # Other optional text, filename extension
)
"""

def process_tags(tags):
    if tags.startswith('('):
        tags_list = tags.strip('()').split(')(')
    else:
        tags_list = tags.strip('[]').split('][')

    resolution = None
    for tag in tags_list:
        match = re.fullmatch(r'^[0-9]{3,4}p$', tag)
        if match and not resolution:
            resolution = int(match.group(0).strip('p'))

    return [resolution]

class TextPacklist(Packlist):
    pack_format = re.compile(
        r"""^\#([0-9]+) \s+  # Start of line, packnumber
        [0-9]+x\             # download count
        \[([ \.0-9]{3}[MG])\]\ # filesize
        """
        + filename_pattern
        + r"""$              # End of filename, end of line
        """, re.VERBOSE)

    def convert_line(self, line: str) -> Optional[PacklistItem]:
        if line.startswith("#"):
            match = self.pack_format.fullmatch(line)
            if match:
                packnumber, size, filename, show_name, episode_nr, version, tags = match.groups()
                if version:
                    version = int(version.strip('v'))

                [resolution] = process_tags(tags)
                if resolution is None:
                    return None

                return PacklistItem(int(packnumber), size.strip(), filename, show_name, int(episode_nr), version, resolution)
        return None


class JSPacklist(Packlist):
    line_format = re.compile(r"(\{.*\})")
    file_format = re.compile(r"^" + filename_pattern + r"$", re.VERBOSE)
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
                filename, show_name, episode_nr, version, tags = match.groups()
                if version:
                    version = int(version.strip('v'))

                [resolution] = process_tags(tags)
                if resolution is None:
                    return None

                return PacklistItem(
                    int(j.get(self.keys['packnumber'])), j.get(self.keys['size']),
                    filename, show_name, int(episode_nr), version, resolution
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

    return packlist
