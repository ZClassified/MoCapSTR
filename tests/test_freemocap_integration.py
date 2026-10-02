"""
FreeMoCap 2 integration: folder layout, export bridge and the timestamp CSV format.

The FreeMoCap checks below replicate how FreeMoCap v2.0.0-alpha.25 reads a recording:
  - freemocap/core/tasks/mocap/mocap_helpers/recording_framerate.py
  - freemocap/api/http/playback/playback_router.py (_read_timestamp_values_for_video)
  - freemocap/core/pipeline/posthoc/video_group_helper.py (cv2 frame counts)

Run from the repository root:
    python -m unittest discover tests
"""
import csv
import glob
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_clip_sync import DT, FPS, make_clip, timestamp_rows  # noqa: E402  (also sets sys.path)

import freemocap_bridge  # noqa: E402
from clip_sync import write_timestamps  # noqa: E402
from project_manager import ProjectManager, safe_name  # noqa: E402


def freemocap_recording_framerate(recording_path):
    """recording_framerate.py: median of from_previous.framerate.hz in the first *_timestamps.csv."""
    import pandas as pd
    candidates = sorted(glob.glob(os.path.join(recording_path, "synchronized_videos", "timestamps", "*_timestamps.csv")))
    values = pd.read_csv(candidates[0], usecols=["from_previous.framerate.hz"])["from_previous.framerate.hz"].dropna()
    values = values[values > 0]
    return float(values.median()) if len(values) >= 10 else None


def freemocap_playback_timestamps(csv_path):
    """playback_router.py: first column whose name contains a time keyword, every row as float."""
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    col = next(i for i, name in enumerate(header)
               if any(kw in name.strip().lower() for kw in ["timestamp", "time", "elapsed", "seconds"]))
    return header[col], [float(row[col]) for row in rows]


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mocapstr_fmc_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TimestampFormatTest(TempDirTest):
    def test_freemocap_reads_framerate_and_timeline(self):
        recording = os.path.join(self.dir, "rec")
        ts_dir = os.path.join(recording, "synchronized_videos", "timestamps")
        os.makedirs(ts_dir)
        times = [i * DT for i in range(200)]
        times[50] = None  # a filler frame must not break FreeMoCap's parser
        write_timestamps(os.path.join(ts_dir, "cam0_timestamps.csv"), timestamp_rows(times), FPS)

        self.assertAlmostEqual(freemocap_recording_framerate(recording), FPS, places=2)
        column, values = freemocap_playback_timestamps(os.path.join(ts_dir, "cam0_timestamps.csv"))
        self.assertEqual(column, "timestamp_s")
        self.assertEqual(len(values), 200)
        self.assertAlmostEqual(values[100], 100 / FPS)


class ProjectManagerTest(TempDirTest):
    def test_one_folder_per_recording(self):
        pm = ProjectManager(self.dir)
        pm.set_project("My Project")
        take = pm.get_recording_folder(is_calibration=False, take_name="Take_01")
        calib1 = pm.get_recording_folder(is_calibration=True)
        calib2 = pm.get_recording_folder(is_calibration=True)

        self.assertEqual(os.path.basename(take), "synchronized_videos")
        self.assertTrue(os.path.basename(os.path.dirname(take)).endswith("_My Project_Take_01"))
        self.assertNotEqual(calib1, calib2)  # never overwrite an earlier calibration
        for path in (take, calib1, calib2):
            self.assertEqual(os.path.dirname(os.path.dirname(path)), self.dir)  # FreeMoCap lists direct children

    def test_safe_name(self):
        self.assertEqual(safe_name('a/b:c*?"<>|', "x"), "a_b_c")
        self.assertEqual(safe_name("   ", "fallback"), "fallback")

    def test_find_recordings_by_project(self):
        pm = ProjectManager(self.dir)
        for project in ("A", "B", "A"):
            pm.set_project(project)
            sync = pm.get_recording_folder(take_name="t")
            with open(os.path.join(os.path.dirname(sync), "session_info.json"), "w") as f:
                json.dump({"project": project}, f)
        os.makedirs(os.path.join(self.dir, "A", "takes", "take_old", "synchronized_videos"))  # <= 1.5.0 layout
        os.makedirs(os.path.join(self.dir, "unrelated_freemocap_recording", "synchronized_videos"))

        found = ProjectManager(self.dir).find_recordings("A")
        self.assertEqual(len(found), 3)
        self.assertTrue(any(p.endswith("take_old") for p in found))


class BridgeTest(TempDirTest):
    def make_recording(self, name, files):
        recording = os.path.join(self.dir, "mocapstr", name)
        videos = os.path.join(recording, "synchronized_videos")
        os.makedirs(os.path.join(videos, "timestamps"))
        for filename, n_frames in files.items():
            make_clip(os.path.join(videos, filename), [i % 100 * 2 for i in range(n_frames)])
        open(os.path.join(videos, "timestamps", "cam0_timestamps.csv"), "w").close()
        with open(os.path.join(recording, "session_info.json"), "w") as f:
            json.dump({"project": "P"}, f)
        return recording

    def test_select_videos_prefers_mp4(self):
        recording = self.make_recording("r", {"cam0.avi": 5, "cam0.mp4": 5, "cam1.mkv": 5})
        picked = [os.path.basename(p) for p in freemocap_bridge.select_videos(os.path.join(recording, "synchronized_videos"))]
        self.assertEqual(picked, ["cam0.mp4", "cam1.mkv"])

    def test_export_one_video_per_camera(self):
        recording = self.make_recording("2026-10-02_12-00-00_P_Take", {"cam0.avi": 30, "cam0.mp4": 30, "cam1.avi": 30})
        target_root = os.path.join(self.dir, "freemocap_data", "recordings")
        stale = os.path.join(target_root, "2026-10-02_12-00-00_P_Take", "synchronized_videos")
        os.makedirs(stale)
        make_clip(os.path.join(stale, "cam7.avi"), [0] * 3)  # leftover from an earlier export

        target = freemocap_bridge.export_recording(recording, recordings_folder=target_root)

        videos = sorted(os.listdir(os.path.join(target, "synchronized_videos")))
        self.assertEqual(videos, ["cam0.mp4", "cam1.avi", "timestamps"])
        self.assertTrue(os.path.exists(os.path.join(target, "synchronized_videos", "timestamps", "cam0_timestamps.csv")))
        self.assertTrue(os.path.exists(os.path.join(target, "session_info.json")))
        # FreeMoCap requires identical cv2 frame counts for all cameras
        counts = {v: int(cv2.VideoCapture(os.path.join(target, "synchronized_videos", v)).get(cv2.CAP_PROP_FRAME_COUNT))
                  for v in videos if v != "timestamps"}
        self.assertEqual(set(counts.values()), {30})

    def test_export_inside_target_is_noop(self):
        target_root = os.path.join(self.dir, "mocapstr")
        recording = self.make_recording("rec", {"cam0.avi": 5})
        self.assertEqual(freemocap_bridge.export_recording(recording, recordings_folder=target_root), recording)
        self.assertTrue(os.path.exists(os.path.join(recording, "synchronized_videos", "cam0.avi")))

    def test_base_folder_from_freemocap_settings(self):
        appdata = os.path.join(self.dir, "appdata")
        os.makedirs(os.path.join(appdata, "freemocap"))
        with mock.patch.dict(os.environ, {"APPDATA": appdata}):
            self.assertTrue(freemocap_bridge.get_freemocap_base_folder().endswith("freemocap_data"))
            with open(os.path.join(appdata, "freemocap", "freemocap-config.json"), "w") as f:
                json.dump({"baseDataFolder": r"D:\mocap_data"}, f)
            self.assertEqual(freemocap_bridge.get_freemocap_base_folder(), r"D:\mocap_data")
            self.assertEqual(freemocap_bridge.get_freemocap_recordings_folder(), os.path.join(r"D:\mocap_data", "recordings"))


if __name__ == "__main__":
    unittest.main()
