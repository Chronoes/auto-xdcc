# pylint: disable=E0401
import hexchat

class Settings:
    
    saved = {}

    def __init__(self):
        self.printer = ...

    def add_watched_setting(self, name, target_value):
        return True    

    def change_watched_setting(self, name): 
        return True
        # TODO make this settings class, that saves settings of the user on start and changes them, then unchange them on unload, important for many things like auto recv, hide gui recv window etc.
        # TODO add auto save to read from plugin_pref that is permanently stored and accessible with menu