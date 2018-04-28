class PacklistItem:
    def __init__(self, packnumber, size, filename, show_name, episode_nr, version, resolution):
        self.packnumber = packnumber
        self.size = size
        self.filename = filename
        self.show_name = show_name
        self.episode_nr = episode_nr
        self.version = version
        self.resolution = resolution

    def is_new(self, episode_nr, resolution):
        return (episode_nr is None or self.episode_nr > episode_nr) and self.resolution == resolution
