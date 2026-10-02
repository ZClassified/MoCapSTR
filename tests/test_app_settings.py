"""
Per-user settings folders, migration of old settings files, settings store and log capture.

Run from the repository root:
    python -m unittest discover tests
"""
import json
import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import app_paths  # noqa: E402
from logging_setup import _StreamToLogger  # noqa: E402
from preset_manager import PresetManager  # noqa: E402
from settings_store import SettingsStore  # noqa: E402


class AppSettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mocapstr_settings_")
        self.env = mock.patch.dict(os.environ, {
            "APPDATA": os.path.join(self.dir, "Roaming"),
            "LOCALAPPDATA": os.path.join(self.dir, "Local"),
        })
        self.env.start()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        self.env.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_folders_are_per_user(self):
        self.assertEqual(app_paths.config_dir(), os.path.join(self.dir, "Roaming", "MoCapSTR"))
        self.assertTrue(app_paths.logs_dir().startswith(os.path.join(self.dir, "Local", "MoCapSTR")))

    def test_old_presets_in_working_directory_are_migrated(self):
        workdir = os.path.join(self.dir, "work")
        os.makedirs(workdir)
        with open(os.path.join(workdir, "presets.json"), "w", encoding="utf-8") as f:
            json.dump({"Studio": {"fps": "50"}}, f)
        os.chdir(workdir)

        presets = PresetManager()
        self.assertTrue(presets.filepath.startswith(app_paths.config_dir()))
        self.assertEqual(presets.get_preset("Studio"), {"fps": "50"})

        presets.save_preset("Neu", {"fps": "40"})  # new presets go to %APPDATA%, not the cwd
        with open(os.path.join(workdir, "presets.json"), encoding="utf-8") as f:
            self.assertNotIn("Neu", json.load(f))

    def test_settings_store_roundtrip(self):
        SettingsStore().save({"project_name": "P", "rotations": {"0": "90° (Portrait)"}})
        self.assertEqual(SettingsStore().data["rotations"]["0"], "90° (Portrait)")

    def test_corrupt_settings_file_is_ignored(self):
        with open(app_paths.config_file("settings.json"), "w", encoding="utf-8") as f:
            f.write("{ not json")
        self.assertEqual(SettingsStore().data, {})


class LogCaptureTest(unittest.TestCase):
    def test_print_output_is_logged_line_by_line(self):
        logger = logging.getLogger("test_capture")
        with self.assertLogs(logger, level="INFO") as captured:
            stream = _StreamToLogger(logger, logging.INFO)
            stream.write("first line\nsecond ")
            stream.write("line\n\n")
        self.assertEqual([r.getMessage() for r in captured.records], ["first line", "second line"])


if __name__ == "__main__":
    unittest.main()
