import cv2
import threading
import os
import time
import queue
import subprocess

class CameraWorker(threading.Thread):
    def __init__(self, cam_id, cap, target_fps=50):
        super().__init__()
        self.cam_id = cam_id
        self.cap = cap
        
        self.is_running = True
        self.is_recording = False
        
        self.latest_frame = None
        self.rotation_degrees = 0
        
        self.current_fps = 0.0
        self.last_fps_time = time.time()
        self.frame_count_for_fps = 0
        
        # Dynamischer Puffer (3 Sekunden bei Ziel-FPS), 
        # um die Startverzögerung von FFmpeg abzufangen.
        buffer_size = int(target_fps * 3)
        self.frame_queue = queue.Queue(maxsize=buffer_size)
        self.writer_thread = None
        self.frames_recorded = 0
        
        self.show_charuco = False
        self.charuco_dict = None
        self.charuco_params = None
        
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
        # We need to know the resolution. Wait until we have a frame.
        if self.latest_frame is None:
            print(f"[{self.cam_id}] Waiting for first frame...")
            while self.latest_frame is None and self.is_running:
                time.sleep(0.01)
                
        if not self.is_running:
            return
            
        resolution = (self.latest_frame.shape[1], self.latest_frame.shape[0])
        
        self.frames_recorded = 0
        # Empty any old frames from the queue
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
                
        self.is_recording = True
        
        self.writer_thread = threading.Thread(target=self._writer_loop, args=(output_path, fps, codec_selection, resolution))
        self.writer_thread.start()
        print(f"[{self.cam_id}] Started recording to {output_path}")

    def stop_recording(self):
        self.is_recording = False
        if self.writer_thread:
            self.writer_thread.join()
            self.writer_thread = None
        print(f"[{self.cam_id}] Stopped recording. Saved {self.frames_recorded} frames.")
        
    def _writer_loop(self, output_path, fps, codec_selection, resolution):
        writer = None
        process = None
        
        # Check if FFmpeg is requested
        if codec_selection.startswith("FFMPEG_"):
            encoder = "libx264"
            if "NVENC" in codec_selection: encoder = "h264_nvenc"
            elif "QSV" in codec_selection: encoder = "h264_qsv"
            elif "AMF" in codec_selection: encoder = "h264_amf"
            
            # Determine ffmpeg executable
            ffmpeg_exe = "ffmpeg"
            if os.path.exists("ffmpeg.exe"):
                ffmpeg_exe = "ffmpeg.exe"
                
            cmd = [
                ffmpeg_exe,
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-s', f"{resolution[0]}x{resolution[1]}",
                '-pix_fmt', 'bgr24',
                '-r', str(fps),
                '-i', '-',
                '-c:v', encoder
            ]

            # Quality settings based on encoder
            if encoder == "libx264":
                # CRF 17 is visually lossless
                cmd.extend(['-preset', 'fast', '-crf', '17'])
            elif encoder == "h264_nvenc":
                # High quality CQ for NVENC
                cmd.extend(['-preset', 'p6', '-rc', 'vbr', '-cq', '19', '-b:v', '20M', '-maxrate', '50M'])
            elif encoder == "h264_amf":
                # AMD Hardware Encoder
                # Einfach eine sehr hohe Bitrate erzwingen, spezielle AMF flags 
                # (wie -usage) verursachen auf manchen FFmpeg Versionen Crashes.
                cmd.extend(['-b:v', '35M'])
            elif encoder == "h264_qsv":
                # Intel Hardware Encoder
                cmd.extend(['-preset', 'veryfast', '-b:v', '30M'])
            else:
                # Generic fallback for Intel/AMD
                cmd.extend(['-b:v', '25M'])
                
            cmd.append(output_path)
            
            try:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                print(f"[{self.cam_id}] FFmpeg not found! Falling back to MJPG.")
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                writer = cv2.VideoWriter(output_path.replace(".mp4", ".avi"), fourcc, fps, resolution)
        else:
            fourcc = cv2.VideoWriter_fourcc(*codec_selection)
            # Versuche Qualitätsparameter mitzugeben (wird von manchen OpenCV-Backends unterstützt)
            if hasattr(cv2, 'VIDEOWRITER_PROP_QUALITY'):
                writer = cv2.VideoWriter(output_path, fourcc, fps, resolution, params=[cv2.VIDEOWRITER_PROP_QUALITY, 100])
            else:
                writer = cv2.VideoWriter(output_path, fourcc, fps, resolution)
            
        while self.is_recording or not self.frame_queue.empty():
            try:
                frame = self.frame_queue.get(timeout=0.1)
                if process and process.stdin:
                    try:
                        process.stdin.write(frame.tobytes())
                        self.frames_recorded += 1
                    except (BrokenPipeError, OSError) as e:
                        print(f"[{self.cam_id}] FFmpeg pipe error: {e}")
                        self.is_recording = False
                elif writer:
                    writer.write(frame)
                    self.frames_recorded += 1
            except queue.Empty:
                continue
                
        if process:
            process.stdin.close()
            process.wait()
        if writer:
            writer.release()
            
    def run(self):
        while self.is_running:
            ret, frame = self.cap.read()
            if ret:
                if self.rotation_degrees == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif self.rotation_degrees == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif self.rotation_degrees == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
                # FPS calculation
                self.frame_count_for_fps += 1
                now = time.time()
                if now - self.last_fps_time >= 1.0:
                    self.current_fps = self.frame_count_for_fps / (now - self.last_fps_time)
                    self.frame_count_for_fps = 0
                    self.last_fps_time = now
                    
                # Charuco Detection offloading
                preview_frame = frame
                if self.show_charuco and self.charuco_dict is not None and self.charuco_params is not None:
                    # Kopie erstellen, damit wir das saubere Bild aufnehmen
                    preview_frame = frame.copy()
                    gray = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2GRAY)
                    
                    try:
                        if hasattr(cv2.aruco, 'ArucoDetector'):
                            detector = cv2.aruco.ArucoDetector(self.charuco_dict, self.charuco_params)
                            corners, ids, rejected = detector.detectMarkers(gray)
                        else:
                            corners, ids, rejected = cv2.aruco.detectMarkers(gray, self.charuco_dict, parameters=self.charuco_params)
                            
                        if corners and len(corners) > 0:
                            cv2.aruco.drawDetectedMarkers(preview_frame, corners, ids)
                    except Exception as e:
                        pass
                        
                # Always keep latest frame for UI preview
                self.latest_frame = preview_frame 
                
                # If recording, write to queue (the clean frame, not preview_frame)
                if self.is_recording:
                    try:
                        # Non-blocking put to avoid slowing down grabbing
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        print(f"[{self.cam_id}] Queue full! Dropping frame.")
            else:
                time.sleep(0.001) # Avoid pegging CPU if timeout
                
    def stop(self):
        self.is_running = False
        self.stop_recording()

class MultiCamManager:
    def __init__(self):
        self.workers = {} # idx -> CameraWorker
        self.is_recording = False
        
    def get_supported_codecs(self):
        return {
            "FFmpeg: H.264 (NVIDIA NVENC)": ("FFMPEG_NVENC", ".mp4"),
            "FFmpeg: H.264 (Intel QSV)": ("FFMPEG_QSV", ".mp4"),
            "FFmpeg: H.264 (AMD AMF)": ("FFMPEG_AMF", ".mp4"),
            "FFmpeg: H.264 (CPU)": ("FFMPEG_CPU", ".mp4"),
            "MJPG (.avi) - Fast & Large": ("MJPG", ".avi"),
            "MP4V (.mp4) - Balanced": ("mp4v", ".mp4"),
            "XVID (.avi) - High Comp": ("XVID", ".avi")
        }
        
    def start_workers(self, cameras, target_fps=50):
        """Starts background grabbing for all opened cameras"""
        for idx, cap in cameras.items():
            if idx not in self.workers:
                worker = CameraWorker(f"Cam_{idx}", cap, target_fps)
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
        fourcc_str, ext = codecs.get(codec_selection, ("MJPG", ".avi"))
        
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
