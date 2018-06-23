from collections import namedtuple

PacklistItemTuple = namedtuple('PacklistItemTuple', ['packnumber', 'size', 'filename', 'show_name', 'episode_nr', 'version', 'resolution'])

class PacklistItem(PacklistItemTuple):
    def is_new(self, episode_nr, resolution):
        return (episode_nr is None or self.episode_nr > episode_nr) and self.resolution == resolution
