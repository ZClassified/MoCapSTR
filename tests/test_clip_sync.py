"""
Hardware-free tests for clip verification/alignment and the recording writer.

Run from the repository root:
    python -m unittest discover tests
"""
import os
import queue
import shutil
import sys
import tempfile
import unittest

import av
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

from clip_sync import (RecordingResult, add_copy_stream, find_missing_frames, finalize_clips,
                       read_timestamps, remux_clip, write_timestamps, TIMESTAMP_FIELDS)
from recorder import CameraWorker, RecordingSession

FPS = 50
DT = 1.0 / FPS


def make_clip(path, values):
    """MJPEG clip whose frame i is filled with brightness values[i]."""
    container = av.open(path, "w")
    stream = container.add_stream("mjpeg", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = 64, 48, "yuvj422p"
    for i, v in enumerate(values):
        frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), v, np.uint8), format="rgb24")
        frame.pts = i
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def frame_values(path):
    with av.open(path) as container:
        return [int(round(f.to_ndarray(format="rgb24").mean())) for f in container.decode(video=0)]


def timestamp_rows(device_times):
    return [{"arrival_ns": int(t * 1e9) if t is not None else None,
             "device_time_s": t, "filler": t is None} for t in device_times]


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mocapstr_test_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name)


class RemuxTest(TempDirTest):
    def test_trim_avi(self):
        clip = self.path("cam1.avi")
        make_clip(clip, [i * 2 for i in range(101)])
        self.assertEqual(remux_clip(clip, FPS, keep_frames=100), 100)
        values = frame_values(clip)
        self.assertEqual(len(values), 100)
        self.assertEqual(values[-1], 99 * 2)
        self.assertFalse(any(name.endswith(".avi") and "syncfix" in name for name in os.listdir(self.dir)))

    def test_trim_mkv_keeps_frame_rate(self):
        clip = self.path("cam0.mkv")
        make_clip(clip, list(range(0, 120, 2)))
        remux_clip(clip, FPS, keep_frames=50)
        with av.open(clip) as container:
            stream = container.streams.video[0]
            self.assertEqual(sum(1 for p in container.demux(stream) if p.dts is not None), 50)
            self.assertEqual(round(float(stream.average_rate)), FPS)

    def test_insert_fillers_and_rewrite_timestamps(self):
        clip = self.path("cam0.avi")
        ts = self.path("cam0_timestamps.csv")
        make_clip(clip, [i * 2 for i in range(10)])
        write_timestamps(ts, timestamp_rows([i * DT for i in range(10)]), FPS)

        frames = remux_clip(clip, FPS, keep_frames=12, insert_before={4: 2}, timestamps_path=ts)

        self.assertEqual(frames, 12)
        values = frame_values(clip)
        self.assertEqual(values[:7], [0, 2, 4, 6, 6, 6, 8])
        rows = read_timestamps(ts)
        self.assertEqual(len(rows), 12)
        self.assertEqual([r["filler"] for r in rows[3:7]], [False, True, True, False])


class FindMissingFramesTest(unittest.TestCase):
    def test_no_gaps(self):
        self.assertEqual(find_missing_frames(timestamp_rows([i * DT for i in range(100)])), {})

    def test_single_missing_trigger(self):
        times = [i * DT for i in range(100) if i != 40]
        self.assertEqual(find_missing_frames(timestamp_rows(times)), {40: 1})

    def test_two_missing_in_a_row(self):
        times = [i * DT for i in range(100) if i not in (40, 41)]
        self.assertEqual(find_missing_frames(timestamp_rows(times)), {40: 2})

    def test_late_delivery_is_not_a_gap(self):
        times = [i * DT for i in range(100)]
        times[40] += 0.9 * DT  # arrives late, next one on time
        self.assertEqual(find_missing_frames(timestamp_rows(times)), {})

    def test_existing_filler_is_accounted_for(self):
        times = [i * DT for i in range(100)]
        times[40] = None  # already replaced by a filler while recording
        self.assertEqual(find_missing_frames(timestamp_rows(times)), {})

    def test_jitter_is_ignored(self):
        rng = np.random.default_rng(1)
        times = [i * DT + float(rng.uniform(-0.002, 0.002)) for i in range(300)]
        self.assertEqual(find_missing_frames(timestamp_rows(times)), {})


class FinalizeClipsTest(TempDirTest):
    def record(self, idx, device_times):
        """Fake recording: brightness encodes the trigger pulse number."""
        clip = self.path(f"cam{idx}.avi")
        ts = self.path(f"cam{idx}_timestamps.csv")
        make_clip(clip, [int(round(t / DT)) * 2 for t in device_times])
        write_timestamps(ts, timestamp_rows(device_times), FPS)
        return RecordingResult(path=clip, frames=len(device_times), timestamps_path=ts)

    def test_equal_clips_untouched(self):
        results = {0: self.record(0, [i * DT for i in range(60)]),
                   1: self.record(1, [i * DT for i in range(60)])}
        counts, messages = finalize_clips(results, FPS, hardware_trigger=True)
        self.assertEqual(counts, {0: 60, 1: 60})
        self.assertEqual([lvl for lvl, _ in messages], ["success"])

    def test_missing_trigger_frame_is_filled(self):
        results = {0: self.record(0, [i * DT for i in range(60)]),
                   1: self.record(1, [i * DT for i in range(60) if i != 30])}
        counts, _ = finalize_clips(results, FPS, hardware_trigger=True)

        self.assertEqual(counts, {0: 60, 1: 60})
        cam0, cam1 = frame_values(self.path("cam0.avi")), frame_values(self.path("cam1.avi"))
        self.assertEqual(len(cam1), 60)
        # Frames after the gap must show the same pulse on both cameras
        self.assertEqual(cam0[31:], cam1[31:])
        self.assertEqual(cam1[30], cam1[29])  # filler = copy of previous frame

    def test_unexplained_length_difference_is_trimmed(self):
        results = {0: self.record(0, [i * DT for i in range(61)]),
                   1: self.record(1, [i * DT for i in range(60)])}
        counts, messages = finalize_clips(results, FPS, hardware_trigger=True)
        self.assertEqual(counts, {0: 60, 1: 60})
        self.assertEqual(len(frame_values(self.path("cam0.avi"))), 60)
        self.assertTrue(any("gekürzt" in text for _, text in messages))

    def test_free_run_does_not_insert_frames(self):
        results = {0: self.record(0, [i * DT for i in range(60)]),
                   1: self.record(1, [i * DT for i in range(60) if i != 30])}
        counts, _ = finalize_clips(results, FPS, hardware_trigger=False)
        self.assertEqual(counts, {0: 59, 1: 59})


class WriterTest(TempDirTest):
    def make_session(self, name, n_frames):
        source = self.path("source.avi")
        make_clip(source, [i * 2 for i in range(n_frames)])
        with av.open(source) as src:
            packets = [bytes(p) for p in src.demux(video=0) if p.dts is not None]
            out_path = self.path(name)
            container = av.open(out_path, "w")
            stream = add_copy_stream(container, src.streams.video[0], FPS)
        ts_path = self.path("ts.csv")
        ts_file = open(ts_path, "w", newline="", encoding="utf-8")
        ts_file.write(",".join(TIMESTAMP_FIELDS) + "\n")
        session = RecordingSession(out_path, container, stream, FPS, ts_path, ts_file, queue_size=100)
        return session, packets

    def make_worker(self, session):
        worker = CameraWorker.__new__(CameraWorker)  # no camera needed
        worker.cam_id = "Test"
        worker.session = session
        worker.is_recording = False  # writer just drains the queue
        return worker

    def test_dropped_packets_are_replaced_by_copies(self):
        for ext in ("avi", "mkv"):
            with self.subTest(container=ext):
                session, packets = self.make_session(f"out.{ext}", 20)
                # Packets 2 and 3 were dropped (queue full) -> gap=2 on packet 4
                for i in range(20):
                    if i in (2, 3):
                        continue
                    session.packet_queue.put((packets[i], i * 1000, i * DT, 2 if i == 4 else 0))
                self.make_worker(session)._writer_loop(session)

                self.assertEqual(session.frames_recorded, 20)
                self.assertEqual(session.filled_frames, 2)
                self.assertEqual(session.mux_errors, 0)
                self.assertEqual(frame_values(session.output_path)[:6], [0, 2, 2, 2, 8, 10])
                rows = read_timestamps(session.timestamps_path)
                self.assertEqual([r["filler"] for r in rows[:6]], [False, False, True, True, False, False])
                # Timeline is consistent -> the post-check finds no further gaps
                self.assertEqual(find_missing_frames(rows), {})
                with av.open(session.output_path) as container:
                    self.assertEqual(round(float(container.streams.video[0].average_rate)), FPS)


if __name__ == "__main__":
    unittest.main()
