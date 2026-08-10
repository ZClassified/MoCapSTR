import json
import os

class PresetManager:
    def __init__(self, filepath="presets.json"):
        self.filepath = filepath
        self.presets = {}
        self.load_presets_from_disk()

    def load_presets_from_disk(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.presets = json.load(f)
            except Exception as e:
                print(f"Error loading presets: {e}")
                self.presets = {}
        else:
            self.presets = {}

    def save_presets_to_disk(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=4)
        except Exception as e:
            print(f"Error saving presets: {e}")

    def save_preset(self, name, data):
        self.presets[name] = data
        self.save_presets_to_disk()

    def get_preset(self, name):
        return self.presets.get(name, None)

    def get_preset_names(self):
        return list(self.presets.keys())
        
    def delete_preset(self, name):
        if name in self.presets:
            del self.presets[name]
            self.save_presets_to_disk()
