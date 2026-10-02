"""
Remembers the last used setup between app starts (%APPDATA%\\MoCapSTR\\settings.json).
"""
import json
import os

from app_paths import config_file


class SettingsStore:
    def __init__(self, path=None):
        self.path = path or config_file("settings.json")
        self.data = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, ValueError):
            pass

    def save(self, data):
        self.data = dict(data)
        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            os.replace(tmp_path, self.path)  # never leave a half-written settings file
        except OSError as e:
            print(f"[Settings] Could not save settings: {e}")
