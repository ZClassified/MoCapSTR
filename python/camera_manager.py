import cv2

class CameraManager:
    def __init__(self):
        self.cameras = {} # Dictionary mapping index to cv2.VideoCapture object
        
    def find_cameras(self, max_index=10):
        """Scans for available cameras using DirectShow on Windows."""
        print("Scanning for cameras...")
        available_cams = []
        for i in range(max_index):
            # CAP_DSHOW is often required on Windows to set exposure properly
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    available_cams.append(i)
                cap.release()
        print(f"Found cameras at indices: {available_cams}")
        return available_cams
        
    def open_camera(self, index):
        if index not in self.cameras:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                self.cameras[index] = cap
                return True
        return False
        
    def close_camera(self, index):
        if index in self.cameras:
            self.cameras[index].release()
            del self.cameras[index]
            
    def close_all(self):
        for index in list(self.cameras.keys()):
            self.close_camera(index)
            
    def apply_settings(self, index, width=1280, height=800, fps=60, exposure_value=None, gain_value=None, wb_value=None):
        """
        Applies settings to a specific camera.
        Reads back the actual values the driver accepted and returns them.
        """
        if index in self.cameras:
            cap = self.cameras[index]
            
            # Disable auto settings
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # Manual
            cap.set(cv2.CAP_PROP_AUTO_WB, 0) # Manual WB
            
            if exposure_value is not None:
                cap.set(cv2.CAP_PROP_EXPOSURE, exposure_value)
            if gain_value is not None:
                cap.set(cv2.CAP_PROP_GAIN, gain_value)
            if wb_value is not None:
                cap.set(cv2.CAP_PROP_WB_TEMPERATURE, wb_value)
                
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            
            # Read back ACTUAL values
            actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            actual_exp = cap.get(cv2.CAP_PROP_EXPOSURE)
            actual_gain = cap.get(cv2.CAP_PROP_GAIN)
            actual_wb = cap.get(cv2.CAP_PROP_WB_TEMPERATURE)
            
            return {
                "width": int(actual_w) if actual_w else None,
                "height": int(actual_h) if actual_h else None,
                "fps": actual_fps,
                "exposure": actual_exp,
                "gain": actual_gain,
                "wb": actual_wb
            }
        return None
        
    def get_frame(self, index):
        if index in self.cameras:
            ret, frame = self.cameras[index].read()
            if ret:
                return frame
        return None

if __name__ == "__main__":
    # Test script
    cam_mgr = CameraManager()
    cams = cam_mgr.find_cameras(5)
    if cams:
        idx = cams[0]
        cam_mgr.open_camera(idx)
        print("Settings applied:", cam_mgr.apply_settings(idx, 1280, 800, 60))
        frame = cam_mgr.get_frame(idx)
        if frame is not None:
            print("Successfully captured a frame of shape:", frame.shape)
        cam_mgr.close_all()
