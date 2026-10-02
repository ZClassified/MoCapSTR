"""
Camera device addressing and the export/convert step (no camera, no UI window needed).

Run from the repository root:
    python -m unittest discover tests
"""
import os
import shutil
import sys
import tempfile
import unittest

import av

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_clip_sync import make_clip  # noqa: E402  (also sets sys.path)

from camera_manager import dshow_device_number  # noqa: E402
from tabs.export_tab import ExportTab, ORIGINALS_FOLDER  # noqa: E402


class DeviceNumberTest(unittest.TestCase):
    def test_identical_names_get_increasing_numbers(self):
        names = ["USB Camera", "Integrated Webcam", "USB Camera", "USB Camera"]
        self.assertEqual([dshow_device_number(names, i) for i in range(4)], [0, 0, 1, 2])


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def make_export_tab(delete_originals=False):
    """ExportTab without a Tk window: only what _convert_single_file/_retire_original use."""
    tab = ExportTab.__new__(ExportTab)
    tab.logs = []
    tab.main_app = type("App", (), {"log": lambda _self, msg, level="info": tab.logs.append((level, msg))})()
    tab.after = lambda *args, **kwargs: None
    tab.progressbar = type("Bar", (), {"set": lambda _self, value: None})()
    tab.delete_original_var = _Var(delete_originals)
    return tab


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mocapstr_export_")
        self.videos = os.path.join(self.dir, "rec", "synchronized_videos")
        os.makedirs(self.videos)
        self.raw = os.path.join(self.videos, "cam0.avi")
        make_clip(self.raw, [i * 4 for i in range(20)])

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_failed_conversion_releases_the_input_file(self):
        tab = make_export_tab()
        bad_output = os.path.join(self.dir, "missing_folder", "cam0.mp4")  # cannot be created
        self.assertFalse(tab._convert_single_file(self.raw, bad_output, "None"))
        os.remove(self.raw)  # PermissionError on Windows if the input were still open

    def test_rotated_conversion_and_original_moved_away(self):
        tab = make_export_tab()
        mp4 = os.path.join(self.videos, "cam0.mp4")
        self.assertTrue(tab._convert_single_file(self.raw, mp4, "90° Clockwise"))
        with av.open(mp4) as container:
            stream = container.streams.video[0]
            self.assertEqual((stream.codec_context.width, stream.codec_context.height), (48, 64))
            self.assertEqual(sum(1 for _ in container.decode(video=0)), 20)

        tab._retire_original(self.raw)
        self.assertEqual(sorted(os.listdir(self.videos)), ["cam0.mp4"])  # one video per camera
        self.assertTrue(os.path.exists(os.path.join(self.dir, "rec", ORIGINALS_FOLDER, "cam0.avi")))


if __name__ == "__main__":
    unittest.main()
