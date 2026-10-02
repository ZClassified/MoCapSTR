import cv2
import threading
import os
import time
import queue
import av
import fractions

from clip_sync import (RecordingResult, TIMESTAMP_FIELDS, TIMESTAMPS_FOLDER_NAME, add_copy_stream,
                       format_timestamp_row)

class PreviewWorker(threading.Thread):
    def __init__(self, camera_worker):
        super().__init__(daemon=True)
        self.camera_worker = camera_worker
        self.queue = queue.Queue(maxsize=2)
        self.is_running = True
        self.raw_frame = None
        
    def run(self):
        while self.is_running:
            try:
                bgr_frame = self.queue.get(timeout=0.1)
                self.raw_frame = bgr_frame
                self._process_and_update(bgr_frame)
            except queue.Empty:
                pass

    def _process_and_update(self, bgr_frame):
        frame = bgr_frame.copy()
        # Apply rotation
        if self.camera_worker.rotation_degrees == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.camera_worker.rotation_degrees == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.camera_worker.rotation_degrees == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
        # Charuco Detection offloading
        if self.camera_worker.show_charuco and self.camera_worker.charuco_dict is not None and self.camera_worker.charuco_params is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            try:
                if hasattr(cv2.aruco, 'ArucoDetector'):
                    detector = cv2.aruco.ArucoDetector(self.camera_worker.charuco_dict, self.camera_worker.charuco_params)
                    corners, ids, rejected = detector.detectMarkers(gray)
                else:
                    corners, ids, rejected = cv2.aruco.detectMarkers(gray, self.camera_worker.charuco_dict, parameters=self.camera_worker.charuco_params)
                    
                if corners and len(corners) > 0:
                    cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            except Exception:
                pass
                
        self.camera_worker.latest_frame = frame

    def apply_rotation_to_cached_frame(self):
        """Immediately re-renders and rotates the cached frame even if stream is paused/stopped."""
        if self.raw_frame is not None:
            self._process_and_update(self.raw_frame)
                
    def stop(self):
        self.is_running = False

class RecordingSession:
    """
    State of one camera for one recording. A fresh object per take, so a writer
    thread that is still finishing an old take can never touch the next one.
    """
    def __init__(self, output_path, container, stream, fps, timestamps_path, timestamps_file, queue_size):
        self.output_path = output_path
        self.container = container
        self.stream = stream
        # Packet time base (frame index units). The muxer may use a different
        # stream time base (Matroska: 1/1000); PyAV rescales on mux().
        self.time_base = fractions.Fraction(1, int(round(fps)))
        self.fps = int(round(fps))
        self.timestamps_path = timestamps_path
        self.timestamps_file = timestamps_file
        self.packet_queue = queue.Queue(maxsize=queue_size)

        # Packets arriving before this perf_counter_ns() value are discarded.
        # None = no restriction. Used to drop stale frames from before the
        # trigger restart (see MultiCamManager.release_recording_gate()).
        self.min_arrival_ns = None

        self.frames_recorded = 0
        self.filled_frames = 0
        self.dropped_packets = 0
        self.mux_errors = 0
        self.pending_gap = 0  # packets dropped since the last enqueued one (demux thread only)
        self.prev_device_time = None  # device time of the previously written frame (None after a filler)


class CameraWorker(threading.Thread):
    def __init__(self, cam_id, container, target_fps=50):
        super().__init__(daemon=True)
        self.cam_id = cam_id
        self.container = container
        self.stream = self.container.streams.video[0]
        self.target_fps = target_fps

        self.is_running = True
        self.is_recording = False

        self.latest_frame = None
        self.rotation_degrees = 0

        self.current_fps = 0.0
        self.last_fps_time = time.time()
        self.last_packet_time = time.time() # Watchdog timestamp
        self.frame_count_for_fps = 0
        self.last_preview_time = 0

        self.session = None
        self.writer_thread = None

        self.show_charuco = False
        self.charuco_dict = None
        self.charuco_params = None

        # Shared threading.Event used for atomic start across all cameras.
        # Packets are only enqueued once this gate is set by MultiCamManager.
        self._record_gate = None

        self.preview_worker = PreviewWorker(self)
        self.preview_worker.start()

    @property
    def frames_recorded(self):
        session = self.session
        return session.frames_recorded if session else 0

    @property
    def lost_frames(self):
        session = self.session
        return (session.dropped_packets + session.mux_errors) if session else 0

    def set_charuco(self, show, dict_str=None):
        self.show_charuco = show
        if show and dict_str:
            dict_mapping = {
                "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
                "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
                "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
                "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
                "DICT_6X6_250": cv2.aruco.DICT_6X6_250
            }
            dict_id = dict_mapping.get(dict_str, cv2.aruco.DICT_4X4_50)
            if hasattr(cv2.aruco, 'getPredefinedDictionary'):
                self.charuco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
            else:
                self.charuco_dict = cv2.aruco.Dictionary_get(dict_id)

            if hasattr(cv2.aruco, 'DetectorParameters'):
                self.charuco_params = cv2.aruco.DetectorParameters()
            else:
                self.charuco_params = cv2.aruco.DetectorParameters_create()

    def set_rotation(self, degrees):
        self.rotation_degrees = degrees
        if self.preview_worker:
            self.preview_worker.apply_rotation_to_cached_frame()

    def prepare_recording(self, output_path, fps, codec_selection, record_gate, timestamps_path=None):
        """
        Phase 1 of the two-phase atomic start:
        Opens the output container and prepares the output stream.
        Recording does NOT begin yet — packets are only enqueued after
        MultiCamManager calls record_gate.set() for all cameras simultaneously.

        Args:
            output_path:     Destination file path.
            fps:             Target frames per second.
            codec_selection: PyAV codec name; only 'mjpeg' (stream copy) is supported.
            record_gate:     Shared threading.Event; set by MultiCamManager
                             after all cameras are prepared.
            timestamps_path: Optional CSV path for per-frame timestamps.

        Returns:
            True on success, False if the output container could not be opened.
        """
        if not self.is_running:
            return False
        if self.session is not None:
            print(f"[{self.cam_id}] Previous recording still active - cannot prepare a new one.")
            return False
        if codec_selection not in ("MJPG", "mjpeg"):
            print(f"[{self.cam_id}] Codec '{codec_selection}' not supported - only MJPEG stream copy.")
            return False

        container = None
        timestamps_file = None
        try:
            # Zero-copy pipeline: the camera's MJPEG packets are written unchanged.
            container = av.open(output_path, mode='w')
            stream = add_copy_stream(container, self.stream, fps)

            if timestamps_path:
                os.makedirs(os.path.dirname(timestamps_path), exist_ok=True)
                timestamps_file = open(timestamps_path, "w", newline="", encoding="utf-8")
                timestamps_file.write(",".join(TIMESTAMP_FIELDS) + "\n")
        except Exception as e:
            print(f"[{self.cam_id}] Error opening output container: {e}")
            for handle in (container, timestamps_file):
                if handle is not None:
                    try:
                        handle.close()
                    except Exception:
                        pass
            return False

        session = RecordingSession(output_path, container, stream, fps,
                                   timestamps_path, timestamps_file,
                                   queue_size=int(self.target_fps * 3))
        self._record_gate = record_gate
        self.session = session
        # Mark as recording so the writer loop keeps running, but the run() loop
        # will only enqueue packets once _record_gate is set.
        self.is_recording = True
        self.writer_thread = threading.Thread(target=self._writer_loop, args=(session,), daemon=True)
        self.writer_thread.start()
        return True

    def request_stop(self):
        """Stops accepting new packets. The writer keeps draining its queue."""
        self.is_recording = False
        self._record_gate = None

    def finish_recording(self, stall_timeout=5.0):
        """
        Waits until the writer has written all queued packets and closed the file.
        Gives up only if the writer makes no progress for `stall_timeout` seconds.

        Returns:
            RecordingResult, or None if this worker was not recording.
        """
        self.request_stop()
        session = self.session
        if session is None:
            return None

        complete = True
        writer = self.writer_thread
        if writer:
            last_progress = (session.frames_recorded, session.packet_queue.qsize())
            last_change = time.time()
            while writer.is_alive():
                writer.join(timeout=0.5)
                progress = (session.frames_recorded, session.packet_queue.qsize())
                if progress != last_progress:
                    last_progress = progress
                    last_change = time.time()
                elif time.time() - last_change > stall_timeout:
                    print(f"[{self.cam_id}] Writer stalled - giving up waiting.")
                    complete = False
                    break
        self.writer_thread = None
        self.session = None

        print(f"[{self.cam_id}] Stopped recording. Saved {session.frames_recorded} frames "
              f"({session.filled_frames} filled).")
        return RecordingResult(
            path=session.output_path,
            frames=session.frames_recorded,
            filled_frames=session.filled_frames,
            dropped_packets=session.dropped_packets,
            mux_errors=session.mux_errors,
            timestamps_path=session.timestamps_path,
            complete=complete,
        )

    def stop_recording(self):
        return self.finish_recording()

    def _write_frame(self, session, data, arrival_ns, device_time, filler):
        packet = av.Packet(data)
        packet.stream = session.stream
        packet.time_base = session.time_base
        packet.pts = session.frames_recorded
        packet.dts = session.frames_recorded
        packet.is_keyframe = True  # MJPEG: every frame is intra-coded
        session.container.mux(packet)

        if session.timestamps_file:
            session.timestamps_file.write(format_timestamp_row(
                session.frames_recorded, session.fps, arrival_ns, device_time, filler,
                session.prev_device_time))
        session.prev_device_time = device_time
        session.frames_recorded += 1
        if filler:
            session.filled_frames += 1

    def _writer_loop(self, session):
        """
        Writes queued packets. Lost packets (queue overflow, mux error) are replaced
        by a copy of the previous frame, so frame N stays frame N on every camera.
        Closes the output files when done.
        """
        last_data = None
        pending_fill = 0
        try:
            while self.is_recording and self.session is session or not session.packet_queue.empty():
                try:
                    data, arrival_ns, device_time, gap = session.packet_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                pending_fill += gap
                if pending_fill and last_data is not None:
                    for _ in range(pending_fill):
                        try:
                            self._write_frame(session, last_data, None, None, filler=True)
                        except Exception as e:
                            print(f"[{self.cam_id}] Mux error (filler): {e}")
                    pending_fill = 0

                try:
                    self._write_frame(session, data, arrival_ns, device_time, filler=False)
                    last_data = data
                except Exception as e:
                    print(f"[{self.cam_id}] Mux error: {e}")
                    session.mux_errors += 1
                    pending_fill += 1
        finally:
            try:
                session.container.close()
            except Exception as e:
                print(f"[{self.cam_id}] Error closing output container: {e}")
            if session.timestamps_file:
                try:
                    session.timestamps_file.close()
                except Exception:
                    pass

    def run(self):
        try:
            for packet in self.container.demux(self.stream):
                arrival_ns = time.perf_counter_ns()
                if not self.is_running:
                    break

                if packet.dts is None:
                    continue

                now = time.time()
                self.last_packet_time = now

                # Calculate FPS based on received packets
                self.frame_count_for_fps += 1
                if now - self.last_fps_time >= 1.0:
                    self.current_fps = self.frame_count_for_fps / (now - self.last_fps_time)
                    self.frame_count_for_fps = 0
                    self.last_fps_time = now

                # 1. Preview Frame dekodieren (VOR dem Queueing, um Race Conditions zu vermeiden)
                bgr_frame = None
                if now - self.last_preview_time >= (1.0 / 15.0):
                    try:
                        for frame in packet.decode():
                            bgr_frame = frame.to_ndarray(format='bgr24')
                            self.last_preview_time = now
                            break # Only decode first frame in packet
                    except Exception as e:
                        pass

                # 2. Enqueue packet for recording.
                # The gate check ensures all cameras start capturing simultaneously:
                # packets are only accepted once MultiCamManager has opened the shared
                # record_gate for every camera (two-phase atomic start).
                gate = self._record_gate
                session = self.session
                if self.is_recording and session is not None and gate is not None and gate.is_set():
                    min_ns = session.min_arrival_ns
                    if min_ns is None or arrival_ns >= min_ns:
                        device_time = None
                        if packet.pts is not None and packet.time_base is not None:
                            device_time = float(packet.pts * packet.time_base)
                        try:
                            session.packet_queue.put_nowait((bytes(packet), arrival_ns, device_time, session.pending_gap))
                            session.pending_gap = 0
                        except queue.Full:
                            # The writer fills the gap with a copy of the previous frame
                            session.pending_gap += 1
                            session.dropped_packets += 1
                            print(f"[{self.cam_id}] Queue full! Dropping packet.")

                # 3. An den PreviewWorker schicken
                if bgr_frame is not None:
                    try:
                        self.preview_worker.queue.put_nowait(bgr_frame)
                    except queue.Full:
                        pass # Drop frame if worker is busy
        except Exception as e:
            print(f"[{self.cam_id}] Demux loop error: {e}")

    def stop(self):
        self.is_running = False
        self.finish_recording()
        if self.preview_worker:
            self.preview_worker.stop()
            self.preview_worker.join(timeout=1.0)

class MultiCamManager:
    def __init__(self):
        self.workers = {} # idx -> CameraWorker
        self.is_recording = False

    def get_supported_codecs(self):
        return {
            "MJPG (.avi) - Fast & Zero Copy": ("mjpeg", ".avi"),
            "MJPG (.mkv) - Fast & Zero Copy": ("mjpeg", ".mkv")
        }

    def start_workers(self, cameras, target_fps=50):
        """Starts background grabbing for all opened PyAV containers"""
        for idx, container in cameras.items():
            if idx not in self.workers:
                worker = CameraWorker(f"Cam_{idx}", container, target_fps)
                worker.start()
                self.workers[idx] = worker

    def stop_workers(self):
        for worker in self.workers.values():
            worker.stop()
        for worker in self.workers.values():
            worker.join(timeout=1.5)
        self.workers.clear()
        self.is_recording = False

    def recording_workers(self):
        """{cam_idx: worker} of all cameras taking part in the current recording."""
        return {idx: w for idx, w in self.workers.items() if w.session is not None}

    def start_recording(self, target_folder, fps, codec_selection, enabled_cameras=None,
                        hold_until_released=False):
        """
        Two-phase atomic recording start:

        Phase 1 — Prepare: Opens output containers for all cameras sequentially.
                  This involves file I/O and may take a few milliseconds per camera.
                  No packets are recorded yet.

        Phase 2 — Arm:    Sets a shared threading.Event, which all camera workers
                  check before enqueuing packets. Because a single Event.set() call
                  is atomic, all cameras start capturing their first frame in the
                  same OS scheduler slice — eliminating start-of-clip frame drift.

        With hold_until_released=True every packet is discarded until
        release_recording_gate() is called. Used in hardware-trigger mode: the
        trigger is restarted after this call and only frames of the new pulses
        are recorded.

        Returns:
            True if at least one camera is recording.
        """
        if self.is_recording:
            return False

        codecs = self.get_supported_codecs()
        fourcc_str, ext = codecs.get(codec_selection, ("mjpeg", ".avi"))
        timestamps_folder = os.path.join(target_folder, TIMESTAMPS_FOLDER_NAME)

        # Shared gate: keeps all workers waiting until every container is ready.
        record_gate = threading.Event()

        # Phase 1: Prepare — open files for each camera (can take a few ms each)
        prepared = []
        for idx, worker in self.workers.items():
            if enabled_cameras is not None and idx not in enabled_cameras:
                continue
            filename = f"cam{idx}{ext}"
            output_path = os.path.join(target_folder, filename)
            timestamps_path = os.path.join(timestamps_folder, f"cam{idx}_timestamps.csv")
            success = worker.prepare_recording(output_path, fps,
                                               codec_selection=fourcc_str,
                                               record_gate=record_gate,
                                               timestamps_path=timestamps_path)
            if success:
                if hold_until_released:
                    worker.session.min_arrival_ns = float("inf")
                prepared.append(idx)

        if not prepared:
            print("[MultiCamManager] No camera could be prepared for recording.")
            return False

        # Phase 2: Arm — open the gate for ALL prepared cameras simultaneously
        record_gate.set()
        print(f"[MultiCamManager] Recording gate opened for cameras: {prepared}")

        self.is_recording = True
        return True

    def release_recording_gate(self, min_arrival_ns):
        """Accept packets that arrive at or after time.perf_counter_ns() == min_arrival_ns."""
        for worker in self.workers.values():
            session = worker.session
            if session is not None:
                session.min_arrival_ns = min_arrival_ns

    def stop_recording(self):
        """
        Stop all camera workers and collect their results.

        Returns:
            dict {cam_idx: RecordingResult} for post-processing (clip_sync.finalize_clips).
            Only includes cameras that actually recorded frames in this session.
        """
        if not self.is_recording:
            return {}
        # Stop all cameras first, then wait: all clips end at the same moment
        # and the writers drain in parallel instead of one after another.
        for worker in self.workers.values():
            worker.request_stop()
        results = {}
        for idx, worker in self.workers.items():
            result = worker.finish_recording()
            if result and result.frames > 0:
                results[idx] = result
        self.is_recording = False
        return results

    def get_latest_frames(self):
        """Returns a dict of {cam_idx: frame} for preview"""
        return {idx: worker.latest_frame for idx, worker in self.workers.items() if worker.latest_frame is not None}

    def set_camera_rotation(self, cam_idx, degrees):
        if cam_idx in self.workers:
            self.workers[cam_idx].set_rotation(degrees)

    def set_charuco_settings(self, show, dict_str):
        for worker in self.workers.values():
            worker.set_charuco(show, dict_str)
