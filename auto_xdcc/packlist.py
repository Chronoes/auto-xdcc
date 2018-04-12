import re
import requests

from collections import namedtuple

# Create named tuple
PacklistItem = namedtuple('PacklistItem', ['packnumber', 'size', 'filename', 'episode_name', 'episode_nr', 'version', 'resolution'])

class Packlist:
    pack_format = re.compile(r"^#([0-9]+)\s+[0-9]+x \[([ \.0-9]+[MG])\] (\[.+\] (.+) - ([0-9]{2})(v[0-9])? \[(480|720|1080)p\]\.[a-z]+)$")

    def __init__(self, url, last_request=0, last_seen=0):
        self.url = url
        self.last_request = last_request
        self.last_seen = last_seen

    def check_diff(self):
        r = requests.head(self.url, timeout=5)
        content_len = int(r.headers['content-length'])
        if content_len > self.last_request + 30:
            self.last_request = content_len
            return True

        return False

    def __iter__(self):
        r = requests.get(self.url, stream=True, timeout=10)
        for line in r.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("#"):

                    match = self.pack_format.fullmatch(line)
                    if match:
                        packnumber, size, filename, episode_name, episode_nr, version, resolution = match.groups()
                        item = PacklistItem(int(packnumber), size.strip(), filename, episode_name, int(episode_nr), version, int(resolution))

                        yield item

    def get_new_items(self):
        for item in self:
            if item.packnumber > self.last_seen:
                yield item
