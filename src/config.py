import json
import os

class ConfigManager:
    def __init__(self):
        self.config_path = os.path.expanduser("~/.config/trashguard/settings.json")
        self.defaults = {
            "limit_percent": 20,
            "language": "de"
        }
        self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            self.settings = self.defaults
            self.save()
        else:
            with open(self.config_path, 'r') as f:
                self.settings = json.load(f)

    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.settings, f, indent=4)
