import cv2
import threading
import os
import time

class CameraWorker(threading.Thread):
    def __init__(self, cam_id, cap):
        super().__init__()
        self.cam_id = cam_id
        self.cap = cap
        
        self.is_running = True
        self.is_recording = False
        self.writer = None
        self.latest_frame = None
        self.frames_recorded = 0
        self.rotation_degrees = 0
        
    def set_rotation(self, degrees):
        self.rotation_degrees = degrees
        
    def start_recording(self, output_path, fps, codec):
        fourcc = cv2.VideoWriter_fourcc(*codec)
        # Dynamically get resolution from the currently grabbed (and potentially rotated) frame
        resolution = (640, 480)
        if self.latest_frame is not None:
            resolution = (self.latest_frame.shape[1], self.latest_frame.shape[0])
            
        self.writer = cv2.VideoWriter(output_path, fourcc, fps, resolution)
        self.frames_recorded = 0
        self.is_recording = True
        print(f"[{self.cam_id}] Started recording to {output_path}")

    def stop_recording(self):
        self.is_recording = False
        if self.writer:
            self.writer.release()
            self.writer = None
        print(f"[{self.cam_id}] Stopped recording. Saved {self.frames_recorded} frames.")
        
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
                    
                # Always keep latest frame for UI preview
                self.latest_frame = frame 
                
                # If recording, write to disk
                if self.is_recording and self.writer:
                    self.writer.write(frame)
                    self.frames_recorded += 1
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
            "MJPG (.avi) - Fast & Large": ("MJPG", ".avi"),
            "MP4V (.mp4) - Balanced": ("mp4v", ".mp4"),
            "XVID (.avi) - High Comp": ("XVID", ".avi")
        }
        
    def start_workers(self, cameras):
        """Starts background grabbing for all opened cameras"""
        for idx, cap in cameras.items():
            if idx not in self.workers:
                worker = CameraWorker(f"Cam_{idx}", cap)
                worker.start()
                self.workers[idx] = worker
                
    def stop_workers(self):
        for worker in self.workers.values():
            worker.stop()
        for worker in self.workers.values():
            worker.join()
        self.workers.clear()

    def start_recording(self, target_folder, fps, codec_selection):
        if self.is_recording:
            return False
            
        codecs = self.get_supported_codecs()
        fourcc_str, ext = codecs.get(codec_selection, ("MJPG", ".avi"))
        
        for idx, worker in self.workers.items():
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
