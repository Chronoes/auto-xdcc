from collections import namedtuple

PacklistItemTuple = namedtuple(
    "PacklistItemTuple", ["packnumber", "size", "filename", "show_name", "episode_nr", "version", "resolution"]
)

Show = namedtuple("Show", ["name", "episode_nr", "version", "resolution", "subdir"])


class PacklistItem(PacklistItemTuple):
    def is_new(self, episode_nr, resolution, version=0):
        return (
            episode_nr is None or self.episode_nr > episode_nr or self.version > version
        ) and self.resolution == resolution

    def is_new_episode(self, show: Show):
        return self.is_new(show.episode_nr, show.resolution, show.version)

    def short_item_name(self):
        return "#{} {} - {:02}".format(self.packnumber, self.show_name, self.episode_nr)
