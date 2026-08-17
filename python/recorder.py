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
        
    def start_recording(self, output_path, fps, codec_selection):
        if not self.is_running:
            return
            
        self.frames_recorded = 0
        self.recording_fps = fps
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
            return
            
        self.is_recording = True
        self.writer_thread = threading.Thread(target=self._writer_loop)
        self.writer_thread.start()
        print(f"[{self.cam_id}] Started recording to {output_path}")

    def stop_recording(self):
        self.is_recording = False
        if self.writer_thread:
            self.writer_thread.join()
            self.writer_thread = None
        
        if self.output_container:
            try:
                self.output_container.close()
            except:
                pass
            self.output_container = None
            self.output_stream = None
            
        print(f"[{self.cam_id}] Stopped recording. Saved {self.frames_recorded} frames.")
        
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
                        else:
                            # Trancoding path - highly simplified, requires decoded frames
                            pass 
                        self.frames_recorded += 1  # Only count on success
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
                        
                # 2. Enqueue packet for recording
                if self.is_recording:
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
        if self.is_recording:
            return False
            
        codecs = self.get_supported_codecs()
        fourcc_str, ext = codecs.get(codec_selection, ("mjpeg", ".avi"))
        
        for idx, worker in self.workers.items():
            if enabled_cameras is not None and idx not in enabled_cameras:
                continue
            filename = f"cam{idx}{ext}"
            output_path = os.path.join(target_folder, filename)
            worker.start_recording(output_path, fps, codec_selection=fourcc_str)
            
        self.is_recording = True
        return True
        
    def stop_recording(self):
        if not self.is_recording:
            return
        for worker in self.workers.values():
            worker.stop_recording()
        self.is_recording = False
        
    def get_latest_frames(self):
        """Returns a dict of {cam_idx: frame} for preview"""
        return {idx: worker.latest_frame for idx, worker in self.workers.items() if worker.latest_frame is not None}
        
    def set_camera_rotation(self, cam_idx, degrees):
        if cam_idx in self.workers:
            self.workers[cam_idx].set_rotation(degrees)
            
    def set_charuco_settings(self, show, dict_str):
        for worker in self.workers.values():
            worker.set_charuco(show, dict_str)
