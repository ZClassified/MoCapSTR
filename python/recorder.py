import cv2
import threading
import os
import time
import queue
import av
import fractions

class PreviewWorker(threading.Thread):
    def __init__(self, camera_worker):
        super().__init__()
        self.camera_worker = camera_worker
        self.queue = queue.Queue(maxsize=2)
        self.is_running = True
        
    def run(self):
        while self.is_running:
            try:
                bgr_frame = self.queue.get(timeout=0.1)
                
                # Apply rotation
                if self.camera_worker.rotation_degrees == 90:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_90_CLOCKWISE)
                elif self.camera_worker.rotation_degrees == 180:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_180)
                elif self.camera_worker.rotation_degrees == 270:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
                # Charuco Detection offloading
                if self.camera_worker.show_charuco and self.camera_worker.charuco_dict is not None and self.camera_worker.charuco_params is not None:
                    gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
                    try:
                        if hasattr(cv2.aruco, 'ArucoDetector'):
                            detector = cv2.aruco.ArucoDetector(self.camera_worker.charuco_dict, self.camera_worker.charuco_params)
                            corners, ids, rejected = detector.detectMarkers(gray)
                        else:
                            corners, ids, rejected = cv2.aruco.detectMarkers(gray, self.camera_worker.charuco_dict, parameters=self.camera_worker.charuco_params)
                            
                        if corners and len(corners) > 0:
                            cv2.aruco.drawDetectedMarkers(bgr_frame, corners, ids)
                    except Exception as e:
                        pass
                        
                self.camera_worker.latest_frame = bgr_frame
            except queue.Empty:
                pass
                
    def stop(self):
        self.is_running = False

class CameraWorker(threading.Thread):
    def __init__(self, cam_id, container, target_fps=50):
        super().__init__()
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
        self.frame_count_for_fps = 0
        self.last_preview_time = 0
        
        self.packet_queue = queue.Queue(maxsize=int(target_fps * 3))
        self.writer_thread = None
        self.frames_recorded = 0
        
        self.show_charuco = False
        self.charuco_dict = None
        self.charuco_params = None
        
        self.output_container = None
        self.output_stream = None
        self.output_path = None

        # Shared threading.Event used for atomic start across all cameras.
        # Packets are only enqueued once this gate is set by MultiCamManager.
        self._record_gate = None
        
        self.preview_worker = PreviewWorker(self)
        self.preview_worker.start()
        
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
        
    def prepare_recording(self, output_path, fps, codec_selection, record_gate):
        """
        Phase 1 of the two-phase atomic start:
        Opens the output container and prepares the output stream.
        Recording does NOT begin yet — packets are only enqueued after
        MultiCamManager calls record_gate.set() for all cameras simultaneously.

        Args:
            output_path:    Destination file path.
            fps:            Target frames per second.
            codec_selection: PyAV codec name (e.g. 'mjpeg').
            record_gate:    Shared threading.Event; set by MultiCamManager
                            after all cameras are prepared.

        Returns:
            True on success, False if the output container could not be opened.
        """
        if not self.is_running:
            return False

        # Reset state for this new session BEFORE any I/O, so that a subsequent
        # stop_recording() call on a failed prepare sees clean defaults.
        self.frames_recorded = 0
        self.recording_fps = fps
        self.output_path = None      # Will be set only on successful open
        self._record_gate = record_gate

        # Flush any leftover packets from a previous session
        while not self.packet_queue.empty():
            try:
                self.packet_queue.get_nowait()
            except queue.Empty:
                break
                
        # For simplicity and maximum performance, we use PyAV Stream Copy for MJPG
        # If they selected a hardware encoder, we would need a decoding/encoding pipeline.
        # Here we prioritize the zero-copy pipeline if MJPG is selected.
        try:
            self.output_container = av.open(output_path, mode='w')
            if codec_selection == "MJPG" or codec_selection == "mjpeg":
                # Direct Stream Copy
                self.output_stream = self.output_container.add_stream(self.stream.name)
                self.output_stream.width = self.stream.codec_context.width
                self.output_stream.height = self.stream.codec_context.height
                if self.stream.codec_context.pix_fmt:
                    self.output_stream.pix_fmt = self.stream.codec_context.pix_fmt
                # Override time_base to match our target_fps for clean monotonic PTS
                self.output_stream.time_base = fractions.Fraction(1, int(fps))
            else:
                # Transcoding path (simplified fallback)
                self.output_stream = self.output_container.add_stream(codec_selection, rate=fps)
                self.output_stream.width = self.stream.codec_context.width
                self.output_stream.height = self.stream.codec_context.height
                self.output_stream.pix_fmt = 'yuv420p'
        except Exception as e:
            print(f"[{self.cam_id}] Error opening output container: {e}")
            # output_path stays None — stop_recording() will return (None, 0)
            return False

        # Only assign output_path after successful container open, so that
        # stop_recording() can use it as a reliable indicator of success.
        self.output_path = output_path

        # Mark as recording so the writer loop keeps running, but the run() loop
        # will only enqueue packets once _record_gate is set.
        self.is_recording = True
        self.writer_thread = threading.Thread(target=self._writer_loop)
        self.writer_thread.start()
        return True

    def stop_recording(self):
        """
        Stop recording, drain the writer queue, and close the output container.

        Returns:
            Tuple (output_path, frames_recorded) for use by trim_clips_to_min_frames(),
            or (None, 0) if this worker was not recording in the current session.
        """
        # Clear the gate first so no new packets slip through during the shutdown window.
        self._record_gate = None
        self.is_recording = False

        if self.writer_thread:
            self.writer_thread.join()
            self.writer_thread = None

        # Capture and reset output_path atomically so that subsequent stop_recording()
        # calls (e.g. from MultiCamManager iterating all workers) always return
        # (None, 0) for cameras that were not part of this recording session.
        path = self.output_path
        frames = self.frames_recorded
        self.output_path = None   # Reset: prevents stale paths leaking into next session

        if self.output_container:
            try:
                self.output_container.close()
            except:
                pass
            self.output_container = None
            self.output_stream = None
            
        print(f"[{self.cam_id}] Stopped recording. Saved {frames} frames.")
        return path, frames
        
    def _writer_loop(self):
        while self.is_recording or not self.packet_queue.empty():
            try:
                packet = self.packet_queue.get(timeout=0.1)
                
                # Mux packet
                if self.output_stream and self.output_container:
                    try:
                        if self.output_stream.type == packet.stream.type and self.output_stream.name == packet.stream.name:
                            # Stream Copy
                            packet.stream = self.output_stream
                            packet.time_base = fractions.Fraction(1, int(self.recording_fps))
                            packet.pts = self.frames_recorded
                            packet.dts = self.frames_recorded
                            self.output_container.mux(packet)
                            # Count only after a successful stream-copy mux.
                            # The transcoding no-op path does NOT increment so that
                            # frames_recorded always matches the actual file contents.
                            self.frames_recorded += 1
                        else:
                            # Transcoding path - highly simplified, requires decoded frames
                            pass
                    except Exception as e:
                        print(f"[{self.cam_id}] Mux error: {e}")
            except queue.Empty:
                continue

    def run(self):
        try:
            for packet in self.container.demux(self.stream):
                if not self.is_running:
                    break
                    
                if packet.dts is None:
                    continue
                    
                # Calculate FPS based on received packets
                self.frame_count_for_fps += 1
                now = time.time()
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
                if self.is_recording:
                    gate_open = (self._record_gate is None or self._record_gate.is_set())
                    if gate_open:
                        try:
                            self.packet_queue.put_nowait(packet)
                        except queue.Full:
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
        self.stop_recording()
        self.preview_worker.stop()
        self.preview_worker.join()

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
            worker.join()
        self.workers.clear()

    def start_recording(self, target_folder, fps, codec_selection, enabled_cameras=None):
        """
        Two-phase atomic recording start:

        Phase 1 — Prepare: Opens output containers for all cameras sequentially.
                  This involves file I/O and may take a few milliseconds per camera.
                  No packets are recorded yet.

        Phase 2 — Arm:    Sets a shared threading.Event, which all camera workers
                  check before enqueuing packets. Because a single Event.set() call
                  is atomic, all cameras start capturing their first frame in the
                  same OS scheduler slice — eliminating start-of-clip frame drift.
        """
        if self.is_recording:
            return False
            
        codecs = self.get_supported_codecs()
        fourcc_str, ext = codecs.get(codec_selection, ("mjpeg", ".avi"))

        # Shared gate: keeps all workers waiting until every container is ready.
        record_gate = threading.Event()

        # Phase 1: Prepare — open files for each camera (can take a few ms each)
        prepared = []
        for idx, worker in self.workers.items():
            if enabled_cameras is not None and idx not in enabled_cameras:
                continue
            filename = f"cam{idx}{ext}"
            output_path = os.path.join(target_folder, filename)
            success = worker.prepare_recording(output_path, fps,
                                               codec_selection=fourcc_str,
                                               record_gate=record_gate)
            if success:
                prepared.append(idx)

        # Phase 2: Arm — open the gate for ALL prepared cameras simultaneously
        record_gate.set()
        print(f"[MultiCamManager] Recording gate opened for cameras: {prepared}")

        self.is_recording = True
        return True
        
    def stop_recording(self):
        """
        Stop all camera workers and collect their results.

        Returns:
            dict {cam_idx: (output_path, frames_recorded)} for post-processing.
            Only includes cameras that were actually recording this session
            (output_path is None for workers that were skipped via enabled_cameras).
        """
        if not self.is_recording:
            return {}
        results = {}
        for idx, worker in self.workers.items():
            path, frames = worker.stop_recording()
            # path is None for workers not included in this session, or for any
            # worker whose prepare_recording() failed. Both are safely excluded.
            if path and frames > 0:
                results[idx] = (path, frames)
        self.is_recording = False
        return results

    def trim_clips_to_min_frames(self, results):
        """
        Post-recording trim: re-mux every clip that is longer than the shortest
        clip, so all output files contain exactly the same number of frames.

        Uses PyAV stream-copy (no re-encoding) for speed and lossless trimming.
        A temporary file is written first; on success it atomically replaces the
        original, so the original is never corrupted.

        Args:
            results: dict returned by stop_recording(),
                     format {cam_idx: (output_path, frames_recorded)}.

        Returns:
            dict {cam_idx: final_frame_count} with the confirmed frame counts.
        """
        if len(results) < 2:
            print("[Trim] Single camera — skipping trim.")
            return {idx: frames for idx, (_, frames) in results.items()}

        frame_counts = {idx: frames for idx, (_, frames) in results.items()}
        min_frames = min(frame_counts.values())
        max_frames = max(frame_counts.values())
        delta = max_frames - min_frames

        print(f"[Trim] Frame counts per camera: {frame_counts}")
        if delta == 0:
            print("[Trim] All clips already equal — no trim needed.")
            return frame_counts

        print(f"[Trim] Trimming all clips to {min_frames} frames (delta was {delta}).")

        final_counts = {}
        for idx, (path, frames) in results.items():
            if frames <= min_frames:
                print(f"[Trim] Cam {idx}: {frames} frames — OK.")
                final_counts[idx] = frames
                continue

            print(f"[Trim] Cam {idx}: {frames} → {min_frames} frames...")
            tmp_path = path + ".trimming.tmp"
            try:
                with av.open(path) as src:
                    src_stream = src.streams.video[0]
                    with av.open(tmp_path, mode='w') as dst:
                        # Mirror the output stream setup from prepare_recording()
                        dst_stream = dst.add_stream(src_stream.name)
                        dst_stream.width = src_stream.codec_context.width
                        dst_stream.height = src_stream.codec_context.height
                        if src_stream.codec_context.pix_fmt:
                            dst_stream.pix_fmt = src_stream.codec_context.pix_fmt
                        dst_stream.time_base = src_stream.time_base

                        frame_idx = 0
                        for packet in src.demux(src_stream):
                            if packet.dts is None:
                                continue
                            if frame_idx >= min_frames:
                                break
                            # Reassign monotonic PTS/DTS matching the original convention
                            packet.stream = dst_stream
                            packet.pts = frame_idx
                            packet.dts = frame_idx
                            packet.time_base = dst_stream.time_base
                            dst.mux(packet)
                            frame_idx += 1

                # Atomic replace: only executed if re-mux succeeded
                os.replace(tmp_path, path)
                print(f"[Trim] Cam {idx}: done ({frame_idx} frames written).")
                final_counts[idx] = frame_idx

            except Exception as e:
                print(f"[Trim] Cam {idx}: FAILED — {e}. Original file kept.")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                final_counts[idx] = frames  # Keep reported count for original file

        return final_counts

    def get_latest_frames(self):
        """Returns a dict of {cam_idx: frame} for preview"""
        return {idx: worker.latest_frame for idx, worker in self.workers.items() if worker.latest_frame is not None}
        
    def set_camera_rotation(self, cam_idx, degrees):
        if cam_idx in self.workers:
            self.workers[cam_idx].set_rotation(degrees)
            
    def set_charuco_settings(self, show, dict_str):
        for worker in self.workers.values():
            worker.set_charuco(show, dict_str)
