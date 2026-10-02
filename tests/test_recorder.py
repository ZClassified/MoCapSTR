"""
Recording pipeline test with simulated cameras (no hardware needed).

Run from the repository root:
    python -m unittest discover tests
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

import av

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_clip_sync import FPS, make_clip, frame_values  # noqa: E402  (also sets sys.path)

from clip_sync import finalize_clips, read_timestamps  # noqa: E402
from recorder import MultiCamManager  # noqa: E402


class FakeCamera:
    """Looks like a PyAV input container; delivers the packets of a file at `fps`."""
    def __init__(self, path, fps=FPS):
        self._container = av.open(path)
        self.streams = self._container.streams
        self.fps = fps

    def demux(self, stream):
        next_time = time.perf_counter()
        for packet in self._container.demux(stream):
            next_time += 1.0 / self.fps
            delay = next_time - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            yield packet

    def close(self):
        self._container.close()


class MultiCamRecordingTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mocapstr_rec_")
        self.source = os.path.join(self.dir, "source.avi")
        make_clip(self.source, [i % 120 * 2 for i in range(600)])  # 12 s of video
        self.cameras = {0: FakeCamera(self.source), 1: FakeCamera(self.source)}
        self.manager = MultiCamManager()
        self.manager.start_workers(self.cameras, target_fps=FPS)
        self.take = os.path.join(self.dir, "take", "synchronized_videos")
        os.makedirs(self.take)

    def tearDown(self):
        self.manager.stop_workers()
        for cam in self.cameras.values():
            cam.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_hold_release_record_stop(self):
        codec = "MJPG (.avi) - Fast & Zero Copy"
        self.assertTrue(self.manager.start_recording(self.take, FPS, codec, enabled_cameras=[0, 1],
                                                     hold_until_released=True))
        time.sleep(0.3)
        # Held: nothing may be written before the release
        self.assertEqual([w.frames_recorded for w in self.manager.workers.values()], [0, 0])

        self.manager.release_recording_gate(time.perf_counter_ns())
        time.sleep(1.0)
        results = self.manager.stop_recording()

        self.assertEqual(sorted(results), [0, 1])
        for idx, result in results.items():
            self.assertTrue(result.complete)
            self.assertGreater(result.frames, 30)
            self.assertEqual(len(frame_values(result.path)), result.frames)
            self.assertEqual(len(read_timestamps(result.timestamps_path)), result.frames)
            self.assertTrue(os.path.exists(os.path.join(self.take, "timestamps", f"cam{idx}_timestamps.csv")))

        counts, _ = finalize_clips(results, FPS, hardware_trigger=False)
        self.assertEqual(len(set(counts.values())), 1)
        self.assertFalse(self.manager.is_recording)

        # A second take right after the first one must work
        self.assertTrue(self.manager.start_recording(self.take, FPS, codec, enabled_cameras=[1]))
        time.sleep(0.3)
        results = self.manager.stop_recording()
        self.assertEqual(sorted(results), [1])

    def test_disabled_camera_is_not_recording(self):
        codec = "MJPG (.mkv) - Fast & Zero Copy"
        self.assertTrue(self.manager.start_recording(self.take, FPS, codec, enabled_cameras=[1]))
        self.assertEqual(list(self.manager.recording_workers()), [1])
        time.sleep(0.3)
        results = self.manager.stop_recording()
        self.assertEqual(sorted(results), [1])
        self.assertTrue(results[1].path.endswith(".mkv"))


if __name__ == "__main__":
    unittest.main()
