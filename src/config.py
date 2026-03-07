import json, os
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".config/trashguard"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.settings = self.load()

    def load(self):
        defaults = {
            "service_enabled": False,
            "interval_idx": 1, 
            "sort_mode_idx": 0, 
            "fixed_gb_val": 2.0,
            "percent_val": 10,
            "use_percentage": False
        }
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    defaults.update(data) # Fehlende Schlüssel auffüllen
            except: pass
        return defaults

    def save(self):
        with open(self.config_file, "w") as f:
            json.dump(self.settings, f, indent=4)