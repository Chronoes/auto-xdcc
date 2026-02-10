import json
import os.path
import collections

from auto_xdcc.packlist_item import Show


class Config(collections.UserDict):
    packlist_manager = None
    printer = None
    telegram_bot = None

    def __init__(self, path):
        self.path = path
        super().__init__(Config.load_config(path))

    @staticmethod
    def load_config(path):
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f)

        raise Exception('Could not load configuration. Please check if "{}" exists and is accessible'.format(path))

    @staticmethod
    def save_config(path, data):
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def persist(self):
        Config.save_config(self.path, self.data)

    def partial_match(self, *keypath, key):
        """
        Attempts to match key against keys in the config in given keypath
        using case insensitive substring match.

        Returns: list of matched (key, value) pairs
        """
        data = self.data
        for kp in keypath:
            if type(data) is not dict:
                raise TypeError("Value at keypath {} is not a dictionary".format(" -> ".join(keypath)))
            elif kp not in data:
                raise KeyError("Check the keypath: {} does not exist in config".format(" -> ".join(keypath)))
            data = data[kp]

        search_key = key.lower().replace(" ", "")
        return [(k, v) for k, v in data.items() if search_key in k.lower().replace(" ", "")]

    def partial_match_shows(self, t="shows", key=""):
        return [self._get_show_strict(show_name, t) for show_name, _ in self.partial_match(t, key=key)]

    def list_shows(self, t="shows"):
        return [self._get_show_strict(show_name, t) for show_name in self.data[t].keys()]

    def get_show(self, show_name: str, t="shows") -> Show | None:
        shows = self.data[t]
        if show_name not in shows:
            return None
        show = shows[show_name]

        if type(show) is list:
            return Show(show_name, show[0], 0, show[1], show[2])
        return Show(show_name, show["episode_nr"], show.get("version", 0), show["resolution"], show.get("subdir", None))

    def _get_show_strict(self, show_name: str, t="shows") -> Show:
        show = self.get_show(show_name, t)
        assert show is not None
        return show

    def save_show(self, show: Show, t="shows"):
        self.data[t][show.name] = show._asdict()


config: Config | None = None


def initialize(path):
    global config
    config = Config(path)
    return config


def get() -> Config:
    global config
    assert config is not None, "Configuration has not been initialized"
    return config
